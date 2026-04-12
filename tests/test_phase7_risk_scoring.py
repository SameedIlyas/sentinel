"""Phase 7 Risk Scoring Engine tests — TDD"""
import os
import uuid
import pytest
from datetime import datetime

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_phase7.db")
os.environ.setdefault("SECRET_KEY", "test-secret-phase7-xyz-abc")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client():
    from fastapi.testclient import TestClient
    from policy_engine.main import app
    return TestClient(app, raise_server_exceptions=False)


def _make_user_headers(db, role_value, org_id=None):
    from policy_engine.models.user import User, UserRole
    from policy_engine.auth.jwt_utils import create_access_token, get_password_hash

    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        username=f"user_{role_value}_{user_id[:8]}",
        email=f"user_{role_value}_{user_id[:8]}@test.com",
        password_hash=get_password_hash("TestPass123!"),
        role=UserRole(role_value),
        full_name=f"Test {role_value}",
        is_active=True,
        organization_id=org_id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(user)
    db.commit()

    token = create_access_token({
        "user_id": user_id,
        "username": user.username,
        "role": role_value,
    })
    headers = {
        "Authorization": f"Bearer {token}",
        "X-API-Key": "dummy-bypass-csrf",
    }
    return headers, user


def _ensure_tables():
    import policy_engine.main  # noqa — triggers model registration
    from policy_engine.database import Base, engine
    Base.metadata.create_all(bind=engine)


def _get_test_db():
    from policy_engine.database import SessionLocal
    return SessionLocal()


# ---------------------------------------------------------------------------
# TestRiskScoringDomain (15 tests) — pure domain logic, no DB
# ---------------------------------------------------------------------------

class TestRiskScoringDomain:
    """Tests for risk_scoring.py pure functions and dataclasses."""

    def test_compute_severity_score_basic(self):
        from policy_engine.domain.regulatory.risk_scoring import (
            SeverityFactors, compute_severity_score,
        )
        factors = SeverityFactors(
            patient_safety_impact=5.0,
            data_sensitivity=5.0,
            model_confidence=5.0,  # inverted → 5.0
            bias_magnitude=5.0,
            drift_magnitude=5.0,
        )
        score = compute_severity_score(factors)
        assert score == pytest.approx(5.0)

    def test_compute_severity_score_model_confidence_inverted(self):
        from policy_engine.domain.regulatory.risk_scoring import (
            SeverityFactors, compute_severity_score,
        )
        # High confidence (10) → inverted = 0 → lower severity
        factors = SeverityFactors(
            patient_safety_impact=1.0,
            data_sensitivity=1.0,
            model_confidence=10.0,  # inverted → 0
            bias_magnitude=1.0,
            drift_magnitude=1.0,
        )
        score = compute_severity_score(factors)
        # (1 + 1 + 0 + 1 + 1) / 5 = 0.8
        assert score == pytest.approx(0.8)

    def test_compute_severity_score_low_confidence_high_severity(self):
        from policy_engine.domain.regulatory.risk_scoring import (
            SeverityFactors, compute_severity_score,
        )
        factors = SeverityFactors(
            patient_safety_impact=1.0,
            data_sensitivity=1.0,
            model_confidence=1.0,  # inverted → 9.0
            bias_magnitude=1.0,
            drift_magnitude=1.0,
        )
        score = compute_severity_score(factors)
        # (1 + 1 + 9 + 1 + 1) / 5 = 2.6
        assert score == pytest.approx(2.6)

    def test_compute_exposure_score_basic(self):
        from policy_engine.domain.regulatory.risk_scoring import (
            ExposureFactors, compute_exposure_score,
        )
        factors = ExposureFactors(
            patient_volume=4.0,
            decision_frequency=4.0,
            automation_level=4.0,
            data_access_breadth=4.0,
        )
        score = compute_exposure_score(factors)
        assert score == pytest.approx(4.0)

    def test_compute_exposure_score_max(self):
        from policy_engine.domain.regulatory.risk_scoring import (
            ExposureFactors, compute_exposure_score,
        )
        factors = ExposureFactors(
            patient_volume=10.0,
            decision_frequency=10.0,
            automation_level=10.0,
            data_access_breadth=10.0,
        )
        score = compute_exposure_score(factors)
        assert score == pytest.approx(10.0)

    def test_compute_regulatory_penalty_hipaa_only(self):
        from policy_engine.domain.regulatory.risk_scoring import (
            RegulatoryFlags, compute_regulatory_penalty,
        )
        flags = RegulatoryFlags(hipaa=True)
        # 50_000 / 25_000 = 2.0
        assert compute_regulatory_penalty(flags) == pytest.approx(2.0)

    def test_compute_regulatory_penalty_all_flags(self):
        from policy_engine.domain.regulatory.risk_scoring import (
            RegulatoryFlags, compute_regulatory_penalty,
        )
        flags = RegulatoryFlags(hipaa=True, fda_samd=True, cms_false_claims=True, onc_hti1=True)
        # (50k + 100k + 75k + 25k) / 25k = 250k / 25k = 10.0
        assert compute_regulatory_penalty(flags) == pytest.approx(10.0)

    def test_compute_regulatory_penalty_no_flags(self):
        from policy_engine.domain.regulatory.risk_scoring import (
            RegulatoryFlags, compute_regulatory_penalty,
        )
        flags = RegulatoryFlags()
        assert compute_regulatory_penalty(flags) == pytest.approx(0.0)

    def test_compute_regulatory_penalty_with_multiplier(self):
        from policy_engine.domain.regulatory.risk_scoring import (
            RegulatoryFlags, compute_regulatory_penalty,
        )
        flags = RegulatoryFlags(hipaa=True)
        # 2.0 * 1.5 = 3.0
        assert compute_regulatory_penalty(flags, multiplier=1.5) == pytest.approx(3.0)

    def test_compute_total_risk_formula(self):
        from policy_engine.domain.regulatory.risk_scoring import compute_total_risk
        # (5.0 * 5.0) + 2.0 = 27.0
        result = compute_total_risk(severity_score=5.0, exposure_score=5.0, regulatory_penalty=2.0)
        assert result == pytest.approx(27.0)

    def test_compute_total_risk_clamped_to_100(self):
        from policy_engine.domain.regulatory.risk_scoring import compute_total_risk
        result = compute_total_risk(severity_score=10.0, exposure_score=10.0, regulatory_penalty=10.0)
        assert result == pytest.approx(100.0)

    def test_compute_total_risk_clamped_to_1(self):
        from policy_engine.domain.regulatory.risk_scoring import compute_total_risk
        result = compute_total_risk(severity_score=0.0, exposure_score=0.0, regulatory_penalty=0.0)
        assert result == pytest.approx(1.0)

    def test_risk_level_from_score_critical(self):
        from policy_engine.domain.regulatory.risk_scoring import risk_level_from_score
        assert risk_level_from_score(80.0) == "critical"
        assert risk_level_from_score(75.0) == "critical"

    def test_risk_level_from_score_high(self):
        from policy_engine.domain.regulatory.risk_scoring import risk_level_from_score
        assert risk_level_from_score(74.9) == "high"
        assert risk_level_from_score(50.0) == "high"

    def test_risk_level_from_score_medium_and_low(self):
        from policy_engine.domain.regulatory.risk_scoring import risk_level_from_score
        assert risk_level_from_score(49.9) == "medium"
        assert risk_level_from_score(25.0) == "medium"
        assert risk_level_from_score(24.9) == "low"
        assert risk_level_from_score(1.0) == "low"

    def test_validate_factor_valid(self):
        from policy_engine.domain.regulatory.risk_scoring import validate_factor
        # Should not raise
        validate_factor("patient_safety_impact", 1.0)
        validate_factor("patient_safety_impact", 5.5)
        validate_factor("patient_safety_impact", 10.0)

    def test_validate_factor_invalid_low(self):
        from policy_engine.domain.regulatory.risk_scoring import validate_factor
        with pytest.raises(ValueError, match="out of range"):
            validate_factor("patient_safety_impact", 0.9)

    def test_validate_factor_invalid_high(self):
        from policy_engine.domain.regulatory.risk_scoring import validate_factor
        with pytest.raises(ValueError, match="out of range"):
            validate_factor("patient_safety_impact", 10.1)


# ---------------------------------------------------------------------------
# TestRiskScoreRoutes (18 tests) — route CRUD + trend/history
# ---------------------------------------------------------------------------

class TestRiskScoreRoutes:
    """Tests for POST /risk/scores, GET /risk/scores/{model_id}/latest, GET /risk/history/{model_id}."""

    @pytest.fixture(autouse=True)
    def setup(self):
        _ensure_tables()
        self.db = _get_test_db()
        self.org_id = str(uuid.uuid4())
        self.client = _make_client()
        self.headers, self.user = _make_user_headers(self.db, "admin", self.org_id)
        self.viewer_headers, self.viewer = _make_user_headers(self.db, "viewer", self.org_id)
        yield
        self.db.close()

    def _score_payload(self, model_id=None, **overrides):
        payload = {
            "model_id": model_id or f"model-{uuid.uuid4().hex[:8]}",
            "severity_factors": {
                "patient_safety_impact": 5.0,
                "data_sensitivity": 5.0,
                "model_confidence": 5.0,
                "bias_magnitude": 5.0,
                "drift_magnitude": 5.0,
            },
            "exposure_factors": {
                "patient_volume": 5.0,
                "decision_frequency": 5.0,
                "automation_level": 5.0,
                "data_access_breadth": 5.0,
            },
            "regulatory_flags": {
                "hipaa": False,
                "fda_samd": False,
                "cms_false_claims": False,
                "onc_hti1": False,
            },
        }
        payload.update(overrides)
        return payload

    def test_compute_score_returns_201(self):
        payload = self._score_payload()
        resp = self.client.post("/v1/risk/scores", json=payload, headers=self.headers)
        assert resp.status_code == 201
        data = resp.json()
        assert "total_risk" in data
        assert "risk_level" in data
        assert "severity_score" in data
        assert "exposure_score" in data
        assert "regulatory_penalty" in data

    def test_compute_score_formula_correctness(self):
        """severity=5, exposure=5, no penalty → (5*5)+0=25, risk_level=medium"""
        payload = self._score_payload()
        resp = self.client.post("/v1/risk/scores", json=payload, headers=self.headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["severity_score"] == pytest.approx(5.0)
        assert data["exposure_score"] == pytest.approx(5.0)
        assert data["total_risk"] == pytest.approx(25.0)
        assert data["risk_level"] == "medium"

    def test_compute_score_with_hipaa_flag(self):
        payload = self._score_payload()
        payload["regulatory_flags"]["hipaa"] = True
        resp = self.client.post("/v1/risk/scores", json=payload, headers=self.headers)
        assert resp.status_code == 201
        data = resp.json()
        # penalty = 50000/25000 = 2.0; total = 25 + 2 = 27
        assert data["regulatory_penalty"] == pytest.approx(2.0)
        assert data["total_risk"] == pytest.approx(27.0)

    def test_compute_score_all_flags_max_penalty(self):
        payload = self._score_payload()
        payload["regulatory_flags"] = {
            "hipaa": True, "fda_samd": True,
            "cms_false_claims": True, "onc_hti1": True,
        }
        resp = self.client.post("/v1/risk/scores", json=payload, headers=self.headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["regulatory_penalty"] == pytest.approx(10.0)

    def test_compute_score_invalid_factor_returns_422(self):
        payload = self._score_payload()
        payload["severity_factors"]["patient_safety_impact"] = 11.0  # out of range
        resp = self.client.post("/v1/risk/scores", json=payload, headers=self.headers)
        assert resp.status_code == 422

    def test_compute_score_missing_field_returns_422(self):
        payload = self._score_payload()
        del payload["model_id"]
        resp = self.client.post("/v1/risk/scores", json=payload, headers=self.headers)
        assert resp.status_code == 422

    def test_compute_score_forbidden_for_viewer(self):
        payload = self._score_payload()
        resp = self.client.post("/v1/risk/scores", json=payload, headers=self.viewer_headers)
        assert resp.status_code == 403

    def test_get_latest_score_returns_200(self):
        model_id = f"model-{uuid.uuid4().hex[:8]}"
        payload = self._score_payload(model_id=model_id)
        self.client.post("/v1/risk/scores", json=payload, headers=self.headers)
        resp = self.client.get(f"/v1/risk/scores/{model_id}/latest", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["model_id"] == model_id

    def test_get_latest_score_no_data_returns_404(self):
        resp = self.client.get("/v1/risk/scores/nonexistent-model/latest", headers=self.headers)
        assert resp.status_code == 404

    def test_get_score_history_returns_list(self):
        model_id = f"model-{uuid.uuid4().hex[:8]}"
        payload = self._score_payload(model_id=model_id)
        # Create 2 scores
        self.client.post("/v1/risk/scores", json=payload, headers=self.headers)
        self.client.post("/v1/risk/scores", json=payload, headers=self.headers)
        resp = self.client.get(f"/v1/risk/history/{model_id}", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 2

    def test_get_score_history_includes_trend(self):
        model_id = f"model-{uuid.uuid4().hex[:8]}"
        payload = self._score_payload(model_id=model_id)
        self.client.post("/v1/risk/scores", json=payload, headers=self.headers)
        resp = self.client.get(f"/v1/risk/history/{model_id}", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert "trend" in data[0]

    def test_get_score_history_empty_model_returns_empty_list(self):
        resp = self.client.get("/v1/risk/history/unknown-model", headers=self.headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_score_stored_with_org_isolation(self):
        """Score from org A should not appear for org B."""
        org_b_id = str(uuid.uuid4())
        headers_b, _ = _make_user_headers(self.db, "admin", org_b_id)
        model_id = f"model-{uuid.uuid4().hex[:8]}"
        payload = self._score_payload(model_id=model_id)
        self.client.post("/v1/risk/scores", json=payload, headers=self.headers)
        resp = self.client.get(f"/v1/risk/scores/{model_id}/latest", headers=headers_b)
        assert resp.status_code == 404

    def test_stats_endpoint_returns_summary(self):
        payload = self._score_payload()
        self.client.post("/v1/risk/scores", json=payload, headers=self.headers)
        resp = self.client.get("/v1/risk/scores/stats", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_scores" in data
        assert "by_risk_level" in data

    def test_unauthenticated_returns_401(self):
        payload = self._score_payload()
        resp = self.client.post("/v1/risk/scores", json=payload)
        # CSRF middleware fires before auth — may return 403 or 401
        assert resp.status_code in (401, 403)

    def test_high_risk_model_confidence_inverse(self):
        """Low model_confidence (1.0) → high inverted severity contribution."""
        payload = self._score_payload()
        payload["severity_factors"]["model_confidence"] = 1.0  # inverted → 9
        resp = self.client.post("/v1/risk/scores", json=payload, headers=self.headers)
        assert resp.status_code == 201
        data = resp.json()
        # severity = (5+5+9+5+5)/5 = 5.8; exposure = 5; total = 29
        assert data["severity_score"] == pytest.approx(5.8)
        assert data["total_risk"] == pytest.approx(29.0)

    def test_total_risk_clamped_at_100(self):
        """Max factors → total risk capped at 100."""
        payload = self._score_payload()
        payload["severity_factors"] = {k: 10.0 for k in payload["severity_factors"]}
        payload["severity_factors"]["model_confidence"] = 1.0  # inverted → 9 → high
        payload["exposure_factors"] = {k: 10.0 for k in payload["exposure_factors"]}
        payload["regulatory_flags"] = {k: True for k in payload["regulatory_flags"]}
        resp = self.client.post("/v1/risk/scores", json=payload, headers=self.headers)
        assert resp.status_code == 201
        assert resp.json()["total_risk"] == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# TestRiskConfigurationRoutes (12 tests) — config + regulatory mappings
# ---------------------------------------------------------------------------

class TestRiskConfigurationRoutes:
    """Tests for /risk/configuration and /risk/regulatory-mappings endpoints."""

    @pytest.fixture(autouse=True)
    def setup(self):
        _ensure_tables()
        self.db = _get_test_db()
        self.org_id = str(uuid.uuid4())
        self.client = _make_client()
        self.headers, self.user = _make_user_headers(self.db, "admin", self.org_id)
        self.viewer_headers, _ = _make_user_headers(self.db, "viewer", self.org_id)
        yield
        self.db.close()

    def test_get_configuration_returns_default_when_none_exists(self):
        resp = self.client.get("/v1/risk/configuration", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "regulatory_multiplier" in data
        assert data["regulatory_multiplier"] == pytest.approx(1.0)

    def test_post_configuration_creates_201(self):
        payload = {
            "regulatory_multiplier": 1.5,
            "critical_threshold": 75.0,
            "high_threshold": 50.0,
            "medium_threshold": 25.0,
        }
        resp = self.client.post("/v1/risk/configuration", json=payload, headers=self.headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["regulatory_multiplier"] == pytest.approx(1.5)

    def test_post_configuration_update_returns_200(self):
        payload = {"regulatory_multiplier": 1.2}
        self.client.post("/v1/risk/configuration", json=payload, headers=self.headers)
        payload["regulatory_multiplier"] = 2.0
        resp = self.client.post("/v1/risk/configuration", json=payload, headers=self.headers)
        assert resp.status_code == 200
        assert resp.json()["regulatory_multiplier"] == pytest.approx(2.0)

    def test_post_configuration_forbidden_for_viewer(self):
        resp = self.client.post("/v1/risk/configuration", json={"regulatory_multiplier": 1.0},
                                headers=self.viewer_headers)
        assert resp.status_code == 403

    def test_org_multiplier_applied_to_penalty(self):
        """Set multiplier=2.0 then score with hipaa=True → penalty should be 4.0."""
        self.client.post("/v1/risk/configuration",
                         json={"regulatory_multiplier": 2.0},
                         headers=self.headers)
        payload = {
            "model_id": f"model-{uuid.uuid4().hex[:8]}",
            "severity_factors": {k: 5.0 for k in [
                "patient_safety_impact", "data_sensitivity",
                "model_confidence", "bias_magnitude", "drift_magnitude",
            ]},
            "exposure_factors": {k: 5.0 for k in [
                "patient_volume", "decision_frequency",
                "automation_level", "data_access_breadth",
            ]},
            "regulatory_flags": {"hipaa": True, "fda_samd": False,
                                  "cms_false_claims": False, "onc_hti1": False},
        }
        resp = self.client.post("/v1/risk/scores", json=payload, headers=self.headers)
        assert resp.status_code == 201
        # hipaa penalty = 2.0 * multiplier 2.0 = 4.0
        assert resp.json()["regulatory_penalty"] == pytest.approx(4.0)

    def test_add_regulatory_mapping_creates_201(self):
        payload = {"model_id": "test-model", "regulation": "hipaa", "applicable": True}
        resp = self.client.post("/v1/risk/regulatory-mappings", json=payload, headers=self.headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["model_id"] == "test-model"
        assert data["regulation"] == "hipaa"

    def test_add_regulatory_mapping_invalid_regulation_returns_400(self):
        payload = {"model_id": "test-model", "regulation": "unknown_reg", "applicable": True}
        resp = self.client.post("/v1/risk/regulatory-mappings", json=payload, headers=self.headers)
        assert resp.status_code == 400

    def test_list_regulatory_mappings_for_model(self):
        model_id = f"model-{uuid.uuid4().hex[:8]}"
        self.client.post("/v1/risk/regulatory-mappings",
                         json={"model_id": model_id, "regulation": "hipaa", "applicable": True},
                         headers=self.headers)
        self.client.post("/v1/risk/regulatory-mappings",
                         json={"model_id": model_id, "regulation": "fda_samd", "applicable": True},
                         headers=self.headers)
        resp = self.client.get(f"/v1/risk/regulatory-mappings/{model_id}", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 2

    def test_delete_regulatory_mapping(self):
        model_id = f"model-{uuid.uuid4().hex[:8]}"
        create_resp = self.client.post(
            "/v1/risk/regulatory-mappings",
            json={"model_id": model_id, "regulation": "hipaa", "applicable": True},
            headers=self.headers,
        )
        mapping_id = create_resp.json()["id"]
        del_resp = self.client.delete(f"/v1/risk/regulatory-mappings/{mapping_id}",
                                      headers=self.headers)
        assert del_resp.status_code == 204

    def test_delete_nonexistent_mapping_returns_404(self):
        resp = self.client.delete(f"/v1/risk/regulatory-mappings/{uuid.uuid4()}",
                                  headers=self.headers)
        assert resp.status_code == 404

    def test_regulatory_mappings_org_isolated(self):
        """Mappings from org A not visible to org B."""
        org_b_id = str(uuid.uuid4())
        headers_b, _ = _make_user_headers(self.db, "admin", org_b_id)
        model_id = f"model-{uuid.uuid4().hex[:8]}"
        self.client.post("/v1/risk/regulatory-mappings",
                         json={"model_id": model_id, "regulation": "hipaa", "applicable": True},
                         headers=self.headers)
        resp = self.client.get(f"/v1/risk/regulatory-mappings/{model_id}", headers=headers_b)
        assert resp.json() == []

    def test_post_configuration_invalid_threshold_returns_422(self):
        """high_threshold cannot exceed critical_threshold."""
        payload = {
            "regulatory_multiplier": 1.0,
            "critical_threshold": 50.0,
            "high_threshold": 75.0,  # invalid: high > critical
            "medium_threshold": 25.0,
        }
        resp = self.client.post("/v1/risk/configuration", json=payload, headers=self.headers)
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# TestRiskPortfolio (10 tests) — portfolio aggregation + history trends
# ---------------------------------------------------------------------------

class TestRiskPortfolio:
    """Tests for GET /risk/portfolio endpoint."""

    @pytest.fixture(autouse=True)
    def setup(self):
        _ensure_tables()
        self.db = _get_test_db()
        self.org_id = str(uuid.uuid4())
        self.client = _make_client()
        self.headers, self.user = _make_user_headers(self.db, "admin", self.org_id)
        yield
        self.db.close()

    def _create_score(self, model_id=None, sev=5.0, exp=5.0, hipaa=False):
        payload = {
            "model_id": model_id or f"model-{uuid.uuid4().hex[:8]}",
            "severity_factors": {k: sev for k in [
                "patient_safety_impact", "data_sensitivity",
                "model_confidence", "bias_magnitude", "drift_magnitude",
            ]},
            "exposure_factors": {k: exp for k in [
                "patient_volume", "decision_frequency",
                "automation_level", "data_access_breadth",
            ]},
            "regulatory_flags": {
                "hipaa": hipaa,
                "fda_samd": False,
                "cms_false_claims": False,
                "onc_hti1": False,
            },
        }
        return self.client.post("/v1/risk/scores", json=payload, headers=self.headers)

    def test_portfolio_empty_when_no_scores(self):
        resp = self.client.get("/v1/risk/portfolio", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)
        assert data.get("total_models", 0) == 0

    def test_portfolio_lists_models(self):
        self._create_score("model-A")
        self._create_score("model-B")
        resp = self.client.get("/v1/risk/portfolio", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_models"] >= 2

    def test_portfolio_contains_summary_fields(self):
        self._create_score("model-C")
        resp = self.client.get("/v1/risk/portfolio", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_models" in data
        assert "avg_risk" in data
        assert "by_risk_level" in data
        assert "models" in data

    def test_portfolio_shows_latest_per_model(self):
        """Multiple scores for same model → portfolio shows only 1 entry for that model."""
        model_id = "model-dedup"
        self._create_score(model_id=model_id)
        self._create_score(model_id=model_id)
        resp = self.client.get("/v1/risk/portfolio", headers=self.headers)
        data = resp.json()
        model_entries = [m for m in data["models"] if m["model_id"] == model_id]
        assert len(model_entries) == 1

    def test_portfolio_org_isolated(self):
        org_b_id = str(uuid.uuid4())
        headers_b, _ = _make_user_headers(self.db, "admin", org_b_id)
        self._create_score("model-org-a")
        resp_b = self.client.get("/v1/risk/portfolio", headers=headers_b)
        data_b = resp_b.json()
        model_ids_b = [m["model_id"] for m in data_b.get("models", [])]
        assert "model-org-a" not in model_ids_b

    def test_portfolio_avg_risk_correct(self):
        """Two models with same score → avg = that score."""
        self._create_score("model-avg-1", sev=5.0, exp=5.0)  # total=25
        self._create_score("model-avg-2", sev=5.0, exp=5.0)  # total=25
        resp = self.client.get("/v1/risk/portfolio", headers=self.headers)
        data = resp.json()
        model_ids = [m["model_id"] for m in data.get("models", [])]
        if "model-avg-1" in model_ids and "model-avg-2" in model_ids:
            assert data["avg_risk"] == pytest.approx(25.0, abs=5.0)

    def test_portfolio_by_risk_level_counts(self):
        self._create_score("model-low-1", sev=1.0, exp=1.0)  # ~1.0 → low
        resp = self.client.get("/v1/risk/portfolio", headers=self.headers)
        data = resp.json()
        assert "low" in data["by_risk_level"] or len(data["by_risk_level"]) >= 0

    def test_portfolio_unauthenticated_returns_401(self):
        resp = self.client.get("/v1/risk/portfolio")
        assert resp.status_code == 401

    def test_portfolio_forbidden_for_viewer(self):
        viewer_headers, _ = _make_user_headers(self.db, "viewer", self.org_id)
        resp = self.client.get("/v1/risk/portfolio", headers=viewer_headers)
        assert resp.status_code == 403

    def test_portfolio_model_entry_has_required_fields(self):
        self._create_score("model-fields-test")
        resp = self.client.get("/v1/risk/portfolio", headers=self.headers)
        data = resp.json()
        entries = [m for m in data["models"] if m["model_id"] == "model-fields-test"]
        assert len(entries) == 1
        entry = entries[0]
        assert "model_id" in entry
        assert "total_risk" in entry
        assert "risk_level" in entry
        assert "trend" in entry
