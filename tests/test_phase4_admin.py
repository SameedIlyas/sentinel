"""Phase 4 Administrative Governance tests"""
import os
import uuid
from datetime import datetime

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_phase4.db")
os.environ.setdefault("SECRET_KEY", "test-secret-phase4-xyz-abc")


# ---------------------------------------------------------------------------
# Helpers for route tests
# ---------------------------------------------------------------------------

def _make_client():
    from fastapi.testclient import TestClient
    from policy_engine.main import app
    return TestClient(app, raise_server_exceptions=False)


def _make_admin_headers_and_user(db):
    """Create a SYSTEM_ADMIN user in DB and return auth headers."""
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
    import policy_engine.main  # noqa
    from policy_engine.database import Base, engine
    Base.metadata.create_all(bind=engine)


def _get_test_db():
    from policy_engine.database import SessionLocal
    return SessionLocal()


# ---------------------------------------------------------------------------
# TestShadowAIDomain (8 tests) — pure domain logic
# ---------------------------------------------------------------------------

class TestShadowAIDomain:
    """Tests for policy_engine.domain.admin.shadow_ai pure domain functions."""

    def test_detect_ai_provider_exact_match(self):
        from policy_engine.domain.admin.shadow_ai import detect_ai_provider
        assert detect_ai_provider("api.openai.com") == "openai"

    def test_detect_ai_provider_subdomain(self):
        from policy_engine.domain.admin.shadow_ai import detect_ai_provider
        assert detect_ai_provider("foo.anthropic.com") == "anthropic"

    def test_detect_ai_provider_unknown(self):
        from policy_engine.domain.admin.shadow_ai import detect_ai_provider
        assert detect_ai_provider("example.com") is None

    def test_phi_risk_clinical_department(self):
        from policy_engine.domain.admin.shadow_ai import assess_phi_risk
        assert assess_phi_risk("api.openai.com", 443, "ICU") == "high"

    def test_phi_risk_standard(self):
        from policy_engine.domain.admin.shadow_ai import assess_phi_risk
        assert assess_phi_risk("api.openai.com", 443, "admin") == "medium"

    def test_phi_risk_unknown_provider(self):
        from policy_engine.domain.admin.shadow_ai import assess_phi_risk
        assert assess_phi_risk("example.com", 443, "ICU") == "none"

    def test_is_allowlisted_exact(self):
        from policy_engine.domain.admin.shadow_ai import is_allowlisted
        assert is_allowlisted("api.internal.com", ["api.internal.com"]) is True

    def test_is_allowlisted_pattern(self):
        from policy_engine.domain.admin.shadow_ai import is_allowlisted
        assert is_allowlisted("api.internal.com", ["*.internal.com"]) is True


# ---------------------------------------------------------------------------
# TestScribeAuditorDomain (8 tests) — pure domain logic
# ---------------------------------------------------------------------------

class TestScribeAuditorDomain:
    """Tests for policy_engine.domain.admin.scribe_auditor pure domain functions."""

    def test_completeness_all_sections(self):
        from policy_engine.domain.admin.scribe_auditor import ScribeAuditEngine
        engine = ScribeAuditEngine()
        note = "HPI: patient presents. Assessment: stable. Plan: follow up. Medication: aspirin. Vital signs: BP 120/80."
        score = engine.check_completeness(note)
        assert score == 100.0

    def test_completeness_partial(self):
        from policy_engine.domain.admin.scribe_auditor import ScribeAuditEngine
        engine = ScribeAuditEngine()
        note = "HPI: patient presents. Assessment: stable. Plan: follow up."
        score = engine.check_completeness(note)
        assert score == 60.0

    def test_completeness_empty(self):
        from policy_engine.domain.admin.scribe_auditor import ScribeAuditEngine
        engine = ScribeAuditEngine()
        assert engine.check_completeness("") == 0.0

    def test_icd_format_valid(self):
        from policy_engine.domain.admin.scribe_auditor import ScribeAuditEngine
        engine = ScribeAuditEngine()
        assert engine.validate_icd_format("J18.9") is True

    def test_icd_format_invalid(self):
        from policy_engine.domain.admin.scribe_auditor import ScribeAuditEngine
        engine = ScribeAuditEngine()
        assert engine.validate_icd_format("J189X99") is False

    def test_cpt_format_valid(self):
        from policy_engine.domain.admin.scribe_auditor import ScribeAuditEngine
        engine = ScribeAuditEngine()
        assert engine.validate_cpt_format("99213") is True

    def test_cpt_format_invalid(self):
        from policy_engine.domain.admin.scribe_auditor import ScribeAuditEngine
        engine = ScribeAuditEngine()
        assert engine.validate_cpt_format("9921") is False

    def test_audit_score_formula(self):
        from policy_engine.domain.admin.scribe_auditor import ScribeAuditEngine
        engine = ScribeAuditEngine()
        # completeness=80 * 0.5 = 40.0, no hallucinations, no attribution errors
        assert engine.compute_audit_score(80, 0, 0) == 40.0


# ---------------------------------------------------------------------------
# TestTransparencyDomain (6 tests) — pure domain logic
# ---------------------------------------------------------------------------

class TestTransparencyDomain:
    """Tests for policy_engine.domain.admin.transparency pure domain functions."""

    def test_validate_record_valid(self):
        from policy_engine.domain.admin.transparency import TransparencyRecord, validate_record
        record = TransparencyRecord(
            model_name="AI Model",
            model_version="1.0",
            algorithm_description="Neural network for clinical decision support",
            plain_language_summary="This AI model helps doctors make clinical decisions by analyzing patient data. It was validated on 10,000 patients.",
            evidence_base="Clinical trial data",
            intended_population="Adult inpatients",
            known_limitations="Not validated for pediatric patients",
        )
        errors = validate_record(record)
        assert errors == []

    def test_validate_record_missing_summary(self):
        from policy_engine.domain.admin.transparency import TransparencyRecord, validate_record
        record = TransparencyRecord(
            model_name="AI Model",
            model_version="1.0",
            algorithm_description="Neural network",
            plain_language_summary="",
            evidence_base="Clinical trial data",
            intended_population="Adult inpatients",
            known_limitations="Not validated for pediatric patients",
        )
        errors = validate_record(record)
        assert len(errors) > 0

    def test_validate_record_short_summary(self):
        from policy_engine.domain.admin.transparency import TransparencyRecord, validate_record
        record = TransparencyRecord(
            model_name="AI Model",
            model_version="1.0",
            algorithm_description="Neural network",
            plain_language_summary="Too short",
            evidence_base="Clinical trial data",
            intended_population="Adult inpatients",
            known_limitations="Not validated for pediatric patients",
        )
        errors = validate_record(record)
        assert len(errors) > 0

    def test_validate_record_missing_population(self):
        from policy_engine.domain.admin.transparency import TransparencyRecord, validate_record
        record = TransparencyRecord(
            model_name="AI Model",
            model_version="1.0",
            algorithm_description="Neural network",
            plain_language_summary="This AI model helps doctors make clinical decisions by analyzing patient data in a safe and reliable manner.",
            evidence_base="Clinical trial data",
            intended_population="",
            known_limitations="Not validated for pediatric patients",
        )
        errors = validate_record(record)
        assert len(errors) > 0

    def test_generate_version_snapshot(self):
        from policy_engine.domain.admin.transparency import TransparencyRecord, generate_version_snapshot
        record = TransparencyRecord(
            model_name="AI Model",
            model_version="1.0",
            algorithm_description="Neural network",
            plain_language_summary="This AI model helps doctors make clinical decisions.",
            evidence_base="Clinical trial data",
            intended_population="Adult inpatients",
            known_limitations="Not validated for pediatric patients",
        )
        snapshot = generate_version_snapshot(record)
        assert "model_name" in snapshot
        assert snapshot["model_name"] == "AI Model"

    def test_transparency_record_creation(self):
        from policy_engine.domain.admin.transparency import TransparencyRecord
        record = TransparencyRecord(
            model_name="Test Model",
            model_version="2.0",
            algorithm_description="Test algorithm",
            plain_language_summary="A comprehensive AI system for healthcare decision support.",
            evidence_base="Peer reviewed studies",
            intended_population="General adult population",
            known_limitations="Limited to adult patients",
        )
        assert record.model_name == "Test Model"
        assert record.model_version == "2.0"


# ---------------------------------------------------------------------------
# TestShadowAIRoutes (10 tests)
# ---------------------------------------------------------------------------

class TestShadowAIRoutes:
    """Integration tests for /v1/admin/shadow-ai/* routes."""

    def setup_method(self):
        _ensure_tables()
        self.client = _make_client()
        self.db = _get_test_db()
        self.headers, self.admin_user = _make_admin_headers_and_user(self.db)
        self.viewer_headers, self.viewer_user = _make_viewer_headers_and_user(self.db)

    def teardown_method(self):
        self.db.close()

    def test_create_detection(self):
        payload = {
            "destination_host": "api.openai.com",
            "destination_port": 443,
            "source_ip": "10.0.0.1",
            "department": "ICU",
            "confidence_score": 0.95,
        }
        resp = self.client.post("/v1/admin/shadow-ai/detections", json=payload, headers=self.headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["destination_host"] == "api.openai.com"
        assert data["ai_provider"] == "openai"
        assert data["phi_risk_level"] == "high"

    def test_list_detections(self):
        # Create one first
        payload = {
            "destination_host": "api.anthropic.com",
            "destination_port": 443,
            "source_ip": "10.0.0.2",
            "department": "admin",
        }
        self.client.post("/v1/admin/shadow-ai/detections", json=payload, headers=self.headers)
        resp = self.client.get("/v1/admin/shadow-ai/detections", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_get_detection_detail(self):
        payload = {
            "destination_host": "cohere.ai",
            "destination_port": 443,
            "source_ip": "10.0.0.3",
            "department": "radiology",
        }
        create_resp = self.client.post("/v1/admin/shadow-ai/detections", json=payload, headers=self.headers)
        det_id = create_resp.json()["id"]
        resp = self.client.get(f"/v1/admin/shadow-ai/detections/{det_id}", headers=self.headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == det_id

    def test_review_detection(self):
        payload = {
            "destination_host": "api.openai.com",
            "destination_port": 443,
            "source_ip": "10.0.0.4",
            "department": "ed",
        }
        create_resp = self.client.post("/v1/admin/shadow-ai/detections", json=payload, headers=self.headers)
        det_id = create_resp.json()["id"]
        review_payload = {"status": "reviewed", "notes": "Approved by IT security team"}
        resp = self.client.patch(f"/v1/admin/shadow-ai/detections/{det_id}/review", json=review_payload, headers=self.headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "reviewed"

    def test_add_to_allowlist(self):
        payload = {
            "host_pattern": "*.internal.hospital.com",
            "reason": "Internal AI tools",
        }
        resp = self.client.post("/v1/admin/shadow-ai/allowlist", json=payload, headers=self.headers)
        assert resp.status_code == 201
        assert resp.json()["host_pattern"] == "*.internal.hospital.com"

    def test_list_allowlist(self):
        resp = self.client.get("/v1/admin/shadow-ai/allowlist", headers=self.headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_delete_allowlist_entry(self):
        payload = {"host_pattern": "api.delete-me.com", "reason": "Test"}
        create_resp = self.client.post("/v1/admin/shadow-ai/allowlist", json=payload, headers=self.headers)
        entry_id = create_resp.json()["id"]
        resp = self.client.delete(f"/v1/admin/shadow-ai/allowlist/{entry_id}", headers=self.headers)
        assert resp.status_code == 204

    def test_get_summary(self):
        resp = self.client.get("/v1/admin/shadow-ai/summary", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "by_provider" in data
        assert "by_phi_risk" in data
        assert "by_status" in data

    def test_detection_forbidden_viewer(self):
        payload = {
            "destination_host": "api.openai.com",
            "destination_port": 443,
            "source_ip": "10.0.0.5",
            "department": "ICU",
        }
        resp = self.client.post("/v1/admin/shadow-ai/detections", json=payload, headers=self.viewer_headers)
        assert resp.status_code == 403

    def test_filter_by_risk_level(self):
        # Create a high-risk detection first
        payload = {
            "destination_host": "api.openai.com",
            "destination_port": 443,
            "source_ip": "10.0.0.6",
            "department": "ICU",
        }
        self.client.post("/v1/admin/shadow-ai/detections", json=payload, headers=self.headers)
        resp = self.client.get("/v1/admin/shadow-ai/detections?phi_risk_level=high", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        for item in data:
            assert item["phi_risk_level"] == "high"


# ---------------------------------------------------------------------------
# TestScribeAuditRoutes (10 tests)
# ---------------------------------------------------------------------------

class TestScribeAuditRoutes:
    """Integration tests for /v1/admin/scribe-audits/* routes."""

    def setup_method(self):
        _ensure_tables()
        self.client = _make_client()
        self.db = _get_test_db()
        self.headers, self.admin_user = _make_admin_headers_and_user(self.db)
        self.viewer_headers, self.viewer_user = _make_viewer_headers_and_user(self.db)

    def teardown_method(self):
        self.db.close()

    def _create_audit(self, note_text=None, session_id=None):
        if note_text is None:
            note_text = "HPI: patient presents with chest pain. Assessment: angina. Plan: refer to cardiology. Medication: aspirin. Vital signs: BP 140/90."
        if session_id is None:
            session_id = str(uuid.uuid4())
        payload = {
            "session_id": session_id,
            "note_text": note_text,
            "source_data": {"bp": "140/90", "hr": "72"},
            "patient_context": "62 year old male",
            "ai_model_used": "gpt-4",
        }
        return self.client.post("/v1/admin/scribe-audits", json=payload, headers=self.headers)

    def test_create_scribe_audit(self):
        resp = self._create_audit()
        assert resp.status_code == 201
        data = resp.json()
        assert "session_id" in data
        assert "audit_score" in data

    def test_scribe_audit_stores_hash_not_note(self):
        resp = self._create_audit()
        assert resp.status_code == 201
        data = resp.json()
        # Raw note text must NOT appear in response
        assert "note_text" not in data

    def test_list_scribe_audits(self):
        self._create_audit()
        resp = self.client.get("/v1/admin/scribe-audits", headers=self.headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_scribe_audit_detail(self):
        create_resp = self._create_audit()
        audit_id = create_resp.json()["id"]
        resp = self.client.get(f"/v1/admin/scribe-audits/{audit_id}", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "findings" in data

    def test_complete_scribe_audit(self):
        create_resp = self._create_audit()
        audit_id = create_resp.json()["id"]
        resp = self.client.post(f"/v1/admin/scribe-audits/{audit_id}/complete", headers=self.headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "complete"

    def test_scribe_audit_stats(self):
        self._create_audit()
        resp = self.client.get("/v1/admin/scribe-audits/stats", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_audits" in data
        assert "avg_audit_score" in data

    def test_hallucination_detection(self):
        # Note contains number "999" not in source_data
        note = "HPI: patient presents. Assessment: BP was 999/80. Plan: monitor. Medication: aspirin. Vital signs noted."
        resp = self._create_audit(note_text=note)
        assert resp.status_code == 201
        data = resp.json()
        assert data["hallucination_detected"] is True

    def test_completeness_scoring(self):
        note = "HPI: patient presents with fever. Assessment: viral infection. Plan: rest and fluids. Medication: ibuprofen 400mg. Vital signs: temp 38.5C BP 110/70."
        resp = self._create_audit(note_text=note)
        assert resp.status_code == 201
        data = resp.json()
        assert data["completeness_score"] == 100.0

    def test_findings_persisted(self):
        # Force hallucination with a number not in source
        note = "HPI: chest pain. Assessment: critical condition 8877. Plan: immediate surgery. Medication: IV morphine. Vital signs stable."
        resp = self._create_audit(note_text=note)
        assert resp.status_code == 201
        data = resp.json()
        assert "findings" in data
        assert isinstance(data["findings"], list)

    def test_scribe_audit_forbidden(self):
        payload = {
            "session_id": str(uuid.uuid4()),
            "note_text": "HPI: test. Assessment: test. Plan: test. Medication: test. Vital signs: test.",
            "source_data": {},
        }
        resp = self.client.post("/v1/admin/scribe-audits", json=payload, headers=self.viewer_headers)
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# TestTransparencyRoutes (13 tests)
# ---------------------------------------------------------------------------

class TestTransparencyRoutes:
    """Integration tests for /v1/transparency/* routes."""

    def setup_method(self):
        _ensure_tables()
        self.client = _make_client()
        self.db = _get_test_db()
        self.headers, self.admin_user = _make_admin_headers_and_user(self.db)
        self.viewer_headers, self.viewer_user = _make_viewer_headers_and_user(self.db)

    def teardown_method(self):
        self.db.close()

    def _valid_record_payload(self):
        return {
            "model_name": f"Clinical AI Model {uuid.uuid4().hex[:6]}",
            "model_version": "1.0",
            "algorithm_description": "Gradient boosted trees for sepsis prediction",
            "plain_language_summary": "This AI model helps identify patients at risk of sepsis by analyzing vital signs and lab results in real time.",
            "evidence_base": "Retrospective study of 50,000 ICU patients at 3 academic medical centers",
            "intended_population": "Adult ICU patients age 18 and older",
            "known_limitations": "Not validated for pediatric patients or outpatient settings",
            "bias_considerations": "May underperform in minority populations",
            "regulatory_status": "FDA 510(k) cleared",
        }

    def test_create_transparency_record(self):
        resp = self.client.post("/v1/transparency", json=self._valid_record_payload(), headers=self.headers)
        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert data["model_name"].startswith("Clinical AI Model")

    def test_list_transparency_public(self):
        # Create and publish a record first
        create_resp = self.client.post("/v1/transparency", json=self._valid_record_payload(), headers=self.headers)
        rec_id = create_resp.json()["id"]
        self.client.post(f"/v1/transparency/{rec_id}/publish", headers=self.headers)
        # Now list without any auth headers
        resp = self.client.get("/v1/transparency")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_transparency_detail_public(self):
        create_resp = self.client.post("/v1/transparency", json=self._valid_record_payload(), headers=self.headers)
        rec_id = create_resp.json()["id"]
        self.client.post(f"/v1/transparency/{rec_id}/publish", headers=self.headers)
        # GET without auth
        resp = self.client.get(f"/v1/transparency/{rec_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == rec_id

    def test_get_versions_public(self):
        create_resp = self.client.post("/v1/transparency", json=self._valid_record_payload(), headers=self.headers)
        rec_id = create_resp.json()["id"]
        self.client.post(f"/v1/transparency/{rec_id}/publish", headers=self.headers)
        # GET versions without auth
        resp = self.client.get(f"/v1/transparency/{rec_id}/versions")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_acknowledge_anonymous(self):
        create_resp = self.client.post("/v1/transparency", json=self._valid_record_payload(), headers=self.headers)
        rec_id = create_resp.json()["id"]
        self.client.post(f"/v1/transparency/{rec_id}/publish", headers=self.headers)
        # POST acknowledge without auth
        resp = self.client.post(
            f"/v1/transparency/{rec_id}/acknowledge",
            json={},
            headers={"X-API-Key": "dummy-bypass-csrf"},
        )
        assert resp.status_code == 201

    def test_acknowledge_with_user(self):
        create_resp = self.client.post("/v1/transparency", json=self._valid_record_payload(), headers=self.headers)
        rec_id = create_resp.json()["id"]
        self.client.post(f"/v1/transparency/{rec_id}/publish", headers=self.headers)
        resp = self.client.post(
            f"/v1/transparency/{rec_id}/acknowledge",
            json={"user_id": "dr-smith-123", "role": "physician"},
            headers={"X-API-Key": "dummy-bypass-csrf"},
        )
        assert resp.status_code == 201

    def test_publish_transparency(self):
        create_resp = self.client.post("/v1/transparency", json=self._valid_record_payload(), headers=self.headers)
        rec_id = create_resp.json()["id"]
        resp = self.client.post(f"/v1/transparency/{rec_id}/publish", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["published_at"] is not None

    def test_update_creates_version(self):
        create_resp = self.client.post("/v1/transparency", json=self._valid_record_payload(), headers=self.headers)
        rec_id = create_resp.json()["id"]
        updated_payload = self._valid_record_payload()
        updated_payload["model_version"] = "2.0"
        resp = self.client.put(f"/v1/transparency/{rec_id}", json=updated_payload, headers=self.headers)
        assert resp.status_code == 200
        assert resp.json()["model_version"] == "2.0"

    def test_list_only_published(self):
        # Create but do NOT publish
        create_resp = self.client.post("/v1/transparency", json=self._valid_record_payload(), headers=self.headers)
        rec_id = create_resp.json()["id"]
        # Public list should not contain it
        resp = self.client.get("/v1/transparency")
        assert resp.status_code == 200
        ids_in_list = [r["id"] for r in resp.json()]
        assert rec_id not in ids_in_list

    def test_create_forbidden_viewer(self):
        resp = self.client.post("/v1/transparency", json=self._valid_record_payload(), headers=self.viewer_headers)
        assert resp.status_code == 403

    def test_create_forbidden_no_auth(self):
        resp = self.client.post(
            "/v1/transparency",
            json=self._valid_record_payload(),
            headers={"X-API-Key": "dummy-bypass-csrf"},  # no Bearer
        )
        assert resp.status_code == 401

    def test_validate_short_summary(self):
        payload = self._valid_record_payload()
        payload["plain_language_summary"] = "Too short"
        resp = self.client.post("/v1/transparency", json=payload, headers=self.headers)
        assert resp.status_code == 422

    def test_version_history_increments(self):
        create_resp = self.client.post("/v1/transparency", json=self._valid_record_payload(), headers=self.headers)
        rec_id = create_resp.json()["id"]
        self.client.post(f"/v1/transparency/{rec_id}/publish", headers=self.headers)
        versions_resp = self.client.get(f"/v1/transparency/{rec_id}/versions")
        assert versions_resp.status_code == 200
        versions = versions_resp.json()
        assert len(versions) >= 1
        assert versions[0]["version_number"] >= 1
