"""Database models — importing here registers each table with Base.metadata.

Every model file MUST be imported here so SQLAlchemy can resolve string-based
ForeignKey references at mapper-configuration time. Missing imports cause
"could not find table 'X' with which to generate a foreign key" errors when
the user-side model is queried.
"""

from policy_engine.models.agent import Agent
from policy_engine.models.policy import Policy
from policy_engine.models.audit_log import AuditLog
from policy_engine.models.alert import Alert
from policy_engine.models.alert_config import AlertConfig
from policy_engine.models.api_key import APIKey
from policy_engine.models.user import User, UserRole
from policy_engine.models.organization import Organization, OrganizationMember  # noqa: F401

__all__ = [
    "Agent",
    "Policy",
    "AuditLog",
    "Alert",
    "AlertConfig",
    "APIKey",
    "User",
    "UserRole",
    "Organization",
    "OrganizationMember",
]
