"""Tests for Tier 2 Sprint 1 transparency auto-generation on publish.

Covers:
  - Fresh model card → transparency draft created with templated summary,
    published_at=None, version_number=1, plus an initial TransparencyVersion
    snapshot.
  - Repeated publish for the same name+version → no duplicate, returns
    existing record_id.
  - Publish at a new version of an existing model name → record's version
    bumped, draft becomes pending review again, new TransparencyVersion row.
  - Performance summary filters out non-public metric keys.
"""
import uuid
from datetime import datetime

from policy_engine.models.model_card import ModelCard
from policy_engine.models.transparency import (
    TransparencyRecordModel,
    TransparencyVersion,
)
from policy_engine.services.transparency_auto_service import (
    auto_create_or_bump_transparency,
    generate_plain_language_summary,
)


def _make_card(
    db_session,
    *,
    name: str = "Sepsis Early Warning",
    version: str = "1.0",
    intended_use: str = (
        "Identify patients at high risk of sepsis within 6 hours of "
        "admission so clinicians can begin antibiotic and fluid therapy earlier"
    ),
    indications: str = "Adult inpatients (age 18-89) on general medical wards",
    contraindications: str = (
        "Pediatric patients, OB/GYN admissions, palliative care patients"
    ),
    performance_metrics: dict | None = None,
    bias_summary: dict | None = None,
) -> ModelCard:
    card = ModelCard(
        id=str(uuid.uuid4()),
        name=name,
        version=version,
        lifecycle_stage="published",
        intended_use=intended_use,
        clinical_indications=indications,
        contraindications=contraindications,
        training_data_source="MIMIC-IV v2.2",
        performance_metrics=performance_metrics or {
            "auc": 0.86,
            "sensitivity": 0.79,
            "internal_run_id": "run-9c1ad03",  # should be filtered out of public summary
        },
        bias_summary=bias_summary or {
            "max_disparity_ratio": 0.92,
            "subgroups": {"sex": {"male": 0.85, "female": 0.84}},
        },
        fda_status="510(k) cleared K223456",
        chai_version="2.0",
        organization_id="org-1",
        model_artifact_uri="mlflow://runs/abc/model",
        training_dataset_sha256="a" * 64,
        evaluation_dataset_sha256="b" * 64,
        external_validation={"sites": ["site-1", "site-2"], "n": 4200},
        monitoring_plan={"drift_baseline_id": "db-1", "cadence": "monthly"},
        pccp={"approved_changes": ["recalibration"]},
        created_by="user-1",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(card)
    db_session.commit()
    db_session.refresh(card)
    return card


def test_auto_create_creates_draft_transparency_record(db_session, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    card = _make_card(db_session)

    result = auto_create_or_bump_transparency(
        db_session, card, created_by="user-1"
    )

    assert result.created is True
    assert result.record_id is not None

    record = (
        db_session.query(TransparencyRecordModel)
        .filter_by(id=result.record_id)
        .first()
    )
    assert record is not None
    assert record.model_name == card.name
    assert record.model_version == card.version
    assert record.published_at is None  # Draft — not yet public
    assert record.version_number == 1
    assert record.organization_id == "org-1"
    assert len(record.plain_language_summary) >= 50
    assert record.regulatory_status == "510(k) cleared K223456"
    # Internal-only metric must NOT leak into public performance summary
    assert "internal_run_id" not in record.performance_summary
    assert record.performance_summary["auc"] == 0.86
    # Bias considerations should mention disparity ratio
    assert "0.92" in record.bias_considerations

    versions = (
        db_session.query(TransparencyVersion)
        .filter_by(record_id=record.id)
        .all()
    )
    assert len(versions) == 1
    assert versions[0].version_number == 1
    assert versions[0].content_snapshot["auto_generated_from_model_card"] == card.id


def test_auto_create_idempotent_for_same_name_and_version(db_session, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    card = _make_card(db_session)

    first = auto_create_or_bump_transparency(db_session, card, created_by="user-1")
    second = auto_create_or_bump_transparency(db_session, card, created_by="user-1")

    assert first.created is True
    assert second.created is False
    assert second.skipped_reason == "record_already_exists"
    assert second.record_id == first.record_id
    assert (
        db_session.query(TransparencyRecordModel)
        .filter_by(model_name=card.name)
        .count()
        == 1
    )


def test_auto_create_bumps_version_for_new_model_card_version(db_session, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    card_v1 = _make_card(db_session, name="Sepsis EW", version="1.0")
    first = auto_create_or_bump_transparency(db_session, card_v1, created_by="user-1")
    assert first.created is True

    # Now publish a v2 of the same model — the record should bump
    card_v2 = _make_card(db_session, name="Sepsis EW", version="2.0")
    second = auto_create_or_bump_transparency(db_session, card_v2, created_by="user-1")

    assert second.created is False
    assert second.bumped_existing_version is True
    assert second.record_id == first.record_id

    record = (
        db_session.query(TransparencyRecordModel)
        .filter_by(id=first.record_id)
        .first()
    )
    assert record.model_version == "2.0"
    assert record.version_number == 2
    assert record.published_at is None  # Bumped → must be re-reviewed

    versions = (
        db_session.query(TransparencyVersion)
        .filter_by(record_id=first.record_id)
        .order_by(TransparencyVersion.version_number)
        .all()
    )
    assert len(versions) == 2
    assert versions[0].version_number == 1
    assert versions[1].version_number == 2


def test_template_summary_used_when_no_anthropic_key(db_session, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    card = _make_card(db_session, name="Stroke Triage", version="1.0")

    summary = generate_plain_language_summary(card)

    assert "Stroke Triage" in summary
    # Template always mentions clinician oversight
    assert "clinician" in summary.lower() or "doctor" in summary.lower()
    assert len(summary) >= 50


def _admin_headers(db_session) -> dict:
    """Create a SYSTEM_ADMIN user and return auth headers (matches rbac.user_id contract)."""
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


def test_publish_endpoint_triggers_transparency_draft(client, db_session, monkeypatch):
    """End-to-end: POST /v1/clinical/model-cards/{id}/publish creates the draft."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    # This test focuses on transparency auto-create — bypass Sprint 3 bias gate
    # which is exercised in test_bias_audit_gate.py.
    monkeypatch.setenv("BIAS_AUDIT_PUBLISH_GATE", "false")
    headers = _admin_headers(db_session)

    create_resp = client.post(
        "/v1/clinical/model-cards",
        headers=headers,
        json={
            "name": "Pneumonia Triage",
            "version": "1.0",
            "intended_use": "Triage chest x-rays for pneumonia in ED adult patients",
            "clinical_indications": "Adult ED patients with respiratory complaints",
            "contraindications": "Pediatric patients, post-op imaging",
            "training_data_source": "CheXpert v1.0 Stanford",
            "performance_metrics": {"auc": 0.91, "sensitivity": 0.86},
            "bias_summary": {"max_disparity_ratio": 0.94},
            "fda_status": "510(k) cleared K987654",
            "model_artifact_uri": "mlflow://runs/xyz/model",
            "training_dataset_sha256": "c" * 64,
            "evaluation_dataset_sha256": "d" * 64,
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    card_id = create_resp.json()["id"]

    # DRAFT → REVIEW
    review_resp = client.post(
        f"/v1/clinical/model-cards/{card_id}/review",
        headers=headers,
    )
    assert review_resp.status_code == 200, review_resp.text

    # REVIEW → PUBLISHED
    publish_resp = client.post(
        f"/v1/clinical/model-cards/{card_id}/publish",
        headers=headers,
    )
    assert publish_resp.status_code == 200, publish_resp.text
    assert publish_resp.json()["lifecycle_stage"] == "published"

    # The transparency draft must now exist
    record = (
        db_session.query(TransparencyRecordModel)
        .filter_by(model_name="Pneumonia Triage", model_version="1.0")
        .first()
    )
    assert record is not None
    assert record.published_at is None
    assert record.version_number == 1
    assert "Pneumonia Triage" in record.plain_language_summary or "tool" in record.plain_language_summary.lower()
