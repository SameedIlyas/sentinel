"""Agent management endpoints"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
import math

from policy_engine.database import get_db
from policy_engine.auth.rbac import authenticate_request
from policy_engine.models.agent import Agent, AgentStatus
from policy_engine.models.schemas import (
    AgentResponse,
    AgentListResponse,
    AgentUpdate,
    AgentCreate,
    AgentActivityMetrics,
    AgentMetricsResponse
)
from policy_engine.services.agent_activity_service import AgentActivityService

router = APIRouter()


@router.get("", response_model=AgentListResponse)
async def list_agents(
    auth_id: str = Depends(authenticate_request),
    status_filter: Optional[str] = Query(None, description="Filter by status (active/inactive/suspended)"),
    owner_user_id: Optional[str] = Query(None, description="Filter by owner user ID"),
    search: Optional[str] = Query(None, description="Search by agent name or ID"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db)
):
    """
    List all agents with filtering and pagination
    
    This endpoint provides visibility into all registered agents in the system,
    supporting filtering by status, owner, and search terms.
    
    Args:
        agent_id: Authenticated agent ID (for authorization)
        status_filter: Filter by agent status
        owner_user_id: Filter by owner user ID
        search: Search term for agent name or ID
        page: Page number for pagination
        page_size: Number of items per page
        db: Database session
        
    Returns:
        Paginated list of agents
    """
    # Build query
    query = db.query(Agent)
    
    # Apply filters
    if status_filter:
        try:
            status_enum = AgentStatus(status_filter.lower())
            query = query.filter(Agent.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_filter}. Must be one of: active, inactive, suspended"
            )
    
    if owner_user_id:
        query = query.filter(Agent.owner_user_id == owner_user_id)
    
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (Agent.id.ilike(search_pattern)) | 
            (Agent.name.ilike(search_pattern))
        )
    
    # Get total count
    total = query.count()
    
    # Calculate pagination
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    offset = (page - 1) * page_size
    
    # Get paginated results
    agents = query.order_by(Agent.last_active.desc()).offset(offset).limit(page_size).all()
    
    return AgentListResponse(
        agents=agents,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/{agent_id_param}", response_model=AgentResponse)
async def get_agent(
    agent_id_param: str,
    auth_id: str = Depends(authenticate_request),
    db: Session = Depends(get_db)
):
    """
    Get a specific agent by ID
    
    This endpoint retrieves detailed information about a specific agent,
    including its configuration, status, and metadata.
    
    Args:
        agent_id_param: Agent ID to retrieve
        agent_id: Authenticated agent ID (for authorization)
        db: Database session
        
    Returns:
        Agent details
        
    Raises:
        HTTPException: If agent not found
    """
    agent = db.query(Agent).filter(Agent.id == agent_id_param).first()
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with ID '{agent_id_param}' not found"
        )
    
    return agent


@router.put("/{agent_id_param}", response_model=AgentResponse)
async def update_agent(
    agent_id_param: str,
    update_data: AgentUpdate,
    auth_id: str = Depends(authenticate_request),
    db: Session = Depends(get_db)
):
    """
    Update an agent's information
    
    This endpoint allows updating agent metadata, status, and configuration.
    Useful for managing agent lifecycle (activating, suspending, etc.).
    
    Args:
        agent_id_param: Agent ID to update
        update_data: Updated agent data
        agent_id: Authenticated agent ID (for authorization)
        db: Database session
        
    Returns:
        Updated agent details
        
    Raises:
        HTTPException: If agent not found
    """
    agent = db.query(Agent).filter(Agent.id == agent_id_param).first()
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with ID '{agent_id_param}' not found"
        )
    
    # Update fields if provided
    update_dict = update_data.model_dump(exclude_unset=True)
    
    for field, value in update_dict.items():
        setattr(agent, field, value)
    
    db.commit()
    db.refresh(agent)
    
    return agent


@router.get("/{agent_id_param}/metrics", response_model=AgentActivityMetrics)
async def get_agent_metrics(
    agent_id_param: str,
    auth_id: str = Depends(authenticate_request),
    db: Session = Depends(get_db)
):
    """
    Get activity metrics for a specific agent
    
    This endpoint provides detailed activity metrics for an agent, including:
    - Total actions performed
    - Blocked vs allowed actions
    - Systems accessed
    - Activity timeline
    
    Args:
        agent_id_param: Agent ID to get metrics for
        agent_id: Authenticated agent ID (for authorization)
        db: Database session
        
    Returns:
        Agent activity metrics
        
    Raises:
        HTTPException: If agent not found
    """
    metrics = AgentActivityService.get_agent_metrics(db, agent_id_param)
    
    if not metrics:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with ID '{agent_id_param}' not found"
        )
    
    return AgentActivityMetrics(**metrics)


@router.get("/metrics/all", response_model=AgentMetricsResponse)
async def get_all_agent_metrics(
    auth_id: str = Depends(authenticate_request),
    db: Session = Depends(get_db)
):
    """
    Get aggregated metrics for all agents
    
    This endpoint provides a comprehensive view of all agent activity across
    the organization, including status distribution and per-agent metrics.
    
    Args:
        agent_id: Authenticated agent ID (for authorization)
        db: Database session
        
    Returns:
        Aggregated agent metrics
    """
    all_metrics = AgentActivityService.get_all_agent_metrics(db)
    
    # Convert metrics to Pydantic models
    metrics_list = [AgentActivityMetrics(**m) for m in all_metrics['metrics']]
    
    return AgentMetricsResponse(
        metrics=metrics_list,
        total_agents=all_metrics['total_agents'],
        active_agents=all_metrics['active_agents'],
        inactive_agents=all_metrics['inactive_agents'],
        suspended_agents=all_metrics['suspended_agents']
    )
