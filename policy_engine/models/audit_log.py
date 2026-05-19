"""Audit log database model"""

from sqlalchemy import Boolean, Column, String, DateTime, JSON, Enum, ForeignKey
from datetime import datetime
import enum

from policy_engine.database import Base


class Decision(str, enum.Enum):
    """Policy decision enumeration"""
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    APPROVED = "approved"
    REQUIRES_APPROVAL = "requires_approval"


class AuditLog(Base):
    """Audit log model representing a logged agent action.

    Attributes:
        id: Unique audit log identifier.
        timestamp: When the action occurred.
        agent_id: ID of the agent that performed the action.
        agent_name: Name of the agent.
        user_id: ID of the user who triggered the agent.
        tool_name: Name of the tool/function called.
        arguments: Sanitized arguments passed to the tool.
        system_accessed: Name of the system accessed.
        data_touched: List of resource identifiers accessed.
        decision: Policy decision (allowed/blocked/approved).
        policy_ids: List of policy IDs that were evaluated.
        reason: Explanation for the decision.
        metadata: Additional metadata as JSON.
        legal_hold: CRIT-008 — when True the row is exempt from the
            retention sweep regardless of age. Flipped by compliance /
            legal operators when litigation or a regulatory request
            requires preservation.
    """
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    agent_id = Column(String, nullable=False, index=True)
    agent_name = Column(String, nullable=False)
    user_id = Column(String, nullable=False, index=True)
    tool_name = Column(String, nullable=False, index=True)
    arguments = Column(JSON, nullable=False)
    system_accessed = Column(String, nullable=False, index=True)
    data_touched = Column(JSON, nullable=False)
    decision = Column(Enum(Decision), nullable=False, index=True)
    policy_ids = Column(JSON, nullable=False)
    reason = Column(String, nullable=False)
    log_metadata = Column('metadata', JSON, default=dict, nullable=False)
    organization_id = Column(String, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=False, index=True)
    # CRIT-008 — exempt the row from retention purge when True.
    legal_hold = Column(
        Boolean, nullable=False, default=False, server_default="0", index=True
    )
