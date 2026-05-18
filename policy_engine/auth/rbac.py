"""RBAC middleware and permission decorators"""

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Callable, List, Optional

from policy_engine.database import get_db
from policy_engine.models.user import User, UserRole, has_permission
from policy_engine.auth.jwt_utils import decode_access_token
from policy_engine.auth.api_key import _verify_api_key_logic
from policy_engine.config import settings


# HTTP Bearer token security scheme
security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Get the current authenticated user from JWT token
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check token blacklist (logout invalidation)
    jti = payload.get("jti")
    if jti:
        from policy_engine.services.token_blacklist import get_token_blacklist
        if get_token_blacklist().is_blacklisted(jti):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    user_id = payload.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    return user


def authenticate_request(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> str:
    """
    Flexible auth: accepts either JWT bearer token or X-API-Key header.
    Returns an identifier string (user_id or agent_id).
    """
    # Try JWT bearer token first
    if credentials is not None:
        payload = decode_access_token(credentials.credentials)
        if payload and payload.get("user_id"):
            # Mirror the blacklist check from get_current_user — logout must
            # invalidate the token across every dependency, not just the routes
            # that use get_current_user. See CRIT-007 in REVIEW.md.
            jti = payload.get("jti")
            if jti:
                from policy_engine.services.token_blacklist import get_token_blacklist
                if get_token_blacklist().is_blacklisted(jti):
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Token has been revoked",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
            user = db.query(User).filter(User.id == payload["user_id"]).first()
            if user and user.is_active:
                return user.id

    # Try API key — delegate entirely to api_key.py to avoid duplicated logic
    api_key = request.headers.get(settings.API_KEY_HEADER)
    if api_key:
        try:
            return _verify_api_key_logic(api_key, db)
        except HTTPException:
            raise

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated. Provide a Bearer token or X-API-Key header.",
    )


def require_role(allowed_roles: List[UserRole]) -> Callable:
    """
    Decorator to require specific user roles
    
    Args:
        allowed_roles: List of roles allowed to access the endpoint
        
    Returns:
        Dependency function that checks user role
        
    Example:
        @router.get("/admin-only")
        def admin_endpoint(user: User = Depends(require_role([UserRole.ADMIN]))):
            ...
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required roles: {[r.value for r in allowed_roles]}"
            )
        return current_user
    
    return role_checker


def require_permission(resource: str, action: str) -> Callable:
    """
    Decorator to require specific permission
    
    Args:
        resource: Resource type (policies, agents, audit_logs, alerts, users)
        action: Action to perform (create, read, update, delete, etc.)
        
    Returns:
        Dependency function that checks user permission
        
    Example:
        @router.post("/policies")
        def create_policy(user: User = Depends(require_permission("policies", "create"))):
            ...
    """
    def permission_checker(current_user: User = Depends(get_current_user)) -> User:
        if not has_permission(current_user.role, resource, action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions to {action} {resource}"
            )
        return current_user
    
    return permission_checker


# Convenience dependency functions
def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """Require admin role"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required"
        )
    return current_user


def get_analyst_or_admin(current_user: User = Depends(get_current_user)) -> User:
    """Require analyst or admin role"""
    if current_user.role not in [UserRole.ADMIN, UserRole.ANALYST]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Analyst or administrator privileges required"
        )
    return current_user


def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Returns None instead of raising 401 — for public endpoints."""
    try:
        return get_current_user(credentials=credentials, db=db)
    except HTTPException:
        return None
