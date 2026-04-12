"""CSRF protection via double-submit cookie pattern."""

import secrets
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from policy_engine.config import settings

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "x-csrf-token"
MUTATING_METHODS = {"POST", "PUT", "DELETE", "PATCH"}


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


class CSRFMiddleware(BaseHTTPMiddleware):
    """Double-submit cookie CSRF protection. Exempt for X-API-Key requests."""

    async def dispatch(self, request: Request, call_next):
        if request.method not in MUTATING_METHODS:
            return await call_next(request)

        # API-key authenticated requests are machine-to-machine — exempt
        api_key = request.headers.get(settings.API_KEY_HEADER)
        if api_key:
            return await call_next(request)

        # WebSocket upgrades — exempt
        if request.headers.get("upgrade", "").lower() == "websocket":
            return await call_next(request)

        # Health endpoints — exempt
        if request.url.path.startswith("/health"):
            return await call_next(request)

        cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
        header_token = request.headers.get(CSRF_HEADER_NAME)

        if not cookie_token or not header_token or cookie_token != header_token:
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF token missing or invalid."},
            )

        return await call_next(request)
