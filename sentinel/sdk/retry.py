"""Retry logic with exponential backoff for Sentinel SDK."""

import functools
import logging
import time
from typing import Any, Callable, Optional, Tuple, Type

logger = logging.getLogger(__name__)


class RetryError(Exception):
    """Raised when all retry attempts are exhausted."""
    pass


class RetryConfig:
    """Configuration for retry behavior."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 0.1,
        max_delay: float = 10.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        """
        Initialize retry configuration.
        
        Args:
            max_attempts: Maximum number of retry attempts (default: 3)
            base_delay: Initial delay between retries in seconds (default: 0.1)
            max_delay: Maximum delay between retries in seconds (default: 10.0)
            exponential_base: Base for exponential backoff calculation (default: 2.0)
            jitter: Whether to add random jitter to delays (default: True)
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
    
    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for a given attempt number.
        
        Args:
            attempt: Current attempt number (0-indexed)
            
        Returns:
            Delay in seconds
        """
        # Calculate exponential backoff
        delay = min(
            self.base_delay * (self.exponential_base ** attempt),
            self.max_delay
        )
        
        # Add jitter if enabled (randomize between 0 and calculated delay)
        if self.jitter:
            import random
            delay = random.uniform(0, delay)
        
        return delay


class RetryMetrics:
    """Tracks retry metrics for monitoring."""
    
    def __init__(self):
        """Initialize retry metrics."""
        self.total_attempts = 0
        self.successful_retries = 0
        self.failed_retries = 0
        self.total_delay = 0.0
    
    def record_attempt(self, attempt: int, delay: float, success: bool) -> None:
        """
        Record a retry attempt.
        
        Args:
            attempt: Attempt number
            delay: Delay before this attempt
            success: Whether the attempt succeeded
        """
        self.total_attempts += 1
        self.total_delay += delay
        
        if success:
            if attempt > 0:
                self.successful_retries += 1
        else:
            if attempt > 0:
                self.failed_retries += 1
    
    def get_stats(self) -> dict[str, Any]:
        """
        Get retry statistics.
        
        Returns:
            Dictionary with retry statistics
        """
        return {
            "total_attempts": self.total_attempts,
            "successful_retries": self.successful_retries,
            "failed_retries": self.failed_retries,
            "total_delay_seconds": round(self.total_delay, 3),
            "average_delay_seconds": (
                round(self.total_delay / self.total_attempts, 3)
                if self.total_attempts > 0 else 0.0
            )
        }
    
    def reset(self) -> None:
        """Reset all metrics."""
        self.total_attempts = 0
        self.successful_retries = 0
        self.failed_retries = 0
        self.total_delay = 0.0


# Global retry metrics instance
_global_metrics = RetryMetrics()


def get_retry_metrics() -> RetryMetrics:
    """
    Get the global retry metrics instance.
    
    Returns:
        Global RetryMetrics instance
    """
    return _global_metrics


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 0.1,
    max_delay: float = 10.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator to add retry logic with exponential backoff to a function.
    
    Args:
        max_attempts: Maximum number of retry attempts (default: 3)
        base_delay: Initial delay between retries in seconds (default: 0.1)
        max_delay: Maximum delay between retries in seconds (default: 10.0)
        exponential_base: Base for exponential backoff calculation (default: 2.0)
        jitter: Whether to add random jitter to delays (default: True)
        exceptions: Tuple of exception types to retry on (default: (Exception,))
        on_retry: Optional callback function called on each retry attempt
                 Should accept (exception, attempt_number) as arguments
    
    Returns:
        Decorated function with retry logic
        
    Example:
        @with_retry(max_attempts=3, base_delay=0.5)
        def make_api_call():
            # API call that might fail
            pass
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=jitter
    )
    
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Optional[Exception] = None
            
            for attempt in range(config.max_attempts):
                try:
                    # Calculate delay for this attempt (0 for first attempt)
                    if attempt > 0:
                        delay = config.calculate_delay(attempt - 1)
                        logger.debug(
                            f"Retry attempt {attempt}/{config.max_attempts - 1} "
                            f"for {func.__name__} after {delay:.3f}s delay"
                        )
                        time.sleep(delay)
                        _global_metrics.record_attempt(attempt, delay, False)
                    
                    # Execute the function
                    result = func(*args, **kwargs)
                    
                    # Record successful attempt
                    if attempt > 0:
                        logger.info(
                            f"Retry successful for {func.__name__} "
                            f"on attempt {attempt + 1}/{config.max_attempts}"
                        )
                        _global_metrics.record_attempt(attempt, 0.0, True)
                    
                    return result
                    
                except exceptions as e:
                    last_exception = e
                    
                    # Log the retry attempt
                    if attempt < config.max_attempts - 1:
                        logger.warning(
                            f"Attempt {attempt + 1}/{config.max_attempts} failed "
                            f"for {func.__name__}: {e}. Retrying..."
                        )
                        
                        # Call retry callback if provided
                        if on_retry:
                            try:
                                on_retry(e, attempt)
                            except Exception as callback_error:
                                logger.error(
                                    f"Error in retry callback: {callback_error}"
                                )
                    else:
                        logger.error(
                            f"All {config.max_attempts} attempts failed "
                            f"for {func.__name__}: {e}"
                        )
                        _global_metrics.record_attempt(attempt, 0.0, False)
            
            # All attempts exhausted
            raise RetryError(
                f"Failed after {config.max_attempts} attempts. "
                f"Last error: {last_exception}"
            ) from last_exception
        
        # Store retry config on wrapper for inspection
        wrapper._retry_config = config  # type: ignore
        
        return wrapper
    
    return decorator


def retry_on_exception(
    func: Callable[..., Any],
    max_attempts: int = 3,
    base_delay: float = 0.1,
    max_delay: float = 10.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None,
    *args: Any,
    **kwargs: Any
) -> Any:
    """
    Execute a function with retry logic (functional interface).
    
    This is an alternative to the decorator for cases where you want to
    apply retry logic without decorating the function.
    
    Args:
        func: Function to execute with retry logic
        max_attempts: Maximum number of retry attempts (default: 3)
        base_delay: Initial delay between retries in seconds (default: 0.1)
        max_delay: Maximum delay between retries in seconds (default: 10.0)
        exponential_base: Base for exponential backoff calculation (default: 2.0)
        jitter: Whether to add random jitter to delays (default: True)
        exceptions: Tuple of exception types to retry on (default: (Exception,))
        on_retry: Optional callback function called on each retry attempt
        *args: Positional arguments to pass to func
        **kwargs: Keyword arguments to pass to func
    
    Returns:
        Result of the function call
        
    Raises:
        RetryError: If all retry attempts are exhausted
        
    Example:
        result = retry_on_exception(
            make_api_call,
            max_attempts=3,
            base_delay=0.5,
            arg1="value1"
        )
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=jitter
    )
    
    last_exception: Optional[Exception] = None
    
    for attempt in range(config.max_attempts):
        try:
            # Calculate delay for this attempt (0 for first attempt)
            if attempt > 0:
                delay = config.calculate_delay(attempt - 1)
                logger.debug(
                    f"Retry attempt {attempt}/{config.max_attempts - 1} "
                    f"for {func.__name__} after {delay:.3f}s delay"
                )
                time.sleep(delay)
                _global_metrics.record_attempt(attempt, delay, False)
            
            # Execute the function
            result = func(*args, **kwargs)
            
            # Record successful attempt
            if attempt > 0:
                logger.info(
                    f"Retry successful for {func.__name__} "
                    f"on attempt {attempt + 1}/{config.max_attempts}"
                )
                _global_metrics.record_attempt(attempt, 0.0, True)
            
            return result
            
        except exceptions as e:
            last_exception = e
            
            # Log the retry attempt
            if attempt < config.max_attempts - 1:
                logger.warning(
                    f"Attempt {attempt + 1}/{config.max_attempts} failed "
                    f"for {func.__name__}: {e}. Retrying..."
                )
                
                # Call retry callback if provided
                if on_retry:
                    try:
                        on_retry(e, attempt)
                    except Exception as callback_error:
                        logger.error(f"Error in retry callback: {callback_error}")
            else:
                logger.error(
                    f"All {config.max_attempts} attempts failed "
                    f"for {func.__name__}: {e}"
                )
                _global_metrics.record_attempt(attempt, 0.0, False)
    
    # All attempts exhausted
    raise RetryError(
        f"Failed after {config.max_attempts} attempts. "
        f"Last error: {last_exception}"
    ) from last_exception
