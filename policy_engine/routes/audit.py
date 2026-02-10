"""Audit log endpoints"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from typing import Optional, Literal
from datetime import datetime
import uuid
import csv
import io
import json

from policy_engine.database import get_db
from policy_engine.auth.api_key import get_current_agent
from policy_engine.models.audit_log import AuditLog, Decision
from policy_engine.models.schemas import (
    AuditLogCreate,
    AuditLogResponse,
    AuditLogListResponse,
    AuditLogSearchRequest
)
from policy_engine.services.audit_retention import retention_service

router = APIRouter()


@router.post("/log", response_model=AuditLogResponse, status_code=status.HTTP_201_CREATED)
async def create_audit_log(
    log_data: AuditLogCreate,
    agent_id: str = Depends(get_current_agent),
    db: Session = Depends(get_db)
):
    """
    Create an audit log entry
    
    This endpoint records every action taken by an AI agent. Audit logs are
    immutable once created and must be retained for compliance purposes.
    
    Args:
        log_data: Audit log data
        agent_id: Authenticated agent ID
        db: Database session
        
    Returns:
        Created audit log entry
        
    Raises:
        HTTPException: If creation fails
    """
    # Ensure the agent_id in request matches authenticated agent
    if log_data.agent_id != agent_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Agent ID in request ({log_data.agent_id}) does not match authenticated agent ({agent_id})"
        )
    
    # Generate unique ID
    log_id = f"audit_{uuid.uuid4().hex[:16]}"
    
    # Map decision string to enum
    decision_map = {
        'allowed': Decision.ALLOWED,
        'blocked': Decision.BLOCKED,
        'approved': Decision.APPROVED
    }
    decision_enum = decision_map.get(log_data.decision.lower(), Decision.ALLOWED)
    
    # Create audit log entry
    audit_log = AuditLog(
        id=log_id,
        timestamp=datetime.utcnow(),
        agent_id=log_data.agent_id,
        agent_name=log_data.agent_name,
        user_id=log_data.user_id,
        tool_name=log_data.tool_name,
        arguments=log_data.arguments,
        system_accessed=log_data.system_accessed,
        data_touched=log_data.data_touched,
        decision=decision_enum,
        policy_ids=log_data.policy_ids,
        reason=log_data.reason,
        metadata=log_data.metadata or {}
    )
    
    db.add(audit_log)
    db.commit()
    db.refresh(audit_log)
    
    return audit_log


@router.get("/logs", response_model=AuditLogListResponse)
async def get_audit_logs(
    agent_id: str = Depends(get_current_agent),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    filter_agent_id: Optional[str] = Query(None, description="Filter by agent ID"),
    filter_user_id: Optional[str] = Query(None, description="Filter by user ID"),
    filter_tool_name: Optional[str] = Query(None, description="Filter by tool name"),
    filter_system: Optional[str] = Query(None, description="Filter by system accessed"),
    filter_decision: Optional[str] = Query(None, description="Filter by decision"),
    start_date: Optional[str] = Query(None, description="Filter from date (ISO 8601)"),
    end_date: Optional[str] = Query(None, description="Filter until date (ISO 8601)"),
    search: Optional[str] = Query(None, description="Search across all fields")
):
    """
    Query audit logs with filtering and pagination
    
    This endpoint allows searching and filtering audit logs for compliance
    and investigation purposes.
    
    Args:
        agent_id: Authenticated agent ID
        db: Database session
        page: Page number
        page_size: Items per page
        filter_agent_id: Filter by agent ID
        filter_user_id: Filter by user ID
        filter_tool_name: Filter by tool name
        filter_system: Filter by system accessed
        filter_decision: Filter by decision
        start_date: Filter from date
        end_date: Filter until date
        search: Search query across all fields
        
    Returns:
        Paginated list of audit logs
    """
    # Build query
    query = db.query(AuditLog)
    
    # Apply filters
    if filter_agent_id:
        query = query.filter(AuditLog.agent_id == filter_agent_id)
    
    if filter_user_id:
        query = query.filter(AuditLog.user_id == filter_user_id)
    
    if filter_tool_name:
        query = query.filter(AuditLog.tool_name == filter_tool_name)
    
    if filter_system:
        query = query.filter(AuditLog.system_accessed == filter_system)
    
    if filter_decision:
        decision_map = {
            'allowed': Decision.ALLOWED,
            'blocked': Decision.BLOCKED,
            'approved': Decision.APPROVED
        }
        decision_enum = decision_map.get(filter_decision.lower())
        if decision_enum:
            query = query.filter(AuditLog.decision == decision_enum)
    
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            query = query.filter(AuditLog.timestamp >= start_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid start_date format. Use ISO 8601 format."
            )
    
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            query = query.filter(AuditLog.timestamp <= end_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid end_date format. Use ISO 8601 format."
            )
    
    # Search functionality across multiple fields
    if search:
        search_filter = or_(
            AuditLog.agent_id.ilike(f"%{search}%"),
            AuditLog.agent_name.ilike(f"%{search}%"),
            AuditLog.user_id.ilike(f"%{search}%"),
            AuditLog.tool_name.ilike(f"%{search}%"),
            AuditLog.system_accessed.ilike(f"%{search}%"),
            AuditLog.reason.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)
    
    # Get total count
    total = query.count()
    
    # Calculate pagination
    total_pages = (total + page_size - 1) // page_size
    offset = (page - 1) * page_size
    
    # Get page of results, ordered by timestamp descending (newest first)
    logs = query.order_by(AuditLog.timestamp.desc()).offset(offset).limit(page_size).all()
    
    return AuditLogListResponse(
        logs=logs,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/logs/export")
async def export_audit_logs(
    format: Literal["json", "csv"] = Query("json", description="Export format"),
    agent_id: str = Depends(get_current_agent),
    db: Session = Depends(get_db),
    filter_agent_id: Optional[str] = Query(None, description="Filter by agent ID"),
    filter_user_id: Optional[str] = Query(None, description="Filter by user ID"),
    filter_tool_name: Optional[str] = Query(None, description="Filter by tool name"),
    filter_system: Optional[str] = Query(None, description="Filter by system accessed"),
    filter_decision: Optional[str] = Query(None, description="Filter by decision"),
    start_date: Optional[str] = Query(None, description="Filter from date (ISO 8601)"),
    end_date: Optional[str] = Query(None, description="Filter until date (ISO 8601)"),
    limit: int = Query(10000, ge=1, le=100000, description="Maximum number of records")
):
    """
    Export audit logs in JSON or CSV format
    
    This endpoint allows exporting audit logs for compliance reporting
    and offline analysis.
    
    Args:
        format: Export format (json or csv)
        agent_id: Authenticated agent ID
        db: Database session
        filter_agent_id: Filter by agent ID
        filter_user_id: Filter by user ID
        filter_tool_name: Filter by tool name
        filter_system: Filter by system accessed
        filter_decision: Filter by decision
        start_date: Filter from date
        end_date: Filter until date
        limit: Maximum records to export
        
    Returns:
        File download response
    """
    # Build query (same filters as get_audit_logs)
    query = db.query(AuditLog)
    
    if filter_agent_id:
        query = query.filter(AuditLog.agent_id == filter_agent_id)
    
    if filter_user_id:
        query = query.filter(AuditLog.user_id == filter_user_id)
    
    if filter_tool_name:
        query = query.filter(AuditLog.tool_name == filter_tool_name)
    
    if filter_system:
        query = query.filter(AuditLog.system_accessed == filter_system)
    
    if filter_decision:
        decision_map = {
            'allowed': Decision.ALLOWED,
            'blocked': Decision.BLOCKED,
            'approved': Decision.APPROVED
        }
        decision_enum = decision_map.get(filter_decision.lower())
        if decision_enum:
            query = query.filter(AuditLog.decision == decision_enum)
    
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            query = query.filter(AuditLog.timestamp >= start_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid start_date format"
            )
    
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            query = query.filter(AuditLog.timestamp <= end_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid end_date format"
            )
    
    # Get logs (limited and ordered)
    logs = query.order_by(AuditLog.timestamp.desc()).limit(limit).all()
    
    # Export based on format
    if format == "json":
        # Convert to JSON
        logs_data = []
        for log in logs:
            logs_data.append({
                "id": log.id,
                "timestamp": log.timestamp.isoformat(),
                "agent_id": log.agent_id,
                "agent_name": log.agent_name,
                "user_id": log.user_id,
                "tool_name": log.tool_name,
                "arguments": log.arguments,
                "system_accessed": log.system_accessed,
                "data_touched": log.data_touched,
                "decision": log.decision.value,
                "policy_ids": log.policy_ids,
                "reason": log.reason,
                "metadata": log.metadata
            })
        
        json_str = json.dumps(logs_data, indent=2)
        
        return Response(
            content=json_str,
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=audit_logs_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
            }
        )
    
    else:  # CSV format
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            "id",
            "timestamp",
            "agent_id",
            "agent_name",
            "user_id",
            "tool_name",
            "system_accessed",
            "decision",
            "reason",
            "policy_ids",
            "data_touched"
        ])
        
        # Write data rows
        for log in logs:
            writer.writerow([
                log.id,
                log.timestamp.isoformat(),
                log.agent_id,
                log.agent_name,
                log.user_id,
                log.tool_name,
                log.system_accessed,
                log.decision.value,
                log.reason,
                json.dumps(log.policy_ids),
                json.dumps(log.data_touched)
            ])
        
        csv_content = output.getvalue()
        
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=audit_logs_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
            }
        )


@router.get("/logs/{log_id}", response_model=AuditLogResponse)
async def get_audit_log(
    log_id: str,
    agent_id: str = Depends(get_current_agent),
    db: Session = Depends(get_db)
):
    """
    Get a specific audit log entry by ID
    
    Args:
        log_id: Audit log ID
        agent_id: Authenticated agent ID
        db: Database session
        
    Returns:
        Audit log entry
        
    Raises:
        HTTPException: If log not found
    """
    log = db.query(AuditLog).filter(AuditLog.id == log_id).first()
    
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit log with ID '{log_id}' not found"
        )
    
    return log


@router.get("/logs/retention/stats", response_model=dict)
async def get_retention_stats(
    agent_id: str = Depends(get_current_agent),
    db: Session = Depends(get_db)
):
    """
    Get audit log retention statistics.
    
    Returns retention policy statistics including:
    - total_logs: Total number of audit logs
    - logs_for_archival: Number of logs older than 365 days
    - oldest_log_age_days: Age of oldest log in days
    - newest_log_age_days: Age of newest log in days
    
    Args:
        agent_id: Authenticated agent ID
        db: Database session
        
    Returns:
        Retention statistics dictionary
    """
    stats = retention_service.get_retention_stats(db)
    return stats
