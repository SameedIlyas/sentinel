"""Revenue Cycle Integrity routes."""
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from policy_engine.auth.rbac import get_current_user
from policy_engine.database import get_db
from policy_engine.domain.finance.revenue_cycle import (
    RevenueFindings, compute_risk_score, detect_modifier_abuse,
    detect_unbundling, detect_upcoding,
)
from policy_engine.models.revenue_cycle import CodingBenchmark, RevenueCycleAudit
from policy_engine.models.user import has_permission

router = APIRouter()


class RevenueCycleCreate(BaseModel):
    claim_id: str
    claim_date: Optional[str] = None
    provider_id: Optional[str] = None
    payer_id: Optional[str] = None
    primary_diagnosis_code: Optional[str] = None
    procedure_codes: list = []
    modifiers: list = []
    billed_amount: float = 0.0


class BenchmarkCreate(BaseModel):
    procedure_code: str
    specialty: Optional[str] = None
    p25_amount: float
    p50_amount: float
    p75_amount: float
    p90_amount: float
    national_frequency_per_1000: Optional[float] = None
    source: str


class ReviewBody(BaseModel):
    notes: Optional[str] = None


# MUST be before /{id}
@router.get("/revenue-cycle/stats")
def revenue_cycle_stats(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not has_permission(current_user.role, "revenue_cycle", "read"):
        raise HTTPException(403, "Forbidden")

    audits = (db.query(RevenueCycleAudit)
              .filter(RevenueCycleAudit.organization_id == current_user.organization_id)
              .all())

    total = len(audits)
    avg_risk = sum(a.risk_score for a in audits) / total if total else 0.0
    flagged = sum(1 for a in audits if a.risk_score > 30)

    return {
        "total_audits": total,
        "avg_risk_score": avg_risk,
        "flagged_count": flagged,
    }


# MUST be before /{id}
@router.post("/revenue-cycle/benchmarks", status_code=201)
def create_benchmark(
    body: BenchmarkCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not has_permission(current_user.role, "revenue_cycle", "read") and \
       not has_permission(current_user.role, "prior_auth", "create"):
        raise HTTPException(403, "Forbidden")

    benchmark = CodingBenchmark(
        id=str(uuid.uuid4()),
        procedure_code=body.procedure_code,
        specialty=body.specialty,
        p25_amount=body.p25_amount,
        p50_amount=body.p50_amount,
        p75_amount=body.p75_amount,
        p90_amount=body.p90_amount,
        national_frequency_per_1000=body.national_frequency_per_1000,
        last_updated=datetime.utcnow(),
        source=body.source,
        organization_id=current_user.organization_id,
    )
    db.add(benchmark)
    db.commit()
    db.refresh(benchmark)

    return {
        "id": benchmark.id,
        "procedure_code": benchmark.procedure_code,
        "specialty": benchmark.specialty,
        "p90_amount": benchmark.p90_amount,
        "source": benchmark.source,
    }


@router.get("/revenue-cycle/benchmarks")
def list_benchmarks(
    procedure_code: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not has_permission(current_user.role, "revenue_cycle", "read") and \
       not has_permission(current_user.role, "prior_auth", "read"):
        raise HTTPException(403, "Forbidden")

    q = db.query(CodingBenchmark)
    if procedure_code:
        q = q.filter(CodingBenchmark.procedure_code == procedure_code)

    benchmarks = q.all()
    return [{"id": b.id, "procedure_code": b.procedure_code, "specialty": b.specialty,
             "p90_amount": b.p90_amount, "source": b.source} for b in benchmarks]


@router.post("/revenue-cycle", status_code=201)
def create_revenue_audit(
    body: RevenueCycleCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not has_permission(current_user.role, "revenue_cycle", "read") and \
       not has_permission(current_user.role, "prior_auth", "create"):
        raise HTTPException(403, "Forbidden")

    findings: list[RevenueFindings] = []

    # Check upcoding against benchmarks
    for code in body.procedure_codes:
        bm = (db.query(CodingBenchmark)
              .filter(CodingBenchmark.procedure_code == code)
              .order_by(CodingBenchmark.last_updated.desc())
              .first())
        if bm and detect_upcoding(code, body.billed_amount, {"p90_amount": bm.p90_amount}):
            findings.append(RevenueFindings(
                finding_type="upcoding",
                severity="critical",
                description=f"Billed amount ${body.billed_amount} exceeds p90 benchmark ${bm.p90_amount} for {code}",
                affected_codes=[code],
                estimated_overbilling=body.billed_amount - bm.p90_amount,
            ))

    # Check unbundling
    unbundling_warnings = detect_unbundling(body.procedure_codes)
    for w in unbundling_warnings:
        findings.append(RevenueFindings(
            finding_type="unbundling",
            severity="high",
            description=w,
            affected_codes=body.procedure_codes,
            estimated_overbilling=None,
        ))

    # Check modifier abuse
    modifier_warnings = detect_modifier_abuse(body.modifiers, body.procedure_codes)
    for w in modifier_warnings:
        findings.append(RevenueFindings(
            finding_type="modifier_abuse",
            severity="medium",
            description=w,
            affected_codes=body.procedure_codes,
            estimated_overbilling=None,
        ))

    risk_score = compute_risk_score(findings) if findings else 0.0
    status = "clean" if risk_score == 0.0 else ("critical" if risk_score >= 70 else "flagged")

    now = datetime.utcnow()
    audit_id = str(uuid.uuid4())

    audit = RevenueCycleAudit(
        id=audit_id,
        claim_id=body.claim_id,
        claim_date=body.claim_date,
        provider_id=body.provider_id,
        payer_id=body.payer_id,
        primary_diagnosis_code=body.primary_diagnosis_code,
        procedure_codes=body.procedure_codes,
        modifiers=body.modifiers,
        billed_amount=body.billed_amount,
        expected_amount_range={},
        risk_score=risk_score,
        findings=[{"type": f.finding_type, "severity": f.severity, "description": f.description,
                   "affected_codes": f.affected_codes} for f in findings],
        status=status,
        organization_id=current_user.organization_id,
        created_at=now,
        updated_at=now,
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)

    return {
        "id": audit.id,
        "claim_id": audit.claim_id,
        "risk_score": audit.risk_score,
        "status": audit.status,
        "findings": audit.findings,
        "created_at": audit.created_at.isoformat(),
    }


@router.get("/revenue-cycle")
def list_revenue_audits(
    status: Optional[str] = Query(None),
    min_risk: Optional[float] = Query(None),
    max_risk: Optional[float] = Query(None),
    provider_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not has_permission(current_user.role, "revenue_cycle", "read"):
        raise HTTPException(403, "Forbidden")

    q = db.query(RevenueCycleAudit).filter(
        RevenueCycleAudit.organization_id == current_user.organization_id
    )
    if status:
        q = q.filter(RevenueCycleAudit.status == status)
    if min_risk is not None:
        q = q.filter(RevenueCycleAudit.risk_score >= min_risk)
    if max_risk is not None:
        q = q.filter(RevenueCycleAudit.risk_score <= max_risk)
    if provider_id:
        q = q.filter(RevenueCycleAudit.provider_id == provider_id)

    audits = q.order_by(RevenueCycleAudit.created_at.desc()).all()
    return [{"id": a.id, "claim_id": a.claim_id, "risk_score": a.risk_score,
             "status": a.status, "created_at": a.created_at.isoformat()} for a in audits]


@router.get("/revenue-cycle/{audit_id}")
def get_revenue_audit(
    audit_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not has_permission(current_user.role, "revenue_cycle", "read"):
        raise HTTPException(403, "Forbidden")

    audit = db.query(RevenueCycleAudit).filter(
        RevenueCycleAudit.id == audit_id,
        RevenueCycleAudit.organization_id == current_user.organization_id
    ).first()
    if not audit:
        raise HTTPException(404, "Not found")

    return {"id": audit.id, "claim_id": audit.claim_id, "risk_score": audit.risk_score,
            "status": audit.status, "findings": audit.findings,
            "billed_amount": audit.billed_amount, "procedure_codes": audit.procedure_codes,
            "created_at": audit.created_at.isoformat()}


@router.patch("/revenue-cycle/{audit_id}/review")
def review_revenue_audit(
    audit_id: str,
    body: ReviewBody,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not has_permission(current_user.role, "revenue_cycle", "read") and \
       not has_permission(current_user.role, "prior_auth", "update"):
        raise HTTPException(403, "Forbidden")

    audit = db.query(RevenueCycleAudit).filter(
        RevenueCycleAudit.id == audit_id,
        RevenueCycleAudit.organization_id == current_user.organization_id
    ).first()
    if not audit:
        raise HTTPException(404, "Not found")

    audit.status = "reviewed"
    audit.reviewed_by = current_user.id
    audit.reviewed_at = datetime.utcnow()
    audit.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(audit)

    return {"id": audit.id, "status": audit.status, "reviewed_at": audit.reviewed_at.isoformat()}
