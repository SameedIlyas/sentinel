"""Risk Scoring Engine routes."""
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, field_validator, model_validator
from sqlalchemy.orm import Session

from policy_engine.auth.rbac import get_current_user
from policy_engine.database import get_db
from policy_engine.domain.regulatory.risk_scoring import (
    ExposureFactors,
    RegulatoryFlags,
    SeverityFactors,
    compute_exposure_score,
    compute_regulatory_penalty,
    compute_severity_score,
    compute_total_risk,
    risk_level_from_score,
    validate_factor,
)
from policy_engine.models.risk_score import (
    RiskConfiguration,
    RiskRegulatoryMapping,
    RiskScore,
    RiskScoreHistory,
)
from policy_engine.models.user import has_permission

router = APIRouter()

# Valid regulation names
_VALID_REGULATIONS = {"hipaa", "fda_samd", "cms_false_claims", "onc_hti1"}


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class SeverityFactorsIn(BaseModel):
    patient_safety_impact: float
    data_sensitivity: float
    model_confidence: float
    bias_magnitude: float
    drift_magnitude: float


class ExposureFactorsIn(BaseModel):
    patient_volume: float
    decision_frequency: float
    automation_level: float
    data_access_breadth: float


class RegulatoryFlagsIn(BaseModel):
    hipaa: bool = False
    fda_samd: bool = False
    cms_false_claims: bool = False
    onc_hti1: bool = False


class RiskScoreCreate(BaseModel):
    model_id: str
    agent_id: Optional[str] = None
    severity_factors: SeverityFactorsIn
    exposure_factors: ExposureFactorsIn
    regulatory_flags: RegulatoryFlagsIn

    @field_validator("severity_factors")
    @classmethod
    def validate_severity(cls, v):
        for name, value in v.model_dump().items():
            validate_factor(name, value)
        return v

    @field_validator("exposure_factors")
    @classmethod
    def validate_exposure(cls, v):
        for name, value in v.model_dump().items():
            validate_factor(name, value)
        return v


class RiskConfigurationCreate(BaseModel):
    regulatory_multiplier: float = 1.0
    critical_threshold: float = 75.0
    high_threshold: float = 50.0
    medium_threshold: float = 25.0

    @model_validator(mode="after")
    def validate_thresholds(self):
        if self.high_threshold >= self.critical_threshold:
            raise ValueError("high_threshold must be less than critical_threshold")
        if self.medium_threshold >= self.high_threshold:
            raise ValueError("medium_threshold must be less than high_threshold")
        return self


class RegulatoryMappingCreate(BaseModel):
    model_id: str
    regulation: str
    applicable: bool = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_org_config(db: Session, org_id: Optional[str]) -> RiskConfiguration:
    """Return stored config or an in-memory stub with defaults."""
    if org_id:
        cfg = db.query(RiskConfiguration).filter(
            RiskConfiguration.organization_id == org_id
        ).first()
        if cfg:
            return cfg
    # In-memory stub
    stub = RiskConfiguration()
    stub.id = "default"
    stub.regulatory_multiplier = 1.0
    stub.critical_threshold = 75.0
    stub.high_threshold = 50.0
    stub.medium_threshold = 25.0
    return stub


def _determine_trend(delta: Optional[float]) -> str:
    if delta is None:
        return "stable"
    if delta >= 1.0:
        return "up"
    if delta <= -1.0:
        return "down"
    return "stable"


def _score_to_dict(s: RiskScore) -> dict:
    return {
        "id": s.id,
        "model_id": s.model_id,
        "agent_id": s.agent_id,
        "organization_id": s.organization_id,
        "severity_score": s.severity_score,
        "exposure_score": s.exposure_score,
        "regulatory_penalty": s.regulatory_penalty,
        "total_risk": s.total_risk,
        "risk_level": s.risk_level,
        "severity_factors": s.severity_factors,
        "exposure_factors": s.exposure_factors,
        "regulatory_flags": s.regulatory_flags,
        "org_multiplier": s.org_multiplier,
        "computed_at": s.computed_at.isoformat(),
    }


def _history_to_dict(h: RiskScoreHistory) -> dict:
    return {
        "id": h.id,
        "model_id": h.model_id,
        "total_risk": h.total_risk,
        "risk_level": h.risk_level,
        "delta": h.delta,
        "trend": h.trend,
        "computed_at": h.computed_at.isoformat(),
    }


def _config_to_dict(cfg: RiskConfiguration) -> dict:
    return {
        "id": cfg.id,
        "organization_id": getattr(cfg, "organization_id", None),
        "regulatory_multiplier": cfg.regulatory_multiplier,
        "critical_threshold": cfg.critical_threshold,
        "high_threshold": cfg.high_threshold,
        "medium_threshold": cfg.medium_threshold,
    }


def _mapping_to_dict(m: RiskRegulatoryMapping) -> dict:
    return {
        "id": m.id,
        "organization_id": m.organization_id,
        "model_id": m.model_id,
        "regulation": m.regulation,
        "applicable": m.applicable,
        "created_at": m.created_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# Routes — specific paths BEFORE /{model_id} or /{mapping_id}
# ---------------------------------------------------------------------------

@router.get("/risk/scores/stats")
def risk_score_stats(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not has_permission(current_user.role, "risk_scores", "read"):
        raise HTTPException(403, "Forbidden")

    scores = db.query(RiskScore).filter(
        RiskScore.organization_id == current_user.organization_id
    ).all()

    by_level: dict = {}
    total_risk_sum = 0.0
    for s in scores:
        lvl = str(s.risk_level)
        by_level[lvl] = by_level.get(lvl, 0) + 1
        total_risk_sum += s.total_risk

    count = len(scores)
    return {
        "total_scores": count,
        "avg_risk": round(total_risk_sum / count, 2) if count else 0.0,
        "by_risk_level": by_level,
    }


@router.get("/risk/portfolio")
def get_risk_portfolio(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Aggregate view: latest risk score per model_id for the org."""
    if not has_permission(current_user.role, "risk_scores", "read"):
        raise HTTPException(403, "Forbidden")

    all_scores = (
        db.query(RiskScore)
        .filter(RiskScore.organization_id == current_user.organization_id)
        .order_by(RiskScore.computed_at.desc())
        .all()
    )

    # Deduplicate: keep latest per model_id
    seen: set = set()
    latest_per_model: list[RiskScore] = []
    for s in all_scores:
        if s.model_id not in seen:
            seen.add(s.model_id)
            latest_per_model.append(s)

    # Determine trend per model using last 2 history entries
    portfolio_models = []
    for s in latest_per_model:
        hist = (
            db.query(RiskScoreHistory)
            .filter(
                RiskScoreHistory.model_id == s.model_id,
                RiskScoreHistory.organization_id == current_user.organization_id,
            )
            .order_by(RiskScoreHistory.computed_at.desc())
            .limit(2)
            .all()
        )
        trend = hist[0].trend if hist else "stable"
        portfolio_models.append({
            "model_id": s.model_id,
            "total_risk": s.total_risk,
            "risk_level": s.risk_level,
            "trend": trend,
            "computed_at": s.computed_at.isoformat(),
        })

    total_models = len(portfolio_models)
    avg_risk = (
        round(sum(m["total_risk"] for m in portfolio_models) / total_models, 2)
        if total_models else 0.0
    )
    by_level: dict = {}
    for m in portfolio_models:
        lvl = m["risk_level"]
        by_level[lvl] = by_level.get(lvl, 0) + 1

    return {
        "total_models": total_models,
        "avg_risk": avg_risk,
        "by_risk_level": by_level,
        "models": portfolio_models,
    }


@router.get("/risk/configuration")
def get_risk_configuration(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not has_permission(current_user.role, "risk_scores", "read"):
        raise HTTPException(403, "Forbidden")
    cfg = _get_org_config(db, current_user.organization_id)
    return _config_to_dict(cfg)


@router.post("/risk/configuration")
def upsert_risk_configuration(
    body: RiskConfigurationCreate,
    response: Response,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not has_permission(current_user.role, "risk_scores", "update"):
        raise HTTPException(403, "Forbidden")

    existing = db.query(RiskConfiguration).filter(
        RiskConfiguration.organization_id == current_user.organization_id
    ).first()

    now = datetime.utcnow()
    if existing:
        existing.regulatory_multiplier = body.regulatory_multiplier
        existing.critical_threshold = body.critical_threshold
        existing.high_threshold = body.high_threshold
        existing.medium_threshold = body.medium_threshold
        existing.updated_at = now
        db.commit()
        db.refresh(existing)
        response.status_code = 200
        return _config_to_dict(existing)
    else:
        cfg = RiskConfiguration(
            id=str(uuid.uuid4()),
            organization_id=current_user.organization_id,
            regulatory_multiplier=body.regulatory_multiplier,
            critical_threshold=body.critical_threshold,
            high_threshold=body.high_threshold,
            medium_threshold=body.medium_threshold,
            created_at=now,
            updated_at=now,
        )
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
        response.status_code = 201
        return _config_to_dict(cfg)


@router.post("/risk/scores", status_code=201)
def compute_and_store_risk_score(
    body: RiskScoreCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not has_permission(current_user.role, "risk_scores", "create"):
        raise HTTPException(403, "Forbidden")

    # Load org config for multiplier
    cfg = _get_org_config(db, current_user.organization_id)
    multiplier = cfg.regulatory_multiplier

    # Build domain objects
    sev_factors = SeverityFactors(
        patient_safety_impact=body.severity_factors.patient_safety_impact,
        data_sensitivity=body.severity_factors.data_sensitivity,
        model_confidence=body.severity_factors.model_confidence,
        bias_magnitude=body.severity_factors.bias_magnitude,
        drift_magnitude=body.severity_factors.drift_magnitude,
    )
    exp_factors = ExposureFactors(
        patient_volume=body.exposure_factors.patient_volume,
        decision_frequency=body.exposure_factors.decision_frequency,
        automation_level=body.exposure_factors.automation_level,
        data_access_breadth=body.exposure_factors.data_access_breadth,
    )
    reg_flags = RegulatoryFlags(
        hipaa=body.regulatory_flags.hipaa,
        fda_samd=body.regulatory_flags.fda_samd,
        cms_false_claims=body.regulatory_flags.cms_false_claims,
        onc_hti1=body.regulatory_flags.onc_hti1,
    )

    severity_score = compute_severity_score(sev_factors)
    exposure_score = compute_exposure_score(exp_factors)
    regulatory_penalty = compute_regulatory_penalty(reg_flags, multiplier=multiplier)
    total_risk = compute_total_risk(severity_score, exposure_score, regulatory_penalty)
    risk_level = risk_level_from_score(total_risk)

    now = datetime.utcnow()

    # Fetch previous score BEFORE adding new entry to avoid auto-flush issues
    prev_score = (
        db.query(RiskScore)
        .filter(
            RiskScore.model_id == body.model_id,
            RiskScore.organization_id == current_user.organization_id,
        )
        .order_by(RiskScore.computed_at.desc())
        .first()
    )
    prev_total = prev_score.total_risk if prev_score else None
    delta = (total_risk - prev_total) if prev_total is not None else None
    trend = _determine_trend(delta)

    score = RiskScore(
        id=str(uuid.uuid4()),
        organization_id=current_user.organization_id,
        model_id=body.model_id,
        agent_id=body.agent_id,
        severity_score=severity_score,
        exposure_score=exposure_score,
        regulatory_penalty=regulatory_penalty,
        total_risk=total_risk,
        risk_level=risk_level,
        severity_factors=body.severity_factors.model_dump(),
        exposure_factors=body.exposure_factors.model_dump(),
        regulatory_flags=body.regulatory_flags.model_dump(),
        org_multiplier=multiplier,
        computed_at=now,
        created_at=now,
    )
    db.add(score)

    # Write history entry
    history = RiskScoreHistory(
        id=str(uuid.uuid4()),
        organization_id=current_user.organization_id,
        model_id=body.model_id,
        total_risk=total_risk,
        risk_level=risk_level,
        delta=delta,
        trend=trend,
        computed_at=now,
    )
    db.add(history)
    db.commit()
    db.refresh(score)
    return _score_to_dict(score)


@router.get("/risk/scores/{model_id}/latest")
def get_latest_risk_score(
    model_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not has_permission(current_user.role, "risk_scores", "read"):
        raise HTTPException(403, "Forbidden")

    score = (
        db.query(RiskScore)
        .filter(
            RiskScore.model_id == model_id,
            RiskScore.organization_id == current_user.organization_id,
        )
        .order_by(RiskScore.computed_at.desc())
        .first()
    )
    if not score:
        raise HTTPException(404, "No risk score found for this model")
    return _score_to_dict(score)


@router.get("/risk/history/{model_id}")
def get_risk_score_history(
    model_id: str,
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not has_permission(current_user.role, "risk_scores", "read"):
        raise HTTPException(403, "Forbidden")

    entries = (
        db.query(RiskScoreHistory)
        .filter(
            RiskScoreHistory.model_id == model_id,
            RiskScoreHistory.organization_id == current_user.organization_id,
        )
        .order_by(RiskScoreHistory.computed_at.desc())
        .limit(limit)
        .all()
    )
    return [_history_to_dict(h) for h in entries]


@router.post("/risk/regulatory-mappings", status_code=201)
def add_regulatory_mapping(
    body: RegulatoryMappingCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not has_permission(current_user.role, "risk_scores", "create"):
        raise HTTPException(403, "Forbidden")

    if body.regulation not in _VALID_REGULATIONS:
        raise HTTPException(
            400,
            f"Invalid regulation '{body.regulation}'. Must be one of: {sorted(_VALID_REGULATIONS)}",
        )

    mapping = RiskRegulatoryMapping(
        id=str(uuid.uuid4()),
        organization_id=current_user.organization_id,
        model_id=body.model_id,
        regulation=body.regulation,
        applicable=body.applicable,
        created_at=datetime.utcnow(),
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return _mapping_to_dict(mapping)


@router.get("/risk/regulatory-mappings/{model_id}")
def list_regulatory_mappings(
    model_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not has_permission(current_user.role, "risk_scores", "read"):
        raise HTTPException(403, "Forbidden")

    mappings = db.query(RiskRegulatoryMapping).filter(
        RiskRegulatoryMapping.model_id == model_id,
        RiskRegulatoryMapping.organization_id == current_user.organization_id,
    ).all()
    return [_mapping_to_dict(m) for m in mappings]


@router.delete("/risk/regulatory-mappings/{mapping_id}", status_code=204)
def delete_regulatory_mapping(
    mapping_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not has_permission(current_user.role, "risk_scores", "delete"):
        raise HTTPException(403, "Forbidden")

    mapping = db.query(RiskRegulatoryMapping).filter(
        RiskRegulatoryMapping.id == mapping_id,
        RiskRegulatoryMapping.organization_id == current_user.organization_id,
    ).first()
    if not mapping:
        raise HTTPException(404, "Regulatory mapping not found")

    db.delete(mapping)
    db.commit()
