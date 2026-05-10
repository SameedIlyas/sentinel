"""CSRF protection via double-submit cookie pattern.

CSRF is enforced only for cookie-authenticated state-changing requests.
Stateless clients (Bearer JWT, X-API-Key) are exempt because the browser
will not auto-send those headers cross-origin, removing the CSRF attack
vector. The login bootstrap endpoint is also exempt because no auth token
exists yet at that point.
"""

import secrets
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from policy_engine.config import settings

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "x-csrf-token"
MUTATING_METHODS = {"POST", "PUT", "DELETE", "PATCH"}

# Bootstrap endpoints that issue tokens — CSRF cannot apply because
# the client has no credential yet to derive a token from.
#
# Webhook endpoints are also exempt: third-party callers (Stripe,
# payment processors, etc.) cannot send CSRF tokens. Authenticity is
# enforced via HMAC signature verification at the route handler.
EXEMPT_PATHS = (
    "/health",
    "/v1/auth/login",
    "/v1/auth/refresh",
    "/v1/billing/clinic/webhook",
)


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


class CSRFMiddleware(BaseHTTPMiddleware):
    """Double-submit cookie CSRF protection for cookie-authenticated requests."""

    async def dispatch(self, request: Request, call_next):
        if request.method not in MUTATING_METHODS:
            return await call_next(request)

        # API-key authenticated requests are machine-to-machine — exempt
        api_key = request.headers.get(settings.API_KEY_HEADER)
        if api_key:
            return await call_next(request)

        # Bearer JWT in Authorization header is not auto-sent by browsers
        # cross-origin, so CSRF does not apply.
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            return await call_next(request)

        # WebSocket upgrades — exempt
        if request.headers.get("upgrade", "").lower() == "websocket":
            return await call_next(request)

        # Bootstrap endpoints — exempt
        if any(request.url.path.startswith(p) for p in EXEMPT_PATHS):
            return await call_next(request)

        cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
        header_token = request.headers.get(CSRF_HEADER_NAME)

        if not cookie_token or not header_token or cookie_token != header_token:
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF token missing or invalid."},
            )

        return await call_next(request)
