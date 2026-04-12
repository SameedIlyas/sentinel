"""Rate limiting middleware — Redis-backed with in-memory fallback."""

import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from policy_engine.config import settings

logger = logging.getLogger(__name__)


def _get_redis_limiter():
    """Lazy-load Redis limiter to avoid import-time Redis connection."""
    try:
        import redis as redis_lib
        from policy_engine.services.redis_rate_limiter import RedisRateLimiter
        r = redis_lib.from_url(settings.REDIS_URL, socket_connect_timeout=1)
        return RedisRateLimiter(
            redis_client=r,
            requests_per_minute=settings.RATE_LIMIT_PER_MINUTE,
            fallback_enabled=True,
        )
    except Exception as e:
        logger.warning("Could not initialise Redis rate limiter: %s", e)
        from policy_engine.services.redis_rate_limiter import RedisRateLimiter
        return RedisRateLimiter(
            redis_client=None,
            requests_per_minute=settings.RATE_LIMIT_PER_MINUTE,
            fallback_enabled=True,
        )


_limiter = None


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce rate limiting per API key (Redis-backed)."""

    async def dispatch(self, request: Request, call_next):
        global _limiter
        if _limiter is None:
            _limiter = _get_redis_limiter()

        if request.url.path.startswith("/health"):
            return await call_next(request)

        api_key = request.headers.get(settings.API_KEY_HEADER)
        identifier = api_key or request.client.host if request.client else "anonymous"

        if identifier:
            allowed, remaining = _limiter.is_allowed(identifier)
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded. Please try again later."},
                    headers={
                        "X-RateLimit-Limit": str(settings.RATE_LIMIT_PER_MINUTE),
                        "X-RateLimit-Remaining": "0",
                        "Retry-After": "60",
                    },
                )

        response = await call_next(request)
        if identifier:
            response.headers["X-RateLimit-Limit"] = str(settings.RATE_LIMIT_PER_MINUTE)
            response.headers["X-RateLimit-Remaining"] = str(
                getattr(_limiter, '_last_remaining', settings.RATE_LIMIT_PER_MINUTE)
            )
        return response
