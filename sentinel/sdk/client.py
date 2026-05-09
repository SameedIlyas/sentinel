"""HTTP client for Sentinel middleware communication."""

import logging
import time
from typing import Any, Dict
from urllib.parse import urljoin

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    requests = None  # type: ignore

from sentinel.models.policy import PolicyCheckRequest, PolicyCheckResponse
from sentinel.sdk.cache import PolicyCache
from sentinel.sdk.retry import with_retry, get_retry_metrics


logger = logging.getLogger(__name__)


class MiddlewareClientError(Exception):
    """Raised when middleware communication fails."""
    pass


class MiddlewareClient:
    """HTTP client for communicating with Sentinel middleware."""
    
    def __init__(
        self,
        endpoint: str,
        api_key: str,
        timeout: float = 0.5,
        max_retries: int = 3,
        enable_cache: bool = True,
        cache_ttl: int = 300
    ):
        """
        Initialize the middleware client.
        
        Args:
            endpoint: Base URL for the Sentinel API
            api_key: API key for authentication
            timeout: Request timeout in seconds (default: 0.5s for <100ms target)
            max_retries: Maximum number of retry attempts
            enable_cache: Enable local policy caching (default: True)
            cache_ttl: Cache TTL in seconds (default: 300 = 5 minutes)
            
        Raises:
            MiddlewareClientError: If requests library is not available
        """
        if not HAS_REQUESTS:
            raise MiddlewareClientError(
                "requests library is required. Install with: pip install requests"
            )
        
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        
        # Initialize cache
        self.cache = PolicyCache(ttl_seconds=cache_ttl) if enable_cache else None
        
        # Degraded mode tracking
        self._degraded_mode = False
        self._last_health_check = 0.0
        self._health_check_interval = 30.0  # Check every 30 seconds
        self._consecutive_failures = 0
        self._failure_threshold = 3  # Enter degraded mode after 3 failures
        
        # Create session with connection pooling
        self.session = self._create_session()
        
        logger.info(f"Initialized MiddlewareClient (cache={'enabled' if enable_cache else 'disabled'})")

    
    def _create_session(self) -> Any:
        """
        Create a requests session with connection pooling and retry logic.
        
        Returns:
            Configured requests session
        """
        session = requests.Session()  # type: ignore
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=0.1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST", "GET"]
        )
        
        # Mount adapter with retry strategy
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=20
        )
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set default headers
        session.headers.update({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "Sentinel-SDK/0.1.0"
        })
        
        return session
    
    def check_policy(self, request: PolicyCheckRequest) -> PolicyCheckResponse:
        """
        Check policy for a tool call.
        
        Args:
            request: Policy check request
            
        Returns:
            Policy check response with decision
            
        Raises:
            MiddlewareClientError: If the request fails and no cache is available
        """
        # Check cache first if enabled
        if self.cache:
            cached_response = self.cache.get(
                agent_id=request.agent_id,
                tool_name=request.tool_name,
                arguments=request.arguments
            )
            if cached_response:
                logger.debug("Returning cached policy decision")
                return cached_response
        
        # Try to get fresh policy decision from middleware
        try:
            response = self._make_policy_request(request)
            
            # Cache the response if caching is enabled
            if self.cache:
                self.cache.set(
                    agent_id=request.agent_id,
                    tool_name=request.tool_name,
                    arguments=request.arguments,
                    response=response
                )
            
            # Mark successful request
            self._mark_success()
            
            return response
            
        except MiddlewareClientError:
            # Mark failure
            self._mark_failure()
            
            # If in degraded mode, apply fail-safe logic
            if self._degraded_mode:
                logger.warning(
                    f"Middleware unavailable (degraded mode). "
                    f"Applying fail-safe policy for {request.tool_name}"
                )
                return self._apply_fail_safe_policy(request)
            
            # Not in degraded mode yet, re-raise the error
            raise
    
    def _make_policy_request(self, request: PolicyCheckRequest) -> PolicyCheckResponse:
        """
        Make the actual HTTP request to check policy.
        
        Args:
            request: Policy check request
            
        Returns:
            Policy check response
            
        Raises:
            MiddlewareClientError: If the request fails
        """
        return self._make_policy_request_with_retry(request)
    
    @with_retry(
        max_attempts=3,
        base_delay=0.1,
        max_delay=2.0,
        exponential_base=2.0,
        jitter=True,
        exceptions=(MiddlewareClientError,)
    )
    def _make_policy_request_with_retry(self, request: PolicyCheckRequest) -> PolicyCheckResponse:
        """
        Make the actual HTTP request to check policy with retry logic.
        
        Args:
            request: Policy check request
            
        Returns:
            Policy check response
            
        Raises:
            MiddlewareClientError: If the request fails after all retries
        """
        url = urljoin(self.endpoint, "/v1/policy/check")
        
        try:
            # Serialize request
            if hasattr(request, "dict"):
                payload = request.dict()
            else:
                payload = request.__dict__
            
            # Make request
            response = self.session.post(
                url,
                json=payload,
                timeout=self.timeout
            )
            
            # Check for errors
            response.raise_for_status()
            
            # Parse response
            data = response.json()
            
            # Create response object
            if hasattr(PolicyCheckResponse, "parse_obj"):
                return PolicyCheckResponse.parse_obj(data)
            else:
                return PolicyCheckResponse(**data)
            
        except requests.exceptions.Timeout as e:  # type: ignore
            logger.error(f"Policy check request timed out: {e}")
            raise MiddlewareClientError(f"Request timed out after {self.timeout}s") from e
        
        except requests.exceptions.ConnectionError as e:  # type: ignore
            logger.error(f"Failed to connect to middleware: {e}")
            raise MiddlewareClientError("Failed to connect to Sentinel middleware") from e
        
        except requests.exceptions.HTTPError as e:  # type: ignore
            logger.error(f"HTTP error from middleware: {e}")
            raise MiddlewareClientError(f"HTTP error: {e.response.status_code}") from e
        
        except (ValueError, KeyError) as e:
            logger.error(f"Failed to parse middleware response: {e}")
            raise MiddlewareClientError("Invalid response from middleware") from e
        
        except Exception as e:
            logger.error(f"Unexpected error during policy check: {e}")
            raise MiddlewareClientError(f"Unexpected error: {e}") from e
    
    def _mark_failure(self) -> None:
        """Mark a failed request and potentially enter degraded mode."""
        self._consecutive_failures += 1
        
        if self._consecutive_failures >= self._failure_threshold and not self._degraded_mode:
            self._degraded_mode = True
            logger.warning(
                f"Entering degraded mode after {self._consecutive_failures} consecutive failures. "
                f"Will use cached policies and fail-safe mode."
            )
    
    def _mark_success(self) -> None:
        """Mark a successful request and potentially exit degraded mode."""
        if self._degraded_mode:
            logger.info("Middleware connection restored. Exiting degraded mode.")
            self._degraded_mode = False
        
        self._consecutive_failures = 0
    
    def _apply_fail_safe_policy(self, request: PolicyCheckRequest) -> PolicyCheckResponse:
        """
        Apply fail-safe policy when middleware is unavailable and no cache exists.
        
        Fail-safe mode blocks all actions to ensure security.
        
        Args:
            request: Policy check request
            
        Returns:
            Policy check response with block decision
        """
        logger.warning(
            f"No cached policy for {request.tool_name}. "
            f"Blocking action in fail-safe mode."
        )
        
        return PolicyCheckResponse(
            decision="block",
            reason="Middleware unavailable and no cached policy available (fail-safe mode)",
            masked_data=None,
            policy_ids=[]
        )
    
    def is_degraded(self) -> bool:
        """
        Check if the client is in degraded mode.
        
        Returns:
            True if in degraded mode, False otherwise
        """
        return self._degraded_mode
    
    def check_health(self) -> bool:
        """
        Check if the middleware is available.
        
        Returns:
            True if middleware is healthy, False otherwise
        """
        current_time = time.time()
        
        # Rate limit health checks
        if current_time - self._last_health_check < self._health_check_interval:
            return not self._degraded_mode
        
        self._last_health_check = current_time
        
        url = urljoin(self.endpoint, "/health")
        
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            # Mark success if we were in degraded mode
            if self._degraded_mode:
                self._mark_success()
            
            return True
            
        except Exception as e:
            logger.debug(f"Health check failed: {e}")
            return False
    
    def send_telemetry(self, data: Dict[str, Any]) -> None:
        """
        Send telemetry data to middleware (async, non-blocking).
        
        Args:
            data: Telemetry data dictionary
        """
        url = urljoin(self.endpoint, "/v1/telemetry")
        
        try:
            # Send telemetry asynchronously (fire and forget)
            self.session.post(
                url,
                json=data,
                timeout=self.timeout
            )
        except Exception as e:
            # Log but don't raise - telemetry failures shouldn't block execution
            logger.warning(f"Failed to send telemetry: {e}")
    
    def get_retry_metrics(self) -> Dict[str, Any]:
        """
        Get retry metrics for monitoring.
        
        Returns:
            Dictionary with retry statistics
        """
        return get_retry_metrics().get_stats()
    
    def close(self) -> None:
        """Close the HTTP session and release resources."""
        if self.session:
            self.session.close()
    
    def __enter__(self) -> "MiddlewareClient":
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()
