"""Tests for the daily risk-portfolio recompute service (Sprint 2 task #4)."""
import uuid
from datetime import datetime, timedelta

from policy_engine.models.audit_log import AuditLog
from policy_engine.models.bias_audit import BiasAuditModel, BiasAuditResultModel
from policy_engine.models.drift import DriftAlert, DriftBaseline, DriftMeasurementModel
from policy_engine.models.model_card import ModelCard
from policy_engine.models.post_market import (
    AdverseEvent,
    AdverseEventSeverityDB,
    AdverseEventStatusDB,
)
from policy_engine.models.risk_score import (
    RiskRegulatoryMapping,
    RiskScore,
    RiskScoreHistory,
)
from policy_engine.services.risk_recompute import (
    is_enabled,
    recompute_all,
    recompute_for_card,
)


def _published_card(db_session, *, name="m1") -> ModelCard:
    now = datetime.utcnow()
    card = ModelCard(
        id=str(uuid.uuid4()),
        name=name,
        version="1.0",
        lifecycle_stage="published",
        intended_use="Clinical decision support for adult inpatients",
        clinical_indications="Adult inpatients on general medical wards",
        contraindications="Pediatric patients, palliative care",
        training_data_source="MIMIC-IV",
        performance_metrics={"auc": 0.85},
        bias_summary={},
        chai_version="2.0",
        organization_id="org-1",
        model_artifact_uri="mlflow://x",
        training_dataset_sha256="a" * 64,
        evaluation_dataset_sha256="b" * 64,
        external_validation={},
        monitoring_plan={},
        pccp={},
        created_by="u",
        created_at=now,
        updated_at=now,
    )
    db_session.add(card)
    db_session.commit()
    return card


def _draft_card(db_session, *, name="m-draft") -> ModelCard:
    now = datetime.utcnow()
    card = ModelCard(
        id=str(uuid.uuid4()),
        name=name,
        version="1.0",
        lifecycle_stage="draft",
        chai_version="2.0",
        organization_id="org-1",
        performance_metrics={},
        bias_summary={},
        external_validation={},
        monitoring_plan={},
        pccp={},
        created_by="u",
        created_at=now,
        updated_at=now,
    )
    db_session.add(card)
    db_session.commit()
    return card


def _add_audit_log(db_session, *, decision: str, system: str = "ehr") -> None:
    db_session.add(AuditLog(
        id=str(uuid.uuid4()),
        agent_id="agent-1",
        agent_name="Agent 1",
        user_id="u",
        tool_name="t",
        arguments={},
        system_accessed=system,
        data_touched=[],
        decision=decision,
        policy_ids=[],
        reason="r",
        log_metadata={},
        timestamp=datetime.utcnow(),
    ))
    db_session.commit()


def test_recompute_skips_unpublished_card(db_session):
    card = _draft_card(db_session)

    score = recompute_for_card(db_session, card)

    assert score is None
    assert db_session.query(RiskScore).count() == 0


def test_recompute_writes_score_for_published_card(db_session):
    card = _published_card(db_session)

    score = recompute_for_card(db_session, card)

    assert score is not None
    assert score.model_id == card.id
    assert score.organization_id == "org-1"
    assert 1.0 <= score.total_risk <= 100.0
    assert score.risk_level in ("low", "medium", "high", "critical")
    assert score.severity_factors["data_sensitivity"] == 8.0  # clinical text
    # AUC=0.85 → model_confidence ≈ 7.3
    assert score.severity_factors["model_confidence"] > 5.0

    history = (
        db_session.query(RiskScoreHistory)
        .filter_by(model_id=card.id)
        .all()
    )
    assert len(history) == 1
    # First score → no prior, delta None
    assert history[0].delta is None
    assert history[0].trend == "stable"


def test_recompute_picks_highest_adverse_event_severity(db_session):
    card = _published_card(db_session)
    now = datetime.utcnow()
    db_session.add(AdverseEvent(
        id=str(uuid.uuid4()),
        organization_id="org-1",
        model_id=card.id,
        event_type="misdiagnosis",
        severity=AdverseEventSeverityDB.CRITICAL,
        description="Severe outcome",
        status=AdverseEventStatusDB.OPEN,
        reported_at=now,
        created_at=now,
    ))
    db_session.commit()

    score = recompute_for_card(db_session, card)
    # CRITICAL=10.0 + open(+1.0, capped at 10) → 10.0
    assert score.severity_factors["patient_safety_impact"] == 10.0
    # Severity factor lifts the score, but final level also depends on exposure.
    # Re-running with no exposure produces a small total — that's expected.
    assert score.severity_score >= 4.5


def test_recompute_uses_bias_audit_results(db_session):
    card = _published_card(db_session)
    now = datetime.utcnow()
    audit = BiasAuditModel(
        id=str(uuid.uuid4()),
        model_card_id=card.id,
        audit_name="audit-1",
        status="complete",
        organization_id="org-1",
        created_by="u",
        created_at=now,
        completed_at=now,
    )
    db_session.add(audit)
    db_session.add(BiasAuditResultModel(
        id=str(uuid.uuid4()),
        audit_id=audit.id,
        subgroup_id=None,
        metric_name="demographic_parity",
        metric_value=0.6,
        reference_value=1.0,
        disparity_ratio=0.5,  # poor fairness
        passes_threshold=False,
        threshold_used=0.8,
    ))
    db_session.commit()

    score = recompute_for_card(db_session, card)
    # disparity_ratio=0.5 → factor = 1.0 + 0.5 * 9.0 = 5.5
    assert 5.0 <= score.severity_factors["bias_magnitude"] <= 6.0


def test_recompute_uses_drift_alerts(db_session):
    card = _published_card(db_session)
    now = datetime.utcnow()

    baseline = DriftBaseline(
        id=str(uuid.uuid4()),
        model_id=card.id,
        baseline_name="baseline-1",
        feature_distributions={},
        performance_baseline={},
        organization_id="org-1",
        created_at=now,
    )
    db_session.add(baseline)
    measurement = DriftMeasurementModel(
        id=str(uuid.uuid4()),
        baseline_id=baseline.id,
        measurement_time=now,
        feature_distributions={},
        psi_scores={},
        ks_scores={},
        performance_current={},
        drift_detected=True,
        drift_magnitude=0.7,
    )
    db_session.add(measurement)
    db_session.add(DriftAlert(
        id=str(uuid.uuid4()),
        measurement_id=measurement.id,
        alert_type="psi_breach",
        severity="critical",
        message="PSI > 0.5",
        created_at=now,
    ))
    db_session.commit()

    score = recompute_for_card(db_session, card)
    assert score.severity_factors["drift_magnitude"] == 10.0  # critical


def test_recompute_applies_regulatory_flags(db_session):
    card = _published_card(db_session)
    now = datetime.utcnow()
    for reg in ("hipaa", "fda_samd"):
        db_session.add(RiskRegulatoryMapping(
            id=str(uuid.uuid4()),
            organization_id="org-1",
            model_id=card.id,
            regulation=reg,
            applicable=True,
            created_at=now,
        ))
    db_session.commit()

    score = recompute_for_card(db_session, card)
    # HIPAA (50k) + FDA SAMD (100k) = 150k / 25k = 6.0 penalty
    assert score.regulatory_flags["hipaa"] is True
    assert score.regulatory_flags["fda_samd"] is True
    assert 5.5 <= score.regulatory_penalty <= 6.5


def test_recompute_history_captures_trend(db_session):
    card = _published_card(db_session)

    first = recompute_for_card(db_session, card)
    # Drive risk UP by adding a critical adverse event
    now = datetime.utcnow()
    db_session.add(AdverseEvent(
        id=str(uuid.uuid4()),
        organization_id="org-1",
        model_id=card.id,
        event_type="x",
        severity=AdverseEventSeverityDB.CRITICAL,
        description="x",
        status=AdverseEventStatusDB.OPEN,
        reported_at=now,
        created_at=now,
    ))
    db_session.commit()

    second = recompute_for_card(db_session, card)
    assert second.total_risk > first.total_risk

    histories = (
        db_session.query(RiskScoreHistory)
        .filter_by(model_id=card.id)
        .order_by(RiskScoreHistory.computed_at)
        .all()
    )
    assert len(histories) == 2
    assert histories[1].delta is not None
    assert histories[1].delta > 0
    assert histories[1].trend == "up"


def test_recompute_all_iterates_every_published_card(db_session, monkeypatch):
    _published_card(db_session, name="m1")
    _published_card(db_session, name="m2")
    _draft_card(db_session, name="m-draft")

    monkeypatch.setattr(db_session, "close", lambda: None)
    outcome = recompute_all(db_factory=lambda: db_session)

    assert outcome.cards_seen == 3
    assert outcome.scores_written == 2
    assert outcome.skipped_unpublished == 1
    assert outcome.errors == []


def test_is_enabled_reads_env(monkeypatch):
    monkeypatch.delenv("RISK_AUTO_RECOMPUTE", raising=False)
    assert is_enabled() is False
    monkeypatch.setenv("RISK_AUTO_RECOMPUTE", "true")
    assert is_enabled() is True
