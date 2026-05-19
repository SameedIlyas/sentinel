"""Agent management endpoints.

Tenancy: every list/get/update path is scoped to the caller's
``organization_id``. SYSTEM_ADMIN bypasses the scope so platform
operators can still triage cross-tenant. Cross-tenant access returns 404,
never 403, to avoid leaking the existence of other-tenant rows
(CRIT-001).
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.orm.query import Query as SAQuery
from typing import Optional
import math

from policy_engine.database import get_db
from policy_engine.auth.rbac import (
    authenticate_request_context,
    AuthContext,
)
from policy_engine.models.agent import Agent, AgentStatus
from policy_engine.models.user import UserRole
from policy_engine.models.schemas import (
    AgentResponse,
    AgentListResponse,
    AgentUpdate,
    AgentActivityMetrics,
    AgentMetricsResponse,
)
from policy_engine.services.agent_activity_service import AgentActivityService

router = APIRouter()


def _is_system_admin(auth: AuthContext) -> bool:
    return auth.is_user and auth.role == UserRole.SYSTEM_ADMIN


def _scope_to_tenant(query: SAQuery, auth: AuthContext) -> SAQuery:
    """Restrict ``query`` to the caller's org unless they are SYSTEM_ADMIN."""
    if _is_system_admin(auth):
        return query
    return query.filter(Agent.organization_id == auth.organization_id)


@router.get("", response_model=AgentListResponse)
async def list_agents(
    auth: AuthContext = Depends(authenticate_request_context),
    status_filter: Optional[str] = Query(None, description="Filter by status (active/inactive/suspended)"),
    owner_user_id: Optional[str] = Query(None, description="Filter by owner user ID"),
    search: Optional[str] = Query(None, description="Search by agent name or ID"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
):
    """List agents scoped to the caller's organization."""
    query = _scope_to_tenant(db.query(Agent), auth)

    if status_filter:
        try:
            status_enum = AgentStatus(status_filter.lower())
            query = query.filter(Agent.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_filter}. Must be one of: active, inactive, suspended",
            )

    if owner_user_id:
        query = query.filter(Agent.owner_user_id == owner_user_id)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (Agent.id.ilike(search_pattern))
            | (Agent.name.ilike(search_pattern))
        )

    total = query.count()
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    offset = (page - 1) * page_size

    agents = (
        query.order_by(Agent.last_active.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    return AgentListResponse(
        agents=agents,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/metrics/all", response_model=AgentMetricsResponse)
async def get_all_agent_metrics(
    auth: AuthContext = Depends(authenticate_request_context),
    db: Session = Depends(get_db),
):
    """Aggregated metrics for the caller's organisation (or all orgs if
    SYSTEM_ADMIN)."""
    org_id = None if _is_system_admin(auth) else auth.organization_id
    all_metrics = AgentActivityService.get_all_agent_metrics(
        db, organization_id=org_id
    )

    metrics_list = [AgentActivityMetrics(**m) for m in all_metrics["metrics"]]

    return AgentMetricsResponse(
        metrics=metrics_list,
        total_agents=all_metrics["total_agents"],
        active_agents=all_metrics["active_agents"],
        inactive_agents=all_metrics["inactive_agents"],
        suspended_agents=all_metrics["suspended_agents"],
    )


@router.get("/{agent_id_param}", response_model=AgentResponse)
async def get_agent(
    agent_id_param: str,
    auth: AuthContext = Depends(authenticate_request_context),
    db: Session = Depends(get_db),
):
    """Get an agent by ID, scoped to the caller's organization."""
    agent = _scope_to_tenant(
        db.query(Agent).filter(Agent.id == agent_id_param), auth
    ).first()

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with ID '{agent_id_param}' not found",
        )

    return agent


@router.put("/{agent_id_param}", response_model=AgentResponse)
async def update_agent(
    agent_id_param: str,
    update_data: AgentUpdate,
    auth: AuthContext = Depends(authenticate_request_context),
    db: Session = Depends(get_db),
):
    """Update an agent. Cross-tenant updates 404 — never 403 — to avoid
    leaking the existence of other-tenant rows."""
    agent = _scope_to_tenant(
        db.query(Agent).filter(Agent.id == agent_id_param), auth
    ).first()

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with ID '{agent_id_param}' not found",
        )

    update_dict = update_data.model_dump(exclude_unset=True)
    # Defensive: never let a payload override organization_id.
    update_dict.pop("organization_id", None)

    for field, value in update_dict.items():
        setattr(agent, field, value)

    db.commit()
    db.refresh(agent)

    return agent


@router.get("/{agent_id_param}/metrics", response_model=AgentActivityMetrics)
async def get_agent_metrics(
    agent_id_param: str,
    auth: AuthContext = Depends(authenticate_request_context),
    db: Session = Depends(get_db),
):
    """Per-agent metrics, scoped to the caller's organization."""
    # First verify the agent exists in the caller's scope. Without this,
    # a cross-tenant caller could probe metrics existence.
    agent = _scope_to_tenant(
        db.query(Agent).filter(Agent.id == agent_id_param), auth
    ).first()
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with ID '{agent_id_param}' not found",
        )

    metrics = AgentActivityService.get_agent_metrics(db, agent_id_param)
    if not metrics:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with ID '{agent_id_param}' not found",
        )

    return AgentActivityMetrics(**metrics)
