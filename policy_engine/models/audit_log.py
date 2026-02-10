"""Audit log database model"""

from sqlalchemy import Column, String, DateTime, JSON, Enum
from datetime import datetime
import enum

from policy_engine.database import Base


class Decision(str, enum.Enum):
    """Policy decision enumeration"""
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    APPROVED = "approved"


class AuditLog(Base):
    """
    Audit log model representing a logged agent action
    
    Attributes:
        id: Unique audit log identifier
        timestamp: When the action occurred
        agent_id: ID of the agent that performed the action
        agent_name: Name of the agent
        user_id: ID of the user who triggered the agent
        tool_name: Name of the tool/function called
        arguments: Sanitized arguments passed to the tool
        system_accessed: Name of the system accessed
        data_touched: List of resource identifiers accessed
        decision: Policy decision (allowed/blocked/approved)
        policy_ids: List of policy IDs that were evaluated
        reason: Explanation for the decision
        metadata: Additional metadata as JSON
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
    data_touched = Column(JSON, nullable=False)  # List of resource identifiers
    decision = Column(Enum(Decision), nullable=False, index=True)
    policy_ids = Column(JSON, nullable=False)  # List of policy IDs
    reason = Column(String, nullable=False)
    metadata = Column(JSON, default=dict, nullable=False)
