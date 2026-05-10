"""Authentication endpoints (login, logout)"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime

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
from policy_engine.services.token_blacklist import get_token_blacklist
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional


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
    db: Session = Depends(get_db)
):
    """
    Authenticate user and return JWT token
    
    This endpoint authenticates a user with username and password, and returns
    a JWT access token that can be used for subsequent authenticated requests.
    
    Args:
        credentials: User login credentials (username and password)
        db: Database session
        
    Returns:
        JWT access token and user information
        
    Raises:
        HTTPException: If credentials are invalid or user is inactive
    """
    # Find user by username
    user = db.query(User).filter(User.username == credentials.username.lower()).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify password
    if not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    # Update last login timestamp
    user.last_login = datetime.utcnow()
    db.commit()
    
    # Create JWT token
    token_data = {
        "user_id": user.id,
        "username": user.username,
        "role": user.role.value,
        "org_id": user.organization_id,
    }
    access_token = create_access_token(token_data)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=get_token_expiration_time(),
        user=_build_user_response(user, db),
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_security),
    current_user: User = Depends(get_current_user),
):
    """Logout current user and invalidate the JWT token."""
    if credentials is not None:
        payload = decode_access_token(credentials.credentials)
        if payload and "jti" in payload:
            from datetime import datetime
            exp = payload.get("exp")
            remaining = max(0, int(exp - datetime.utcnow().timestamp())) if exp else 3600
            get_token_blacklist().add(payload["jti"], expires_in_seconds=remaining)

    return {
        "message": "Successfully logged out",
        "username": current_user.username,
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Refresh JWT access token
    
    This endpoint allows refreshing an existing (valid) token to extend the
    session. Returns a new token with a new expiration time.
    
    Args:
        current_user: Current authenticated user (from existing token)
        db: Database session
        
    Returns:
        New JWT access token and user information
    """
    # Create new JWT token
    token_data = {
        "user_id": current_user.id,
        "username": current_user.username,
        "role": current_user.role.value,
        "org_id": current_user.organization_id,
    }
    access_token = create_access_token(token_data)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=get_token_expiration_time(),
        user=_build_user_response(current_user, db),
    )


@router.get("/validate", response_model=UserResponse)
async def validate_token(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Validate current JWT token

    Returns the authenticated user including their organization tier so the
    dashboard can render tier-aware navigation without a second round-trip.
    """
    return _build_user_response(current_user, db)
