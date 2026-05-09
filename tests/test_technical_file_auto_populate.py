"""Tests for Tier 2 Sprint 4 technical file auto-population."""
import uuid
from datetime import datetime, timedelta

from policy_engine.models.bias_audit import BiasAuditModel, BiasAuditResultModel
from policy_engine.models.model_card import ModelCard
from policy_engine.models.post_market import (
    AdverseEvent,
    AdverseEventSeverityDB,
    AdverseEventStatusDB,
)
from policy_engine.models.technical_file import (
    RegulatoryTypeDB,
    TechnicalFile,
    TechnicalFileLifecycleDB,
    TechnicalFileSection,
)
from policy_engine.services.technical_file_auto_service import (
    SECTION_CLINICAL_EVALUATION,
    SECTION_DEVICE_DESCRIPTION,
    SECTION_INTENDED_USE,
    SECTION_PERFORMANCE_DATA,
    SECTION_PMS_PLAN,
    SECTION_RISK_MANAGEMENT,
    populate_from_model_card,
)


def _card(db_session, *, name="Sepsis EW") -> ModelCard:
    now = datetime.utcnow()
    card = ModelCard(
        id=str(uuid.uuid4()),
        name=name,
        version="1.0",
        lifecycle_stage="published",
        intended_use="Sepsis early warning for adult inpatients",
        clinical_indications="ICU + general medical wards",
        contraindications="Pediatric patients, palliative care",
        training_data_source="MIMIC-IV v2.2",
        performance_metrics={"auc": 0.86, "sensitivity": 0.79},
        bias_summary={"max_disparity_ratio": 0.92},
        fda_status="510(k) cleared K223456",
        chai_version="2.0",
        organization_id="org-1",
        model_artifact_uri="mlflow://x",
        training_dataset_sha256="a" * 64,
        evaluation_dataset_sha256="b" * 64,
        framework_version="PyTorch 2.1",
        external_validation={"sites": ["s1", "s2"], "n": 4200},
        monitoring_plan={"cadence": "monthly", "drift_baseline_id": "db-1"},
        pccp={"approved_changes": ["recalibration"]},
        created_by="u",
        created_at=now,
        updated_at=now,
    )
    db_session.add(card)
    db_session.commit()
    return card


def _tf(db_session, *, regulatory_type=RegulatoryTypeDB.FDA_510K) -> TechnicalFile:
    now = datetime.utcnow()
    tf = TechnicalFile(
        id=str(uuid.uuid4()),
        title="Sepsis 510(k)",
        regulatory_type=regulatory_type,
        product_name="Sepsis EW",
        device_version="1.0",
        lifecycle_stage=TechnicalFileLifecycleDB.DRAFT,
        organization_id="org-1",
        created_by="u",
        created_at=now,
        updated_at=now,
    )
    db_session.add(tf)
    db_session.commit()
    return tf


def test_populate_from_model_card_creates_fda_510k_sections(db_session):
    card = _card(db_session)
    tf = _tf(db_session, regulatory_type=RegulatoryTypeDB.FDA_510K)

    outcome = populate_from_model_card(
        db_session,
        technical_file_id=tf.id,
        model_card_id=card.id,
    )

    assert outcome.errors == []
    assert outcome.sections_created == 6  # 510(k) has 6 sections

    sections = (
        db_session.query(TechnicalFileSection)
        .filter_by(file_id=tf.id)
        .order_by(TechnicalFileSection.order_index)
        .all()
    )
    section_types = [s.section_type for s in sections]
    assert SECTION_DEVICE_DESCRIPTION in section_types
    assert SECTION_INTENDED_USE in section_types
    assert SECTION_PERFORMANCE_DATA in section_types
    assert SECTION_RISK_MANAGEMENT in section_types
    assert SECTION_CLINICAL_EVALUATION in section_types
    assert SECTION_PMS_PLAN not in section_types  # only EU MDR
    assert all(s.auto_generated is True for s in sections)


def test_populate_eu_mdr_includes_pms_sections(db_session):
    card = _card(db_session)
    tf = _tf(db_session, regulatory_type=RegulatoryTypeDB.EU_MDR)

    outcome = populate_from_model_card(
        db_session,
        technical_file_id=tf.id,
        model_card_id=card.id,
    )

    assert outcome.sections_created == 8  # 6 base + PMS plan + clinical evidence

    section_types = {
        s.section_type
        for s in db_session.query(TechnicalFileSection)
        .filter_by(file_id=tf.id)
        .all()
    }
    assert SECTION_PMS_PLAN in section_types


def test_populate_does_not_overwrite_human_authored_sections(db_session):
    card = _card(db_session)
    tf = _tf(db_session)

    # Pre-existing human-authored intended_use section
    now = datetime.utcnow()
    db_session.add(TechnicalFileSection(
        id=str(uuid.uuid4()),
        file_id=tf.id,
        section_type=SECTION_INTENDED_USE,
        content="HUMAN-AUTHORED CONTENT",
        order_index=99,
        auto_generated=False,
        created_at=now,
        updated_at=now,
    ))
    db_session.commit()

    outcome = populate_from_model_card(
        db_session,
        technical_file_id=tf.id,
        model_card_id=card.id,
    )

    intended = (
        db_session.query(TechnicalFileSection)
        .filter_by(file_id=tf.id, section_type=SECTION_INTENDED_USE)
        .first()
    )
    assert intended.content == "HUMAN-AUTHORED CONTENT"
    assert intended.auto_generated is False
    assert outcome.sections_skipped >= 1


def test_populate_overwrites_auto_generated_sections_when_overwrite_true(db_session):
    card = _card(db_session)
    tf = _tf(db_session)

    populate_from_model_card(
        db_session,
        technical_file_id=tf.id,
        model_card_id=card.id,
    )

    # Mutate the card and re-populate with overwrite
    card.intended_use = "UPDATED intended_use after re-validation"
    db_session.commit()

    outcome = populate_from_model_card(
        db_session,
        technical_file_id=tf.id,
        model_card_id=card.id,
        overwrite=True,
    )
    assert outcome.sections_updated >= 1

    intended = (
        db_session.query(TechnicalFileSection)
        .filter_by(file_id=tf.id, section_type=SECTION_INTENDED_USE)
        .first()
    )
    assert "UPDATED intended_use after re-validation" in intended.content


def test_populate_includes_adverse_event_counts_in_risk_management(db_session):
    card = _card(db_session)
    tf = _tf(db_session)

    now = datetime.utcnow()
    db_session.add(AdverseEvent(
        id=str(uuid.uuid4()),
        organization_id="org-1",
        model_id=card.id,
        event_type="misdiagnosis",
        severity=AdverseEventSeverityDB.CRITICAL,
        description="x",
        status=AdverseEventStatusDB.OPEN,
        reported_at=now,
        created_at=now,
    ))
    db_session.commit()

    populate_from_model_card(
        db_session,
        technical_file_id=tf.id,
        model_card_id=card.id,
    )

    risk = (
        db_session.query(TechnicalFileSection)
        .filter_by(file_id=tf.id, section_type=SECTION_RISK_MANAGEMENT)
        .first()
    )
    assert "Open adverse events" in risk.content
    assert "Critical/high severity events" in risk.content


def test_populate_includes_bias_audit_failures_in_risk_management(db_session):
    card = _card(db_session)
    tf = _tf(db_session)

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
        metric_name="dp",
        metric_value=0.5,
        reference_value=1.0,
        disparity_ratio=0.5,
        passes_threshold=False,
        threshold_used=0.8,
    ))
    db_session.commit()

    populate_from_model_card(
        db_session,
        technical_file_id=tf.id,
        model_card_id=card.id,
    )

    risk = (
        db_session.query(TechnicalFileSection)
        .filter_by(file_id=tf.id, section_type=SECTION_RISK_MANAGEMENT)
        .first()
    )
    assert "Failing bias-audit subgroups" in risk.content


def test_populate_returns_error_when_model_card_missing(db_session):
    tf = _tf(db_session)
    outcome = populate_from_model_card(
        db_session,
        technical_file_id=tf.id,
        model_card_id="does-not-exist",
    )
    assert "model_card_not_found" in outcome.errors
    assert outcome.sections_created == 0


def test_populate_returns_error_when_technical_file_missing(db_session):
    card = _card(db_session)
    outcome = populate_from_model_card(
        db_session,
        technical_file_id="does-not-exist",
        model_card_id=card.id,
    )
    assert "technical_file_not_found" in outcome.errors
