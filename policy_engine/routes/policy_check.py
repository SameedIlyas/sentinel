"""Policy check/evaluation endpoints"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging
from datetime import datetime, timezone
from typing import Optional

from policy_engine.database import get_db
from policy_engine.auth.api_key import get_current_agent
from policy_engine.models.schemas import PolicyCheckRequest, PolicyCheckResponse, PolicyType
from policy_engine.services.policy_evaluation import PolicyEvaluationService
from policy_engine.models.audit_log import AuditLog
from policy_engine.models.alert_config import AlertConfig
from policy_engine.services.alert_service import AlertService
from policy_engine.services.slack_service import slack_service
from policy_engine.services.agent_activity_service import AgentActivityService

router = APIRouter()
logger = logging.getLogger(__name__)


def create_audit_log(
    db: Session,
    request: PolicyCheckRequest,
    response: PolicyCheckResponse
):
    """
    Create an audit log entry for a policy check
    
    Args:
        db: Database session
        request: Policy check request
        response: Policy check response
    """
    try:
        import uuid as _uuid

        decision_map = {
            'allow': 'allowed',
            'block': 'blocked',
            'require_approval': 'requires_approval',
        }

        context = request.context or {}

        audit_log = AuditLog(
            id=str(_uuid.uuid4()),
            agent_id=request.agent_id,
            agent_name=context.get('agent_name', request.agent_id),
            user_id=request.user_id,
            tool_name=request.tool_name,
            arguments=request.arguments,
            system_accessed=context.get('system', 'unknown'),
            data_touched=context.get('data_touched', []),
            decision=decision_map.get(response.decision, 'blocked'),
            policy_ids=response.policy_ids,
            reason=response.reason,
            log_metadata=response.metadata or {},
            timestamp=datetime.now(timezone.utc),
        )
        
        db.add(audit_log)
        db.commit()
        
        logger.info(f"Created audit log {audit_log.id} for agent={request.agent_id}, tool={request.tool_name}")
        
        return audit_log.id
        
    except Exception as e:
        logger.error(f"Failed to create audit log: {str(e)}", exc_info=True)
        db.rollback()
        return None


def trigger_alert(
    db: Session,
    request: PolicyCheckRequest,
    response: PolicyCheckResponse,
    audit_log_id: Optional[str] = None
):
    """
    Trigger alerts based on policy check results
    
    Args:
        db: Database session
        request: Policy check request
        response: Policy check response
        audit_log_id: Related audit log ID
    """
    try:
        alert_service = AlertService(db)
        
        # Determine if alert should be triggered
        if not alert_service.should_trigger_alert(
            decision=response.decision,
            is_new_agent=False  # TODO: Track new agent detection
        ):
            return
        
        # Determine policy type from response (check first policy ID)
        policy_type = None
        if response.policy_ids:
            from policy_engine.models.policy import Policy
            first_policy = db.query(Policy).filter(
                Policy.id == response.policy_ids[0]
            ).first()
            if first_policy:
                try:
                    policy_type = PolicyType(first_policy.policy_type)
                except ValueError:
                    pass
        
        # Classify severity and determine alert type
        severity = alert_service.classify_severity(
            policy_type=policy_type if policy_type else PolicyType.ACCESS_CONTROL,
            decision=response.decision,
            is_new_agent=False
        )
        
        alert_type = alert_service.determine_alert_type(
            policy_type=policy_type if policy_type else PolicyType.ACCESS_CONTROL,
            decision=response.decision,
            tool_name=request.tool_name,
            is_new_agent=False
        )
        
        if not alert_type:
            return
        
        # Build alert description
        description = (
            f"Agent '{request.agent_id}' attempted action '{request.tool_name}' "
            f"which was {response.decision}. Reason: {response.reason}"
        )
        
        # Create alert
        alert = alert_service.create_alert(
            severity=severity,
            alert_type=alert_type,
            agent_id=request.agent_id,
            description=description,
            audit_log_id=audit_log_id,
            auto_deduplicate=True
        )
        
        if not alert:
            logger.debug("Alert was deduplicated")
            return
        
        # Send to Slack if configured
        # Get global webhook or policy-specific webhook
        global_webhook_config = db.query(AlertConfig).filter(
            AlertConfig.alert_type == "_global_webhook"
        ).first()
        
        webhook_url = None
        if global_webhook_config and global_webhook_config.enabled:
            webhook_url = global_webhook_config.slack_webhook_url
        
        # Check for alert-type specific webhook
        alert_rule = db.query(AlertConfig).filter(
            AlertConfig.alert_type == alert_type,
            AlertConfig.enabled == True
        ).first()
        
        if alert_rule and alert_rule.slack_webhook_url:
            webhook_url = alert_rule.slack_webhook_url
        
        if webhook_url:
            # Send alert to Slack (async, don't block on failure)
            try:
                policy_name = first_policy.name if first_policy else None
                slack_service.send_alert(
                    alert=alert,
                    agent_name=request.agent_id,  # Could be enhanced with agent name lookup
                    policy_violated=policy_name,
                    action_attempted=request.tool_name,
                    webhook_url=webhook_url
                )
            except Exception as slack_error:
                logger.error(f"Failed to send Slack alert: {str(slack_error)}")
        
        logger.info(
            f"Alert triggered: id={alert.id}, type={alert_type}, "
            f"severity={severity.value}, agent={request.agent_id}"
        )
        
    except Exception as e:
        logger.error(f"Failed to trigger alert: {str(e)}", exc_info=True)
        # Don't fail the policy check if alerting fails
        db.rollback()


@router.post("/check", response_model=PolicyCheckResponse)
async def check_policy(
    request: PolicyCheckRequest,
    agent_id: str = Depends(get_current_agent),
    db: Session = Depends(get_db)
):
    """
    Evaluate policies for a tool call
    
    This endpoint is the core of the Policy Engine. It receives a tool call
    request from an AI agent and evaluates all applicable policies to determine
    whether the action should be allowed, blocked, or requires approval.
    
    Args:
        request: Policy check request containing tool call details
        agent_id: Authenticated agent ID from API key
        db: Database session
        
    Returns:
        Policy check response with decision and explanation
        
    Raises:
        HTTPException: If evaluation fails
    """
    try:
        # Ensure the agent_id in request matches authenticated agent
        if request.agent_id != agent_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Agent ID in request ({request.agent_id}) does not match authenticated agent ({agent_id})"
            )
        
        # Register or update agent activity (auto-registration on first SDK call)
        AgentActivityService.register_or_update_agent(
            db=db,
            agent_id=agent_id,
            agent_name=request.context.get('agent_name') if request.context else None,
            owner_user_id=request.user_id,
            llm_provider=request.context.get('llm_provider') if request.context else None,
            metadata=request.context or {}
        )
        
        # Initialize policy evaluation service
        evaluation_service = PolicyEvaluationService(db)
        
        # Evaluate policies
        logger.info(f"Evaluating policies for agent={request.agent_id}, tool={request.tool_name}")
        response = evaluation_service.evaluate(request)
        
        # Create audit log entry
        audit_log_id = create_audit_log(db, request, response)
        
        # Trigger alerts for policy violations
        trigger_alert(db, request, response, audit_log_id)
        
        # Log the decision
        logger.info(
            f"Policy decision for agent={request.agent_id}, tool={request.tool_name}: "
            f"{response.decision} - {response.reason}"
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Policy evaluation error: {str(e)}", exc_info=True)
        
        # Fail-safe: block on error
        error_response = PolicyCheckResponse(
            decision='block',
            reason=f"Policy evaluation failed: {str(e)}. Blocking for safety.",
            masked_data=None,
            policy_ids=[],
            metadata={'error': str(e), 'fail_safe': True}
        )
        
        # Log the error response
        audit_log_id = create_audit_log(db, request, error_response)
        
        # Trigger alerts for error-induced blocks
        trigger_alert(db, request, error_response, audit_log_id)
        
        return error_response


@router.post("/check/batch", response_model=list[PolicyCheckResponse])
async def check_policies_batch(
    requests: list[PolicyCheckRequest],
    agent_id: str = Depends(get_current_agent),
    db: Session = Depends(get_db)
):
    """
    Evaluate policies for multiple tool calls in batch
    
    This endpoint allows evaluating multiple tool calls in a single request
    for improved performance.
    
    Args:
        requests: List of policy check requests
        agent_id: Authenticated agent ID from API key
        db: Database session
        
    Returns:
        List of policy check responses
        
    Raises:
        HTTPException: If batch size exceeds limit
    """
    # Limit batch size
    MAX_BATCH_SIZE = 100
    if len(requests) > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Batch size ({len(requests)}) exceeds maximum ({MAX_BATCH_SIZE})"
        )
    
    # Validate all requests belong to authenticated agent
    for request in requests:
        if request.agent_id != agent_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Agent ID mismatch in batch request"
            )
    
    # Register or update agent activity (use first request for metadata)
    if requests:
        first_request = requests[0]
        AgentActivityService.register_or_update_agent(
            db=db,
            agent_id=agent_id,
            agent_name=first_request.context.get('agent_name') if first_request.context else None,
            owner_user_id=first_request.user_id,
            llm_provider=first_request.context.get('llm_provider') if first_request.context else None,
            metadata=first_request.context or {}
        )
    
    # Initialize policy evaluation service
    evaluation_service = PolicyEvaluationService(db)
    
    # Evaluate all requests
    responses = []
    for request in requests:
        try:
            response = evaluation_service.evaluate(request)
            responses.append(response)
            
            # Create audit log entry
            audit_log_id = create_audit_log(db, request, response)
            
            # Trigger alerts for policy violations
            trigger_alert(db, request, response, audit_log_id)
            
        except Exception as e:
            logger.error(f"Batch evaluation error for tool={request.tool_name}: {str(e)}")
            # Fail-safe for individual request
            error_response = PolicyCheckResponse(
                decision='block',
                reason=f"Policy evaluation failed: {str(e)}",
                masked_data=None,
                policy_ids=[],
                metadata={'error': str(e), 'fail_safe': True}
            )
            responses.append(error_response)
            
            # Log the error response and trigger alerts
            audit_log_id = create_audit_log(db, request, error_response)
            trigger_alert(db, request, error_response, audit_log_id)
    
    return responses


@router.delete("/check/cache", status_code=status.HTTP_204_NO_CONTENT)
async def clear_evaluation_cache(
    agent_id: str = Depends(get_current_agent),
    db: Session = Depends(get_db)
):
    """
    Clear the policy evaluation cache
    
    This endpoint allows clearing the evaluation cache, which can be useful
    after updating policies to ensure new policies are immediately applied.
    
    Args:
        agent_id: Authenticated agent ID from API key
        db: Database session
        
    Returns:
        No content
    """
    evaluation_service = PolicyEvaluationService(db)
    evaluation_service.clear_cache()
    
    logger.info(f"Policy evaluation cache cleared by agent={agent_id}")
    
    return None
