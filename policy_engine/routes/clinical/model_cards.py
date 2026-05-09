"""Model Card CRUD + lifecycle endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Any, Dict, List, Optional
import uuid
from datetime import datetime

from policy_engine.database import get_db
from policy_engine.auth.rbac import get_current_user
from policy_engine.models.user import User, has_permission
from policy_engine.models.model_card import ModelCard, ModelCardVersion
from policy_engine.models.bias_audit import BiasAuditModel, BiasAuditResultModel
from policy_engine.models.drift import DriftBaseline, DriftAlert, DriftMeasurementModel
from policy_engine.models.post_market import AdverseEvent
from policy_engine.models.risk_score import RiskScore
from policy_engine.models.transparency import TransparencyRecordModel
from policy_engine.domain.clinical.model_card import LifecycleStage, ModelCardEntity
from policy_engine.config import settings
from policy_engine.services.github_integration import GitHubIntegrationService
from policy_engine.services.mlflow_integration import MLflowIntegrationService
from policy_engine.services.model_card_service import (
    ModelCardAutoFillRequest,
    ModelCardAutoFillResult,
    ModelCardAutoFillService,
)
from policy_engine.services.transparency_auto_service import (
    auto_create_or_bump_transparency,
)
from pydantic import BaseModel

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ModelCardCreate(BaseModel):
    name: str
    version: str = "1.0"
    intended_use: Optional[str] = None
    clinical_indications: Optional[str] = None
    contraindications: Optional[str] = None
    training_data_source: Optional[str] = None
    performance_metrics: Optional[dict] = None
    bias_summary: Optional[dict] = None
    fda_status: Optional[str] = None
    chai_version: str = "2.0"
    organization_id: Optional[str] = None
    # Pinned lineage (optional at create, required at publish)
    model_artifact_uri: Optional[str] = None
    training_dataset_sha256: Optional[str] = None
    evaluation_dataset_sha256: Optional[str] = None
    git_commit_sha: Optional[str] = None
    framework_version: Optional[str] = None
    external_validation: Optional[dict] = None
    monitoring_plan: Optional[dict] = None
    pccp: Optional[dict] = None


class ModelCardUpdate(BaseModel):
    name: Optional[str] = None
    version: Optional[str] = None
    intended_use: Optional[str] = None
    clinical_indications: Optional[str] = None
    contraindications: Optional[str] = None
    training_data_source: Optional[str] = None
    performance_metrics: Optional[dict] = None
    bias_summary: Optional[dict] = None
    fda_status: Optional[str] = None
    model_artifact_uri: Optional[str] = None
    training_dataset_sha256: Optional[str] = None
    evaluation_dataset_sha256: Optional[str] = None
    git_commit_sha: Optional[str] = None
    framework_version: Optional[str] = None
    external_validation: Optional[dict] = None
    monitoring_plan: Optional[dict] = None
    pccp: Optional[dict] = None


class ModelCardResponse(BaseModel):
    id: str
    name: str
    version: str
    lifecycle_stage: str
    intended_use: Optional[str] = None
    clinical_indications: Optional[str] = None
    contraindications: Optional[str] = None
    training_data_source: Optional[str] = None
    performance_metrics: dict = {}
    bias_summary: dict = {}
    fda_status: Optional[str] = None
    chai_version: str
    organization_id: Optional[str] = None
    model_artifact_uri: Optional[str] = None
    training_dataset_sha256: Optional[str] = None
    evaluation_dataset_sha256: Optional[str] = None
    git_commit_sha: Optional[str] = None
    framework_version: Optional[str] = None
    external_validation: dict = {}
    monitoring_plan: dict = {}
    pccp: dict = {}
    created_by: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CHAISection(BaseModel):
    key: str
    label: str
    status: str         # "complete" | "partial" | "missing"
    detail: Optional[str] = None


class CHAIComplianceResponse(BaseModel):
    card_id: str
    score: int          # 0..11
    total: int = 11
    percent: int
    sections: List[CHAISection]
    publishable: bool
    blockers: List[str]


class RelatedArtifact(BaseModel):
    kind: str           # "bias_audit" | "drift_baseline" | "drift_alert" | "adverse_event" | "risk_score" | "transparency_record"
    id: str
    title: str
    status: Optional[str] = None
    severity: Optional[str] = None
    timestamp: Optional[datetime] = None


class RelatedArtifactsResponse(BaseModel):
    card_id: str
    bias_audits: List[RelatedArtifact]
    drift_baselines: List[RelatedArtifact]
    drift_alerts: List[RelatedArtifact]
    adverse_events: List[RelatedArtifact]
    risk_scores: List[RelatedArtifact]
    transparency_records: List[RelatedArtifact]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_permission(current_user: User, action: str) -> None:
    if not has_permission(current_user.role, "model_cards", action):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions to {action} model_cards",
        )


def _get_card_or_404(card_id: str, db: Session) -> ModelCard:
    card = db.query(ModelCard).filter(ModelCard.id == card_id).first()
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model card not found")
    return card


def _to_response(card: ModelCard) -> dict:
    return {
        "id": card.id,
        "name": card.name,
        "version": card.version,
        "lifecycle_stage": card.lifecycle_stage,
        "intended_use": card.intended_use,
        "clinical_indications": card.clinical_indications,
        "contraindications": card.contraindications,
        "training_data_source": card.training_data_source,
        "performance_metrics": card.performance_metrics or {},
        "bias_summary": card.bias_summary or {},
        "fda_status": card.fda_status,
        "chai_version": card.chai_version,
        "organization_id": card.organization_id,
        "model_artifact_uri": getattr(card, "model_artifact_uri", None),
        "training_dataset_sha256": getattr(card, "training_dataset_sha256", None),
        "evaluation_dataset_sha256": getattr(card, "evaluation_dataset_sha256", None),
        "git_commit_sha": getattr(card, "git_commit_sha", None),
        "framework_version": getattr(card, "framework_version", None),
        "external_validation": getattr(card, "external_validation", None) or {},
        "monitoring_plan": getattr(card, "monitoring_plan", None) or {},
        "pccp": getattr(card, "pccp", None) or {},
        "created_by": card.created_by,
        "created_at": card.created_at,
        "updated_at": card.updated_at,
    }


# ---------------------------------------------------------------------------
# CHAI v2.0 — 11 mandatory sections
# ---------------------------------------------------------------------------

CHAI_SECTIONS = [
    ("model_identity",        "Model Identity"),
    ("intended_use",          "Intended Use & Population"),
    ("contraindications",     "Out-of-scope / Contraindications"),
    ("training_data",         "Training Data"),
    ("external_validation",   "External Validation"),
    ("quantitative_analyses", "Quantitative Analyses (per-subgroup)"),
    ("fairness",              "Fairness"),
    ("training_procedure",    "Training Procedure / Lineage"),
    ("monitoring",            "Continuous Monitoring"),
    ("governance",            "Governance & Contact"),
    ("pccp",                  "Predetermined Change Control Plan"),
]


def _chai_score(card: ModelCard) -> CHAIComplianceResponse:
    """Compute CHAI v2.0 compliance scorecard for a model card."""
    sections: List[CHAISection] = []

    # Helpers
    def _has_text(s: Optional[str], min_len: int = 20) -> bool:
        return bool(s and len(s.strip()) >= min_len)

    def _has_dict(d: Optional[dict], min_keys: int = 1) -> bool:
        return bool(d and isinstance(d, dict) and len(d) >= min_keys)

    perf = card.performance_metrics or {}
    bias = card.bias_summary or {}
    ext_val = getattr(card, "external_validation", None) or {}
    monitoring = getattr(card, "monitoring_plan", None) or {}
    pccp = getattr(card, "pccp", None) or {}

    # 1. Model Identity
    has_identity = bool(card.name and card.version and card.created_by)
    sections.append(CHAISection(
        key="model_identity",
        label="Model Identity",
        status="complete" if has_identity else "missing",
        detail="name + version + owner present" if has_identity else "missing name/version/owner",
    ))

    # 2. Intended Use
    has_intended = _has_text(card.intended_use, 20) and _has_text(card.clinical_indications, 5)
    sections.append(CHAISection(
        key="intended_use",
        label="Intended Use & Population",
        status="complete" if has_intended else (
            "partial" if _has_text(card.intended_use, 5) else "missing"
        ),
        detail=None if has_intended else "intended_use + clinical_indications must be specified",
    ))

    # 3. Contraindications
    has_contra = _has_text(card.contraindications, 5)
    sections.append(CHAISection(
        key="contraindications",
        label="Out-of-scope / Contraindications",
        status="complete" if has_contra else "missing",
        detail=None if has_contra else "contraindications must be reviewed by a human",
    ))

    # 4. Training Data
    has_training = _has_text(card.training_data_source, 5)
    sections.append(CHAISection(
        key="training_data",
        label="Training Data",
        status="complete" if has_training else "missing",
        detail=None if has_training else "training_data_source must be specified",
    ))

    # 5. External Validation
    ext_val_complete = (
        _has_dict(ext_val, 1)
        and any(k in ext_val for k in ("sites", "auc", "n", "studies"))
    )
    sections.append(CHAISection(
        key="external_validation",
        label="External Validation",
        status="complete" if ext_val_complete else "missing",
        detail=None if ext_val_complete else "external_validation should include sites + sample sizes",
    ))

    # 6. Quantitative Analyses
    has_quant = _has_dict(perf, 2)  # at least 2 metrics
    sections.append(CHAISection(
        key="quantitative_analyses",
        label="Quantitative Analyses",
        status="complete" if has_quant else (
            "partial" if _has_dict(perf, 1) else "missing"
        ),
        detail=None if has_quant else "performance_metrics should include ≥2 metrics",
    ))

    # 7. Fairness
    has_fairness = _has_dict(bias, 1) and (
        "subgroups" in bias or "max_disparity_ratio" in bias or "passes_4_5ths_rule" in bias
    )
    sections.append(CHAISection(
        key="fairness",
        label="Fairness",
        status="complete" if has_fairness else (
            "partial" if _has_dict(bias, 1) else "missing"
        ),
        detail=None if has_fairness else "bias_summary should include subgroups or disparity ratio",
    ))

    # 8. Training Procedure / Lineage
    has_lineage = bool(
        getattr(card, "model_artifact_uri", None)
        and getattr(card, "training_dataset_sha256", None)
        and getattr(card, "evaluation_dataset_sha256", None)
    )
    sections.append(CHAISection(
        key="training_procedure",
        label="Training Procedure / Lineage",
        status="complete" if has_lineage else (
            "partial" if getattr(card, "model_artifact_uri", None) else "missing"
        ),
        detail=None if has_lineage else "model_artifact_uri + training_dataset_sha256 + evaluation_dataset_sha256 required",
    ))

    # 9. Continuous Monitoring
    has_monitoring = _has_dict(monitoring, 1) and (
        "drift_baseline_id" in monitoring or "cadence" in monitoring
    )
    sections.append(CHAISection(
        key="monitoring",
        label="Continuous Monitoring",
        status="complete" if has_monitoring else "missing",
        detail=None if has_monitoring else "monitoring_plan should include drift_baseline_id + cadence",
    ))

    # 10. Governance & Contact
    has_governance = bool(card.fda_status) or bool(card.organization_id)
    sections.append(CHAISection(
        key="governance",
        label="Governance & Contact",
        status="complete" if has_governance else "missing",
        detail=None if has_governance else "fda_status or organization governance must be set",
    ))

    # 11. PCCP (FDA 2023)
    has_pccp = _has_dict(pccp, 1)
    sections.append(CHAISection(
        key="pccp",
        label="Predetermined Change Control Plan",
        status="complete" if has_pccp else "missing",
        detail=None if has_pccp else "pccp should describe pre-approved changes (FDA 2023 guidance)",
    ))

    score = sum(1 for s in sections if s.status == "complete")
    blockers = [s.label for s in sections if s.status == "missing" and s.key in {
        "model_identity", "intended_use", "training_procedure",
    }]
    return CHAIComplianceResponse(
        card_id=card.id,
        score=score,
        total=len(sections),
        percent=int(round(100 * score / len(sections))),
        sections=sections,
        publishable=len(blockers) == 0,
        blockers=blockers,
    )


def _related_artifacts(card: ModelCard, db: Session) -> RelatedArtifactsResponse:
    """Find every governance artifact linked to this model card."""
    card_id = card.id

    bias_audits = (
        db.query(BiasAuditModel)
        .filter(BiasAuditModel.model_card_id == card_id)
        .all()
    )
    drift_baselines = (
        db.query(DriftBaseline)
        .filter(DriftBaseline.model_id == card_id)
        .all()
    )
    baseline_ids = [b.id for b in drift_baselines]
    drift_alerts: list = []
    if baseline_ids:
        # alerts linked via measurement → baseline
        measurements = (
            db.query(DriftMeasurementModel.id)
            .filter(DriftMeasurementModel.baseline_id.in_(baseline_ids))
            .all()
        )
        measurement_ids = [m[0] for m in measurements]
        if measurement_ids:
            drift_alerts = (
                db.query(DriftAlert)
                .filter(DriftAlert.measurement_id.in_(measurement_ids))
                .all()
            )
    adverse = (
        db.query(AdverseEvent)
        .filter(AdverseEvent.model_id == card_id)
        .all()
    )
    risk_scores = (
        db.query(RiskScore)
        .filter(RiskScore.model_id == card_id)
        .order_by(RiskScore.computed_at.desc())
        .limit(10)
        .all()
    )
    transparency = (
        db.query(TransparencyRecordModel)
        .filter(TransparencyRecordModel.model_name == card.name)
        .all()
    )

    return RelatedArtifactsResponse(
        card_id=card_id,
        bias_audits=[
            RelatedArtifact(
                kind="bias_audit", id=ba.id, title=ba.audit_name,
                status=ba.status, timestamp=ba.created_at,
            )
            for ba in bias_audits
        ],
        drift_baselines=[
            RelatedArtifact(
                kind="drift_baseline", id=b.id, title=b.baseline_name,
                timestamp=b.created_at,
            )
            for b in drift_baselines
        ],
        drift_alerts=[
            RelatedArtifact(
                kind="drift_alert", id=a.id,
                title=a.message[:80] + ("…" if len(a.message) > 80 else ""),
                severity=a.severity, timestamp=a.created_at,
            )
            for a in drift_alerts
        ],
        adverse_events=[
            RelatedArtifact(
                kind="adverse_event", id=e.id,
                title=f"{e.event_type}: {e.description[:60]}",
                severity=str(e.severity), status=str(e.status),
                timestamp=e.reported_at,
            )
            for e in adverse
        ],
        risk_scores=[
            RelatedArtifact(
                kind="risk_score", id=r.id,
                title=f"Risk {r.total_risk:.1f} ({r.risk_level})",
                severity=r.risk_level, timestamp=r.computed_at,
            )
            for r in risk_scores
        ],
        transparency_records=[
            RelatedArtifact(
                kind="transparency_record", id=t.id, title=t.model_name,
                timestamp=t.created_at,
            )
            for t in transparency
        ],
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/model-cards", response_model=List[ModelCardResponse])
def list_model_cards(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_permission(current_user, "read")
    cards = db.query(ModelCard).all()
    return [_to_response(c) for c in cards]


@router.post("/model-cards", status_code=status.HTTP_201_CREATED)
def create_model_card(
    payload: ModelCardCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_permission(current_user, "create")
    now = datetime.utcnow()
    card = ModelCard(
        id=str(uuid.uuid4()),
        name=payload.name,
        version=payload.version,
        lifecycle_stage="draft",
        intended_use=payload.intended_use,
        clinical_indications=payload.clinical_indications,
        contraindications=payload.contraindications,
        training_data_source=payload.training_data_source,
        performance_metrics=payload.performance_metrics or {},
        bias_summary=payload.bias_summary or {},
        fda_status=payload.fda_status,
        chai_version=payload.chai_version,
        organization_id=payload.organization_id,
        model_artifact_uri=payload.model_artifact_uri,
        training_dataset_sha256=payload.training_dataset_sha256,
        evaluation_dataset_sha256=payload.evaluation_dataset_sha256,
        git_commit_sha=payload.git_commit_sha,
        framework_version=payload.framework_version,
        external_validation=payload.external_validation or {},
        monitoring_plan=payload.monitoring_plan or {},
        pccp=payload.pccp or {},
        created_by=current_user.id,
        created_at=now,
        updated_at=now,
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    return _to_response(card)


@router.get("/model-cards/{card_id}")
def get_model_card(
    card_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_permission(current_user, "read")
    card = _get_card_or_404(card_id, db)
    return _to_response(card)


@router.put("/model-cards/{card_id}")
def update_model_card(
    card_id: str,
    payload: ModelCardUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_permission(current_user, "update")
    card = _get_card_or_404(card_id, db)

    if card.lifecycle_stage not in ("draft", "review"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only DRAFT or REVIEW cards can be updated",
        )

    update_data = payload.dict(exclude_unset=True)
    for field_name, value in update_data.items():
        setattr(card, field_name, value)
    card.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(card)
    return _to_response(card)


@router.post("/model-cards/{card_id}/review")
def submit_for_review(
    card_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Transition DRAFT -> REVIEW."""
    _check_permission(current_user, "update")
    card = _get_card_or_404(card_id, db)

    entity = ModelCardEntity(id=card.id, name=card.name, lifecycle_stage=LifecycleStage(card.lifecycle_stage))
    try:
        entity.transition_to(LifecycleStage.REVIEW)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    card.lifecycle_stage = entity.lifecycle_stage.value
    card.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(card)
    return _to_response(card)


@router.post("/model-cards/{card_id}/publish")
def publish_model_card(
    card_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Transition REVIEW -> PUBLISHED and create a version snapshot.

    Publish is BLOCKED unless artifact lineage is pinned: model_artifact_uri,
    training_dataset_sha256, and evaluation_dataset_sha256 must all be set.
    Without lineage, the card describes an aspiration rather than a real model.

    Tier 2 Sprint 3 — additionally blocks publish unless a complete bias audit
    < 90 days old exists for the card. The bias gate may be relaxed by
    setting BIAS_AUDIT_PUBLISH_GATE=false (NOT recommended in production —
    intended for demo and bootstrap scenarios only).
    """
    import os
    _check_permission(current_user, "update")
    card = _get_card_or_404(card_id, db)

    # Lineage gate — required before any publish
    missing = []
    if not getattr(card, "model_artifact_uri", None):
        missing.append("model_artifact_uri")
    if not getattr(card, "training_dataset_sha256", None):
        missing.append("training_dataset_sha256")
    if not getattr(card, "evaluation_dataset_sha256", None):
        missing.append("evaluation_dataset_sha256")
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "lineage_required",
                "message": "Model card cannot be published without pinned artifact lineage",
                "missing_fields": missing,
                "guidance": "Set model_artifact_uri (e.g. mlflow://runs/abc/model), training_dataset_sha256, and evaluation_dataset_sha256 before publishing.",
            },
        )

    # Bias audit gate — Tier 2 Sprint 3
    bias_gate_enabled = os.environ.get(
        "BIAS_AUDIT_PUBLISH_GATE", "true"
    ).lower() in ("1", "true", "yes", "on")
    if bias_gate_enabled:
        from datetime import timedelta as _td
        cutoff = datetime.utcnow() - _td(days=90)
        recent_audit = (
            db.query(BiasAuditModel)
            .filter(
                BiasAuditModel.model_card_id == card.id,
                BiasAuditModel.status == "complete",
                BiasAuditModel.completed_at >= cutoff,
            )
            .order_by(BiasAuditModel.completed_at.desc())
            .first()
        )
        if recent_audit is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "bias_audit_required",
                    "message": (
                        "Model card cannot be published without a complete bias "
                        "audit (< 90 days old) linked to this model."
                    ),
                    "guidance": (
                        "Run a bias audit (POST /v1/clinical/bias-audits/{id}/run) "
                        "with model_card_id set to this card, then retry publish. "
                        "Set BIAS_AUDIT_PUBLISH_GATE=false to bypass for demo only."
                    ),
                },
            )

        # If a recent audit exists, ensure it didn't fail any subgroups
        failing = (
            db.query(BiasAuditResultModel)
            .filter(
                BiasAuditResultModel.audit_id == recent_audit.id,
                BiasAuditResultModel.passes_threshold.is_(False),
            )
            .count()
        )
        if failing > 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "bias_audit_failing",
                    "message": (
                        f"Most recent bias audit has {failing} failing "
                        "subgroup(s). Resolve fairness issues before publishing."
                    ),
                    "audit_id": recent_audit.id,
                    "guidance": (
                        "Review failing subgroups in the audit report and "
                        "either retrain to mitigate disparity, document an "
                        "approved exception in bias_summary, then re-run "
                        "the audit and retry publish."
                    ),
                },
            )

    entity = ModelCardEntity(id=card.id, name=card.name, lifecycle_stage=LifecycleStage(card.lifecycle_stage))
    try:
        entity.transition_to(LifecycleStage.PUBLISHED)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    card.lifecycle_stage = entity.lifecycle_stage.value
    card.updated_at = datetime.utcnow()

    # Create version snapshot — captures the full card content at publish time
    version_record = ModelCardVersion(
        id=str(uuid.uuid4()),
        model_card_id=card.id,
        version_number=card.version,
        content={
            "name": card.name,
            "version": card.version,
            "lifecycle_stage": card.lifecycle_stage,
            "intended_use": card.intended_use,
            "clinical_indications": card.clinical_indications,
            "contraindications": card.contraindications,
            "training_data_source": card.training_data_source,
            "performance_metrics": card.performance_metrics or {},
            "bias_summary": card.bias_summary or {},
            "external_validation": getattr(card, "external_validation", None) or {},
            "monitoring_plan": getattr(card, "monitoring_plan", None) or {},
            "pccp": getattr(card, "pccp", None) or {},
            "model_artifact_uri": getattr(card, "model_artifact_uri", None),
            "training_dataset_sha256": getattr(card, "training_dataset_sha256", None),
            "evaluation_dataset_sha256": getattr(card, "evaluation_dataset_sha256", None),
            "git_commit_sha": getattr(card, "git_commit_sha", None),
            "framework_version": getattr(card, "framework_version", None),
            "fda_status": card.fda_status,
        },
        published_by=current_user.id,
        published_at=datetime.utcnow(),
    )
    db.add(version_record)
    db.commit()
    db.refresh(card)

    # Tier 2 Sprint 1 — auto-generate transparency record draft on publish.
    # Failures never block the publish.
    auto_create_or_bump_transparency(db, card, created_by=current_user.id)

    return _to_response(card)


# ---------------------------------------------------------------------------
# CHAI compliance scorecard
# ---------------------------------------------------------------------------

@router.get("/model-cards/{card_id}/chai-compliance", response_model=CHAIComplianceResponse)
def get_chai_compliance(
    card_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return CHAI v2.0 compliance scorecard (X / 11 sections complete)."""
    _check_permission(current_user, "read")
    card = _get_card_or_404(card_id, db)
    return _chai_score(card)


# ---------------------------------------------------------------------------
# Related artifacts (bias audits, drift, adverse events, risk scores, transparency)
# ---------------------------------------------------------------------------

@router.get("/model-cards/{card_id}/related", response_model=RelatedArtifactsResponse)
def get_related_artifacts(
    card_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return every governance artifact linked to this model card."""
    _check_permission(current_user, "read")
    card = _get_card_or_404(card_id, db)
    return _related_artifacts(card, db)


# ---------------------------------------------------------------------------
# JSON-LD export (machine-readable — schema.org / FHIR / CHAI)
# ---------------------------------------------------------------------------

@router.get("/model-cards/{card_id}/export")
def export_model_card(
    card_id: str,
    fmt: str = "json-ld",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export model card as JSON-LD (default) or Markdown.

    Query: ?fmt=json-ld | markdown
    """
    _check_permission(current_user, "read")
    card = _get_card_or_404(card_id, db)

    if fmt == "markdown":
        return _markdown_export(card)
    return _jsonld_export(card)


def _jsonld_export(card: ModelCard) -> Dict[str, Any]:
    """JSON-LD export aligned with schema.org/SoftwareApplication + CHAI fields."""
    return {
        "@context": {
            "schema": "https://schema.org/",
            "chai": "https://coalitionforhealthai.org/schema/v2.0/",
        },
        "@type": "schema:SoftwareApplication",
        "@id": f"urn:sentinel:model-card:{card.id}",
        "schema:name": card.name,
        "schema:softwareVersion": card.version,
        "schema:applicationCategory": "Clinical AI / Healthcare Decision Support",
        "schema:operatingSystem": getattr(card, "framework_version", None),
        "chai:lifecycle_stage": card.lifecycle_stage,
        "chai:intended_use": card.intended_use,
        "chai:clinical_indications": card.clinical_indications,
        "chai:contraindications": card.contraindications,
        "chai:training_data_source": card.training_data_source,
        "chai:performance_metrics": card.performance_metrics or {},
        "chai:bias_summary": card.bias_summary or {},
        "chai:external_validation": getattr(card, "external_validation", None) or {},
        "chai:monitoring_plan": getattr(card, "monitoring_plan", None) or {},
        "chai:pccp": getattr(card, "pccp", None) or {},
        "chai:fda_status": card.fda_status,
        "chai:chai_version": card.chai_version,
        "chai:lineage": {
            "model_artifact_uri": getattr(card, "model_artifact_uri", None),
            "training_dataset_sha256": getattr(card, "training_dataset_sha256", None),
            "evaluation_dataset_sha256": getattr(card, "evaluation_dataset_sha256", None),
            "git_commit_sha": getattr(card, "git_commit_sha", None),
        },
        "schema:dateCreated": card.created_at.isoformat(),
        "schema:dateModified": card.updated_at.isoformat(),
        "schema:author": card.created_by,
        "chai:export_timestamp": datetime.utcnow().isoformat(),
    }


def _markdown_export(card: ModelCard) -> Dict[str, str]:
    """Render the card as a CHAI-aligned Markdown document."""
    perf = card.performance_metrics or {}
    bias = card.bias_summary or {}
    ext_val = getattr(card, "external_validation", None) or {}
    monitoring = getattr(card, "monitoring_plan", None) or {}
    pccp = getattr(card, "pccp", None) or {}

    def _kv_lines(d: Dict[str, Any]) -> str:
        return "\n".join(f"- **{k}**: {v}" for k, v in d.items()) or "_(none)_"

    md = f"""# Model Card — {card.name} (v{card.version})

**Lifecycle:** {card.lifecycle_stage}
**FDA Status:** {card.fda_status or '_unspecified_'}
**CHAI version:** {card.chai_version}

## 1. Model Identity
- **Name:** {card.name}
- **Version:** {card.version}
- **Owner:** {card.created_by}
- **Created:** {card.created_at.isoformat()}

## 2. Intended Use & Population
{card.intended_use or '_(not specified)_'}

**Clinical indications:** {card.clinical_indications or '_(not specified)_'}

## 3. Out-of-scope / Contraindications
{card.contraindications or '_(not specified — REQUIRES HUMAN REVIEW)_'}

## 4. Training Data
{card.training_data_source or '_(not specified)_'}

## 5. External Validation
{_kv_lines(ext_val)}

## 6. Quantitative Analyses (Performance)
{_kv_lines(perf)}

## 7. Fairness
{_kv_lines(bias)}

## 8. Training Procedure / Lineage
- **Artifact URI:** {getattr(card, 'model_artifact_uri', None) or '_(not pinned)_'}
- **Training dataset SHA-256:** {getattr(card, 'training_dataset_sha256', None) or '_(not pinned)_'}
- **Evaluation dataset SHA-256:** {getattr(card, 'evaluation_dataset_sha256', None) or '_(not pinned)_'}
- **Git commit:** {getattr(card, 'git_commit_sha', None) or '_(not pinned)_'}
- **Framework:** {getattr(card, 'framework_version', None) or '_(not pinned)_'}

## 9. Continuous Monitoring
{_kv_lines(monitoring)}

## 10. Governance & Contact
- **FDA status:** {card.fda_status or '_(not specified)_'}
- **Organization:** {card.organization_id or '_(not specified)_'}

## 11. Predetermined Change Control Plan (PCCP)
{_kv_lines(pccp)}

---
_Exported: {datetime.utcnow().isoformat()}Z by Sentinel AI Governance Platform_
"""
    return {"format": "markdown", "content": md}


@router.post("/model-cards/{card_id}/retire")
def retire_model_card(
    card_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Transition PUBLISHED -> RETIRED."""
    _check_permission(current_user, "update")
    card = _get_card_or_404(card_id, db)

    entity = ModelCardEntity(id=card.id, name=card.name, lifecycle_stage=LifecycleStage(card.lifecycle_stage))
    try:
        entity.transition_to(LifecycleStage.RETIRED)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    card.lifecycle_stage = entity.lifecycle_stage.value
    card.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(card)
    return _to_response(card)


@router.get("/model-cards/{card_id}/export-summary")
def export_summary(
    card_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return structured JSON summary of the model card."""
    _check_permission(current_user, "read")
    card = _get_card_or_404(card_id, db)
    return {
        "id": card.id,
        "name": card.name,
        "version": card.version,
        "lifecycle_stage": card.lifecycle_stage,
        "intended_use": card.intended_use,
        "fda_status": card.fda_status,
        "chai_version": card.chai_version,
        "performance_metrics": card.performance_metrics or {},
        "bias_summary": card.bias_summary or {},
        "export_timestamp": datetime.utcnow().isoformat(),
    }


@router.post(
    "/model-cards/{card_id}/auto-fill",
    response_model=ModelCardAutoFillResult,
    status_code=status.HTTP_200_OK,
)
async def auto_fill_model_card(
    card_id: str,
    payload: ModelCardAutoFillRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Auto-populate CHAI model card sections from GitHub + MLflow."""
    _check_permission(current_user, "update")
    _get_card_or_404(card_id, db)

    github_svc = GitHubIntegrationService(
        token=settings.GITHUB_TOKEN,
        base_url=settings.GITHUB_API_BASE_URL,
        timeout_seconds=settings.GITHUB_REQUEST_TIMEOUT_SECONDS,
    )
    mlflow_svc = MLflowIntegrationService(
        tracking_uri=settings.MLFLOW_TRACKING_URI,
        timeout_seconds=settings.MLFLOW_REQUEST_TIMEOUT_SECONDS,
    )
    service = ModelCardAutoFillService(
        github_service=github_svc,
        mlflow_service=mlflow_svc,
    )

    try:
        return await service.auto_fill(payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
