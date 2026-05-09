"""Shadow AI Discovery routes — /v1/admin/shadow-ai/*"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Any, List, Optional
from datetime import datetime, timedelta
import uuid

from policy_engine.database import get_db
from policy_engine.auth.api_key import get_current_agent
from policy_engine.auth.rbac import get_current_user
from policy_engine.models.user import User, has_permission
from policy_engine.models.shadow_ai import ShadowAIDetectionModel, ShadowAIAllowlist
from policy_engine.domain.admin.shadow_ai import detect_ai_provider, assess_phi_risk
from policy_engine.services.shadow_ai_ingest import (
    FlowRecord,
    VENDOR_PARSERS,
    ingest_flow_records,
    ingest_vendor_payload,
)
from pydantic import BaseModel, Field

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


class IngestFlowRecord(BaseModel):
    """One canonical flow record. Use this when posting from a custom collector."""
    destination_host: str = Field(..., min_length=1, max_length=255)
    destination_port: int = Field(443, ge=1, le=65535)
    source_ip: Optional[str] = Field(None, max_length=64)
    bytes_transferred: int = Field(0, ge=0)
    method: Optional[str] = Field(None, max_length=10)
    user_agent: Optional[str] = Field(None, max_length=512)
    department: Optional[str] = Field(None, max_length=128)
    timestamp: Optional[datetime] = None


class IngestRequest(BaseModel):
    """Canonical batch ingest payload — vendor-agnostic flow records."""
    records: List[IngestFlowRecord] = Field(..., min_length=1, max_length=5000)


class VendorIngestRequest(BaseModel):
    """Pass-through ingest for vendor-specific payloads (Cloudflare, Zscaler, ...)."""
    vendor: str = Field(..., description="One of: cloudflare, zscaler, netskope, aws_vpc")
    payload: Any = Field(..., description="Raw vendor payload (list/dict/string)")


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


@router.post("/ingest", status_code=status.HTTP_202_ACCEPTED)
def ingest_canonical_records(
    payload: IngestRequest,
    db: Session = Depends(get_db),
    agent_id: str = Depends(get_current_agent),
):
    """Tier 3 — accept a batch of canonical flow records from any collector.

    Authenticated via SDK API key. Use vendor-specific endpoints below for
    raw Cloudflare / Zscaler / VPC payloads instead of normalising client-side.
    """
    records = [
        FlowRecord(
            destination_host=r.destination_host,
            destination_port=r.destination_port,
            source_ip=r.source_ip,
            bytes_transferred=r.bytes_transferred,
            method=r.method,
            user_agent=r.user_agent,
            department=r.department,
            timestamp=r.timestamp,
        )
        for r in payload.records
    ]
    outcome = ingest_flow_records(db, records, organization_id=None)
    return {
        "received": outcome.received,
        "classified_as_ai": outcome.classified_as_ai,
        "detections_created": outcome.detections_created,
        "detections_deduped": outcome.detections_deduped,
        "allowlisted": outcome.allowlisted,
        "errors": outcome.errors,
        "agent_id": agent_id,
    }


@router.post("/ingest/vendor", status_code=status.HTTP_202_ACCEPTED)
def ingest_vendor_records(
    payload: VendorIngestRequest,
    db: Session = Depends(get_db),
    agent_id: str = Depends(get_current_agent),
):
    """Tier 3 — accept raw payloads from supported vendors and parse server-side.

    Supported vendors: cloudflare (Logpush JSON-lines), zscaler / netskope
    (SIEM flat JSON), aws_vpc (VPC Flow Logs v2 lines).
    """
    if payload.vendor.lower() not in VENDOR_PARSERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "unsupported_vendor",
                "supported": sorted(VENDOR_PARSERS.keys()),
            },
        )
    outcome = ingest_vendor_payload(
        db, vendor=payload.vendor, payload=payload.payload, organization_id=None,
    )
    return {
        "vendor": payload.vendor,
        "received": outcome.received,
        "classified_as_ai": outcome.classified_as_ai,
        "detections_created": outcome.detections_created,
        "detections_deduped": outcome.detections_deduped,
        "allowlisted": outcome.allowlisted,
        "errors": outcome.errors,
        "agent_id": agent_id,
    }


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
