"""Shadow AI Discovery routes — /v1/admin/shadow-ai/*"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime, timedelta
import uuid

from policy_engine.database import get_db
from policy_engine.auth.rbac import get_current_user
from policy_engine.models.user import User, has_permission
from policy_engine.models.shadow_ai import ShadowAIDetectionModel, ShadowAIAllowlist
from policy_engine.domain.admin.shadow_ai import detect_ai_provider, assess_phi_risk
from pydantic import BaseModel

router = APIRouter(prefix="/shadow-ai", tags=["admin-shadow-ai"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class DetectionCreate(BaseModel):
    destination_host: str
    destination_port: int = 443
    source_ip: Optional[str] = None
    department: Optional[str] = None
    confidence_score: float = 1.0
    notes: Optional[str] = None


class DetectionReview(BaseModel):
    status: str
    notes: Optional[str] = None


class AllowlistCreate(BaseModel):
    host_pattern: str
    reason: Optional[str] = None
    expires_at: Optional[datetime] = None


class DetectionResponse(BaseModel):
    id: str
    detected_at: datetime
    source_ip: Optional[str]
    destination_host: str
    destination_port: int
    ai_provider: Optional[str]
    confidence_score: float
    department: Optional[str]
    phi_risk_level: str
    status: str
    notes: Optional[str]
    organization_id: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class AllowlistResponse(BaseModel):
    id: str
    host_pattern: str
    reason: Optional[str]
    approved_at: datetime
    expires_at: Optional[datetime]
    organization_id: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_shadow_ai_write(current_user: User) -> None:
    if not has_permission(current_user.role, "shadow_ai", "create"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions for shadow AI management",
        )


def _require_shadow_ai_read(current_user: User) -> None:
    if not has_permission(current_user.role, "shadow_ai", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to read shadow AI data",
        )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/detections", status_code=status.HTTP_201_CREATED)
def create_detection(
    payload: DetectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new shadow AI detection record."""
    _require_shadow_ai_write(current_user)

    ai_provider = detect_ai_provider(payload.destination_host)
    phi_risk = assess_phi_risk(
        payload.destination_host,
        payload.destination_port,
        payload.department or "",
    )

    now = datetime.utcnow()
    detection = ShadowAIDetectionModel(
        id=str(uuid.uuid4()),
        detected_at=now,
        source_ip=payload.source_ip,
        destination_host=payload.destination_host,
        destination_port=payload.destination_port,
        ai_provider=ai_provider,
        confidence_score=payload.confidence_score,
        department=payload.department,
        phi_risk_level=phi_risk,
        status="detected",
        notes=payload.notes,
        organization_id=current_user.organization_id,
        created_at=now,
    )
    db.add(detection)
    db.commit()
    db.refresh(detection)
    return detection


@router.get("/detections", response_model=List[DetectionResponse])
def list_detections(
    status: Optional[str] = Query(None),
    phi_risk_level: Optional[str] = Query(None),
    ai_provider: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List shadow AI detections with optional filters."""
    _require_shadow_ai_read(current_user)

    q = db.query(ShadowAIDetectionModel)
    if status:
        q = q.filter(ShadowAIDetectionModel.status == status)
    if phi_risk_level:
        q = q.filter(ShadowAIDetectionModel.phi_risk_level == phi_risk_level)
    if ai_provider:
        q = q.filter(ShadowAIDetectionModel.ai_provider == ai_provider)
    return q.order_by(ShadowAIDetectionModel.created_at.desc()).all()


@router.get("/detections/{detection_id}", response_model=DetectionResponse)
def get_detection(
    detection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single detection by ID."""
    _require_shadow_ai_read(current_user)

    detection = db.query(ShadowAIDetectionModel).filter(
        ShadowAIDetectionModel.id == detection_id
    ).first()
    if not detection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Detection not found")
    return detection


@router.patch("/detections/{detection_id}/review")
def review_detection(
    detection_id: str,
    payload: DetectionReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update the status/notes of a detection after manual review."""
    if not has_permission(current_user.role, "shadow_ai", "update"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    detection = db.query(ShadowAIDetectionModel).filter(
        ShadowAIDetectionModel.id == detection_id
    ).first()
    if not detection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Detection not found")

    detection.status = payload.status
    if payload.notes is not None:
        detection.notes = payload.notes
    db.commit()
    db.refresh(detection)
    return detection


@router.post("/allowlist", status_code=status.HTTP_201_CREATED)
def add_to_allowlist(
    payload: AllowlistCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a host pattern to the shadow AI allowlist."""
    _require_shadow_ai_write(current_user)

    now = datetime.utcnow()
    entry = ShadowAIAllowlist(
        id=str(uuid.uuid4()),
        host_pattern=payload.host_pattern,
        reason=payload.reason,
        approved_by=current_user.id,
        approved_at=now,
        expires_at=payload.expires_at,
        organization_id=current_user.organization_id,
        created_at=now,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/allowlist", response_model=List[AllowlistResponse])
def list_allowlist(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all allowlist entries."""
    _require_shadow_ai_read(current_user)
    return db.query(ShadowAIAllowlist).order_by(ShadowAIAllowlist.created_at.desc()).all()


@router.delete("/allowlist/{allowlist_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_allowlist_entry(
    allowlist_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove an entry from the allowlist."""
    if not has_permission(current_user.role, "shadow_ai", "delete"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    entry = db.query(ShadowAIAllowlist).filter(ShadowAIAllowlist.id == allowlist_id).first()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Allowlist entry not found")
    db.delete(entry)
    db.commit()


@router.get("/summary")
def get_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a 30-day summary of shadow AI detections."""
    _require_shadow_ai_read(current_user)

    since = datetime.utcnow() - timedelta(days=30)
    detections = db.query(ShadowAIDetectionModel).filter(
        ShadowAIDetectionModel.created_at >= since
    ).all()

    by_provider: dict = {}
    by_phi_risk: dict = {}
    by_status: dict = {}

    for d in detections:
        provider = d.ai_provider or "unknown"
        by_provider[provider] = by_provider.get(provider, 0) + 1

        risk = d.phi_risk_level or "none"
        by_phi_risk[risk] = by_phi_risk.get(risk, 0) + 1

        s = d.status or "detected"
        by_status[s] = by_status.get(s, 0) + 1

    return {
        "period_days": 30,
        "total": len(detections),
        "by_provider": by_provider,
        "by_phi_risk": by_phi_risk,
        "by_status": by_status,
    }
