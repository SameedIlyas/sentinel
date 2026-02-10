"""Alert configuration database model"""

from sqlalchemy import Column, String, DateTime, Boolean, JSON
from datetime import datetime

from policy_engine.database import Base


class AlertConfig(Base):
    """
    Alert configuration model for storing alert rules and webhook settings
    
    Attributes:
        id: Unique configuration identifier
        policy_type: Policy type this rule applies to (null for global)
        alert_type: Type of alert to trigger
        severity: Severity level for triggered alerts
        conditions: Additional JSON conditions for triggering
        slack_webhook_url: Slack webhook URL for this rule
        enabled: Whether this alert rule is enabled
        created_at: When the configuration was created
        updated_at: When the configuration was last updated
    """
    __tablename__ = "alert_configs"
    
    id = Column(String, primary_key=True, index=True)
    policy_type = Column(String, nullable=True, index=True)  # null for global config
    alert_type = Column(String, nullable=False, index=True)
    severity = Column(String, nullable=False)
    conditions = Column(JSON, nullable=True)
    slack_webhook_url = Column(String, nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
