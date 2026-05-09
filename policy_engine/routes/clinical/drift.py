"""Drift Detection endpoints — baselines, measurements, alerts."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Any, Dict, List, Optional
import uuid
from datetime import datetime

from policy_engine.database import get_db
from policy_engine.auth.api_key import get_current_agent
from policy_engine.auth.rbac import get_current_user
from policy_engine.models.user import User, has_permission
from policy_engine.models.drift import DriftBaseline, DriftMeasurementModel, DriftAlert
from policy_engine.domain.clinical.drift_detector import (
    population_stability_index,
    kolmogorov_smirnov_test,
    performance_drift_detected,
    severity_from_psi,
)
from policy_engine.services.drift_ingestion import ingest_inference_batch
from pydantic import BaseModel, Field

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class DriftBaselineCreate(BaseModel):
    model_id: str
    baseline_name: str
    feature_distributions: dict
    performance_baseline: dict
    organization_id: Optional[str] = None


class DriftMeasureRequest(BaseModel):
    baseline_id: str
    current_distributions: dict
    current_performance: dict


class DriftLogBatchRequest(BaseModel):
    """Tier 2 Sprint 5 — accepts batched inference records from the SDK
    `drift_logger`. Each record carries the model's input features (and
    optionally the prediction + ground truth + latency).

    Records are buffered server-side; the periodic recompute job converts the
    buffer into PSI / KS measurements and DriftAlerts.
    """

    baseline_id: str = Field(..., description="DriftBaseline ID to attach to")
    model_id: Optional[str] = None
    records: List[Dict[str, Any]] = Field(
        ..., min_length=1, max_length=5000,
        description="Inference records. Each must include `features` (dict).",
    )


class DriftBaselineResponse(BaseModel):
    id: str
    model_id: str
    baseline_name: str
    feature_distributions: dict
    performance_baseline: dict
    created_at: datetime
    organization_id: Optional[str] = None

    class Config:
        from_attributes = True


class DriftAlertResponse(BaseModel):
    id: str
    measurement_id: str
    alert_type: str
    severity: str
    message: str
    acknowledged: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_permission(current_user: User, action: str) -> None:
    if not has_permission(current_user.role, "drift_detection", action):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions to {action} drift_detection",
        )


def _to_baseline_response(b: DriftBaseline) -> dict:
    return {
        "id": b.id,
        "model_id": b.model_id,
        "baseline_name": b.baseline_name,
        "feature_distributions": b.feature_distributions or {},
        "performance_baseline": b.performance_baseline or {},
        "created_at": b.created_at,
        "organization_id": b.organization_id,
    }


def _to_alert_response(a: DriftAlert) -> dict:
    return {
        "id": a.id,
        "measurement_id": a.measurement_id,
        "alert_type": a.alert_type,
        "severity": a.severity,
        "message": a.message,
        "acknowledged": a.acknowledged,
        "created_at": a.created_at,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/drift/baselines", status_code=status.HTTP_201_CREATED)
def create_drift_baseline(
    payload: DriftBaselineCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_permission(current_user, "create")
    now = datetime.utcnow()
    baseline = DriftBaseline(
        id=str(uuid.uuid4()),
        model_id=payload.model_id,
        baseline_name=payload.baseline_name,
        feature_distributions=payload.feature_distributions,
        performance_baseline=payload.performance_baseline,
        organization_id=payload.organization_id,
        created_at=now,
    )
    db.add(baseline)
    db.commit()
    db.refresh(baseline)
    return _to_baseline_response(baseline)


@router.get("/drift/baselines", response_model=List[DriftBaselineResponse])
def list_drift_baselines(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_permission(current_user, "read")
    baselines = db.query(DriftBaseline).all()
    return [_to_baseline_response(b) for b in baselines]


@router.post("/drift/measure")
def measure_drift(
    payload: DriftMeasureRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Compute drift metrics vs baseline and create measurement + alerts."""
    _check_permission(current_user, "create")

    baseline = db.query(DriftBaseline).filter(DriftBaseline.id == payload.baseline_id).first()
    if not baseline:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Baseline not found")

    psi_scores = {}
    ks_scores = {}
    max_psi = 0.0

    baseline_dists = baseline.feature_distributions or {}
    current_dists = payload.current_distributions or {}

    for feature, current_vals in current_dists.items():
        baseline_vals = baseline_dists.get(feature, [])
        if baseline_vals and current_vals:
            psi = population_stability_index(
                [float(v) for v in baseline_vals],
                [float(v) for v in current_vals],
            )
            ks_stat, ks_p = kolmogorov_smirnov_test(
                [float(v) for v in baseline_vals],
                [float(v) for v in current_vals],
            )
            psi_scores[feature] = psi
            ks_scores[feature] = ks_p
            max_psi = max(max_psi, psi)

    # Check performance drift
    baseline_perf = baseline.performance_baseline or {}
    current_perf = payload.current_performance or {}
    perf_drift = False
    if "auroc" in baseline_perf and "auroc" in current_perf:
        perf_drift = performance_drift_detected(
            float(baseline_perf["auroc"]),
            float(current_perf["auroc"]),
        )

    drift_detected = max_psi > 0.1 or perf_drift
    severity = severity_from_psi(max_psi)

    now = datetime.utcnow()
    measurement = DriftMeasurementModel(
        id=str(uuid.uuid4()),
        baseline_id=payload.baseline_id,
        measurement_time=now,
        feature_distributions=current_dists,
        psi_scores={k: float(v) for k, v in psi_scores.items()},
        ks_scores={k: float(v) for k, v in ks_scores.items()},
        performance_current=current_perf,
        drift_detected=bool(drift_detected),
        drift_magnitude=float(max_psi),
    )
    db.add(measurement)
    db.flush()

    alerts_created = []
    if drift_detected:
        if max_psi > 0.1:
            alert = DriftAlert(
                id=str(uuid.uuid4()),
                measurement_id=measurement.id,
                alert_type="data_drift",
                severity=severity.value,
                message=f"Data drift detected. Max PSI: {max_psi:.4f}",
                acknowledged=False,
                created_at=now,
            )
            db.add(alert)
            alerts_created.append(alert.id)

        if perf_drift:
            perf_alert = DriftAlert(
                id=str(uuid.uuid4()),
                measurement_id=measurement.id,
                alert_type="performance_drift",
                severity="high",
                message=f"Performance drift detected. AUROC dropped from {baseline_perf.get('auroc')} to {current_perf.get('auroc')}",
                acknowledged=False,
                created_at=now,
            )
            db.add(perf_alert)
            alerts_created.append(perf_alert.id)

    db.commit()

    return {
        "measurement_id": measurement.id,
        "baseline_id": payload.baseline_id,
        "drift_detected": bool(drift_detected),
        "drift_magnitude": float(max_psi),
        "severity": severity.value,
        "psi_scores": {k: float(v) for k, v in psi_scores.items()},
        "ks_scores": {k: float(v) for k, v in ks_scores.items()},
        "alerts_created": len(alerts_created),
    }


@router.post("/drift/log-batch", status_code=status.HTTP_202_ACCEPTED)
def log_drift_batch(
    payload: DriftLogBatchRequest,
    db: Session = Depends(get_db),
    agent_id: str = Depends(get_current_agent),
):
    """Tier 2 Sprint 5 — SDK drift logger batch endpoint.

    Accepts batched inference records from production model servers and
    appends them to the rolling drift buffer. Returns immediately with
    `accepted` / `rejected` counts. The periodic background recompute job
    turns the buffer into measurements + alerts.

    Authenticated via SDK API key (`X-API-Key`).
    """
    outcome = ingest_inference_batch(
        db,
        baseline_id=payload.baseline_id,
        records=payload.records,
        model_id=payload.model_id,
    )
    if outcome.measurement_id is None and outcome.accepted == 0 and outcome.rejected:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DriftBaseline not found",
        )
    return {
        "baseline_id": payload.baseline_id,
        "accepted": outcome.accepted,
        "rejected": outcome.rejected,
        "buffer_measurement_id": outcome.measurement_id,
        "agent_id": agent_id,
    }


@router.get("/drift/alerts", response_model=List[DriftAlertResponse])
def list_drift_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_permission(current_user, "read")
    alerts = db.query(DriftAlert).all()
    return [_to_alert_response(a) for a in alerts]


@router.patch("/drift/alerts/{alert_id}/acknowledge")
def acknowledge_drift_alert(
    alert_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_permission(current_user, "update")
    alert = db.query(DriftAlert).filter(DriftAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    alert.acknowledged = True
    db.commit()
    db.refresh(alert)
    return _to_alert_response(alert)
