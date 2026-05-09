"""Tests for Tier 2 Sprint 3 bias audit gate + equalized odds extension."""
import uuid
from datetime import datetime, timedelta

import pytest

from policy_engine.domain.clinical.bias_audit import (
    confusion_rates,
    run_bias_audit,
)
from policy_engine.models.bias_audit import BiasAuditModel, BiasAuditResultModel
from policy_engine.models.hitl import HITLReview
from policy_engine.models.model_card import ModelCard


# ---------------------------------------------------------------------------
# Domain — equalized odds extension
# ---------------------------------------------------------------------------

def test_confusion_rates_basic():
    predictions = [1, 0, 1, 1, 0, 0]
    labels =      [1, 0, 1, 0, 1, 0]
    indices = list(range(len(predictions)))
    tpr, fpr = confusion_rates(predictions, labels, indices)
    # Positives in labels: 3 (idx 0, 2, 4); model predicted positive on 0, 2 → TPR = 2/3
    # Negatives in labels: 3 (idx 1, 3, 5); model predicted positive on 3 → FPR = 1/3
    assert abs(tpr - 2/3) < 1e-9
    assert abs(fpr - 1/3) < 1e-9


def test_confusion_rates_empty_returns_zero():
    tpr, fpr = confusion_rates([1, 0], [1, 0], [])
    assert tpr == 0.0
    assert fpr == 0.0


def test_run_bias_audit_emits_demographic_parity_and_equalized_odds():
    # 4 samples — group A: heavy positives, group B: heavy negatives
    predictions = [1, 1, 0, 0]
    labels =      [1, 0, 1, 0]
    groups = {"sex": ["A", "A", "B", "B"]}

    results = run_bias_audit(predictions, labels, groups)

    metric_names = {r.metric_name for r in results}
    assert "disparate_impact_ratio" in metric_names
    assert "equalized_odds_tpr_ratio" in metric_names
    assert "equalized_odds_fpr_ratio" in metric_names

    # 2 subgroups × 3 metrics = 6 rows
    assert len(results) == 6


def test_run_bias_audit_can_disable_equalized_odds():
    predictions = [1, 0]
    labels = [1, 0]
    groups = {"sex": ["A", "B"]}

    results = run_bias_audit(
        predictions, labels, groups, include_equalized_odds=False
    )
    assert {r.metric_name for r in results} == {"disparate_impact_ratio"}


def test_run_bias_audit_passes_when_groups_balanced():
    predictions = [1, 1, 0, 0, 1, 1, 0, 0]
    labels =      [1, 0, 1, 0, 1, 0, 1, 0]
    groups = {"sex": ["A", "A", "A", "A", "B", "B", "B", "B"]}

    results = run_bias_audit(predictions, labels, groups)

    # Every result should pass — both groups have identical performance
    assert all(r.passes_80_percent_rule for r in results)


# ---------------------------------------------------------------------------
# Bias audit gate — publish endpoint enforcement
# ---------------------------------------------------------------------------

def _admin_headers(db_session) -> dict:
    from policy_engine.models.user import User, UserRole
    from policy_engine.auth.jwt_utils import create_access_token, get_password_hash

    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        username=f"admin_{user_id[:8]}",
        email=f"admin_{user_id[:8]}@test.local",
        password_hash=get_password_hash("TestPass123!"),
        role=UserRole.SYSTEM_ADMIN,
        full_name="Test Admin",
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(user)
    db_session.commit()

    token = create_access_token({
        "user_id": user_id,
        "username": user.username,
        "role": "system_admin",
    })
    return {
        "Authorization": f"Bearer {token}",
        "X-API-Key": "dummy-bypass-csrf",
    }


def _create_card_via_api(client, headers, name="Sepsis Triage") -> str:
    resp = client.post(
        "/v1/clinical/model-cards",
        headers=headers,
        json={
            "name": name,
            "version": "1.0",
            "intended_use": "Sepsis early warning for adult inpatients",
            "clinical_indications": "Adult ICU + general medical wards",
            "contraindications": "Pediatric patients",
            "training_data_source": "MIMIC-IV",
            "performance_metrics": {"auc": 0.86},
            "model_artifact_uri": "mlflow://x",
            "training_dataset_sha256": "a" * 64,
            "evaluation_dataset_sha256": "b" * 64,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_publish_blocked_without_recent_bias_audit(client, db_session, monkeypatch):
    monkeypatch.setenv("BIAS_AUDIT_PUBLISH_GATE", "true")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    headers = _admin_headers(db_session)

    card_id = _create_card_via_api(client, headers, "GateTestCard1")
    client.post(f"/v1/clinical/model-cards/{card_id}/review", headers=headers)

    resp = client.post(
        f"/v1/clinical/model-cards/{card_id}/publish",
        headers=headers,
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"] == "bias_audit_required"


def test_publish_blocked_when_bias_audit_has_failing_subgroups(
    client, db_session, monkeypatch
):
    monkeypatch.setenv("BIAS_AUDIT_PUBLISH_GATE", "true")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    headers = _admin_headers(db_session)

    card_id = _create_card_via_api(client, headers, "GateTestCard2")
    client.post(f"/v1/clinical/model-cards/{card_id}/review", headers=headers)

    # Insert a complete audit but with a failing subgroup
    now = datetime.utcnow()
    audit = BiasAuditModel(
        id=str(uuid.uuid4()),
        model_card_id=card_id,
        audit_name="audit-1",
        status="complete",
        organization_id=None,
        created_by="u",
        created_at=now,
        completed_at=now,
    )
    db_session.add(audit)
    db_session.add(BiasAuditResultModel(
        id=str(uuid.uuid4()),
        audit_id=audit.id,
        subgroup_id=None,
        metric_name="disparate_impact_ratio",
        metric_value=0.5,
        reference_value=1.0,
        disparity_ratio=0.5,
        passes_threshold=False,
        threshold_used=0.8,
    ))
    db_session.commit()

    resp = client.post(
        f"/v1/clinical/model-cards/{card_id}/publish",
        headers=headers,
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"] == "bias_audit_failing"


def test_publish_succeeds_with_recent_passing_bias_audit(
    client, db_session, monkeypatch
):
    monkeypatch.setenv("BIAS_AUDIT_PUBLISH_GATE", "true")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    headers = _admin_headers(db_session)

    card_id = _create_card_via_api(client, headers, "GateTestCard3")
    client.post(f"/v1/clinical/model-cards/{card_id}/review", headers=headers)

    now = datetime.utcnow()
    audit = BiasAuditModel(
        id=str(uuid.uuid4()),
        model_card_id=card_id,
        audit_name="audit-passing",
        status="complete",
        organization_id=None,
        created_by="u",
        created_at=now,
        completed_at=now,
    )
    db_session.add(audit)
    db_session.add(BiasAuditResultModel(
        id=str(uuid.uuid4()),
        audit_id=audit.id,
        subgroup_id=None,
        metric_name="disparate_impact_ratio",
        metric_value=0.95,
        reference_value=1.0,
        disparity_ratio=0.95,
        passes_threshold=True,
        threshold_used=0.8,
    ))
    db_session.commit()

    resp = client.post(
        f"/v1/clinical/model-cards/{card_id}/publish",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["lifecycle_stage"] == "published"


def test_publish_gate_bypass_via_env_flag(client, db_session, monkeypatch):
    monkeypatch.setenv("BIAS_AUDIT_PUBLISH_GATE", "false")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    headers = _admin_headers(db_session)

    card_id = _create_card_via_api(client, headers, "GateTestCard4")
    client.post(f"/v1/clinical/model-cards/{card_id}/review", headers=headers)

    resp = client.post(
        f"/v1/clinical/model-cards/{card_id}/publish",
        headers=headers,
    )
    # No bias audit exists, but gate is disabled → publish proceeds
    assert resp.status_code == 200, resp.text


def test_old_bias_audit_does_not_satisfy_gate(client, db_session, monkeypatch):
    monkeypatch.setenv("BIAS_AUDIT_PUBLISH_GATE", "true")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    headers = _admin_headers(db_session)

    card_id = _create_card_via_api(client, headers, "GateTestCard5")
    client.post(f"/v1/clinical/model-cards/{card_id}/review", headers=headers)

    # Audit is too old (> 90 days)
    old_date = datetime.utcnow() - timedelta(days=120)
    db_session.add(BiasAuditModel(
        id=str(uuid.uuid4()),
        model_card_id=card_id,
        audit_name="audit-old",
        status="complete",
        organization_id=None,
        created_by="u",
        created_at=old_date,
        completed_at=old_date,
    ))
    db_session.commit()

    resp = client.post(
        f"/v1/clinical/model-cards/{card_id}/publish",
        headers=headers,
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"] == "bias_audit_required"


# ---------------------------------------------------------------------------
# HITL auto-create on bias audit failure
# ---------------------------------------------------------------------------

def test_run_bias_audit_creates_hitl_review_on_failure(
    client, db_session, monkeypatch
):
    headers = _admin_headers(db_session)

    # Create a card
    card_id = _create_card_via_api(client, headers, "HITLBiasFailCard")

    # Create a bias audit row
    audit_resp = client.post(
        "/v1/clinical/bias-audits",
        headers=headers,
        json={
            "audit_name": "fail-test",
            "model_card_id": card_id,
            "dataset_description": "synthetic test data",
        },
    )
    assert audit_resp.status_code == 201, audit_resp.text
    audit_id = audit_resp.json()["id"]

    # Heavily skewed predictions → fails 80% rule for sex:B
    run_resp = client.post(
        f"/v1/clinical/bias-audits/{audit_id}/run",
        headers=headers,
        json={
            "predictions": [1, 1, 1, 1, 0, 0, 0, 0],
            "labels":      [1, 1, 0, 0, 1, 1, 0, 0],
            "groups": {"sex": ["A", "A", "A", "A", "B", "B", "B", "B"]},
        },
    )
    assert run_resp.status_code == 200, run_resp.text
    body = run_resp.json()
    assert body["status"] == "complete"
    assert body["failing_subgroups"] >= 1
    assert body["hitl_review_id"] is not None

    review = (
        db_session.query(HITLReview)
        .filter_by(id=body["hitl_review_id"])
        .first()
    )
    assert review is not None
    assert "fail-test" in review.title
    assert review.priority in ("high", "urgent")
    assert review.ai_decision["source"] == "bias_audit_failure"
