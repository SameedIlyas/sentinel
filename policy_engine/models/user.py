"""User database model for RBAC"""

from sqlalchemy import Column, String, DateTime, Boolean, Enum, ForeignKey
from datetime import datetime
import enum

from policy_engine.database import Base


class UserRole(str, enum.Enum):
    """User role enumeration for RBAC — 8 healthcare roles."""
    SYSTEM_ADMIN = "system_admin"
    ORG_ADMIN = "admin"          # value kept as "admin" for backward compat
    ADMIN = "admin"              # Alias for ORG_ADMIN — backward compatibility
    CMIO = "cmio"
    DATA_SCIENTIST = "data_scientist"
    COMPLIANCE_OFFICER = "compliance_officer"
    CLINICAL_USER = "clinical_user"
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
        role: User role
        full_name: User's full name
        created_at: Timestamp when user was created
        updated_at: Timestamp when user was last updated
        last_login: Timestamp of last login
        is_active: Whether user account is active
        organization_id: FK to organizations table (multi-tenancy)
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
    organization_id = Column(String, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)


# Permission mappings for each role
ROLE_PERMISSIONS = {
    UserRole.SYSTEM_ADMIN: {
        # Full access to all resources including healthcare-specific ones
        "policies": ["create", "read", "update", "delete"],
        "agents": ["create", "read", "update", "delete"],
        "audit_logs": ["read", "export"],
        "alerts": ["create", "read", "update", "acknowledge", "configure"],
        "users": ["create", "read", "update", "delete"],
        "organizations": ["create", "read", "update", "delete"],
        "model_cards": ["create", "read", "update", "delete"],
        "bias_audits": ["create", "read", "update", "delete"],
        "drift_detection": ["create", "read", "update", "delete"],
        "hitl_reviews": ["create", "read", "update", "delete"],
        "shadow_ai": ["create", "read", "update", "delete"],
        "scribe_audits": ["create", "read", "update", "delete"],
        "transparency": ["create", "read", "update", "delete"],
        "prior_auth": ["create", "read", "update", "delete"],
        "revenue_cycle": ["create", "read", "update", "delete"],
        "technical_files": ["create", "read", "update", "delete"],
        "post_market": ["create", "read", "update", "delete"],
        "risk_scores": ["create", "read", "update", "delete"],
    },
    UserRole.ORG_ADMIN: {
        # Full access within org (same as old ADMIN)
        "policies": ["create", "read", "update", "delete"],
        "agents": ["create", "read", "update", "delete"],
        "audit_logs": ["read", "export"],
        "alerts": ["create", "read", "update", "acknowledge", "configure"],
        "users": ["create", "read", "update", "delete"],
        "model_cards": ["create", "read", "update", "delete"],
        "bias_audits": ["create", "read", "update"],
        "drift_detection": ["read", "update"],
        "hitl_reviews": ["create", "read", "update"],
        "shadow_ai": ["read"],
        "scribe_audits": ["read"],
        "transparency": ["read"],
        "prior_auth": ["create", "read", "update"],
        "revenue_cycle": ["read"],
        "technical_files": ["create", "read", "update"],
        "post_market": ["read"],
        "risk_scores": ["create", "read", "update", "delete"],
    },
    UserRole.CMIO: {
        "policies": ["create", "read", "update"],
        "agents": ["read", "update"],
        "audit_logs": ["read", "export"],
        "alerts": ["read", "acknowledge"],
        "users": ["read"],
        "model_cards": ["create", "read", "update"],
        "bias_audits": ["read"],
        "drift_detection": ["read"],
        "hitl_reviews": ["create", "read", "update"],
        "risk_scores": ["read"],
        "transparency": ["read"],
    },
    UserRole.DATA_SCIENTIST: {
        "policies": ["read"],
        "agents": ["read"],
        "audit_logs": ["read"],
        "alerts": ["read"],
        "model_cards": ["create", "read", "update"],
        "bias_audits": ["create", "read", "update"],
        "drift_detection": ["create", "read", "update"],
        "risk_scores": ["create", "read", "update"],
        "technical_files": ["create", "read", "update"],
    },
    UserRole.COMPLIANCE_OFFICER: {
        "policies": ["read", "update"],
        "agents": ["read"],
        "audit_logs": ["read", "export"],
        "alerts": ["read", "acknowledge"],
        "users": ["read"],
        "model_cards": ["read"],
        "bias_audits": ["read"],
        "drift_detection": ["read"],
        "transparency": ["read"],
        "post_market": ["read"],
        "risk_scores": ["read"],
        "technical_files": ["read"],
    },
    UserRole.CLINICAL_USER: {
        "policies": ["read"],
        "agents": ["read"],
        "audit_logs": ["read"],
        "alerts": ["read"],
        "hitl_reviews": ["create", "read", "update"],
        "prior_auth": ["create", "read"],
        "risk_scores": ["read"],
        "scribe_audits": ["read"],
        "shadow_ai": ["read"],
    },
    UserRole.ANALYST: {
        # Read-only access to policies, full access to logs and alerts
        "policies": ["read"],
        "agents": ["read"],
        "audit_logs": ["read", "export"],
        "alerts": ["read", "acknowledge", "configure"],
        "users": ["read"],
    },
    UserRole.VIEWER: {
        # Read-only access to everything except user management
        "policies": ["read"],
        "agents": ["read"],
        "audit_logs": ["read"],
        "alerts": ["read"],
        "users": [],
    },
}


def has_permission(user_role: UserRole, resource: str, action: str) -> bool:
    """
    Check if a user role has permission to perform an action on a resource.

    Args:
        user_role: User's role
        resource: Resource type (policies, agents, audit_logs, alerts, users, etc.)
        action: Action to perform (create, read, update, delete, etc.)

    Returns:
        True if user has permission, False otherwise
    """
    if resource not in ROLE_PERMISSIONS.get(user_role, {}):
        return False
    return action in ROLE_PERMISSIONS[user_role][resource]
