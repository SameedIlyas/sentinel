"""Policy database model"""

from sqlalchemy import Column, String, DateTime, JSON, Boolean, Integer, Enum, ForeignKey
from datetime import datetime
import enum

from policy_engine.database import Base


class PolicyType(str, enum.Enum):
    """Policy type enumeration"""
    ACCESS_CONTROL = "access_control"
    FINANCIAL = "financial"
    DATA_PROTECTION = "data_protection"


class Policy(Base):
    """
    Policy model representing a security policy
    
    Attributes:
        id: Unique policy identifier
        name: Human-readable policy name
        description: Policy description
        policy_type: Type of policy (access_control, financial, data_protection)
        rules: List of policy rules as JSON
        applies_to: List of agent IDs this policy applies to (or ["*"] for all)
        priority: Policy priority (higher number = higher priority)
        enabled: Whether the policy is currently enabled
        created_by: ID of user who created the policy
        created_at: Timestamp when policy was created
        updated_at: Timestamp when policy was last updated
    """
    __tablename__ = "policies"
    
    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    policy_type = Column(Enum(PolicyType), nullable=False, index=True)
    rules = Column(JSON, nullable=False)
    applies_to = Column(JSON, nullable=False)  # List of agent IDs or ["*"]
    priority = Column(Integer, default=0, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    organization_id = Column(String, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)
