"""Rate limiting middleware"""

import time
from collections import defaultdict
from fastapi import HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from policy_engine.config import settings


class RateLimiter:
    """Simple in-memory rate limiter"""
    
    def __init__(self, requests_per_minute: int):
        self.requests_per_minute = requests_per_minute
        self.requests = defaultdict(list)
    
    def is_allowed(self, key: str) -> bool:
        """
        Check if request is allowed based on rate limit
        
        Args:
            key: Identifier for rate limiting (e.g., API key)
            
        Returns:
            True if request is allowed, False otherwise
        """
        now = time.time()
        minute_ago = now - 60
        
        # Remove old requests
        self.requests[key] = [
            req_time for req_time in self.requests[key]
            if req_time > minute_ago
        ]
        
        # Check if under limit
        if len(self.requests[key]) >= self.requests_per_minute:
            return False
        
        # Add current request
        self.requests[key].append(now)
        return True


# Global rate limiter instance
rate_limiter = RateLimiter(settings.RATE_LIMIT_PER_MINUTE)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce rate limiting per API key"""
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks
        if request.url.path.startswith("/health"):
            return await call_next(request)
        
        # Get API key from header
        api_key = request.headers.get(settings.API_KEY_HEADER)
        
        if api_key:
            # Check rate limit
            if not rate_limiter.is_allowed(api_key):
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded. Please try again later."
                )
        
        return await call_next(request)
