"""Core decorator for securing AI agents."""

import functools
import os
from typing import Any, Callable, Dict, Optional

from sentinel.sdk.interceptor import ToolCallInterceptor


class ConfigurationError(Exception):
    """Raised when decorator configuration is invalid."""
    pass


class SentinelConfig:
    """Configuration for Sentinel SDK."""
    
    def __init__(
        self,
        agent_id: str,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None
    ):
        """
        Initialize Sentinel configuration.
        
        Args:
            agent_id: Unique identifier for the agent
            api_key: Sentinel API key (can also be set via SENTINEL_API_KEY env var)
            endpoint: Sentinel API endpoint URL (can also be set via SENTINEL_ENDPOINT env var)
            
        Raises:
            ConfigurationError: If required configuration is missing or invalid
        """
        self.agent_id = agent_id
        self.api_key = api_key or os.getenv("SENTINEL_API_KEY")
        self.endpoint = endpoint or os.getenv("SENTINEL_ENDPOINT", "https://api.sentinel.ai")
        
        self._validate()
    
    def _validate(self) -> None:
        """Validate configuration parameters."""
        if not self.agent_id:
            raise ConfigurationError("agent_id is required")
        
        if not isinstance(self.agent_id, str):
            raise ConfigurationError("agent_id must be a string")
        
        if not self.api_key:
            raise ConfigurationError(
                "api_key is required. Provide it in config or set SENTINEL_API_KEY environment variable"
            )
        
        if not isinstance(self.api_key, str):
            raise ConfigurationError("api_key must be a string")
        
        if not self.api_key.startswith("sentinel_"):
            raise ConfigurationError("api_key must start with 'sentinel_'")
        
        if not self.endpoint:
            raise ConfigurationError("endpoint is required")
        
        if not isinstance(self.endpoint, str):
            raise ConfigurationError("endpoint must be a string")
        
        if not (self.endpoint.startswith("http://") or self.endpoint.startswith("https://")):
            raise ConfigurationError("endpoint must be a valid HTTP/HTTPS URL")


def secure_agent(
    agent_id: str,
    config: Optional[Dict[str, Any]] = None
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator to secure AI agent functions with Sentinel policy enforcement.
    
    Args:
        agent_id: Unique identifier for the agent
        config: Configuration dictionary containing:
            - api_key: Sentinel API key (optional if SENTINEL_API_KEY env var is set)
            - endpoint: Sentinel API endpoint URL (optional, defaults to https://api.sentinel.ai)
            
    Returns:
        Decorated function with security wrapper
        
    Raises:
        ConfigurationError: If configuration is invalid or missing required parameters
        
    Example:
        @secure_agent(
            agent_id="invoice-processor",
            config={
                "api_key": "sentinel_key_xxx",
                "endpoint": "https://api.sentinel.ai"
            }
        )
        def invoice_agent():
            pass
    """
    # Parse and validate configuration
    config = config or {}
    
    try:
        sentinel_config = SentinelConfig(
            agent_id=agent_id,
            api_key=config.get("api_key"),
            endpoint=config.get("endpoint")
        )
    except ConfigurationError as e:
        # Fail fast on configuration errors
        raise ConfigurationError(f"Invalid Sentinel configuration: {e}") from e
    
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        # Create interceptor instance
        interceptor = ToolCallInterceptor(
            agent_id=sentinel_config.agent_id,
            user_id=config.get("user_id")
        )
        
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Store config and interceptor on wrapper for access
            wrapper._sentinel_config = sentinel_config  # type: ignore
            wrapper._sentinel_interceptor = interceptor  # type: ignore
            
            # Intercept the call (side-effects only — telemetry / policy checks)
            interceptor.intercept(
                func=func,
                args=args,
                kwargs=kwargs,
                context=config.get("context")
            )
            
            # Execute the original function
            result = func(*args, **kwargs)
            
            return result
        
        # Store config and interceptor on wrapper for access
        wrapper._sentinel_config = sentinel_config  # type: ignore
        wrapper._sentinel_interceptor = interceptor  # type: ignore
        
        return wrapper
    return decorator
