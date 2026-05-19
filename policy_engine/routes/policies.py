"""Policy management endpoints.

Tenancy: every list/get/update/delete path is scoped to the caller's
``organization_id``. SYSTEM_ADMIN bypasses the scope so platform
operators can still triage cross-tenant. Cross-tenant access returns
404, never 403, to avoid leaking the existence of other-tenant rows
(CRIT-001).

POST writes ``organization_id = auth.organization_id`` and never trusts
a client-supplied value.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.orm.query import Query as SAQuery
from typing import Optional
import uuid
from datetime import datetime

from policy_engine.database import get_db
from policy_engine.auth.rbac import (
    authenticate_request_context,
    AuthContext,
)
from policy_engine.models.policy import Policy
from policy_engine.models.user import UserRole
from policy_engine.models.schemas import (
    PolicyCreate,
    PolicyUpdate,
    PolicyResponse,
    PolicyListResponse,
    PolicyDeleteResponse,
)
from policy_engine.services.policy_validator import PolicyValidator

router = APIRouter()


def _is_system_admin(auth: AuthContext) -> bool:
    return auth.is_user and auth.role == UserRole.SYSTEM_ADMIN


def _scope_to_tenant(query: SAQuery, auth: AuthContext) -> SAQuery:
    if _is_system_admin(auth):
        return query
    return query.filter(Policy.organization_id == auth.organization_id)


@router.post("", response_model=PolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_policy(
    policy: PolicyCreate,
    auth: AuthContext = Depends(authenticate_request_context),
    db: Session = Depends(get_db),
):
    """Create a policy owned by the caller's organization."""
    validator = PolicyValidator(db)
    is_valid, errors = validator.validate_policy(policy)
    if not is_valid:
        error_details = [{"field": e.field, "message": e.message} for e in errors]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Policy validation failed",
                "errors": error_details,
            },
        )

    conflicts = validator.detect_conflicts(policy)
    if conflicts:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Policy conflicts detected",
                "conflicts": conflicts,
            },
        )

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
        created_by=auth.identity,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        # Force tenancy from the auth context. Never trust a client value.
        organization_id=auth.organization_id,
    )

    db.add(db_policy)
    db.commit()
    db.refresh(db_policy)

    return db_policy


@router.get("/{policy_id}", response_model=PolicyResponse)
async def get_policy(
    policy_id: str,
    auth: AuthContext = Depends(authenticate_request_context),
    db: Session = Depends(get_db),
):
    """Retrieve a policy by ID, scoped to the caller's organization."""
    policy = _scope_to_tenant(
        db.query(Policy).filter(Policy.id == policy_id), auth
    ).first()

    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy with ID '{policy_id}' not found",
        )

    return policy


@router.put("/{policy_id}", response_model=PolicyResponse)
async def update_policy(
    policy_id: str,
    policy_update: PolicyUpdate,
    auth: AuthContext = Depends(authenticate_request_context),
    db: Session = Depends(get_db),
):
    """Update a policy. Cross-tenant updates return 404."""
    db_policy = _scope_to_tenant(
        db.query(Policy).filter(Policy.id == policy_id), auth
    ).first()

    if not db_policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy with ID '{policy_id}' not found",
        )

    validator = PolicyValidator(db)
    is_valid, errors = validator.validate_update(policy_id, policy_update)
    if not is_valid:
        error_details = [{"field": e.field, "message": e.message} for e in errors]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Policy validation failed",
                "errors": error_details,
            },
        )

    update_data = policy_update.model_dump(exclude_unset=True)
    # Defensive: never let a payload override organization_id.
    update_data.pop("organization_id", None)

    if "rules" in update_data and update_data["rules"]:
        update_data["rules"] = [rule.model_dump() for rule in policy_update.rules]

    if "priority" in update_data or "applies_to" in update_data:
        temp_policy = PolicyCreate(
            name=update_data.get("name", db_policy.name),
            description=update_data.get("description", db_policy.description),
            policy_type=update_data.get("policy_type", db_policy.policy_type),
            rules=policy_update.rules if policy_update.rules else [],
            applies_to=update_data.get("applies_to", db_policy.applies_to),
            priority=update_data.get("priority", db_policy.priority),
            enabled=update_data.get("enabled", db_policy.enabled),
        )

        conflicts = validator.detect_conflicts(
            temp_policy, exclude_policy_id=policy_id
        )
        if conflicts:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "Policy conflicts detected",
                    "conflicts": conflicts,
                },
            )

    for field, value in update_data.items():
        setattr(db_policy, field, value)

    db_policy.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(db_policy)

    return db_policy


@router.delete("/{policy_id}", response_model=PolicyDeleteResponse)
async def delete_policy(
    policy_id: str,
    auth: AuthContext = Depends(authenticate_request_context),
    db: Session = Depends(get_db),
):
    """Delete a policy. Cross-tenant deletes return 404."""
    policy = _scope_to_tenant(
        db.query(Policy).filter(Policy.id == policy_id), auth
    ).first()

    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy with ID '{policy_id}' not found",
        )

    db.delete(policy)
    db.commit()

    return PolicyDeleteResponse(
        success=True,
        message=f"Policy '{policy.name}' deleted successfully",
        policy_id=policy_id,
    )


@router.get("", response_model=PolicyListResponse)
async def list_policies(
    auth: AuthContext = Depends(authenticate_request_context),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    policy_type: Optional[str] = Query(None, description="Filter by policy type"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    applies_to_agent: Optional[str] = Query(None, description="Filter by agent ID"),
):
    """List policies scoped to the caller's organization."""
    query = _scope_to_tenant(db.query(Policy), auth)

    if policy_type:
        query = query.filter(Policy.policy_type == policy_type)

    if enabled is not None:
        query = query.filter(Policy.enabled == enabled)

    if applies_to_agent:
        query = query.filter(
            (Policy.applies_to.contains([applies_to_agent]))
            | (Policy.applies_to.contains(["*"]))
        )

    total = query.count()
    total_pages = (total + page_size - 1) // page_size
    offset = (page - 1) * page_size

    policies = (
        query.order_by(Policy.priority.desc(), Policy.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    return PolicyListResponse(
        policies=policies,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
