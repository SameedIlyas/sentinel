"""User database model for RBAC"""

from sqlalchemy import Column, String, DateTime, Boolean, Enum
from datetime import datetime
import enum

from policy_engine.database import Base


class UserRole(str, enum.Enum):
    """User role enumeration for RBAC"""
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


class User(Base):
    """
    User model for dashboard access with role-based permissions
    
    Attributes:
        id: Unique user identifier
        username: Unique username for login
        email: User email address
        password_hash: Bcrypt hashed password
        role: User role (admin, analyst, viewer)
        full_name: User's full name
        created_at: Timestamp when user was created
        updated_at: Timestamp when user was last updated
        last_login: Timestamp of last login
        is_active: Whether user account is active
    """
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.VIEWER, nullable=False)
    full_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)


# Permission mappings for each role
ROLE_PERMISSIONS = {
    UserRole.ADMIN: {
        # Full access to everything
        "policies": ["create", "read", "update", "delete"],
        "agents": ["create", "read", "update", "delete"],
        "audit_logs": ["read", "export"],
        "alerts": ["create", "read", "update", "acknowledge", "configure"],
        "users": ["create", "read", "update", "delete"],
    },
    UserRole.ANALYST: {
        # Read-only access to policies, full access to logs and alerts
        "policies": ["read"],
        "agents": ["read"],
        "audit_logs": ["read", "export"],
        "alerts": ["read", "acknowledge", "configure"],
        "users": ["read"],  # Can view users but not modify
    },
    UserRole.VIEWER: {
        # Read-only access to everything except user management
        "policies": ["read"],
        "agents": ["read"],
        "audit_logs": ["read"],
        "alerts": ["read"],
        "users": [],  # No access to user management
    }
}


def has_permission(user_role: UserRole, resource: str, action: str) -> bool:
    """
    Check if a user role has permission to perform an action on a resource
    
    Args:
        user_role: User's role
        resource: Resource type (policies, agents, audit_logs, alerts, users)
        action: Action to perform (create, read, update, delete, etc.)
        
    Returns:
        True if user has permission, False otherwise
    """
    if resource not in ROLE_PERMISSIONS.get(user_role, {}):
        return False
    
    return action in ROLE_PERMISSIONS[user_role][resource]
