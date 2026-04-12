"""Prior Authorization routes — append-only, hash chain."""
import hashlib
import time
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from policy_engine.auth.rbac import get_current_user
from policy_engine.database import get_db
from policy_engine.domain.finance.prior_auth import (
    DENIAL_REASON_CODES, FinalDecision, PriorAuthDecision,
    compute_record_hash, verify_chain,
)
from policy_engine.models.prior_auth import PriorAuthChainStatus, PriorAuthRecord
from policy_engine.models.user import UserRole, has_permission

router = APIRouter()


class PriorAuthCreate(BaseModel):
    patient_id: str  # Will be hashed before storing
    claim_id: str
    service_type: Optional[str] = None
    request_date: Optional[str] = None
    decision_date: Optional[str] = None
    ai_recommendation: str
    ai_confidence: float = 0.0
    human_reviewer_id: Optional[str] = None
    final_decision: str
    denial_reason_code: Optional[str] = None
    ai_rationale: Optional[str] = None
    override_reason: Optional[str] = None


@router.post("/prior-auth", status_code=201)
def create_prior_auth(
    body: PriorAuthCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not has_permission(current_user.role, "prior_auth", "create"):
        raise HTTPException(403, "Forbidden")

    # Hash patient_id — NEVER store raw
    patient_id_hash = hashlib.sha256(body.patient_id.encode()).hexdigest()

    # Fetch last record for chain
    last = (db.query(PriorAuthRecord)
            .filter(PriorAuthRecord.organization_id == current_user.organization_id)
            .order_by(PriorAuthRecord.created_at.desc())
            .first())
    prev_record_hash = last.record_hash if last else ""

    now = datetime.utcnow()
    record_id = str(uuid.uuid4())

    record_data = {
        "patient_id_hash": patient_id_hash,
        "claim_id": body.claim_id,
        "service_type": body.service_type or "",
        "request_date": body.request_date or "",
        "ai_recommendation": body.ai_recommendation,
        "final_decision": body.final_decision,
        "denial_reason_code": body.denial_reason_code or "",
        "human_reviewer_id": body.human_reviewer_id or "",
        "created_at": now.isoformat(),
    }
    record_hash = compute_record_hash(record_data, prev_record_hash)

    record = PriorAuthRecord(
        id=record_id,
        patient_id_hash=patient_id_hash,
        claim_id=body.claim_id,
        service_type=body.service_type,
        request_date=body.request_date,
        decision_date=body.decision_date,
        ai_recommendation=body.ai_recommendation,
        ai_confidence=body.ai_confidence,
        human_reviewer_id=body.human_reviewer_id,
        final_decision=body.final_decision,
        denial_reason_code=body.denial_reason_code,
        ai_rationale=body.ai_rationale,
        override_reason=body.override_reason,
        prev_record_hash=prev_record_hash,
        record_hash=record_hash,
        organization_id=current_user.organization_id,
        created_at=now,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return {
        "id": record.id, "claim_id": record.claim_id,
        "patient_id_hash": record.patient_id_hash,
        "ai_recommendation": record.ai_recommendation,
        "final_decision": record.final_decision,
        "prev_record_hash": record.prev_record_hash,
        "record_hash": record.record_hash,
        "created_at": record.created_at.isoformat(),
        "organization_id": record.organization_id,
    }


# MUST be before /{id} to avoid path conflict
@router.get("/prior-auth/verify-chain")
def verify_prior_auth_chain(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # Accessible to COMPLIANCE_OFFICER and above, and anyone with prior_auth read
    allowed_roles = {UserRole.SYSTEM_ADMIN, UserRole.ORG_ADMIN, UserRole.COMPLIANCE_OFFICER}
    if current_user.role not in allowed_roles and not has_permission(current_user.role, "prior_auth", "read"):
        raise HTTPException(403, "Forbidden")

    start = time.time()
    records_db = (db.query(PriorAuthRecord)
                  .filter(PriorAuthRecord.organization_id == current_user.organization_id)
                  .order_by(PriorAuthRecord.created_at.asc())
                  .all())

    records = [{
        "id": r.id,
        "data": {
            "patient_id_hash": r.patient_id_hash,
            "claim_id": r.claim_id,
            "service_type": r.service_type or "",
            "request_date": r.request_date or "",
            "ai_recommendation": r.ai_recommendation,
            "final_decision": r.final_decision,
            "denial_reason_code": r.denial_reason_code or "",
            "human_reviewer_id": r.human_reviewer_id or "",
            "created_at": r.created_at.isoformat() if r.created_at else "",
        },
        "record_hash": r.record_hash,
    } for r in records_db]

    chain_valid, broken_at = verify_chain(records)
    duration_ms = int((time.time() - start) * 1000)
    now = datetime.utcnow()

    # Store chain status
    status = PriorAuthChainStatus(
        id=str(uuid.uuid4()),
        organization_id=current_user.organization_id,
        last_verified_at=now,
        total_records=len(records),
        chain_valid=chain_valid,
        broken_at_record_id=broken_at,
        verification_duration_ms=duration_ms,
        created_at=now,
    )
    db.add(status)
    db.commit()

    return {
        "chain_valid": chain_valid,
        "total_records": len(records),
        "broken_at_record_id": broken_at,
        "verified_at": now.isoformat(),
        "duration_ms": duration_ms,
    }


@router.get("/prior-auth/stats")
def prior_auth_stats(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not has_permission(current_user.role, "prior_auth", "read"):
        raise HTTPException(403, "Forbidden")

    records = (db.query(PriorAuthRecord)
               .filter(PriorAuthRecord.organization_id == current_user.organization_id)
               .all())

    total = len(records)
    approved = sum(1 for r in records if r.final_decision == "approved")
    denied = sum(1 for r in records if r.final_decision == "denied")

    return {
        "total_records": total,
        "approval_rate": approved / total if total else 0.0,
        "denial_rate": denied / total if total else 0.0,
    }


@router.get("/prior-auth")
def list_prior_auth(
    final_decision: Optional[str] = Query(None),
    ai_recommendation: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not has_permission(current_user.role, "prior_auth", "read"):
        raise HTTPException(403, "Forbidden")

    q = db.query(PriorAuthRecord).filter(
        PriorAuthRecord.organization_id == current_user.organization_id
    )
    if final_decision:
        q = q.filter(PriorAuthRecord.final_decision == final_decision)
    if ai_recommendation:
        q = q.filter(PriorAuthRecord.ai_recommendation == ai_recommendation)

    records = q.order_by(PriorAuthRecord.created_at.desc()).all()
    return [{"id": r.id, "claim_id": r.claim_id, "final_decision": r.final_decision,
             "ai_recommendation": r.ai_recommendation, "record_hash": r.record_hash,
             "prev_record_hash": r.prev_record_hash,
             "created_at": r.created_at.isoformat()} for r in records]


@router.get("/prior-auth/{record_id}")
def get_prior_auth(
    record_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not has_permission(current_user.role, "prior_auth", "read"):
        raise HTTPException(403, "Forbidden")

    record = db.query(PriorAuthRecord).filter(
        PriorAuthRecord.id == record_id,
        PriorAuthRecord.organization_id == current_user.organization_id
    ).first()
    if not record:
        raise HTTPException(404, "Not found")

    return {"id": record.id, "claim_id": record.claim_id, "final_decision": record.final_decision,
            "ai_recommendation": record.ai_recommendation, "record_hash": record.record_hash,
            "prev_record_hash": record.prev_record_hash, "patient_id_hash": record.patient_id_hash,
            "created_at": record.created_at.isoformat()}
