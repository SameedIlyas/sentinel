"""Server-side drift inference ingestion + periodic recompute.

Tier 2 Sprint 5 — companion to `sentinel.sdk.drift_logger`. Receives batches
of raw inference records, persists them as a rolling buffer attached to a
DriftBaseline, and runs scheduled recomputation that converts the buffered
distributions into PSI / KS measurements + alerts.

Storage strategy:
  - Each raw batch is appended into a `DriftMeasurement` row's
    `feature_distributions` JSON column under a `_raw_records` key.
  - The recompute job groups raw records since the last "computed" measurement,
    computes per-feature PSI vs the baseline, KS p-values, and writes a fresh
    DriftMeasurement + (when over threshold) DriftAlert.

For the demo workload this is fine. A production deployment would route raw
records to an analytical store (ClickHouse, BigQuery, Athena) and run the
recompute against that — same downstream interface.
"""
from __future__ import annotations

import logging
import os
import statistics
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from policy_engine.database import SessionLocal
from policy_engine.domain.clinical.drift_detector import (
    kolmogorov_smirnov_test,
    population_stability_index,
    severity_from_psi,
)
from policy_engine.models.drift import (
    DriftAlert,
    DriftBaseline,
    DriftMeasurementModel,
)
from policy_engine.services.hitl_auto_service import create_hitl_review

logger = logging.getLogger(__name__)


PSI_ALERT_THRESHOLD = 0.2  # 0.1 = small drift, 0.2 = significant
KS_ALERT_THRESHOLD = 0.01  # KS test p-value


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _env_flag(name: str, default: bool = False) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.lower() in ("1", "true", "yes", "on")


def is_recompute_enabled() -> bool:
    return _env_flag("DRIFT_AUTO_RECOMPUTE", default=False)


def recompute_interval_seconds() -> float:
    raw = os.environ.get("DRIFT_AUTO_RECOMPUTE_INTERVAL_SECONDS", "21600")  # 6h
    try:
        return max(300.0, float(raw))
    except (TypeError, ValueError):
        return 21600.0


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

@dataclass
class IngestOutcome:
    accepted: int = 0
    rejected: int = 0
    measurement_id: Optional[str] = None


def ingest_inference_batch(
    db: Session,
    *,
    baseline_id: str,
    records: List[Dict[str, Any]],
    model_id: Optional[str] = None,
) -> IngestOutcome:
    """Persist raw inference records into a buffering DriftMeasurement.

    The records are stored under feature_distributions["_raw_records"]; the
    next scheduled recompute pass will turn them into per-feature PSI/KS
    measurements + alerts.

    Returns IngestOutcome with counts and the measurement_id of the buffer.
    """
    outcome = IngestOutcome()

    baseline = (
        db.query(DriftBaseline).filter(DriftBaseline.id == baseline_id).first()
    )
    if not baseline:
        outcome.rejected = len(records)
        return outcome

    # Filter records — must have a `features` dict
    valid: List[Dict[str, Any]] = []
    for r in records:
        if not isinstance(r, dict):
            outcome.rejected += 1
            continue
        if not isinstance(r.get("features"), dict):
            outcome.rejected += 1
            continue
        valid.append(r)
    outcome.accepted = len(valid)
    if not valid:
        return outcome

    # Find or create the open buffer measurement for this baseline
    buffer = (
        db.query(DriftMeasurementModel)
        .filter(
            DriftMeasurementModel.baseline_id == baseline_id,
            DriftMeasurementModel.drift_detected.is_(False),
            # Recognise buffer rows by a sentinel key in feature_distributions
        )
        .order_by(DriftMeasurementModel.measurement_time.desc())
        .first()
    )

    if buffer is not None and not (buffer.feature_distributions or {}).get(
        "_buffer", False
    ):
        buffer = None

    now = datetime.utcnow()
    if buffer is None:
        buffer = DriftMeasurementModel(
            id=str(uuid.uuid4()),
            baseline_id=baseline_id,
            measurement_time=now,
            feature_distributions={"_buffer": True, "_raw_records": []},
            psi_scores={},
            ks_scores={},
            performance_current={},
            drift_detected=False,
            drift_magnitude=0.0,
        )
        db.add(buffer)
        db.flush()

    existing = (buffer.feature_distributions or {}).get("_raw_records", [])
    new_distribution = {
        "_buffer": True,
        "_raw_records": existing + valid,
    }
    buffer.feature_distributions = new_distribution
    buffer.measurement_time = now
    db.commit()

    outcome.measurement_id = buffer.id
    return outcome


# ---------------------------------------------------------------------------
# Recompute
# ---------------------------------------------------------------------------

@dataclass
class RecomputeOutcome:
    baselines_seen: int = 0
    measurements_computed: int = 0
    alerts_created: int = 0
    hitl_reviews_created: int = 0
    errors: List[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []


def _coerce_float_list(values: List[Any]) -> List[float]:
    out: List[float] = []
    for v in values:
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            continue
    return out


def _features_per_record(records: List[Dict[str, Any]]) -> Dict[str, List[float]]:
    """Flip from list[record] to dict[feature_name, list[value]] (numerics only)."""
    by_feature: Dict[str, List[float]] = defaultdict(list)
    for record in records:
        feats = record.get("features") or {}
        for key, value in feats.items():
            try:
                by_feature[key].append(float(value))
            except (TypeError, ValueError):
                continue
    return dict(by_feature)


def _baseline_distributions(baseline: DriftBaseline) -> Dict[str, List[float]]:
    out: Dict[str, List[float]] = {}
    for feature, values in (baseline.feature_distributions or {}).items():
        if isinstance(values, list):
            floats = _coerce_float_list(values)
            if floats:
                out[feature] = floats
    return out


def recompute_drift_for_baseline(
    db: Session, baseline: DriftBaseline
) -> Optional[DriftMeasurementModel]:
    """Convert the open buffer for `baseline` into a real DriftMeasurement."""
    buffer = (
        db.query(DriftMeasurementModel)
        .filter(DriftMeasurementModel.baseline_id == baseline.id)
        .order_by(DriftMeasurementModel.measurement_time.desc())
        .first()
    )
    if buffer is None or not (buffer.feature_distributions or {}).get("_buffer"):
        return None

    raw = buffer.feature_distributions.get("_raw_records", [])
    if not raw:
        return None

    current_dists = _features_per_record(raw)
    baseline_dists = _baseline_distributions(baseline)

    psi_scores: Dict[str, float] = {}
    ks_scores: Dict[str, float] = {}
    max_psi = 0.0
    min_ks_p = 1.0

    for feature, current_values in current_dists.items():
        baseline_values = baseline_dists.get(feature)
        if not baseline_values or not current_values:
            continue
        psi = population_stability_index(baseline_values, current_values)
        try:
            _, ks_p = kolmogorov_smirnov_test(baseline_values, current_values)
        except Exception:
            ks_p = 1.0
        psi_scores[feature] = float(psi)
        ks_scores[feature] = float(ks_p)
        max_psi = max(max_psi, psi)
        min_ks_p = min(min_ks_p, ks_p)

    drift_detected = (max_psi > PSI_ALERT_THRESHOLD) or (
        min_ks_p < KS_ALERT_THRESHOLD
    )
    severity = severity_from_psi(max_psi)
    now = datetime.utcnow()

    # Convert the buffer into a real measurement
    buffer.feature_distributions = {
        f: current_dists[f][-100:] for f in current_dists  # keep tail for audit
    }
    buffer.psi_scores = psi_scores
    buffer.ks_scores = ks_scores
    buffer.measurement_time = now
    buffer.drift_detected = bool(drift_detected)
    buffer.drift_magnitude = float(max_psi)

    # Compute simple performance signal — fraction of predictions vs baseline
    # mean prediction (when ground truth absent we just track drift on inputs).
    db.flush()

    return buffer


def recompute_all(*, db_factory: Optional[Any] = None) -> RecomputeOutcome:
    db_factory = db_factory or SessionLocal
    db = db_factory()
    outcome = RecomputeOutcome()
    try:
        baselines = db.query(DriftBaseline).all()
        outcome.baselines_seen = len(baselines)
        for baseline in baselines:
            try:
                measurement = recompute_drift_for_baseline(db, baseline)
                if measurement is None:
                    continue
                outcome.measurements_computed += 1

                if measurement.drift_detected:
                    severity = severity_from_psi(measurement.drift_magnitude).value
                    alert = DriftAlert(
                        id=str(uuid.uuid4()),
                        measurement_id=measurement.id,
                        alert_type="data_drift",
                        severity=severity,
                        message=(
                            f"Auto drift recompute: max PSI = "
                            f"{measurement.drift_magnitude:.4f}"
                        ),
                        acknowledged=False,
                        created_at=datetime.utcnow(),
                    )
                    db.add(alert)
                    db.commit()
                    outcome.alerts_created += 1

                    review_id = create_hitl_review(
                        db,
                        title=(
                            f"Drift alert: model {baseline.model_id} "
                            f"PSI={measurement.drift_magnitude:.3f}"
                        ),
                        description=(
                            "Auto drift-recompute detected significant feature "
                            "distribution shift. Highest PSI / lowest KS feature "
                            "is in the linked DriftMeasurement. Investigate root "
                            "cause and either retrain or update baseline."
                        ),
                        ai_decision={
                            "source": "drift_auto_recompute",
                            "baseline_id": baseline.id,
                            "model_id": baseline.model_id,
                            "measurement_id": measurement.id,
                            "max_psi": measurement.drift_magnitude,
                            "psi_scores": measurement.psi_scores,
                            "ks_scores": measurement.ks_scores,
                        },
                        risk_score=80.0 if severity in ("high", "critical") else 60.0,
                        priority="urgent" if severity == "critical" else "high",
                        organization_id=baseline.organization_id,
                        actor_id="system:drift_recompute",
                        seed_action="drift_auto_alert",
                    )
                    if review_id:
                        outcome.hitl_reviews_created += 1
                else:
                    db.commit()
            except Exception as exc:
                msg = f"recompute failed baseline={baseline.id}: {exc}"
                outcome.errors.append(msg)
                logger.error(msg, exc_info=True)
                try:
                    db.rollback()
                except Exception:
                    pass
    finally:
        db.close()

    logger.info(
        "Drift recompute pass: baselines=%d measurements=%d alerts=%d hitl=%d errors=%d",
        outcome.baselines_seen, outcome.measurements_computed,
        outcome.alerts_created, outcome.hitl_reviews_created, len(outcome.errors),
    )
    return outcome


def make_recompute_job():
    def _job() -> None:
        try:
            recompute_all()
        except Exception as exc:
            logger.error("Drift recompute job failed: %s", exc, exc_info=True)
    return _job
