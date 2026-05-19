"""Authentication endpoints (login, logout, refresh, validate).

CRIT-011 close — the access token is delivered as an HttpOnly cookie so
XSS cannot exfiltrate the bearer token. A companion JS-readable
``csrf_token`` cookie carries the value the dashboard echoes into the
``X-CSRF-Token`` header on mutating requests; the existing CSRF
middleware enforces the double-submit check.

Backwards-compatible: legacy SDK / server-to-server callers can still
send ``Authorization: Bearer <jwt>`` — the auth dependency accepts
either source.
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional

from policy_engine.database import get_db
from policy_engine.models.user import User
from policy_engine.models.organization import Organization
from policy_engine.models.schemas import UserLogin, TokenResponse, UserResponse
from policy_engine.auth.jwt_utils import (
    verify_password,
    create_access_token,
    get_token_expiration_time,
    decode_access_token,
)
from policy_engine.auth.rbac import get_current_user
from policy_engine.auth.session_cookie import (
    clear_session_cookies,
    set_session_cookies,
)
from policy_engine.services.token_blacklist import get_token_blacklist
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials


def _build_user_response(user: User, db: Session) -> UserResponse:
    """Compose UserResponse including the org's product tier."""
    tier: Optional[str] = None
    if user.organization_id:
        org = (
            db.query(Organization)
            .filter(Organization.id == user.organization_id)
            .first()
        )
        if org is not None:
            tier = org.tier or "enterprise"
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role.value,
        full_name=user.full_name,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login=user.last_login,
        is_active=user.is_active,
        organization_id=user.organization_id,
        tier=tier,
    )


_security = HTTPBearer(auto_error=False)

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    response: Response,
    db: Session = Depends(get_db),
):
    """Authenticate a user and start a cookie session.

    On success the response contains:

    1. ``Set-Cookie: access_token=...`` — HttpOnly Secure SameSite=lax.
       JS cannot read this; the browser sends it automatically on
       same-site requests. This is the CRIT-011 exfil mitigation.
    2. ``Set-Cookie: csrf_token=...`` — JS-readable. The dashboard
       echoes the value into ``X-CSRF-Token`` on POST/PUT/DELETE/PATCH
       requests so the CSRF middleware accepts the call.
    3. Response body — ``user`` and ``csrf_token`` so the SPA can
       hydrate without a second round-trip. ``access_token`` is
       intentionally an empty string in browser flows; non-browser SDK
       callers that need a bearer token should use the X-API-Key path.
    """
    user = (
        db.query(User)
        .filter(User.username == credentials.username.lower())
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    user.last_login = datetime.utcnow()
    db.commit()

    token_data = {
        "user_id": user.id,
        "username": user.username,
        "role": user.role.value,
        "org_id": user.organization_id,
    }
    access_token = create_access_token(token_data)
    expires_in = get_token_expiration_time()

    csrf_token = set_session_cookies(
        response,
        access_token=access_token,
        max_age_seconds=expires_in,
    )

    return TokenResponse(
        # access_token="" → browser flow uses the HttpOnly cookie.
        # Empty string keeps the schema stable for older SDKs that may
        # destructure the field.
        access_token="",
        token_type="bearer",
        expires_in=expires_in,
        user=_build_user_response(user, db),
        csrf_token=csrf_token,
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    response: Response,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_security),
    current_user: User = Depends(get_current_user),
):
    """Log out — blacklist the token (if available) and clear both auth cookies."""
    # If a header bearer was used we can blacklist its jti. The cookie
    # path doesn't expose the raw token to handlers (it's HttpOnly and
    # not echoed back), so we instead clear the cookie — the browser
    # stops sending it. A future token-version-bump path covers hard
    # revoke for active cookie sessions.
    if credentials is not None:
        payload = decode_access_token(credentials.credentials)
        if payload and "jti" in payload:
            exp = payload.get("exp")
            remaining = (
                max(0, int(exp - datetime.utcnow().timestamp()))
                if exp
                else 3600
            )
            get_token_blacklist().add(
                payload["jti"], expires_in_seconds=remaining
            )

    clear_session_cookies(response)

    return {
        "message": "Successfully logged out",
        "username": current_user.username,
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Issue a fresh access token and rotate the session cookies."""
    token_data = {
        "user_id": current_user.id,
        "username": current_user.username,
        "role": current_user.role.value,
        "org_id": current_user.organization_id,
    }
    access_token = create_access_token(token_data)
    expires_in = get_token_expiration_time()

    csrf_token = set_session_cookies(
        response,
        access_token=access_token,
        max_age_seconds=expires_in,
    )

    return TokenResponse(
        access_token="",
        token_type="bearer",
        expires_in=expires_in,
        user=_build_user_response(current_user, db),
        csrf_token=csrf_token,
    )


@router.get("/validate", response_model=UserResponse)
async def validate_token(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Validate the current JWT and return the authenticated user."""
    return _build_user_response(current_user, db)
