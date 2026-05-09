"""Alert management endpoints"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
import logging
import uuid

from policy_engine.database import get_db
from policy_engine.auth.rbac import authenticate_request
from policy_engine.models.alert import Alert
from policy_engine.models.alert_config import AlertConfig
from policy_engine.models.schemas import (
    AlertResponse,
    AlertListResponse,
    AlertAcknowledge,
    AlertRuleResponse,
    AlertConfigRequest,
    SlackConfig
)
from policy_engine.services.alert_service import AlertService
from policy_engine.services.slack_service import slack_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/configure", status_code=status.HTTP_200_OK)
async def configure_alerts(
    config: AlertConfigRequest,
    auth_id: str = Depends(authenticate_request),
    db: Session = Depends(get_db)
):
    """
    Configure alert rules and Slack webhook settings
    
    This endpoint allows administrators to configure:
    - Global Slack webhook URL
    - Alert rules per policy type
    - Alert routing and severity
    
    Args:
       config: Alert configuration including webhook URL and rules
        agent_id: Authenticated agent ID
        db: Database session
        
    Returns:
        Configuration status and created rules
    """
    try:
        created_rules = []
        
        # Store or update global webhook (stored as a special config record)
        if config.global_slack_webhook:
            global_config = db.query(AlertConfig).filter(
                AlertConfig.alert_type == "_global_webhook"
            ).first()
            
            if global_config:
                global_config.slack_webhook_url = config.global_slack_webhook
                global_config.enabled = True
            else:
                global_config = AlertConfig(
                    id=str(uuid.uuid4()),
                    policy_type=None,
                    alert_type="_global_webhook",
                    severity="low",
                    slack_webhook_url=config.global_slack_webhook,
                    enabled=True
                )
                db.add(global_config)
            
            # Update global Slack service with new webhook
            slack_service.default_webhook_url = config.global_slack_webhook
        
        # Create alert rules
        if config.alert_rules:
            for rule in config.alert_rules:
                alert_rule = AlertConfig(
                    id=str(uuid.uuid4()),
                    policy_type=rule.policy_type.value if rule.policy_type else None,
                    alert_type=rule.alert_type,
                    severity=rule.severity.value,
                    conditions=rule.conditions,
                    slack_webhook_url=rule.slack_webhook_url,
                    enabled=rule.enabled
                )
                db.add(alert_rule)
                created_rules.append(alert_rule)
        
        db.commit()
        
        logger.info(f"Alert configuration updated: {len(created_rules)} rules created")
        
        return {
            "message": "Alert configuration updated successfully",
            "global_webhook_configured": config.global_slack_webhook is not None,
            "rules_created": len(created_rules),
            "rules": [
                AlertRuleResponse(
                    id=rule.id,
                    policy_type=rule.policy_type,
                    alert_type=rule.alert_type,
                    severity=rule.severity,
                    conditions=rule.conditions,
                    slack_webhook_url=rule.slack_webhook_url,
                    enabled=rule.enabled,
                    created_at=rule.created_at
                )
                for rule in created_rules
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to configure alerts: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to configure alerts: {str(e)}"
        )


@router.get("", response_model=AlertListResponse)
async def get_alerts(
    auth_id: str = Depends(authenticate_request),
    db: Session = Depends(get_db),
    alert_type: Optional[str] = Query(None, description="Filter by alert type"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    acknowledged: Optional[bool] = Query(None, description="Filter by acknowledgment status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page")
):
    """
    Query alerts with filtering and pagination
    
    Args:
        agent_id: Authenticated agent ID
        db: Database session
        alert_type: Filter by alert type
        severity: Filter by severity
        acknowledged: Filter by acknowledgment status
        page: Page number
        page_size: Items per page
        
    Returns:
        Paginated list of alerts
    """
    try:
        # Build query
        query = db.query(Alert)
        
        # Apply filters
        if alert_type:
            query = query.filter(Alert.alert_type == alert_type)
        
        if severity:
            query = query.filter(Alert.severity == severity)
        
        if acknowledged is not None:
            query = query.filter(Alert.acknowledged == acknowledged)
        
        # Get total count
        total = query.count()
        
        # Calculate pagination
        total_pages = (total + page_size - 1) // page_size
        offset = (page - 1) * page_size
        
        # Get page of results, ordered by timestamp descending (newest first)
        alerts = query.order_by(Alert.timestamp.desc()).offset(offset).limit(page_size).all()
        
        return AlertListResponse(
            alerts=alerts,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Failed to query alerts: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query alerts: {str(e)}"
        )


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(
    alert_id: str,
    auth_id: str = Depends(authenticate_request),
    db: Session = Depends(get_db)
):
    """
    Get a specific alert by ID
    
    Args:
        alert_id: Alert ID
        agent_id: Authenticated agent ID
        db: Database session
        
    Returns:
        Alert details
    """
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with ID '{alert_id}' not found"
        )
    
    return alert


@router.post("/{alert_id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert(
    alert_id: str,
    acknowledge_data: AlertAcknowledge,
    auth_id: str = Depends(authenticate_request),
    db: Session = Depends(get_db)
):
    """
    Acknowledge an alert
    
    Args:
        alert_id: Alert ID
        acknowledge_data: Acknowledgment data containing user ID
        agent_id: Authenticated agent ID
        db: Database session
        
    Returns:
        Updated alert
    """
    alert_service = AlertService(db)
    alert = alert_service.acknowledge_alert(alert_id, acknowledge_data.acknowledged_by)
    
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with ID '{alert_id}' not found"
        )
    
    return alert


@router.post("/test", status_code=status.HTTP_200_OK)
async def test_slack_webhook(
    config: SlackConfig,
    auth_id: str = Depends(authenticate_request),
    db: Session = Depends(get_db)
):
    """
    Send a test message to Slack to verify webhook configuration
    
    Args:
        config: Slack configuration with webhook URL
        agent_id: Authenticated agent ID
        db: Database session
        
    Returns:
        Test result status
    """
    if not config.enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Slack configuration is disabled"
        )
    
    success = slack_service.send_test_message(config.webhook_url)
    
    if success:
        return {
            "success": True,
            "message": "Test message sent successfully to Slack"
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send test message to Slack. Check webhook URL and Slack configuration."
        )


@router.get("/rules/list", response_model=list[AlertRuleResponse])
async def list_alert_rules(
    auth_id: str = Depends(authenticate_request),
    db: Session = Depends(get_db),
    enabled_only: bool = Query(False, description="Show only enabled rules")
):
    """
    List all alert rules
    
    Args:
        agent_id: Authenticated agent ID
        db: Database session
        enabled_only: Whether to show only enabled rules
        
    Returns:
        List of alert rules
    """
    query = db.query(AlertConfig).filter(
        AlertConfig.alert_type != "_global_webhook"
    )
    
    if enabled_only:
        query = query.filter(AlertConfig.enabled.is_(True))
    
    rules = query.all()
    
    return [
        AlertRuleResponse(
            id=rule.id,
            policy_type=rule.policy_type,
            alert_type=rule.alert_type,
            severity=rule.severity,
            conditions=rule.conditions,
            slack_webhook_url=rule.slack_webhook_url,
            enabled=rule.enabled,
            created_at=rule.created_at
        )
        for rule in rules
    ]

