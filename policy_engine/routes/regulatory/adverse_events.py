"""Adverse Event routes — post-market surveillance reporting."""
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from policy_engine.auth.rbac import get_current_user
from policy_engine.database import get_db
from policy_engine.domain.regulatory.post_market import classify_severity
from policy_engine.models.post_market import (
    AdverseEvent,
    AdverseEventSeverityDB,
    AdverseEventStatusDB,
)
from policy_engine.models.user import has_permission

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class AdverseEventCreate(BaseModel):
    model_id: str
    event_type: str
    severity: str
    description: str
    patient_impact: Optional[str] = None
    agent_id: Optional[str] = None
    reported_by: Optional[str] = None


class AdverseEventClassify(BaseModel):
    patient_harm: bool = False
    system_failure: bool = False
    regulatory_violation: bool = False
    data_breach: bool = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _event_to_dict(ev: AdverseEvent) -> dict:
    return {
        "id": ev.id,
        "model_id": ev.model_id,
        "agent_id": ev.agent_id,
        "event_type": ev.event_type,
        "severity": ev.severity,
        "description": ev.description,
        "patient_impact": ev.patient_impact,
        "reported_by": ev.reported_by,
        "status": ev.status,
        "organization_id": ev.organization_id,
        "reported_at": ev.reported_at.isoformat() if ev.reported_at else None,
        "resolved_at": ev.resolved_at.isoformat() if ev.resolved_at else None,
        "created_at": ev.created_at.isoformat(),
    }


def _get_event_or_404(db: Session, event_id: str, org_id: Optional[str]) -> AdverseEvent:
    ev = db.query(AdverseEvent).filter(
        AdverseEvent.id == event_id,
        AdverseEvent.organization_id == org_id,
    ).first()
    if not ev:
        raise HTTPException(404, "Adverse event not found")
    return ev


# ---------------------------------------------------------------------------
# Routes — specific paths BEFORE /{event_id}
# ---------------------------------------------------------------------------


@router.get("/adverse-events/stats")
def adverse_event_stats(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not has_permission(current_user.role, "post_market", "read"):
        raise HTTPException(403, "Forbidden")

    events = db.query(AdverseEvent).filter(
        AdverseEvent.organization_id == current_user.organization_id
    ).all()

    total = len(events)
    by_severity: dict = {}
    by_status: dict = {}
    for ev in events:
        sev = str(ev.severity)
        by_severity[sev] = by_severity.get(sev, 0) + 1
        status = str(ev.status)
        by_status[status] = by_status.get(status, 0) + 1

    return {
        "total_events": total,
        "by_severity": by_severity,
        "by_status": by_status,
    }


@router.post("/adverse-events", status_code=201)
def create_adverse_event(
    body: AdverseEventCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not has_permission(current_user.role, "post_market", "create"):
        raise HTTPException(403, "Forbidden")

    try:
        severity = AdverseEventSeverityDB(body.severity)
    except ValueError:
        raise HTTPException(400, f"Invalid severity: {body.severity}")

    now = datetime.utcnow()
    ev = AdverseEvent(
        id=str(uuid.uuid4()),
        model_id=body.model_id,
        agent_id=body.agent_id,
        event_type=body.event_type,
        severity=severity,
        description=body.description,
        patient_impact=body.patient_impact,
        reported_by=body.reported_by,
        status=AdverseEventStatusDB.OPEN,
        organization_id=current_user.organization_id,
        reported_at=now,
        created_at=now,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return _event_to_dict(ev)


@router.post("/adverse-events/classify")
def classify_adverse_event(body: AdverseEventClassify):
    """Return suggested severity from boolean flags (no auth — classification helper)."""
    severity = classify_severity(
        body.patient_harm,
        body.system_failure,
        body.regulatory_violation,
        body.data_breach,
    )
    return {"severity": severity.value}


@router.get("/adverse-events")
def list_adverse_events(
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    model_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not has_permission(current_user.role, "post_market", "read"):
        raise HTTPException(403, "Forbidden")

    q = db.query(AdverseEvent).filter(
        AdverseEvent.organization_id == current_user.organization_id
    )
    if severity:
        q = q.filter(AdverseEvent.severity == severity)
    if status:
        q = q.filter(AdverseEvent.status == status)
    if model_id:
        q = q.filter(AdverseEvent.model_id == model_id)

    return [_event_to_dict(ev) for ev in q.order_by(AdverseEvent.created_at.desc()).all()]


@router.get("/adverse-events/{event_id}")
def get_adverse_event(
    event_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not has_permission(current_user.role, "post_market", "read"):
        raise HTTPException(403, "Forbidden")
    return _event_to_dict(_get_event_or_404(db, event_id, current_user.organization_id))


@router.patch("/adverse-events/{event_id}/resolve")
def resolve_adverse_event(
    event_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not has_permission(current_user.role, "post_market", "update"):
        raise HTTPException(403, "Forbidden")

    ev = _get_event_or_404(db, event_id, current_user.organization_id)

    if ev.status == AdverseEventStatusDB.RESOLVED:
        raise HTTPException(409, "Event is already resolved")

    ev.status = AdverseEventStatusDB.RESOLVED
    ev.resolved_at = datetime.utcnow()
    db.commit()
    db.refresh(ev)
    return _event_to_dict(ev)


@router.patch("/adverse-events/{event_id}/investigate")
def investigate_adverse_event(
    event_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not has_permission(current_user.role, "post_market", "update"):
        raise HTTPException(403, "Forbidden")

    ev = _get_event_or_404(db, event_id, current_user.organization_id)

    if ev.status != AdverseEventStatusDB.OPEN:
        raise HTTPException(409, "Can only move OPEN events to INVESTIGATING")

    ev.status = AdverseEventStatusDB.INVESTIGATING
    db.commit()
    db.refresh(ev)
    return _event_to_dict(ev)
