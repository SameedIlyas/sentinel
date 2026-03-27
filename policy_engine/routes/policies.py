"""Policy management endpoints"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
import uuid
from datetime import datetime
import logging

from policy_engine.database import get_db
from policy_engine.auth.rbac import authenticate_request
from policy_engine.models.policy import Policy
from policy_engine.models.schemas import (
    PolicyCreate,
    PolicyUpdate,
    PolicyResponse,
    PolicyListResponse,
    PolicyDeleteResponse,
    PolicyValidationResponse
)
from policy_engine.services.policy_validator import PolicyValidator
from policy_engine.services.policy_evaluation import PolicyEvaluationService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("", response_model=PolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_policy(
    policy: PolicyCreate,
    auth_id: str = Depends(authenticate_request),
    db: Session = Depends(get_db)
):
    """
    Create a new policy
    
    Args:
        policy: Policy data
        agent_id: Authenticated agent ID
        db: Database session
        
    Returns:
        Created policy
        
    Raises:
        HTTPException: If policy validation fails
    """
    # Validate policy
    validator = PolicyValidator(db)
    is_valid, errors = validator.validate_policy(policy)
    
    if not is_valid:
        error_details = [{"field": e.field, "message": e.message} for e in errors]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Policy validation failed",
                "errors": error_details
            }
        )
    
    # Check for conflicts
    conflicts = validator.detect_conflicts(policy)
    if conflicts:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Policy conflicts detected",
                "conflicts": conflicts
            }
        )
    
    # Create policy
    policy_id = f"pol_{uuid.uuid4().hex[:16]}"
    
    db_policy = Policy(
        id=policy_id,
        name=policy.name,
        description=policy.description,
        policy_type=policy.policy_type,
        rules=[rule.model_dump() for rule in policy.rules],
        applies_to=policy.applies_to,
        priority=policy.priority,
        enabled=policy.enabled,
        created_by=auth_id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    db.add(db_policy)
    db.commit()
    db.refresh(db_policy)
    
    # Invalidate cache for affected agents
    _invalidate_policy_cache(db, policy_id)
    
    return db_policy


@router.get("/{policy_id}", response_model=PolicyResponse)
async def get_policy(
    policy_id: str,
    auth_id: str = Depends(authenticate_request),
    db: Session = Depends(get_db)
):
    """
    Retrieve a policy by ID
    
    Args:
        policy_id: Policy ID
        agent_id: Authenticated agent ID
        db: Database session
        
    Returns:
        Policy data
        
    Raises:
        HTTPException: If policy not found
    """
    policy = db.query(Policy).filter(Policy.id == policy_id).first()
    
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy with ID '{policy_id}' not found"
        )
    
    return policy


@router.put("/{policy_id}", response_model=PolicyResponse)
async def update_policy(
    policy_id: str,
    policy_update: PolicyUpdate,
    auth_id: str = Depends(authenticate_request),
    db: Session = Depends(get_db)
):
    """
    Update an existing policy
    
    Args:
        policy_id: Policy ID
        policy_update: Updated policy data
        agent_id: Authenticated agent ID
        db: Database session
        
    Returns:
        Updated policy
        
    Raises:
        HTTPException: If policy not found or validation fails
    """
    # Get existing policy
    db_policy = db.query(Policy).filter(Policy.id == policy_id).first()
    
    if not db_policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy with ID '{policy_id}' not found"
        )
    
    # Validate update
    validator = PolicyValidator(db)
    is_valid, errors = validator.validate_update(policy_id, policy_update)
    
    if not is_valid:
        error_details = [{"field": e.field, "message": e.message} for e in errors]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Policy validation failed",
                "errors": error_details
            }
        )
    
    # Update fields
    update_data = policy_update.model_dump(exclude_unset=True)
    
    # Convert rules to dict if present
    if 'rules' in update_data and update_data['rules']:
        update_data['rules'] = [rule.model_dump() for rule in policy_update.rules]
    
    # Check for conflicts if priority or applies_to changed
    if 'priority' in update_data or 'applies_to' in update_data:
        # Create a temporary policy object for conflict detection
        temp_policy = PolicyCreate(
            name=update_data.get('name', db_policy.name),
            description=update_data.get('description', db_policy.description),
            policy_type=update_data.get('policy_type', db_policy.policy_type),
            rules=policy_update.rules if policy_update.rules else [
                # Convert DB rules back to PolicyRule objects for validation
                # This is a simplified version
            ],
            applies_to=update_data.get('applies_to', db_policy.applies_to),
            priority=update_data.get('priority', db_policy.priority),
            enabled=update_data.get('enabled', db_policy.enabled)
        )
        
        conflicts = validator.detect_conflicts(temp_policy, exclude_policy_id=policy_id)
        if conflicts:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "Policy conflicts detected",
                    "conflicts": conflicts
                }
            )
    
    # Apply updates
    for field, value in update_data.items():
        setattr(db_policy, field, value)
    
    db_policy.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(db_policy)
    
    # Invalidate cache for this policy
    _invalidate_policy_cache(db, policy_id)
    
    return db_policy


@router.delete("/{policy_id}", response_model=PolicyDeleteResponse)
async def delete_policy(
    policy_id: str,
    auth_id: str = Depends(authenticate_request),
    db: Session = Depends(get_db)
):
    """
    Delete a policy
    
    Args:
        policy_id: Policy ID
        agent_id: Authenticated agent ID
        db: Database session
        
    Returns:
        Deletion confirmation
        
    Raises:
        HTTPException: If policy not found
    """
    policy = db.query(Policy).filter(Policy.id == policy_id).first()
    
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy with ID '{policy_id}' not found"
        )
    
    db.delete(policy)
    db.commit()
    
    # Invalidate cache for this policy
    _invalidate_policy_cache(db, policy_id)
    
    return PolicyDeleteResponse(
        success=True,
        message=f"Policy '{policy.name}' deleted successfully",
        policy_id=policy_id
    )


@router.get("", response_model=PolicyListResponse)
async def list_policies(
    auth_id: str = Depends(authenticate_request),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    policy_type: Optional[str] = Query(None, description="Filter by policy type"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    applies_to_agent: Optional[str] = Query(None, description="Filter by agent ID")
):
    """
    List policies with pagination and filtering
    
    Args:
        agent_id: Authenticated agent ID
        db: Database session
        page: Page number (1-indexed)
        page_size: Number of items per page
        policy_type: Optional filter by policy type
        enabled: Optional filter by enabled status
        applies_to_agent: Optional filter by agent ID
        
    Returns:
        Paginated list of policies
    """
    # Build query
    query = db.query(Policy)
    
    # Apply filters
    if policy_type:
        query = query.filter(Policy.policy_type == policy_type)
    
    if enabled is not None:
        query = query.filter(Policy.enabled == enabled)
    
    if applies_to_agent:
        # Filter policies that apply to this specific agent or all agents
        query = query.filter(
            (Policy.applies_to.contains([applies_to_agent])) |
            (Policy.applies_to.contains(["*"]))
        )
    
    # Get total count
    total = query.count()
    
    # Calculate pagination
    total_pages = (total + page_size - 1) // page_size
    offset = (page - 1) * page_size
    
    # Get page of results, ordered by priority (descending) and created_at
    policies = query.order_by(
        Policy.priority.desc(),
        Policy.created_at.desc()
    ).offset(offset).limit(page_size).all()
    
    return PolicyListResponse(
        policies=policies,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


def _invalidate_policy_cache(db: Session, policy_id: str) -> None:
    """
    Invalidate cache for a policy
    
    Args:
        db: Database session
        policy_id: Policy ID
    """
    try:
        # Create a temporary evaluation service to access cache
        eval_service = PolicyEvaluationService(db)
        invalidated = eval_service.invalidate_cache(policy_id=policy_id)
        logger.info(f"Invalidated {invalidated} cache entries for policy: {policy_id}")
    except Exception as e:
        logger.error(f"Failed to invalidate cache for policy {policy_id}: {e}")
        # Don't fail the request if cache invalidation fails
