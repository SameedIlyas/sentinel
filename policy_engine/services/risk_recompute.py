"""Daily risk-portfolio recompute job.

Tier 2 Sprint 2 — turns the Risk Portfolio page from "what someone last
POSTed" to "live risk score per published model". Re-derives severity and
exposure factors from real signals (adverse events, drift, audit log volume,
bias audit results) and stores a fresh RiskScore row per published model.

Pure-Python implementation; deterministic given DB state. The scheduled job
runs once a day at 02:00 (configurable via env), but the function is also
callable from tests + an admin endpoint for on-demand recompute.
"""
from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from policy_engine.database import SessionLocal
from policy_engine.domain.regulatory.risk_scoring import (
    ExposureFactors,
    RegulatoryFlags,
    SeverityFactors,
    compute_exposure_score,
    compute_regulatory_penalty,
    compute_severity_score,
    compute_total_risk,
    risk_level_from_score,
)
from policy_engine.models.audit_log import AuditLog
from policy_engine.models.bias_audit import BiasAuditModel, BiasAuditResultModel
from policy_engine.models.drift import DriftAlert, DriftBaseline, DriftMeasurementModel
from policy_engine.models.model_card import ModelCard
from policy_engine.models.post_market import AdverseEvent, AdverseEventSeverityDB
from policy_engine.models.risk_score import (
    RiskConfiguration,
    RiskRegulatoryMapping,
    RiskScore,
    RiskScoreHistory,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _env_flag(name: str, default: bool = False) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.lower() in ("1", "true", "yes", "on")


def is_enabled() -> bool:
    """RISK_AUTO_RECOMPUTE=true to enable the daily background job."""
    return _env_flag("RISK_AUTO_RECOMPUTE", default=False)


def recompute_interval_seconds() -> float:
    """Default: 24 hours."""
    raw = os.environ.get("RISK_AUTO_RECOMPUTE_INTERVAL_SECONDS", "86400")
    try:
        value = float(raw)
        return max(300.0, value)
    except (TypeError, ValueError):
        return 86400.0


# ---------------------------------------------------------------------------
# Factor extractors — derive from real DB signals
# ---------------------------------------------------------------------------

# Map AdverseEvent severity → patient_safety_impact factor (1..10)
_SEVERITY_TO_FACTOR = {
    AdverseEventSeverityDB.LOW: 3.0,
    AdverseEventSeverityDB.MEDIUM: 5.0,
    AdverseEventSeverityDB.HIGH: 8.0,
    AdverseEventSeverityDB.CRITICAL: 10.0,
}

_OPEN_STATUSES = ("open", "investigating", "reported_to_fda")


def _compute_patient_safety_impact(db: Session, model_id: str) -> float:
    """Highest open adverse-event severity in the last 90 days, defaulting to 1.0."""
    cutoff = datetime.utcnow() - timedelta(days=90)
    events = (
        db.query(AdverseEvent)
        .filter(
            AdverseEvent.model_id == model_id,
            AdverseEvent.reported_at >= cutoff,
        )
        .all()
    )
    if not events:
        return 1.0

    weights = []
    for ev in events:
        weight = _SEVERITY_TO_FACTOR.get(ev.severity, 3.0)
        # Open or reported events count more than resolved
        status_value = ev.status.value if hasattr(ev.status, "value") else str(ev.status)
        if status_value in _OPEN_STATUSES:
            weight += 1.0
        weights.append(min(10.0, weight))
    return max(weights)


def _compute_bias_magnitude(db: Session, model_id: str) -> float:
    """Lowest passes_threshold disparity ratio across recent bias audits maps to bias factor.

    A disparity ratio of 1.0 (perfect) → 1.0 magnitude.
    A disparity ratio of 0.0 → 10.0 magnitude.
    """
    audits = (
        db.query(BiasAuditModel)
        .filter(
            BiasAuditModel.model_card_id == model_id,
            BiasAuditModel.status == "complete",
        )
        .order_by(BiasAuditModel.completed_at.desc())
        .limit(5)
        .all()
    )
    if not audits:
        return 1.0

    audit_ids = [a.id for a in audits]
    results = (
        db.query(BiasAuditResultModel)
        .filter(BiasAuditResultModel.audit_id.in_(audit_ids))
        .all()
    )
    if not results:
        return 1.0

    worst_ratio = min(r.disparity_ratio for r in results if r.disparity_ratio is not None)
    # Convert: ratio=1.0 → 1.0; ratio=0.5 → 5.5; ratio=0.0 → 10.0
    factor = 1.0 + (1.0 - max(0.0, min(1.0, worst_ratio))) * 9.0
    return min(10.0, max(1.0, factor))


def _compute_drift_magnitude(db: Session, model_id: str) -> float:
    """Use the highest unresolved DriftAlert severity in the last 30 days."""
    cutoff = datetime.utcnow() - timedelta(days=30)
    baselines = (
        db.query(DriftBaseline)
        .filter(DriftBaseline.model_id == model_id)
        .all()
    )
    if not baselines:
        return 1.0

    baseline_ids = [b.id for b in baselines]
    measurement_ids = [
        m.id
        for m in db.query(DriftMeasurementModel.id)
        .filter(DriftMeasurementModel.baseline_id.in_(baseline_ids))
        .all()
    ]
    if not measurement_ids:
        return 1.0

    alerts = (
        db.query(DriftAlert)
        .filter(
            DriftAlert.measurement_id.in_(measurement_ids),
            DriftAlert.created_at >= cutoff,
        )
        .all()
    )
    if not alerts:
        return 1.0

    severity_factor = {
        "low": 3.0, "medium": 5.0, "high": 8.0, "critical": 10.0,
    }
    return max(severity_factor.get((a.severity or "").lower(), 3.0) for a in alerts)


def _compute_decision_frequency(db: Session, model_id: str) -> float:
    """Map count of audit_log entries in the last 30 days to a 1..10 factor.

    0 decisions → 1.0
    1k decisions → ~5.0
    10k+ decisions → 10.0 (saturates)
    """
    cutoff = datetime.utcnow() - timedelta(days=30)
    count = (
        db.query(AuditLog)
        .filter(
            AuditLog.timestamp >= cutoff,
            AuditLog.log_metadata.isnot(None),
        )
        .count()
    )
    # Logarithmic-ish mapping
    if count <= 1:
        return 1.0
    import math
    return max(1.0, min(10.0, 1.0 + math.log10(count) * 2.5))


def _compute_automation_level(db: Session, model_id: str) -> float:
    """Ratio of allowed audit-log entries vs require_approval/blocked = automation level."""
    cutoff = datetime.utcnow() - timedelta(days=30)
    rows = (
        db.query(AuditLog.decision)
        .filter(AuditLog.timestamp >= cutoff)
        .all()
    )
    if not rows:
        return 1.0
    decisions = [r[0] for r in rows]
    auto = sum(1 for d in decisions if d == "allowed")
    total = len(decisions)
    if total == 0:
        return 1.0
    ratio = auto / total
    # ratio=0 → 1.0; ratio=1 → 10.0
    return max(1.0, min(10.0, 1.0 + ratio * 9.0))


def _compute_data_access_breadth(db: Session, model_id: str) -> float:
    """Count of distinct systems_accessed by audit logs in the last 30 days."""
    cutoff = datetime.utcnow() - timedelta(days=30)
    rows = (
        db.query(AuditLog.system_accessed)
        .filter(AuditLog.timestamp >= cutoff)
        .distinct()
        .all()
    )
    distinct_systems = len({r[0] for r in rows if r[0]})
    if distinct_systems == 0:
        return 1.0
    # 1 system → 2.0; 5 systems → 6.0; 10+ → 10.0
    return max(1.0, min(10.0, 1.0 + distinct_systems))


def _compute_data_sensitivity(card: ModelCard) -> float:
    """Pick from card metadata: clinical → 8, finance → 6, otherwise 4."""
    text = " ".join(filter(None, [
        card.intended_use, card.clinical_indications, card.training_data_source,
    ])).lower()
    if any(k in text for k in ("phi", "patient", "clinical", "medical", "diagnosis")):
        return 8.0
    if any(k in text for k in ("financial", "claim", "billing", "transaction")):
        return 6.0
    return 4.0


def _compute_model_confidence(card: ModelCard) -> float:
    """Pull AUC/accuracy from performance_metrics; default 5.0 when absent."""
    perf = card.performance_metrics or {}
    auc = perf.get("auc") or perf.get("auroc") or perf.get("accuracy")
    if auc is None:
        return 5.0
    try:
        value = float(auc)
    except (TypeError, ValueError):
        return 5.0
    # AUC 0.5 → 1.0; AUC 1.0 → 10.0
    return max(1.0, min(10.0, 1.0 + (value - 0.5) * 18.0))


def _regulatory_flags_for_model(
    db: Session, model_id: str, organization_id: Optional[str]
) -> RegulatoryFlags:
    """Read the per-model regulatory mapping from RiskRegulatoryMapping, if any."""
    rows = (
        db.query(RiskRegulatoryMapping)
        .filter(
            RiskRegulatoryMapping.model_id == model_id,
            RiskRegulatoryMapping.applicable.is_(True),
        )
        .all()
    )
    flags = RegulatoryFlags()
    for r in rows:
        if r.regulation == "hipaa":
            flags.hipaa = True
        elif r.regulation == "fda_samd":
            flags.fda_samd = True
        elif r.regulation == "cms_false_claims":
            flags.cms_false_claims = True
        elif r.regulation == "onc_hti1":
            flags.onc_hti1 = True
    return flags


def _multiplier_for_org(db: Session, organization_id: Optional[str]) -> float:
    if not organization_id:
        return 1.0
    cfg = (
        db.query(RiskConfiguration)
        .filter(RiskConfiguration.organization_id == organization_id)
        .first()
    )
    return cfg.regulatory_multiplier if cfg else 1.0


def _trend(prev: Optional[float], current: float) -> str:
    if prev is None:
        return "stable"
    delta = current - prev
    if delta > 1.0:
        return "up"
    if delta < -1.0:
        return "down"
    return "stable"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@dataclass
class RecomputeOutcome:
    cards_seen: int = 0
    scores_written: int = 0
    skipped_unpublished: int = 0
    errors: List[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []


def recompute_for_card(db: Session, card: ModelCard) -> Optional[RiskScore]:
    """Recompute and persist a fresh RiskScore for a single (published) model card.

    Returns the newly-created RiskScore row, or None if the card is unpublished.
    """
    if (card.lifecycle_stage or "").lower() != "published":
        return None

    sev_factors = SeverityFactors(
        patient_safety_impact=_compute_patient_safety_impact(db, card.id),
        data_sensitivity=_compute_data_sensitivity(card),
        model_confidence=_compute_model_confidence(card),
        bias_magnitude=_compute_bias_magnitude(db, card.id),
        drift_magnitude=_compute_drift_magnitude(db, card.id),
    )
    exp_factors = ExposureFactors(
        patient_volume=5.0,  # placeholder until patient_id correlation lands
        decision_frequency=_compute_decision_frequency(db, card.id),
        automation_level=_compute_automation_level(db, card.id),
        data_access_breadth=_compute_data_access_breadth(db, card.id),
    )
    flags = _regulatory_flags_for_model(db, card.id, card.organization_id)
    multiplier = _multiplier_for_org(db, card.organization_id)

    severity_score = compute_severity_score(sev_factors)
    exposure_score = compute_exposure_score(exp_factors)
    regulatory_penalty = compute_regulatory_penalty(flags, multiplier=multiplier)
    total = compute_total_risk(severity_score, exposure_score, regulatory_penalty)
    level = risk_level_from_score(total)

    now = datetime.utcnow()

    prev_score = (
        db.query(RiskScore)
        .filter(
            RiskScore.model_id == card.id,
            RiskScore.organization_id == card.organization_id,
        )
        .order_by(RiskScore.computed_at.desc())
        .first()
    )
    prev_total = prev_score.total_risk if prev_score else None

    score = RiskScore(
        id=str(uuid.uuid4()),
        organization_id=card.organization_id,
        model_id=card.id,
        agent_id=None,
        severity_score=severity_score,
        exposure_score=exposure_score,
        regulatory_penalty=regulatory_penalty,
        total_risk=total,
        risk_level=level,
        severity_factors={
            "patient_safety_impact": sev_factors.patient_safety_impact,
            "data_sensitivity": sev_factors.data_sensitivity,
            "model_confidence": sev_factors.model_confidence,
            "bias_magnitude": sev_factors.bias_magnitude,
            "drift_magnitude": sev_factors.drift_magnitude,
        },
        exposure_factors={
            "patient_volume": exp_factors.patient_volume,
            "decision_frequency": exp_factors.decision_frequency,
            "automation_level": exp_factors.automation_level,
            "data_access_breadth": exp_factors.data_access_breadth,
        },
        regulatory_flags={
            "hipaa": flags.hipaa,
            "fda_samd": flags.fda_samd,
            "cms_false_claims": flags.cms_false_claims,
            "onc_hti1": flags.onc_hti1,
        },
        org_multiplier=multiplier,
        computed_at=now,
        created_at=now,
    )
    db.add(score)

    db.add(RiskScoreHistory(
        id=str(uuid.uuid4()),
        organization_id=card.organization_id,
        model_id=card.id,
        total_risk=total,
        risk_level=level,
        delta=(total - prev_total) if prev_total is not None else None,
        trend=_trend(prev_total, total),
        computed_at=now,
    ))
    db.commit()
    return score


def recompute_all(*, db_factory: Optional[Any] = None) -> RecomputeOutcome:
    """Recompute risk for every published ModelCard. Idempotent per pass."""
    db_factory = db_factory or SessionLocal
    db = db_factory()
    outcome = RecomputeOutcome()
    try:
        cards = db.query(ModelCard).all()
        outcome.cards_seen = len(cards)
        for card in cards:
            try:
                score = recompute_for_card(db, card)
                if score is None:
                    outcome.skipped_unpublished += 1
                else:
                    outcome.scores_written += 1
            except Exception as exc:
                msg = f"recompute failed for card={card.id}: {exc}"
                outcome.errors.append(msg)
                logger.error(msg, exc_info=True)
                try:
                    db.rollback()
                except Exception:
                    pass
    finally:
        db.close()

    logger.info(
        "Risk recompute pass: cards=%d scores=%d skipped=%d errors=%d",
        outcome.cards_seen, outcome.scores_written,
        outcome.skipped_unpublished, len(outcome.errors),
    )
    return outcome


def make_recompute_job():
    """Build a zero-arg callable for the scheduler."""
    def _job() -> None:
        try:
            recompute_all()
        except Exception as exc:
            logger.error("Risk recompute job failed: %s", exc, exc_info=True)
    return _job
