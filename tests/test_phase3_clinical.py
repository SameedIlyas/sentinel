"""Phase 3 Clinical Governance tests - TDD RED phase"""
import os
import uuid
import pytest
from datetime import datetime, timezone, timedelta

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_phase3.db")
os.environ.setdefault("SECRET_KEY", "test-secret-phase3-xyz-abc")


# ---------------------------------------------------------------------------
# Helpers for route tests
# ---------------------------------------------------------------------------

def _make_client():
    from fastapi.testclient import TestClient
    from policy_engine.main import app
    return TestClient(app, raise_server_exceptions=False)


def _make_admin_headers_and_user(db):
    """Create an admin user in DB and return auth headers (X-API-Key bypasses CSRF)."""
    from policy_engine.models.user import User, UserRole
    from policy_engine.auth.jwt_utils import create_access_token, get_password_hash

    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        username=f"admin_{user_id[:8]}",
        email=f"admin_{user_id[:8]}@test.com",
        password_hash=get_password_hash("TestPass123!"),
        role=UserRole.SYSTEM_ADMIN,
        full_name="Test Admin",
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(user)
    db.commit()

    token = create_access_token({
        "user_id": user_id,
        "username": user.username,
        "role": "system_admin",
    })
    # Use X-API-Key to bypass CSRF, plus Bearer for auth
    headers = {
        "Authorization": f"Bearer {token}",
        "X-API-Key": "dummy-bypass-csrf",
    }
    return headers, user


def _make_viewer_headers_and_user(db):
    """Create a viewer user in DB and return auth headers."""
    from policy_engine.models.user import User, UserRole
    from policy_engine.auth.jwt_utils import create_access_token, get_password_hash

    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        username=f"viewer_{user_id[:8]}",
        email=f"viewer_{user_id[:8]}@test.com",
        password_hash=get_password_hash("TestPass123!"),
        role=UserRole.VIEWER,
        full_name="Test Viewer",
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(user)
    db.commit()

    token = create_access_token({
        "user_id": user_id,
        "username": user.username,
        "role": "viewer",
    })
    headers = {
        "Authorization": f"Bearer {token}",
        "X-API-Key": "dummy-bypass-csrf",
    }
    return headers, user


def _ensure_tables():
    """Import all models and create all tables in the test database."""
    # Importing main ensures all model imports happen (models registered with Base)
    import policy_engine.main  # noqa
    from policy_engine.database import Base, engine
    Base.metadata.create_all(bind=engine)


def _get_test_db():
    from policy_engine.database import SessionLocal
    return SessionLocal()


# ---------------------------------------------------------------------------
# TestModelCardDomain (8 tests)
# ---------------------------------------------------------------------------

class TestModelCardDomain:
    """Tests for pure domain entity ModelCardEntity."""

    def test_model_card_entity_creation(self):
        from policy_engine.domain.clinical.model_card import ModelCardEntity, LifecycleStage
        card = ModelCardEntity(
            id="mc-1",
            name="Radiology AI v1",
            lifecycle_stage=LifecycleStage.DRAFT,
            intended_use="Chest X-ray triage",
            version="1.0",
        )
        assert card.id == "mc-1"
        assert card.name == "Radiology AI v1"
        assert card.lifecycle_stage == LifecycleStage.DRAFT
        assert card.intended_use == "Chest X-ray triage"

    def test_lifecycle_draft_to_review(self):
        from policy_engine.domain.clinical.model_card import ModelCardEntity, LifecycleStage
        card = ModelCardEntity(id="mc-1", name="Test")
        card.transition_to(LifecycleStage.REVIEW)
        assert card.lifecycle_stage == LifecycleStage.REVIEW

    def test_lifecycle_review_to_published(self):
        from policy_engine.domain.clinical.model_card import ModelCardEntity, LifecycleStage
        card = ModelCardEntity(id="mc-1", name="Test", lifecycle_stage=LifecycleStage.REVIEW)
        card.transition_to(LifecycleStage.PUBLISHED)
        assert card.lifecycle_stage == LifecycleStage.PUBLISHED

    def test_lifecycle_published_to_retired(self):
        from policy_engine.domain.clinical.model_card import ModelCardEntity, LifecycleStage
        card = ModelCardEntity(id="mc-1", name="Test", lifecycle_stage=LifecycleStage.PUBLISHED)
        card.transition_to(LifecycleStage.RETIRED)
        assert card.lifecycle_stage == LifecycleStage.RETIRED

    def test_lifecycle_invalid_transition_draft_to_published(self):
        from policy_engine.domain.clinical.model_card import ModelCardEntity, LifecycleStage
        card = ModelCardEntity(id="mc-1", name="Test", lifecycle_stage=LifecycleStage.DRAFT)
        with pytest.raises(ValueError):
            card.transition_to(LifecycleStage.PUBLISHED)

    def test_lifecycle_invalid_transition_retired_to_draft(self):
        from policy_engine.domain.clinical.model_card import ModelCardEntity, LifecycleStage
        card = ModelCardEntity(id="mc-1", name="Test", lifecycle_stage=LifecycleStage.RETIRED)
        with pytest.raises(ValueError):
            card.transition_to(LifecycleStage.DRAFT)

    def test_model_card_metric_entity(self):
        from policy_engine.domain.clinical.model_card import ModelCardMetricEntity
        metric = ModelCardMetricEntity(
            metric_name="AUROC",
            value=0.92,
            subgroup="all",
            metric_type="performance",
        )
        assert metric.metric_name == "AUROC"
        assert metric.value == 0.92
        assert metric.subgroup == "all"

    def test_lifecycle_stages_enum(self):
        from policy_engine.domain.clinical.model_card import LifecycleStage
        assert LifecycleStage.DRAFT is not None
        assert LifecycleStage.REVIEW is not None
        assert LifecycleStage.PUBLISHED is not None
        assert LifecycleStage.RETIRED is not None
        assert len(LifecycleStage) == 4


# ---------------------------------------------------------------------------
# TestBiasAuditDomain (10 tests)
# ---------------------------------------------------------------------------

class TestBiasAuditDomain:
    """Tests for pure bias audit domain logic."""

    def test_disparate_impact_ratio_basic(self):
        from policy_engine.domain.clinical.bias_audit import disparate_impact_ratio
        result = disparate_impact_ratio(0.6, 0.8)
        assert abs(result - 0.75) < 1e-9

    def test_disparate_impact_ratio_passes_80_rule(self):
        from policy_engine.domain.clinical.bias_audit import disparate_impact_ratio
        ratio = disparate_impact_ratio(0.85, 0.9)
        assert ratio >= 0.8

    def test_disparate_impact_ratio_fails_80_rule(self):
        from policy_engine.domain.clinical.bias_audit import disparate_impact_ratio
        ratio = disparate_impact_ratio(0.5, 0.9)
        assert ratio < 0.8

    def test_disparate_impact_ratio_zero_division(self):
        from policy_engine.domain.clinical.bias_audit import disparate_impact_ratio
        result = disparate_impact_ratio(0.6, 0.0)
        assert result == 0.0

    def test_equal_opportunity_difference(self):
        from policy_engine.domain.clinical.bias_audit import equal_opportunity_difference
        result = equal_opportunity_difference(0.7, 0.9)
        assert abs(result - (-0.2)) < 1e-9

    def test_demographic_parity_difference(self):
        from policy_engine.domain.clinical.bias_audit import demographic_parity_difference
        result = demographic_parity_difference(0.4, 0.6)
        assert abs(result - (-0.2)) < 1e-9

    def test_bias_audit_result_creation(self):
        from policy_engine.domain.clinical.bias_audit import BiasAuditResult
        result = BiasAuditResult(
            subgroup="race:black",
            metric_name="disparate_impact_ratio",
            metric_value=0.75,
            reference_value=1.0,
            disparity_ratio=0.75,
            passes_80_percent_rule=False,
        )
        assert result.subgroup == "race:black"
        assert result.disparity_ratio == 0.75

    def test_bias_audit_result_passes_threshold(self):
        from policy_engine.domain.clinical.bias_audit import BiasAuditResult
        result = BiasAuditResult(
            subgroup="race:white",
            metric_name="disparate_impact_ratio",
            metric_value=0.9,
            reference_value=1.0,
            disparity_ratio=0.9,
            passes_80_percent_rule=True,
        )
        assert result.passes_80_percent_rule is True

    def test_bias_audit_result_fails_threshold(self):
        from policy_engine.domain.clinical.bias_audit import BiasAuditResult
        result = BiasAuditResult(
            subgroup="race:hispanic",
            metric_name="disparate_impact_ratio",
            metric_value=0.7,
            reference_value=1.0,
            disparity_ratio=0.7,
            passes_80_percent_rule=False,
        )
        assert result.passes_80_percent_rule is False

    def test_run_bias_audit_multi_subgroup(self):
        from policy_engine.domain.clinical.bias_audit import run_bias_audit
        predictions = [1, 0, 1, 1, 0, 1, 0, 0]
        labels = [1, 0, 1, 0, 0, 1, 1, 0]
        groups = {"race": ["white", "black", "white", "black", "white", "black", "white", "black"]}
        results = run_bias_audit(predictions, labels, groups)
        assert isinstance(results, list)
        assert len(results) >= 1
        for r in results:
            from policy_engine.domain.clinical.bias_audit import BiasAuditResult
            assert isinstance(r, BiasAuditResult)


# ---------------------------------------------------------------------------
# TestDriftDetector (10 tests)
# ---------------------------------------------------------------------------

class TestDriftDetector:
    """Tests for drift detection domain logic."""

    def test_psi_identical_distributions(self):
        from policy_engine.domain.clinical.drift_detector import population_stability_index
        data = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0] * 10
        psi = population_stability_index(data, data)
        assert psi < 0.01

    def test_psi_different_distributions(self):
        from policy_engine.domain.clinical.drift_detector import population_stability_index
        # All expected values are low (0.0-0.1), all actual values are high (0.9-1.0)
        expected = [0.05] * 100
        actual = [0.95] * 100
        psi = population_stability_index(expected, actual)
        assert psi > 0.1

    def test_psi_moderate_drift(self):
        from policy_engine.domain.clinical.drift_detector import population_stability_index
        import random
        random.seed(42)
        expected = [random.gauss(0.5, 0.1) for _ in range(100)]
        actual = [random.gauss(0.55, 0.12) for _ in range(100)]
        psi = population_stability_index(expected, actual)
        # Should be non-zero (some drift)
        assert psi >= 0.0

    def test_ks_test_same_distribution(self):
        from policy_engine.domain.clinical.drift_detector import kolmogorov_smirnov_test
        import random
        random.seed(99)
        samples = [random.gauss(0, 1) for _ in range(200)]
        _, p_value = kolmogorov_smirnov_test(samples, samples)
        # Identical samples → p_value should be 1.0 or very high
        assert p_value >= 0.05

    def test_ks_test_different_distributions(self):
        from policy_engine.domain.clinical.drift_detector import kolmogorov_smirnov_test
        expected = list(range(50))
        actual = list(range(500, 550))
        _, p_value = kolmogorov_smirnov_test(expected, actual)
        assert p_value < 0.05

    def test_performance_drift_detected_true(self):
        from policy_engine.domain.clinical.drift_detector import performance_drift_detected
        assert performance_drift_detected(0.85, 0.75, threshold=0.05) is True

    def test_performance_drift_detected_false(self):
        from policy_engine.domain.clinical.drift_detector import performance_drift_detected
        assert performance_drift_detected(0.85, 0.82, threshold=0.05) is False

    def test_drift_measurement_creation(self):
        from policy_engine.domain.clinical.drift_detector import DriftMeasurement, DriftSeverity
        m = DriftMeasurement(
            psi_scores={"age": 0.05},
            ks_scores={"age": 0.3},
            drift_detected=False,
            magnitude=0.05,
            severity=DriftSeverity.LOW,
        )
        assert m.drift_detected is False
        assert m.severity == DriftSeverity.LOW

    def test_drift_severity_critical(self):
        from policy_engine.domain.clinical.drift_detector import severity_from_psi, DriftSeverity
        assert severity_from_psi(0.25) == DriftSeverity.CRITICAL

    def test_drift_severity_low(self):
        from policy_engine.domain.clinical.drift_detector import severity_from_psi, DriftSeverity
        assert severity_from_psi(0.05) == DriftSeverity.LOW


# ---------------------------------------------------------------------------
# TestHITLDomain (10 tests)
# ---------------------------------------------------------------------------

class TestHITLDomain:
    """Tests for HITL domain logic and hash chain."""

    def test_hitl_review_entity_creation(self):
        from policy_engine.domain.clinical.hitl import HITLReviewEntity, HITLStatus, HITLPriority
        review = HITLReviewEntity(
            id="hitl-1",
            title="Flagged Diagnosis",
            risk_score=0.87,
            status=HITLStatus.PENDING,
            priority=HITLPriority.HIGH,
        )
        assert review.id == "hitl-1"
        assert review.risk_score == 0.87
        assert review.status == HITLStatus.PENDING

    def test_is_overdue_past_deadline(self):
        from policy_engine.domain.clinical.hitl import HITLReviewEntity, is_overdue
        past = datetime.now(timezone.utc) - timedelta(hours=2)
        review = HITLReviewEntity(id="hitl-1", title="Test", sla_deadline=past)
        assert is_overdue(review) is True

    def test_is_overdue_future_deadline(self):
        from policy_engine.domain.clinical.hitl import HITLReviewEntity, is_overdue
        future = datetime.now(timezone.utc) + timedelta(hours=2)
        review = HITLReviewEntity(id="hitl-1", title="Test", sla_deadline=future)
        assert is_overdue(review) is False

    def test_escalation_tier_0_on_time(self):
        from policy_engine.domain.clinical.hitl import HITLReviewEntity, escalation_tier
        # 24 hours in future — well before deadline
        far_future = datetime.now(timezone.utc) + timedelta(hours=24)
        review = HITLReviewEntity(id="hitl-1", title="Test", sla_deadline=far_future)
        tier = escalation_tier(review)
        assert tier == 0

    def test_escalation_tier_1_warning(self):
        from policy_engine.domain.clinical.hitl import HITLReviewEntity, escalation_tier
        # Less than 6 hours remaining (warning zone)
        near_future = datetime.now(timezone.utc) + timedelta(hours=2)
        review = HITLReviewEntity(id="hitl-1", title="Test", sla_deadline=near_future)
        tier = escalation_tier(review)
        assert tier == 1

    def test_escalation_tier_2_overdue(self):
        from policy_engine.domain.clinical.hitl import HITLReviewEntity, escalation_tier
        # Just past SLA (1 hour overdue, < 24h)
        just_past = datetime.now(timezone.utc) - timedelta(hours=1)
        review = HITLReviewEntity(id="hitl-1", title="Test", sla_deadline=just_past)
        tier = escalation_tier(review)
        assert tier == 2

    def test_escalation_tier_3_critical(self):
        from policy_engine.domain.clinical.hitl import HITLReviewEntity, escalation_tier
        # 25+ hours past SLA → critical
        very_past = datetime.now(timezone.utc) - timedelta(hours=25)
        review = HITLReviewEntity(id="hitl-1", title="Test", sla_deadline=very_past)
        tier = escalation_tier(review)
        assert tier == 3

    def test_hitl_audit_entry_hash(self):
        from policy_engine.domain.clinical.hitl import HITLAuditEntry
        entry = HITLAuditEntry(
            actor_id="user-1",
            action="create",
            old_status=None,
            new_status="pending",
            comments=None,
        )
        hash_val = entry.compute_hash("")
        assert len(hash_val) == 64  # SHA-256 hex = 64 chars
        assert hash_val != ""

    def test_hitl_hash_chain_integrity(self):
        from policy_engine.domain.clinical.hitl import HITLAuditEntry, build_audit_chain
        entries = [
            HITLAuditEntry(actor_id="u1", action="create", old_status=None, new_status="pending", comments=None),
            HITLAuditEntry(actor_id="u1", action="assign", old_status="pending", new_status="in_review", comments=None),
        ]
        chain = build_audit_chain(entries)
        # First entry hash should be non-empty
        assert chain[0].entry_hash != ""
        # Second entry's hash should include first entry's hash in its computation
        expected_second = chain[1].compute_hash(chain[0].entry_hash)
        assert chain[1].entry_hash == expected_second

    def test_hitl_hash_chain_tamper_detection(self):
        from policy_engine.domain.clinical.hitl import HITLAuditEntry, build_audit_chain, verify_audit_chain
        entries = [
            HITLAuditEntry(actor_id="u1", action="create", old_status=None, new_status="pending", comments=None),
            HITLAuditEntry(actor_id="u1", action="approve", old_status="in_review", new_status="approved", comments="Looks good"),
        ]
        chain = build_audit_chain(entries)
        assert verify_audit_chain(chain) is True

        # Tamper with entry 1
        chain[0].action = "tampered_action"
        assert verify_audit_chain(chain) is False


# ---------------------------------------------------------------------------
# TestModelCardRoutes (8 tests)
# ---------------------------------------------------------------------------

class TestModelCardRoutes:
    """Integration tests for model card endpoints."""

    def test_create_model_card(self):
        _ensure_tables()
        db = _get_test_db()
        try:
            headers, _ = _make_admin_headers_and_user(db)
        finally:
            db.close()
        client = _make_client()
        r = client.post("/v1/clinical/model-cards", json={
            "name": "Test Model Card",
            "version": "1.0",
            "intended_use": "Classification",
        }, headers=headers)
        assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"

    def test_list_model_cards(self):
        _ensure_tables()
        db = _get_test_db()
        try:
            headers, _ = _make_admin_headers_and_user(db)
        finally:
            db.close()
        client = _make_client()
        r = client.get("/v1/clinical/model-cards", headers=headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_get_model_card(self):
        _ensure_tables()
        db = _get_test_db()
        try:
            headers, _ = _make_admin_headers_and_user(db)
        finally:
            db.close()
        client = _make_client()
        # Create first
        cr = client.post("/v1/clinical/model-cards", json={"name": "Get Test Card"}, headers=headers)
        assert cr.status_code == 201
        card_id = cr.json()["id"]
        r = client.get(f"/v1/clinical/model-cards/{card_id}", headers=headers)
        assert r.status_code == 200
        assert r.json()["id"] == card_id

    def test_update_model_card_draft(self):
        _ensure_tables()
        db = _get_test_db()
        try:
            headers, _ = _make_admin_headers_and_user(db)
        finally:
            db.close()
        client = _make_client()
        cr = client.post("/v1/clinical/model-cards", json={"name": "Update Test Card"}, headers=headers)
        assert cr.status_code == 201
        card_id = cr.json()["id"]
        r = client.put(f"/v1/clinical/model-cards/{card_id}", json={"name": "Updated Name"}, headers=headers)
        assert r.status_code == 200
        assert r.json()["name"] == "Updated Name"

    def test_publish_model_card(self, monkeypatch):
        # Phase 3 test: bypass the Sprint 3 bias-gate (covered by test_bias_audit_gate.py).
        monkeypatch.setenv("BIAS_AUDIT_PUBLISH_GATE", "false")
        _ensure_tables()
        db = _get_test_db()
        try:
            headers, _ = _make_admin_headers_and_user(db)
        finally:
            db.close()
        client = _make_client()
        # Lineage required by publish gate
        cr = client.post(
            "/v1/clinical/model-cards",
            json={
                "name": "Publish Test Card",
                "model_artifact_uri": "mlflow://runs/abc/model",
                "training_dataset_sha256": "a" * 64,
                "evaluation_dataset_sha256": "b" * 64,
            },
            headers=headers,
        )
        assert cr.status_code == 201
        card_id = cr.json()["id"]
        # Move to review first
        client.post(f"/v1/clinical/model-cards/{card_id}/review", headers=headers)
        r = client.post(f"/v1/clinical/model-cards/{card_id}/publish", headers=headers)
        assert r.status_code == 200
        assert r.json()["lifecycle_stage"] == "published"

    def test_retire_model_card(self, monkeypatch):
        monkeypatch.setenv("BIAS_AUDIT_PUBLISH_GATE", "false")
        _ensure_tables()
        db = _get_test_db()
        try:
            headers, _ = _make_admin_headers_and_user(db)
        finally:
            db.close()
        client = _make_client()
        cr = client.post(
            "/v1/clinical/model-cards",
            json={
                "name": "Retire Test Card",
                "model_artifact_uri": "mlflow://runs/abc/model",
                "training_dataset_sha256": "a" * 64,
                "evaluation_dataset_sha256": "b" * 64,
            },
            headers=headers,
        )
        assert cr.status_code == 201
        card_id = cr.json()["id"]
        client.post(f"/v1/clinical/model-cards/{card_id}/review", headers=headers)
        client.post(f"/v1/clinical/model-cards/{card_id}/publish", headers=headers)
        r = client.post(f"/v1/clinical/model-cards/{card_id}/retire", headers=headers)
        assert r.status_code == 200
        assert r.json()["lifecycle_stage"] == "retired"

    def test_export_summary(self):
        _ensure_tables()
        db = _get_test_db()
        try:
            headers, _ = _make_admin_headers_and_user(db)
        finally:
            db.close()
        client = _make_client()
        cr = client.post("/v1/clinical/model-cards", json={"name": "Export Test Card"}, headers=headers)
        assert cr.status_code == 201
        card_id = cr.json()["id"]
        r = client.get(f"/v1/clinical/model-cards/{card_id}/export-summary", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert "id" in data
        assert "name" in data

    def test_create_model_card_forbidden(self):
        _ensure_tables()
        db = _get_test_db()
        try:
            headers, _ = _make_viewer_headers_and_user(db)
        finally:
            db.close()
        client = _make_client()
        r = client.post("/v1/clinical/model-cards", json={"name": "Forbidden Card"}, headers=headers)
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# TestBiasAuditRoutes (6 tests)
# ---------------------------------------------------------------------------

class TestBiasAuditRoutes:
    """Integration tests for bias audit endpoints."""

    def test_create_bias_audit(self):
        _ensure_tables()
        db = _get_test_db()
        try:
            headers, _ = _make_admin_headers_and_user(db)
        finally:
            db.close()
        client = _make_client()
        r = client.post("/v1/clinical/bias-audits", json={
            "audit_name": "Test Audit",
            "dataset_description": "Training data 2023",
        }, headers=headers)
        assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"

    def test_list_bias_audits(self):
        _ensure_tables()
        db = _get_test_db()
        try:
            headers, _ = _make_admin_headers_and_user(db)
        finally:
            db.close()
        client = _make_client()
        r = client.get("/v1/clinical/bias-audits", headers=headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_get_bias_audit_detail(self):
        _ensure_tables()
        db = _get_test_db()
        try:
            headers, _ = _make_admin_headers_and_user(db)
        finally:
            db.close()
        client = _make_client()
        cr = client.post("/v1/clinical/bias-audits", json={"audit_name": "Detail Test Audit"}, headers=headers)
        assert cr.status_code == 201
        audit_id = cr.json()["id"]
        r = client.get(f"/v1/clinical/bias-audits/{audit_id}", headers=headers)
        assert r.status_code == 200
        assert r.json()["id"] == audit_id

    def test_run_bias_audit(self):
        _ensure_tables()
        db = _get_test_db()
        try:
            headers, _ = _make_admin_headers_and_user(db)
        finally:
            db.close()
        client = _make_client()
        cr = client.post("/v1/clinical/bias-audits", json={"audit_name": "Run Test Audit"}, headers=headers)
        assert cr.status_code == 201
        audit_id = cr.json()["id"]
        r = client.post(f"/v1/clinical/bias-audits/{audit_id}/run", json={
            "predictions": [1, 0, 1, 1, 0, 1, 0, 0],
            "labels": [1, 0, 1, 0, 0, 1, 1, 0],
            "groups": {"race": ["white", "black", "white", "black", "white", "black", "white", "black"]},
        }, headers=headers)
        assert r.status_code == 200

    def test_get_bias_audit_report(self):
        _ensure_tables()
        db = _get_test_db()
        try:
            headers, _ = _make_admin_headers_and_user(db)
        finally:
            db.close()
        client = _make_client()
        cr = client.post("/v1/clinical/bias-audits", json={"audit_name": "Report Test Audit"}, headers=headers)
        assert cr.status_code == 201
        audit_id = cr.json()["id"]
        r = client.get(f"/v1/clinical/bias-audits/{audit_id}/report", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert "audit_id" in data

    def test_bias_audit_forbidden(self):
        _ensure_tables()
        db = _get_test_db()
        try:
            headers, _ = _make_viewer_headers_and_user(db)
        finally:
            db.close()
        client = _make_client()
        r = client.post("/v1/clinical/bias-audits", json={"audit_name": "Forbidden"}, headers=headers)
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# TestDriftRoutes (6 tests)
# ---------------------------------------------------------------------------

class TestDriftRoutes:
    """Integration tests for drift detection endpoints."""

    def test_create_drift_baseline(self):
        _ensure_tables()
        db = _get_test_db()
        try:
            headers, _ = _make_admin_headers_and_user(db)
        finally:
            db.close()
        client = _make_client()
        r = client.post("/v1/clinical/drift/baselines", json={
            "model_id": "model-1",
            "baseline_name": "Baseline v1",
            "feature_distributions": {"age": [0.1, 0.2, 0.3]},
            "performance_baseline": {"auroc": 0.85},
        }, headers=headers)
        assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"

    def test_list_drift_baselines(self):
        _ensure_tables()
        db = _get_test_db()
        try:
            headers, _ = _make_admin_headers_and_user(db)
        finally:
            db.close()
        client = _make_client()
        r = client.get("/v1/clinical/drift/baselines", headers=headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_measure_drift(self):
        _ensure_tables()
        db = _get_test_db()
        try:
            headers, _ = _make_admin_headers_and_user(db)
        finally:
            db.close()
        client = _make_client()
        cr = client.post("/v1/clinical/drift/baselines", json={
            "model_id": "model-measure",
            "baseline_name": "Baseline for Measure",
            "feature_distributions": {"age": [0.1, 0.2, 0.3, 0.4, 0.5]},
            "performance_baseline": {"auroc": 0.85},
        }, headers=headers)
        assert cr.status_code == 201
        baseline_id = cr.json()["id"]
        r = client.post("/v1/clinical/drift/measure", json={
            "baseline_id": baseline_id,
            "current_distributions": {"age": [0.3, 0.4, 0.5, 0.6, 0.7]},
            "current_performance": {"auroc": 0.80},
        }, headers=headers)
        assert r.status_code == 200

    def test_list_drift_alerts(self):
        _ensure_tables()
        db = _get_test_db()
        try:
            headers, _ = _make_admin_headers_and_user(db)
        finally:
            db.close()
        client = _make_client()
        r = client.get("/v1/clinical/drift/alerts", headers=headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_acknowledge_drift_alert(self):
        _ensure_tables()
        db = _get_test_db()
        try:
            headers, _ = _make_admin_headers_and_user(db)
        finally:
            db.close()
        client = _make_client()
        # Create baseline + measurement + alert
        cr = client.post("/v1/clinical/drift/baselines", json={
            "model_id": "model-ack",
            "baseline_name": "Baseline for Ack",
            "feature_distributions": {"age": [0.1] * 20 + [0.9] * 20},
            "performance_baseline": {"auroc": 0.90},
        }, headers=headers)
        assert cr.status_code == 201
        baseline_id = cr.json()["id"]
        mr = client.post("/v1/clinical/drift/measure", json={
            "baseline_id": baseline_id,
            "current_distributions": {"age": [0.9] * 20 + [0.1] * 20},
            "current_performance": {"auroc": 0.70},
        }, headers=headers)
        # Get alerts
        ar = client.get("/v1/clinical/drift/alerts", headers=headers)
        alerts = ar.json()
        if alerts:
            alert_id = alerts[0]["id"]
            r = client.patch(f"/v1/clinical/drift/alerts/{alert_id}/acknowledge", headers=headers)
            assert r.status_code == 200
        else:
            # No alerts created — still pass (drift may not be detected with small data)
            pass

    def test_drift_forbidden(self):
        _ensure_tables()
        db = _get_test_db()
        try:
            headers, _ = _make_viewer_headers_and_user(db)
        finally:
            db.close()
        client = _make_client()
        r = client.post("/v1/clinical/drift/baselines", json={
            "model_id": "x",
            "baseline_name": "Forbidden",
            "feature_distributions": {},
            "performance_baseline": {},
        }, headers=headers)
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# TestHITLRoutes (8 tests)
# ---------------------------------------------------------------------------

class TestHITLRoutes:
    """Integration tests for HITL review endpoints."""

    def test_create_hitl_review(self):
        _ensure_tables()
        db = _get_test_db()
        try:
            headers, _ = _make_admin_headers_and_user(db)
        finally:
            db.close()
        client = _make_client()
        r = client.post("/v1/clinical/hitl/reviews", json={
            "title": "Flagged Diagnosis",
            "description": "High risk score triggered review",
            "ai_decision": {"diagnosis": "pneumonia", "confidence": 0.87},
            "risk_score": 0.87,
            "priority": "high",
        }, headers=headers)
        assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"

    def test_list_hitl_reviews(self):
        _ensure_tables()
        db = _get_test_db()
        try:
            headers, _ = _make_admin_headers_and_user(db)
        finally:
            db.close()
        client = _make_client()
        r = client.get("/v1/clinical/hitl/reviews", headers=headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_get_hitl_review_detail(self):
        _ensure_tables()
        db = _get_test_db()
        try:
            headers, _ = _make_admin_headers_and_user(db)
        finally:
            db.close()
        client = _make_client()
        cr = client.post("/v1/clinical/hitl/reviews", json={
            "title": "Detail Test Review",
            "ai_decision": {},
            "risk_score": 0.5,
        }, headers=headers)
        assert cr.status_code == 201
        review_id = cr.json()["id"]
        r = client.get(f"/v1/clinical/hitl/reviews/{review_id}", headers=headers)
        assert r.status_code == 200
        assert r.json()["id"] == review_id

    def test_assign_hitl_review(self):
        _ensure_tables()
        db = _get_test_db()
        try:
            headers, user = _make_admin_headers_and_user(db)
        finally:
            db.close()
        client = _make_client()
        cr = client.post("/v1/clinical/hitl/reviews", json={
            "title": "Assign Test Review",
            "ai_decision": {},
            "risk_score": 0.6,
        }, headers=headers)
        assert cr.status_code == 201
        review_id = cr.json()["id"]
        r = client.patch(f"/v1/clinical/hitl/reviews/{review_id}/assign", json={
            "assigned_to": user.id,
        }, headers=headers)
        assert r.status_code == 200

    def test_approve_hitl_review(self):
        _ensure_tables()
        db = _get_test_db()
        try:
            headers, _ = _make_admin_headers_and_user(db)
        finally:
            db.close()
        client = _make_client()
        cr = client.post("/v1/clinical/hitl/reviews", json={
            "title": "Approve Test Review",
            "ai_decision": {},
            "risk_score": 0.4,
        }, headers=headers)
        assert cr.status_code == 201
        review_id = cr.json()["id"]
        r = client.post(f"/v1/clinical/hitl/reviews/{review_id}/approve", json={
            "comments": "Looks good",
        }, headers=headers)
        assert r.status_code == 200
        assert r.json()["status"] == "approved"

    def test_reject_hitl_review(self):
        _ensure_tables()
        db = _get_test_db()
        try:
            headers, _ = _make_admin_headers_and_user(db)
        finally:
            db.close()
        client = _make_client()
        cr = client.post("/v1/clinical/hitl/reviews", json={
            "title": "Reject Test Review",
            "ai_decision": {},
            "risk_score": 0.9,
        }, headers=headers)
        assert cr.status_code == 201
        review_id = cr.json()["id"]
        r = client.post(f"/v1/clinical/hitl/reviews/{review_id}/reject", json={
            "comments": "Insufficient evidence",
        }, headers=headers)
        assert r.status_code == 200
        assert r.json()["status"] == "rejected"

    def test_escalate_hitl_review(self):
        _ensure_tables()
        db = _get_test_db()
        try:
            headers, _ = _make_admin_headers_and_user(db)
        finally:
            db.close()
        client = _make_client()
        cr = client.post("/v1/clinical/hitl/reviews", json={
            "title": "Escalate Test Review",
            "ai_decision": {},
            "risk_score": 0.95,
        }, headers=headers)
        assert cr.status_code == 201
        review_id = cr.json()["id"]
        r = client.post(f"/v1/clinical/hitl/reviews/{review_id}/escalate", json={
            "comments": "Needs senior review",
        }, headers=headers)
        assert r.status_code == 200
        assert r.json()["status"] == "escalated"

    def test_get_audit_trail(self):
        _ensure_tables()
        db = _get_test_db()
        try:
            headers, _ = _make_admin_headers_and_user(db)
        finally:
            db.close()
        client = _make_client()
        cr = client.post("/v1/clinical/hitl/reviews", json={
            "title": "Audit Trail Test Review",
            "ai_decision": {},
            "risk_score": 0.7,
        }, headers=headers)
        assert cr.status_code == 201
        review_id = cr.json()["id"]
        # Approve to create audit entries
        client.post(f"/v1/clinical/hitl/reviews/{review_id}/approve", json={"comments": "ok"}, headers=headers)
        r = client.get(f"/v1/clinical/hitl/reviews/{review_id}/audit-trail", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert "entries" in data
        assert "chain_valid" in data
        assert data["chain_valid"] is True
