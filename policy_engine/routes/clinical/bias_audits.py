"""Bias Audit CRUD + run endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid
from datetime import datetime

from policy_engine.database import get_db
from policy_engine.auth.rbac import get_current_user
from policy_engine.models.user import User, has_permission
from policy_engine.models.bias_audit import BiasAuditModel, BiasAuditResultModel
from policy_engine.models.model_card import ModelCard
from policy_engine.domain.clinical.bias_audit import run_bias_audit
from policy_engine.services.hitl_auto_service import create_hitl_review
from pydantic import BaseModel

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class BiasAuditCreate(BaseModel):
    audit_name: str
    model_card_id: Optional[str] = None
    dataset_description: Optional[str] = None
    organization_id: Optional[str] = None


class BiasAuditRunRequest(BaseModel):
    predictions: List[int]
    labels: List[int]
    groups: dict


class BiasAuditResponse(BaseModel):
    id: str
    audit_name: str
    status: str
    model_card_id: Optional[str] = None
    dataset_description: Optional[str] = None
    organization_id: Optional[str] = None
    created_by: str
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_permission(current_user: User, action: str) -> None:
    if not has_permission(current_user.role, "bias_audits", action):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions to {action} bias_audits",
        )


def _get_audit_or_404(audit_id: str, db: Session) -> BiasAuditModel:
    audit = db.query(BiasAuditModel).filter(BiasAuditModel.id == audit_id).first()
    if not audit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bias audit not found")
    return audit


def _to_response(audit: BiasAuditModel) -> dict:
    return {
        "id": audit.id,
        "audit_name": audit.audit_name,
        "status": audit.status,
        "model_card_id": audit.model_card_id,
        "dataset_description": audit.dataset_description,
        "organization_id": audit.organization_id,
        "created_by": audit.created_by,
        "created_at": audit.created_at,
        "completed_at": audit.completed_at,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/bias-audits", response_model=List[BiasAuditResponse])
def list_bias_audits(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_permission(current_user, "read")
    audits = db.query(BiasAuditModel).all()
    return [_to_response(a) for a in audits]


@router.post("/bias-audits", status_code=status.HTTP_201_CREATED)
def create_bias_audit(
    payload: BiasAuditCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_permission(current_user, "create")
    now = datetime.utcnow()
    audit = BiasAuditModel(
        id=str(uuid.uuid4()),
        audit_name=payload.audit_name,
        model_card_id=payload.model_card_id,
        status="pending",
        dataset_description=payload.dataset_description,
        organization_id=payload.organization_id,
        created_by=current_user.id,
        created_at=now,
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)
    return _to_response(audit)


@router.get("/bias-audits/{audit_id}")
def get_bias_audit(
    audit_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_permission(current_user, "read")
    audit = _get_audit_or_404(audit_id, db)
    return _to_response(audit)


@router.post("/bias-audits/{audit_id}/run")
def run_bias_audit_endpoint(
    audit_id: str,
    payload: BiasAuditRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run bias audit computation and persist results."""
    _check_permission(current_user, "update")
    audit = _get_audit_or_404(audit_id, db)

    audit.status = "running"
    db.commit()

    try:
        results = run_bias_audit(
            predictions=payload.predictions,
            labels=payload.labels,
            groups=payload.groups,
        )

        for r in results:
            result_model = BiasAuditResultModel(
                id=str(uuid.uuid4()),
                audit_id=audit_id,
                subgroup_id=None,
                metric_name=r.metric_name,
                metric_value=r.metric_value,
                reference_value=r.reference_value,
                disparity_ratio=r.disparity_ratio,
                passes_threshold=r.passes_80_percent_rule,
                threshold_used=r.threshold_used,
            )
            db.add(result_model)

        audit.status = "complete"
        audit.completed_at = datetime.utcnow()
        db.commit()
        db.refresh(audit)

        # Tier 2 Sprint 3 — auto-create HITL review when any subgroup fails the
        # 80% (or inverse 4/5ths for FPR) rule. Compliance officer + ML team get
        # paged into the queue automatically.
        failing = [r for r in results if not r.passes_80_percent_rule]
        hitl_review_id = None
        if failing:
            worst = min(failing, key=lambda r: r.disparity_ratio)
            org_id = None
            if audit.model_card_id:
                card = (
                    db.query(ModelCard)
                    .filter(ModelCard.id == audit.model_card_id)
                    .first()
                )
                if card:
                    org_id = card.organization_id

            hitl_review_id = create_hitl_review(
                db,
                title=(
                    f"Bias audit failure: {audit.audit_name} "
                    f"({len(failing)} failing subgroup(s))"
                ),
                description=(
                    f"Bias audit '{audit.audit_name}' completed with "
                    f"{len(failing)} failing subgroup(s). "
                    f"Worst disparity: {worst.subgroup} "
                    f"{worst.metric_name}={worst.metric_value:.3f} "
                    f"(ratio={worst.disparity_ratio:.3f}). "
                    "Review and either remediate or document an approved exception."
                ),
                ai_decision={
                    "source": "bias_audit_failure",
                    "audit_id": audit_id,
                    "model_card_id": audit.model_card_id,
                    "failing_subgroups": [
                        {
                            "subgroup": r.subgroup,
                            "metric_name": r.metric_name,
                            "metric_value": r.metric_value,
                            "disparity_ratio": r.disparity_ratio,
                        }
                        for r in failing
                    ],
                },
                risk_score=80.0 if worst.disparity_ratio < 0.5 else 60.0,
                priority="urgent" if worst.disparity_ratio < 0.5 else "high",
                organization_id=org_id,
                actor_id="system:bias_audit",
                seed_action="bias_audit_failure",
            )

        return {
            "audit_id": audit_id,
            "status": "complete",
            "results_count": len(results),
            "failing_subgroups": len(failing),
            "hitl_review_id": hitl_review_id,
            "results": [
                {
                    "subgroup": r.subgroup,
                    "metric_name": r.metric_name,
                    "metric_value": r.metric_value,
                    "disparity_ratio": r.disparity_ratio,
                    "passes_80_percent_rule": r.passes_80_percent_rule,
                }
                for r in results
            ],
        }
    except Exception as e:
        audit.status = "failed"
        db.commit()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/bias-audits/{audit_id}/report")
def get_bias_audit_report(
    audit_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return structured bias audit report."""
    _check_permission(current_user, "read")
    audit = _get_audit_or_404(audit_id, db)

    results = db.query(BiasAuditResultModel).filter(BiasAuditResultModel.audit_id == audit_id).all()

    passing = [r for r in results if r.passes_threshold]
    failing = [r for r in results if not r.passes_threshold]

    return {
        "audit_id": audit_id,
        "audit_name": audit.audit_name,
        "status": audit.status,
        "total_subgroups": len(results),
        "passing_subgroups": len(passing),
        "failing_subgroups": len(failing),
        "results": [
            {
                "metric_name": r.metric_name,
                "metric_value": r.metric_value,
                "reference_value": r.reference_value,
                "disparity_ratio": r.disparity_ratio,
                "passes_threshold": r.passes_threshold,
                "threshold_used": r.threshold_used,
            }
            for r in results
        ],
    }
