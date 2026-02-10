"""Alert database model"""

from sqlalchemy import Column, String, DateTime, Boolean, Enum
from datetime import datetime
import enum

from policy_engine.database import Base


class AlertSeverity(str, enum.Enum):
    """Alert severity enumeration"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Alert(Base):
    """
    Alert model representing a security alert
    
    Attributes:
        id: Unique alert identifier
        timestamp: When the alert was created
        severity: Alert severity level
        alert_type: Type of alert (blocked_access, high_transaction, new_agent, etc.)
        agent_id: ID of the agent that triggered the alert
        description: Human-readable alert description
        audit_log_id: ID of the related audit log entry
        acknowledged: Whether the alert has been acknowledged
        acknowledged_by: ID of user who acknowledged the alert
        acknowledged_at: When the alert was acknowledged
    """
    __tablename__ = "alerts"
    
    id = Column(String, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    severity = Column(Enum(AlertSeverity), nullable=False, index=True)
    alert_type = Column(String, nullable=False, index=True)
    agent_id = Column(String, nullable=False, index=True)
    description = Column(String, nullable=False)
    audit_log_id = Column(String, nullable=True)
    acknowledged = Column(Boolean, default=False, nullable=False)
    acknowledged_by = Column(String, nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
