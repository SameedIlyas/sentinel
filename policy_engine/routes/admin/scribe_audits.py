"""Ambient Scribe Audit routes — /v1/admin/scribe-audits/*"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Any, Dict, List, Optional
from datetime import datetime
import uuid

from policy_engine.database import get_db
from policy_engine.auth.api_key import get_current_agent
from policy_engine.auth.rbac import get_current_user
from policy_engine.models.user import User, has_permission
from policy_engine.models.scribe_audit import ScribeAuditModel, ScribeAuditFinding as ScribeAuditFindingModel
from policy_engine.domain.admin.scribe_auditor import ScribeAuditEngine, content_hash
from policy_engine.services.scribe_ingest import (
    VENDOR_ADAPTERS,
    ScribeIngestRecord,
    ingest_scribe_record,
    ingest_vendor_payload,
)
from pydantic import BaseModel, Field

router = APIRouter(prefix="/scribe-audits", tags=["admin-scribe-audits"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ScribeAuditCreate(BaseModel):
    session_id: str
    note_text: str
    source_data: Optional[dict] = None
    patient_context: Optional[str] = None
    ai_model_used: Optional[str] = None


class FindingResponse(BaseModel):
    id: str
    audit_id: str
    finding_type: str
    severity: str
    description: str
    suggested_correction: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ScribeAuditResponse(BaseModel):
    id: str
    session_id: str
    audit_score: float
    hallucination_detected: bool
    completeness_score: float
    attribution_score: float
    status: str
    ai_model_used: Optional[str]
    organization_id: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class ScribeAuditDetailResponse(ScribeAuditResponse):
    findings: List[FindingResponse] = []


class ScribeIngestPayload(BaseModel):
    """Tier 3 — canonical scribe ingest body. Use when posting raw transcript+
    note pairs from a custom collector or design-partner pilot."""
    session_id: str = Field(..., min_length=1, max_length=128)
    transcript: str = Field(..., min_length=1, max_length=200_000)
    generated_note: str = Field(..., min_length=1, max_length=200_000)
    ai_model_used: Optional[str] = Field(None, max_length=128)
    clinician_id: Optional[str] = Field(None, max_length=128)
    encounter_id: Optional[str] = Field(None, max_length=128)


class ScribeVendorIngestPayload(BaseModel):
    """Tier 3 — vendor webhook pass-through. Translates vendor payloads
    server-side via the right adapter."""
    vendor: str = Field(..., description="One of: mock, abridge, nabla, deepscribe")
    payload: Dict[str, Any]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_write(current_user: User) -> None:
    if not has_permission(current_user.role, "scribe_audits", "create"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions for scribe audit management",
        )


def _require_read(current_user: User) -> None:
    if not has_permission(current_user.role, "scribe_audits", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to read scribe audits",
        )


# ---------------------------------------------------------------------------
# Routes — IMPORTANT: /stats must come BEFORE /{audit_id}
# ---------------------------------------------------------------------------

@router.post("", status_code=status.HTTP_201_CREATED)
def create_scribe_audit(
    payload: ScribeAuditCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run a scribe audit and persist results. Raw note text is never stored."""
    _require_write(current_user)

    engine = ScribeAuditEngine()
    result = engine.run_audit(
        session_id=payload.session_id,
        note_text=payload.note_text,
        source_data=payload.source_data or {},
    )

    now = datetime.utcnow()
    audit = ScribeAuditModel(
        id=str(uuid.uuid4()),
        session_id=payload.session_id,
        patient_context_hash=content_hash(payload.patient_context) if payload.patient_context else None,
        ai_model_used=payload.ai_model_used,
        generated_note_hash=content_hash(payload.note_text),
        audit_score=result.audit_score,
        hallucination_detected=result.hallucination_detected,
        completeness_score=result.completeness_score,
        attribution_score=result.attribution_score,
        status="pending",
        organization_id=current_user.organization_id,
        audited_by=current_user.id,
        created_at=now,
    )
    db.add(audit)
    db.flush()  # get audit.id before adding findings

    findings = []
    for f in result.findings:
        finding_row = ScribeAuditFindingModel(
            id=str(uuid.uuid4()),
            audit_id=audit.id,
            finding_type=f.finding_type,
            severity=f.severity,
            description=f.description,
            suggested_correction=f.suggested_correction,
            created_at=now,
        )
        db.add(finding_row)
        findings.append(finding_row)

    db.commit()
    db.refresh(audit)

    return {
        "id": audit.id,
        "session_id": audit.session_id,
        "audit_score": audit.audit_score,
        "hallucination_detected": audit.hallucination_detected,
        "completeness_score": audit.completeness_score,
        "attribution_score": audit.attribution_score,
        "status": audit.status,
        "ai_model_used": audit.ai_model_used,
        "organization_id": audit.organization_id,
        "created_at": audit.created_at,
        "completed_at": audit.completed_at,
        "findings": [
            {
                "id": f.id,
                "audit_id": f.audit_id,
                "finding_type": f.finding_type,
                "severity": f.severity,
                "description": f.description,
                "suggested_correction": f.suggested_correction,
                "created_at": f.created_at,
            }
            for f in findings
        ],
    }


@router.post("/ingest", status_code=status.HTTP_202_ACCEPTED)
def ingest_canonical_payload(
    payload: ScribeIngestPayload,
    db: Session = Depends(get_db),
    agent_id: str = Depends(get_current_agent),
):
    """Tier 3 — vendor-agnostic scribe-audit ingest endpoint.

    Used by design-partner pilots that hand-feed a `(transcript, generated_note)`
    JSON payload, and by the per-vendor adapters' fallback path. The
    server runs `audit_note()` (LLM-backed when ANTHROPIC_API_KEY is
    present, deterministic otherwise) and persists the audit + findings.
    """
    record = ScribeIngestRecord(
        session_id=payload.session_id,
        transcript=payload.transcript,
        generated_note=payload.generated_note,
        ai_model_used=payload.ai_model_used,
        clinician_id=payload.clinician_id,
        vendor="mock",
        encounter_id=payload.encounter_id,
    )
    outcome = ingest_scribe_record(db, record)
    return {
        "audit_id": outcome.audit_id,
        "audit_score": outcome.audit_score,
        "hallucination_detected": outcome.hallucination_detected,
        "findings_count": outcome.findings_count,
        "deduplicated": outcome.deduplicated,
        "method": outcome.method,
        "elapsed_ms": outcome.elapsed_ms,
        "agent_id": agent_id,
    }


@router.post("/ingest/vendor", status_code=status.HTTP_202_ACCEPTED)
def ingest_vendor_endpoint(
    payload: ScribeVendorIngestPayload,
    db: Session = Depends(get_db),
    agent_id: str = Depends(get_current_agent),
):
    """Tier 3 — accept raw scribe-vendor webhook payloads.

    Supported vendors: mock, abridge, nabla, deepscribe. The vendor adapter
    translates the payload to the canonical shape; everything downstream is
    one code path.
    """
    if payload.vendor.lower() not in VENDOR_ADAPTERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "unsupported_vendor",
                "supported": sorted(VENDOR_ADAPTERS.keys()),
            },
        )
    try:
        outcome = ingest_vendor_payload(
            db, vendor=payload.vendor, payload=payload.payload,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "invalid_payload", "message": str(exc)},
        ) from exc
    return {
        "vendor": payload.vendor,
        "audit_id": outcome.audit_id,
        "audit_score": outcome.audit_score,
        "hallucination_detected": outcome.hallucination_detected,
        "findings_count": outcome.findings_count,
        "deduplicated": outcome.deduplicated,
        "method": outcome.method,
        "elapsed_ms": outcome.elapsed_ms,
        "agent_id": agent_id,
    }


@router.get("/stats")
def get_scribe_audit_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get aggregate statistics for scribe audits."""
    _require_read(current_user)

    total = db.query(func.count(ScribeAuditModel.id)).scalar() or 0
    avg_score = db.query(func.avg(ScribeAuditModel.audit_score)).scalar() or 0.0
    hallucination_count = (
        db.query(func.count(ScribeAuditModel.id))
        .filter(ScribeAuditModel.hallucination_detected == True)  # noqa: E712
        .scalar()
        or 0
    )
    hallucination_rate = (hallucination_count / total * 100) if total > 0 else 0.0

    return {
        "total_audits": total,
        "avg_audit_score": round(float(avg_score), 2),
        "hallucination_count": hallucination_count,
        "hallucination_rate": round(hallucination_rate, 2),
    }


@router.get("", response_model=List[ScribeAuditResponse])
def list_scribe_audits(
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List scribe audits with optional filter by status."""
    _require_read(current_user)

    q = db.query(ScribeAuditModel)
    if status:
        q = q.filter(ScribeAuditModel.status == status)
    return q.order_by(ScribeAuditModel.created_at.desc()).all()


@router.get("/{audit_id}")
def get_scribe_audit(
    audit_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single scribe audit with its findings."""
    _require_read(current_user)

    audit = db.query(ScribeAuditModel).filter(ScribeAuditModel.id == audit_id).first()
    if not audit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit not found")

    findings = db.query(ScribeAuditFindingModel).filter(
        ScribeAuditFindingModel.audit_id == audit_id
    ).all()

    return {
        "id": audit.id,
        "session_id": audit.session_id,
        "audit_score": audit.audit_score,
        "hallucination_detected": audit.hallucination_detected,
        "completeness_score": audit.completeness_score,
        "attribution_score": audit.attribution_score,
        "status": audit.status,
        "ai_model_used": audit.ai_model_used,
        "organization_id": audit.organization_id,
        "created_at": audit.created_at,
        "completed_at": audit.completed_at,
        "findings": [
            {
                "id": f.id,
                "audit_id": f.audit_id,
                "finding_type": f.finding_type,
                "severity": f.severity,
                "description": f.description,
                "suggested_correction": f.suggested_correction,
                "created_at": f.created_at,
            }
            for f in findings
        ],
    }


@router.post("/{audit_id}/complete")
def complete_scribe_audit(
    audit_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a scribe audit as complete."""
    if not has_permission(current_user.role, "scribe_audits", "update"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    audit = db.query(ScribeAuditModel).filter(ScribeAuditModel.id == audit_id).first()
    if not audit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit not found")

    audit.status = "complete"
    audit.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(audit)
    return audit
