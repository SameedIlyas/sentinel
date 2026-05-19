"""Session-cookie helpers for the HttpOnly JWT migration (CRIT-011 close).

The dashboard historically read the access token from ``localStorage``,
which means any XSS that ran in-page could exfiltrate a working bearer
token. The HttpOnly cookie path closes that exfil surface:

- ``access_token`` is delivered as an HttpOnly + Secure + SameSite=lax
  cookie. JS cannot read it; the browser sends it automatically.
- ``csrf_token`` is delivered alongside as a NON-HttpOnly cookie so JS
  can read it and echo it back via the ``X-CSRF-Token`` header. This
  is the double-submit check enforced by
  :mod:`policy_engine.middleware.csrf`.

For non-browser callers (CI scripts, API clients) the legacy
``Authorization: Bearer <jwt>`` header path remains supported.
"""
from __future__ import annotations

from typing import Optional

from fastapi import Response

from policy_engine.config import settings
from policy_engine.middleware.csrf import CSRF_COOKIE_NAME, generate_csrf_token


def _secure_attr() -> bool:
    """Resolve the ``Secure`` cookie attribute.

    Explicit ``SESSION_COOKIE_SECURE`` overrides; otherwise default ON
    in production and OFF elsewhere so local HTTP development works.
    """
    if settings.SESSION_COOKIE_SECURE is not None:
        return bool(settings.SESSION_COOKIE_SECURE)
    return settings.APP_ENV == "production"


def set_session_cookies(
    response: Response,
    *,
    access_token: str,
    max_age_seconds: int,
) -> str:
    """Attach the HttpOnly access-token cookie + the JS-readable CSRF
    cookie to ``response``. Returns the freshly minted CSRF token so
    handlers can include it in the response body for SPA bootstrap (the
    cookie is also set, but exposing it in the body shortens the path
    to a working first request).
    """
    domain = settings.SESSION_COOKIE_DOMAIN or None
    secure = _secure_attr()
    samesite = settings.SESSION_COOKIE_SAMESITE or "lax"

    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=access_token,
        max_age=max_age_seconds,
        httponly=True,
        secure=secure,
        samesite=samesite,
        domain=domain,
        path=settings.SESSION_COOKIE_PATH,
    )

    csrf_token = generate_csrf_token()
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        max_age=max_age_seconds,
        # NOT httponly — the dashboard reads this cookie and echoes the
        # value into the X-CSRF-Token header for the double-submit
        # check.
        httponly=False,
        secure=secure,
        samesite=samesite,
        domain=domain,
        path=settings.SESSION_COOKIE_PATH,
    )
    return csrf_token


def clear_session_cookies(response: Response) -> None:
    """Best-effort clear of both auth cookies on logout."""
    domain = settings.SESSION_COOKIE_DOMAIN or None
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        domain=domain,
        path=settings.SESSION_COOKIE_PATH,
    )
    response.delete_cookie(
        key=CSRF_COOKIE_NAME,
        domain=domain,
        path=settings.SESSION_COOKIE_PATH,
    )


def read_session_token(request) -> Optional[str]:
    """Return the access-token cookie value, or ``None`` if absent."""
    value = request.cookies.get(settings.SESSION_COOKIE_NAME)
    return value or None
