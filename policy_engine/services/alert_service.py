"""Alert triggering and management service"""

from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging
import uuid

from policy_engine.models.alert import Alert, AlertSeverity
from policy_engine.models.schemas import AlertCreate, PolicyType

logger = logging.getLogger(__name__)


class AlertService:
    """Service for managing alerts and deduplication"""
    
    def __init__(self, db: Session, deduplication_window_seconds: int = 300):
        """
        Initialize alert service
        
        Args:
            db: Database session
            deduplication_window_seconds: Time window for deduplication (default: 5 minutes)
        """
        self.db = db
        self.deduplication_window_seconds = deduplication_window_seconds
    
    def create_alert(
        self,
        severity: AlertSeverity,
        alert_type: str,
        agent_id: str,
        description: str,
        audit_log_id: Optional[str] = None,
        auto_deduplicate: bool = True
    ) -> Optional[Alert]:
        """
        Create a new alert with optional deduplication
        
        Args:
            severity: Alert severity level
            alert_type: Type of alert
            agent_id: ID of agent that triggered the alert
            description: Human-readable description
            audit_log_id: Related audit log entry ID
            auto_deduplicate: Whether to check for duplicate alerts
            
        Returns:
            Created alert or None if deduplicated
        """
        try:
            # Check for duplicates if deduplication is enabled
            if auto_deduplicate:
                if self._is_duplicate(alert_type, agent_id):
                    logger.info(
                        f"Alert deduplicated: type={alert_type}, agent={agent_id}"
                    )
                    return None
            
            # Create new alert
            alert = Alert(
                id=str(uuid.uuid4()),
                timestamp=datetime.utcnow(),
                severity=severity,
                alert_type=alert_type,
                agent_id=agent_id,
                description=description,
                audit_log_id=audit_log_id,
                acknowledged=False
            )
            
            self.db.add(alert)
            self.db.commit()
            self.db.refresh(alert)
            
            logger.info(
                f"Alert created: id={alert.id}, type={alert_type}, "
                f"severity={severity.value}, agent={agent_id}"
            )
            
            return alert
            
        except Exception as e:
            logger.error(f"Failed to create alert: {str(e)}", exc_info=True)
            self.db.rollback()
            return None
    
    def _is_duplicate(self, alert_type: str, agent_id: str) -> bool:
        """
        Check if a similar alert was recently created
        
        Args:
            alert_type: Type of alert
            agent_id: Agent ID
            
        Returns:
            True if duplicate found within deduplication window
        """
        cutoff_time = datetime.utcnow() - timedelta(
            seconds=self.deduplication_window_seconds
        )
        
        existing = self.db.query(Alert).filter(
            Alert.alert_type == alert_type,
            Alert.agent_id == agent_id,
            Alert.timestamp >= cutoff_time
        ).first()
        
        return existing is not None
    
    def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> Optional[Alert]:
        """
        Acknowledge an alert
        
        Args:
            alert_id: Alert ID
            acknowledged_by: ID of user acknowledging the alert
            
        Returns:
            Updated alert or None if not found
        """
        try:
            alert = self.db.query(Alert).filter(Alert.id == alert_id).first()
            
            if not alert:
                logger.warning(f"Alert not found: {alert_id}")
                return None
            
            alert.acknowledged = True
            alert.acknowledged_by = acknowledged_by
            alert.acknowledged_at = datetime.utcnow()
            
            self.db.commit()
            self.db.refresh(alert)
            
            logger.info(f"Alert acknowledged: id={alert_id}, by={acknowledged_by}")
            
            return alert
            
        except Exception as e:
            logger.error(f"Failed to acknowledge alert: {str(e)}", exc_info=True)
            self.db.rollback()
            return None
    
    def get_alert(self, alert_id: str) -> Optional[Alert]:
        """
        Get alert by ID
        
        Args:
            alert_id: Alert ID
            
        Returns:
            Alert or None if not found
        """
        return self.db.query(Alert).filter(Alert.id == alert_id).first()
    
    def classify_severity(
        self,
        policy_type: PolicyType,
        decision: str,
        is_new_agent: bool = False
    ) -> AlertSeverity:
        """
        Classify alert severity based on context
        
        Args:
            policy_type: Type of policy that triggered the alert
            decision: Policy decision (blocked, allowed, etc.)
            is_new_agent: Whether this is a new agent
            
        Returns:
            Alert severity level
        """
        # New agent detection is always critical
        if is_new_agent:
            return AlertSeverity.CRITICAL
        
        # Blocked actions are high or critical based on policy type
        if decision == "blocked":
            if policy_type == PolicyType.DATA_PROTECTION:
                return AlertSeverity.CRITICAL
            elif policy_type == PolicyType.FINANCIAL:
                return AlertSeverity.HIGH
            else:
                return AlertSeverity.MEDIUM
        
        # Require approval actions are medium severity
        if decision == "require_approval":
            return AlertSeverity.MEDIUM
        
        # Default to low severity
        return AlertSeverity.LOW
    
    def determine_alert_type(
        self,
        policy_type: PolicyType,
        decision: str,
        tool_name: str,
        is_new_agent: bool = False
    ) -> Optional[str]:
        """
        Determine the type of alert to create
        
        Args:
            policy_type: Type of policy
            decision: Policy decision
            tool_name: Name of the tool being called
            is_new_agent: Whether this is a new agent
            
        Returns:
            Alert type string or None if no alert needed
        """
        # New agent detection
        if is_new_agent:
            return "new_agent"
        
        # Blocked access
        if decision == "blocked":
            if policy_type == PolicyType.ACCESS_CONTROL:
                return "blocked_access"
            elif policy_type == PolicyType.FINANCIAL:
                # Check if it's a high-value transaction
                if any(keyword in tool_name.lower() for keyword in ["payment", "transaction", "transfer", "purchase"]):
                    return "high_transaction"
                return "blocked_financial_action"
            elif policy_type == PolicyType.DATA_PROTECTION:
                return "data_protection_violation"
        
        # Require approval (financial actions)
        if decision == "require_approval":
            return "approval_required"
        
        # Don't create alerts for allowed actions
        return None
    
    def should_trigger_alert(
        self,
        decision: str,
        policy_type: Optional[PolicyType] = None,
        is_new_agent: bool = False
    ) -> bool:
        """
        Determine if an alert should be triggered
        
        Args:
            decision: Policy decision
            policy_type: Type of policy
            is_new_agent: Whether this is a new agent
            
        Returns:
            True if alert should be triggered
        """
        # Always alert on new agents
        if is_new_agent:
            return True
        
        # Alert on blocked or require_approval actions
        if decision in ["blocked", "require_approval"]:
            return True
        
        return False
