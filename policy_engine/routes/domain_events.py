"""Domain Events read-only route.

Exposes the domain_events table created by migration 007.
Append-only semantics: GET only — no POST/PUT/DELETE.
Access restricted to compliance_officer role.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import Column, DateTime, JSON, String
from sqlalchemy.orm import Session

from policy_engine.auth.rbac import get_current_user
from policy_engine.database import Base, get_db
from policy_engine.models.user import User, UserRole

router = APIRouter()


# ---------------------------------------------------------------------------
# SQLAlchemy model (mirrors migration 007 schema)
# ---------------------------------------------------------------------------

class DomainEvent(Base):
    """Read-only ORM view of the domain_events table."""
    __tablename__ = "domain_events"

    id = Column(String, primary_key=True, index=True)
    event_type = Column(String, nullable=False, index=True)
    payload = Column(JSON, nullable=True)
    org_id = Column(String, nullable=True, index=True)
    created_at = Column(DateTime, nullable=False)
    processed_at = Column(DateTime, nullable=True)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class DomainEventResponse(BaseModel):
    id: str
    event_type: str
    payload: Optional[Dict[str, Any]] = None
    org_id: Optional[str] = None
    created_at: datetime
    processed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

def _require_compliance_officer(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role != UserRole.COMPLIANCE_OFFICER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only compliance_officer role can access domain events",
        )
    return current_user


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.get(
    "/domain-events",
    response_model=List[DomainEventResponse],
    status_code=status.HTTP_200_OK,
)
def list_domain_events(
    skip: int = 0,
    limit: int = 50,
    event_type: Optional[str] = None,
    agent_id: Optional[str] = None,
    from_timestamp: Optional[datetime] = None,
    to_timestamp: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_compliance_officer),
) -> List[DomainEventResponse]:
    """
    Return paginated domain events. Compliance officer only. Read-only.

    Filters:
    - event_type: exact match (e.g. "policy.evaluated")
    - agent_id: matched against payload->agent_id (JSON field)
    - from_timestamp / to_timestamp: created_at range
    """
    query = db.query(DomainEvent)

    if event_type:
        query = query.filter(DomainEvent.event_type == event_type)
    if from_timestamp:
        query = query.filter(DomainEvent.created_at >= from_timestamp)
    if to_timestamp:
        query = query.filter(DomainEvent.created_at <= to_timestamp)

    events = query.order_by(DomainEvent.created_at.desc()).offset(skip).limit(limit).all()

    # Apply agent_id filter in Python (JSON field; avoids DB-specific JSON operators)
    if agent_id:
        events = [
            e for e in events
            if (e.payload or {}).get("agent_id") == agent_id
        ]

    return [DomainEventResponse.model_validate(e) for e in events]
