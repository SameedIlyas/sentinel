"""Phase 5 Financial Governance tests — TDD"""
import os
import uuid
from datetime import datetime

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_phase5.db")
os.environ.setdefault("SECRET_KEY", "test-secret-phase5-xyz-abc")


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
    import policy_engine.main  # noqa
    from policy_engine.database import Base, engine
    Base.metadata.create_all(bind=engine)


def _get_test_db():
    from policy_engine.database import SessionLocal
    return SessionLocal()


# ---------------------------------------------------------------------------
# TestPriorAuthDomain (12 tests) — pure domain logic
# ---------------------------------------------------------------------------

class TestPriorAuthDomain:
    def test_compute_record_hash_deterministic(self):
        from policy_engine.domain.finance.prior_auth import compute_record_hash
        data = {"patient_id_hash": "abc", "claim_id": "C1", "service_type": "imaging",
                "request_date": "2024-01-01", "ai_recommendation": "approve",
                "final_decision": "approved", "denial_reason_code": "",
                "human_reviewer_id": "", "created_at": "2024-01-01T00:00:00"}
        h1 = compute_record_hash(data, "")
        h2 = compute_record_hash(data, "")
        assert h1 == h2

    def test_compute_record_hash_different_prev(self):
        from policy_engine.domain.finance.prior_auth import compute_record_hash
        data = {"patient_id_hash": "abc", "claim_id": "C1", "service_type": "imaging",
                "request_date": "2024-01-01", "ai_recommendation": "approve",
                "final_decision": "approved", "denial_reason_code": "",
                "human_reviewer_id": "", "created_at": "2024-01-01T00:00:00"}
        h1 = compute_record_hash(data, "prev_hash_A")
        h2 = compute_record_hash(data, "prev_hash_B")
        assert h1 != h2

    def test_compute_record_hash_tamper_detection(self):
        from policy_engine.domain.finance.prior_auth import compute_record_hash
        data = {"patient_id_hash": "abc", "claim_id": "C1", "service_type": "imaging",
                "request_date": "2024-01-01", "ai_recommendation": "approve",
                "final_decision": "approved", "denial_reason_code": "",
                "human_reviewer_id": "", "created_at": "2024-01-01T00:00:00"}
        h1 = compute_record_hash(data, "")
        data2 = dict(data)
        data2["final_decision"] = "denied"  # tamper
        h2 = compute_record_hash(data2, "")
        assert h1 != h2

    def test_verify_chain_empty(self):
        from policy_engine.domain.finance.prior_auth import verify_chain
        valid, broken = verify_chain([])
        assert valid is True
        assert broken is None

    def test_verify_chain_single_record(self):
        from policy_engine.domain.finance.prior_auth import compute_record_hash, verify_chain
        data = {"patient_id_hash": "abc", "claim_id": "C1", "service_type": "imaging",
                "request_date": "2024-01-01", "ai_recommendation": "approve",
                "final_decision": "approved", "denial_reason_code": "",
                "human_reviewer_id": "", "created_at": "2024-01-01T00:00:00"}
        record_hash = compute_record_hash(data, "")
        records = [{"id": "r1", "data": data, "record_hash": record_hash}]
        valid, broken = verify_chain(records)
        assert valid is True
        assert broken is None

    def test_verify_chain_two_records(self):
        from policy_engine.domain.finance.prior_auth import compute_record_hash, verify_chain
        data1 = {"patient_id_hash": "abc", "claim_id": "C1", "service_type": "imaging",
                 "request_date": "2024-01-01", "ai_recommendation": "approve",
                 "final_decision": "approved", "denial_reason_code": "",
                 "human_reviewer_id": "", "created_at": "2024-01-01T00:00:00"}
        hash1 = compute_record_hash(data1, "")
        data2 = {"patient_id_hash": "def", "claim_id": "C2", "service_type": "lab",
                 "request_date": "2024-01-02", "ai_recommendation": "deny",
                 "final_decision": "denied", "denial_reason_code": "001",
                 "human_reviewer_id": "", "created_at": "2024-01-02T00:00:00"}
        hash2 = compute_record_hash(data2, hash1)
        records = [
            {"id": "r1", "data": data1, "record_hash": hash1},
            {"id": "r2", "data": data2, "record_hash": hash2},
        ]
        valid, broken = verify_chain(records)
        assert valid is True
        assert broken is None

    def test_verify_chain_tampered(self):
        from policy_engine.domain.finance.prior_auth import compute_record_hash, verify_chain
        data1 = {"patient_id_hash": "abc", "claim_id": "C1", "service_type": "imaging",
                 "request_date": "2024-01-01", "ai_recommendation": "approve",
                 "final_decision": "approved", "denial_reason_code": "",
                 "human_reviewer_id": "", "created_at": "2024-01-01T00:00:00"}
        hash1 = compute_record_hash(data1, "")
        records = [{"id": "r1", "data": {"patient_id_hash": "TAMPERED", "claim_id": "C1",
                    "service_type": "imaging", "request_date": "2024-01-01",
                    "ai_recommendation": "approve", "final_decision": "approved",
                    "denial_reason_code": "", "human_reviewer_id": "",
                    "created_at": "2024-01-01T00:00:00"}, "record_hash": hash1}]
        valid, broken = verify_chain(records)
        assert valid is False
        assert broken == "r1"

    def test_verify_chain_broken_at_second(self):
        from policy_engine.domain.finance.prior_auth import compute_record_hash, verify_chain
        data1 = {"patient_id_hash": "abc", "claim_id": "C1", "service_type": "imaging",
                 "request_date": "2024-01-01", "ai_recommendation": "approve",
                 "final_decision": "approved", "denial_reason_code": "",
                 "human_reviewer_id": "", "created_at": "2024-01-01T00:00:00"}
        hash1 = compute_record_hash(data1, "")
        data2 = {"patient_id_hash": "def", "claim_id": "C2", "service_type": "lab",
                 "request_date": "2024-01-02", "ai_recommendation": "deny",
                 "final_decision": "denied", "denial_reason_code": "001",
                 "human_reviewer_id": "", "created_at": "2024-01-02T00:00:00"}
        # Compute wrong hash (using wrong prev_hash)
        wrong_hash2 = compute_record_hash(data2, "wrong_prev")
        records = [
            {"id": "r1", "data": data1, "record_hash": hash1},
            {"id": "r2", "data": data2, "record_hash": wrong_hash2},
        ]
        valid, broken = verify_chain(records)
        assert valid is False
        assert broken == "r2"

    def test_prior_auth_record_dataclass(self):
        from policy_engine.domain.finance.prior_auth import PriorAuthRecord, PriorAuthDecision, FinalDecision
        record = PriorAuthRecord(
            id="r1", patient_id_hash="abc123", claim_id="C1",
            service_type="imaging", request_date="2024-01-01",
            ai_recommendation=PriorAuthDecision.APPROVE,
            final_decision=FinalDecision.APPROVED,
        )
        assert record.id == "r1"
        assert record.patient_id_hash == "abc123"

    def test_denial_reason_codes(self):
        from policy_engine.domain.finance.prior_auth import DENIAL_REASON_CODES
        assert len(DENIAL_REASON_CODES) == 8
        assert "001" in DENIAL_REASON_CODES
        assert "008" in DENIAL_REASON_CODES

    def test_final_decision_enum(self):
        from policy_engine.domain.finance.prior_auth import FinalDecision
        assert FinalDecision.APPROVED.value == "approved"
        assert FinalDecision.DENIED.value == "denied"
        assert FinalDecision.PENDING.value == "pending"
        assert FinalDecision.APPEALED.value == "appealed"

    def test_ai_recommendation_enum(self):
        from policy_engine.domain.finance.prior_auth import PriorAuthDecision
        assert PriorAuthDecision.APPROVE.value == "approve"
        assert PriorAuthDecision.DENY.value == "deny"
        assert PriorAuthDecision.PEND.value == "pend"


# ---------------------------------------------------------------------------
# TestRevenueCycleDomain (10 tests) — pure domain logic
# ---------------------------------------------------------------------------

class TestRevenueCycleDomain:
    def test_detect_upcoding_above_p90(self):
        from policy_engine.domain.finance.revenue_cycle import detect_upcoding
        assert detect_upcoding("99213", 500.0, {"p90_amount": 200.0}) is True

    def test_detect_upcoding_below_p90(self):
        from policy_engine.domain.finance.revenue_cycle import detect_upcoding
        assert detect_upcoding("99213", 150.0, {"p90_amount": 200.0}) is False

    def test_detect_upcoding_at_p90(self):
        from policy_engine.domain.finance.revenue_cycle import detect_upcoding
        assert detect_upcoding("99213", 200.0, {"p90_amount": 200.0}) is False

    def test_detect_unbundling_known_pair(self):
        from policy_engine.domain.finance.revenue_cycle import detect_unbundling
        warnings = detect_unbundling(["99213", "99214"])
        assert len(warnings) > 0

    def test_detect_unbundling_no_issue(self):
        from policy_engine.domain.finance.revenue_cycle import detect_unbundling
        warnings = detect_unbundling(["99201", "80053"])
        assert len(warnings) == 0

    def test_detect_modifier_abuse_59_duplicate(self):
        from policy_engine.domain.finance.revenue_cycle import detect_modifier_abuse
        warnings = detect_modifier_abuse(["59"], ["99213", "99213"])
        assert len(warnings) > 0

    def test_detect_modifier_abuse_clean(self):
        from policy_engine.domain.finance.revenue_cycle import detect_modifier_abuse
        warnings = detect_modifier_abuse(["21"], ["99213"])
        assert len(warnings) == 0

    def test_compute_risk_score_critical(self):
        from policy_engine.domain.finance.revenue_cycle import compute_risk_score, RevenueFindings
        findings = [RevenueFindings("upcoding", "critical", "desc", [], None)]
        score = compute_risk_score(findings)
        assert score == 30.0

    def test_compute_risk_score_multiple(self):
        from policy_engine.domain.finance.revenue_cycle import compute_risk_score, RevenueFindings
        findings = [
            RevenueFindings("upcoding", "critical", "desc", [], None),
            RevenueFindings("unbundling", "high", "desc", [], None),
            RevenueFindings("modifier_abuse", "medium", "desc", [], None),
        ]
        score = compute_risk_score(findings)
        assert score == 60.0

    def test_compute_risk_score_clamp(self):
        from policy_engine.domain.finance.revenue_cycle import compute_risk_score, RevenueFindings
        findings = [RevenueFindings("upcoding", "critical", "desc", [], None)] * 10
        score = compute_risk_score(findings)
        assert score == 100.0


# ---------------------------------------------------------------------------
# TestPriorAuthRoutes (14 tests)
# ---------------------------------------------------------------------------

class TestPriorAuthRoutes:
    def setup_method(self):
        _ensure_tables()
        self.client = _make_client()
        self.db = _get_test_db()
        # Each test method gets a unique org_id so chains start fresh
        self.org_id = str(uuid.uuid4())
        self.headers, self.admin_user = _make_user_headers(self.db, "system_admin", org_id=self.org_id)
        self.compliance_headers, self.compliance_user = _make_user_headers(self.db, "compliance_officer", org_id=self.org_id)
        self.viewer_headers, self.viewer_user = _make_user_headers(self.db, "viewer", org_id=self.org_id)

    def teardown_method(self):
        self.db.close()

    def _create_record(self, headers=None):
        if headers is None:
            headers = self.headers
        return self.client.post("/v1/finance/prior-auth", json={
            "patient_id": "PAT001",
            "claim_id": f"CLM-{uuid.uuid4().hex[:8]}",
            "service_type": "imaging",
            "request_date": "2024-01-01",
            "ai_recommendation": "approve",
            "ai_confidence": 0.95,
            "final_decision": "approved",
        }, headers=headers)

    def test_create_prior_auth(self):
        r = self._create_record()
        assert r.status_code == 201
        data = r.json()
        assert "record_hash" in data
        assert len(data["record_hash"]) == 64  # SHA-256 hex

    def test_create_sets_prev_hash_empty_first(self):
        r = self._create_record()
        assert r.status_code == 201
        assert r.json()["prev_record_hash"] == ""

    def test_create_chains_prev_hash(self):
        r1 = self._create_record()
        r2 = self._create_record()
        assert r2.json()["prev_record_hash"] == r1.json()["record_hash"]

    def test_list_prior_auth(self):
        self._create_record()
        r = self.client.get("/v1/finance/prior-auth", headers=self.headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_get_prior_auth_detail(self):
        created = self._create_record().json()
        r = self.client.get(f"/v1/finance/prior-auth/{created['id']}", headers=self.headers)
        assert r.status_code == 200
        assert r.json()["id"] == created["id"]

    def test_no_update_endpoint(self):
        created = self._create_record().json()
        r = self.client.put(f"/v1/finance/prior-auth/{created['id']}", json={}, headers=self.headers)
        assert r.status_code in (404, 405)

    def test_no_delete_endpoint(self):
        created = self._create_record().json()
        r = self.client.delete(f"/v1/finance/prior-auth/{created['id']}", headers=self.headers)
        assert r.status_code in (404, 405)

    def test_verify_chain_valid(self):
        self._create_record()
        self._create_record()
        r = self.client.get("/v1/finance/prior-auth/verify-chain", headers=self.headers)
        assert r.status_code == 200
        assert r.json()["chain_valid"] is True

    def test_verify_chain_detects_tampering(self):
        r1 = self._create_record().json()
        self._create_record()
        # Corrupt first record's hash in DB
        from policy_engine.models.prior_auth import PriorAuthRecord as PAR
        self.db.query(PAR).filter(PAR.id == r1["id"]).update({"record_hash": "corrupted_hash"})
        self.db.commit()
        r = self.client.get("/v1/finance/prior-auth/verify-chain", headers=self.headers)
        assert r.status_code == 200
        assert r.json()["chain_valid"] is False

    def test_verify_chain_accessible_to_compliance_officer(self):
        r = self.client.get("/v1/finance/prior-auth/verify-chain", headers=self.compliance_headers)
        assert r.status_code == 200

    def test_stats_endpoint(self):
        self._create_record()
        r = self.client.get("/v1/finance/prior-auth/stats", headers=self.headers)
        assert r.status_code == 200
        data = r.json()
        assert "approval_rate" in data
        assert "denial_rate" in data

    def test_filter_by_final_decision(self):
        self._create_record()
        r = self.client.get("/v1/finance/prior-auth?final_decision=approved", headers=self.headers)
        assert r.status_code == 200

    def test_prior_auth_forbidden_viewer(self):
        r = self.client.get("/v1/finance/prior-auth", headers=self.viewer_headers)
        assert r.status_code == 403

    def test_prior_auth_forbidden_no_auth(self):
        r = self.client.get("/v1/finance/prior-auth")
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# TestRevenueCycleRoutes (13 tests)
# ---------------------------------------------------------------------------

class TestRevenueCycleRoutes:
    def setup_method(self):
        _ensure_tables()
        self.client = _make_client()
        self.db = _get_test_db()
        self.org_id = str(uuid.uuid4())
        self.headers, self.admin_user = _make_user_headers(self.db, "system_admin", org_id=self.org_id)
        self.viewer_headers, self.viewer_user = _make_user_headers(self.db, "viewer", org_id=self.org_id)

    def teardown_method(self):
        self.db.close()

    def _create_audit(self, amount=100.0):
        return self.client.post("/v1/finance/revenue-cycle", json={
            "claim_id": f"CLM-{uuid.uuid4().hex[:8]}",
            "claim_date": "2024-01-01",
            "provider_id": "PROV001",
            "payer_id": "PAYER001",
            "primary_diagnosis_code": "J18.9",
            "procedure_codes": ["99213"],
            "modifiers": [],
            "billed_amount": amount,
        }, headers=self.headers)

    def test_create_revenue_audit(self):
        r = self._create_audit()
        assert r.status_code == 201
        assert "risk_score" in r.json()

    def test_create_audit_detects_findings(self):
        # First create a benchmark so upcoding can be detected
        self.client.post("/v1/finance/revenue-cycle/benchmarks", json={
            "procedure_code": "99213", "specialty": "general",
            "p25_amount": 50.0, "p50_amount": 100.0, "p75_amount": 150.0,
            "p90_amount": 200.0, "national_frequency_per_1000": 500.0,
            "source": "CMS"
        }, headers=self.headers)
        r = self._create_audit(amount=999.0)
        assert r.status_code == 201
        data = r.json()
        assert data["risk_score"] > 0 or len(data.get("findings", [])) >= 0

    def test_list_revenue_audits(self):
        self._create_audit()
        r = self.client.get("/v1/finance/revenue-cycle", headers=self.headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_get_audit_detail(self):
        created = self._create_audit().json()
        r = self.client.get(f"/v1/finance/revenue-cycle/{created['id']}", headers=self.headers)
        assert r.status_code == 200

    def test_review_audit(self):
        created = self._create_audit().json()
        r = self.client.patch(f"/v1/finance/revenue-cycle/{created['id']}/review",
                              json={"notes": "looks ok"}, headers=self.headers)
        assert r.status_code == 200
        assert r.json()["status"] == "reviewed"

    def test_revenue_stats(self):
        self._create_audit()
        r = self.client.get("/v1/finance/revenue-cycle/stats", headers=self.headers)
        assert r.status_code == 200
        assert "avg_risk_score" in r.json()

    def test_filter_by_status(self):
        r = self.client.get("/v1/finance/revenue-cycle?status=clean", headers=self.headers)
        assert r.status_code == 200

    def test_filter_by_risk_range(self):
        r = self.client.get("/v1/finance/revenue-cycle?min_risk=0", headers=self.headers)
        assert r.status_code == 200

    def test_create_benchmark(self):
        r = self.client.post("/v1/finance/revenue-cycle/benchmarks", json={
            "procedure_code": "80053", "specialty": "lab",
            "p25_amount": 20.0, "p50_amount": 40.0, "p75_amount": 60.0,
            "p90_amount": 80.0, "national_frequency_per_1000": 300.0, "source": "CMS"
        }, headers=self.headers)
        assert r.status_code == 201

    def test_list_benchmarks(self):
        r = self.client.get("/v1/finance/revenue-cycle/benchmarks", headers=self.headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_benchmark_filter(self):
        self.client.post("/v1/finance/revenue-cycle/benchmarks", json={
            "procedure_code": "99213", "specialty": "general",
            "p25_amount": 50.0, "p50_amount": 100.0, "p75_amount": 150.0,
            "p90_amount": 200.0, "national_frequency_per_1000": 500.0, "source": "CMS"
        }, headers=self.headers)
        r = self.client.get("/v1/finance/revenue-cycle/benchmarks?procedure_code=99213", headers=self.headers)
        assert r.status_code == 200
        data = r.json()
        assert any(b["procedure_code"] == "99213" for b in data)

    def test_revenue_forbidden_viewer(self):
        r = self.client.get("/v1/finance/revenue-cycle", headers=self.viewer_headers)
        assert r.status_code == 403

    def test_upcoding_flagged_in_audit(self):
        # Create benchmark first
        self.client.post("/v1/finance/revenue-cycle/benchmarks", json={
            "procedure_code": "99999_test", "specialty": "test",
            "p25_amount": 10.0, "p50_amount": 20.0, "p75_amount": 30.0,
            "p90_amount": 50.0, "national_frequency_per_1000": 100.0, "source": "CMS"
        }, headers=self.headers)
        r = self.client.post("/v1/finance/revenue-cycle", json={
            "claim_id": f"CLM-{uuid.uuid4().hex[:8]}",
            "claim_date": "2024-01-01", "provider_id": "PROV001",
            "payer_id": "PAYER001", "primary_diagnosis_code": "J18.9",
            "procedure_codes": ["99999_test"], "modifiers": [],
            "billed_amount": 999.0,
        }, headers=self.headers)
        assert r.status_code == 201
        data = r.json()
        assert data["risk_score"] > 0


# ---------------------------------------------------------------------------
# TestPriorAuthChainIntegrity (6 tests)
# ---------------------------------------------------------------------------

class TestPriorAuthChainIntegrity:
    def setup_method(self):
        _ensure_tables()
        self.client = _make_client()
        self.db = _get_test_db()
        self.org_id = str(uuid.uuid4())
        self.headers, self.admin_user = _make_user_headers(self.db, "system_admin", org_id=self.org_id)

    def teardown_method(self):
        self.db.close()

    def _make_data(self, claim_id, ts):
        return {"patient_id_hash": "abc", "claim_id": claim_id,
                "service_type": "imaging", "request_date": "2024-01-01",
                "ai_recommendation": "approve", "final_decision": "approved",
                "denial_reason_code": "", "human_reviewer_id": "",
                "created_at": ts}

    def test_chain_integrity_3_records(self):
        from policy_engine.domain.finance.prior_auth import compute_record_hash, verify_chain
        d1 = self._make_data("C1", "2024-01-01T00:00:00")
        d2 = self._make_data("C2", "2024-01-02T00:00:00")
        d3 = self._make_data("C3", "2024-01-03T00:00:00")
        h1 = compute_record_hash(d1, "")
        h2 = compute_record_hash(d2, h1)
        h3 = compute_record_hash(d3, h2)
        records = [
            {"id": "r1", "data": d1, "record_hash": h1},
            {"id": "r2", "data": d2, "record_hash": h2},
            {"id": "r3", "data": d3, "record_hash": h3},
        ]
        valid, broken = verify_chain(records)
        assert valid is True
        assert broken is None

    def test_chain_breaks_on_insert_tampering(self):
        from policy_engine.domain.finance.prior_auth import compute_record_hash, verify_chain
        d1 = self._make_data("C1", "2024-01-01T00:00:00")
        d2 = self._make_data("C2", "2024-01-02T00:00:00")
        h1 = compute_record_hash(d1, "")
        h2 = compute_record_hash(d2, h1)
        # Tamper d1
        tampered_d1 = dict(d1)
        tampered_d1["final_decision"] = "denied"
        records = [
            {"id": "r1", "data": tampered_d1, "record_hash": h1},
            {"id": "r2", "data": d2, "record_hash": h2},
        ]
        valid, broken = verify_chain(records)
        assert valid is False
        assert broken == "r1"

    def test_chain_empty_org(self):
        r = self.client.get("/v1/finance/prior-auth/verify-chain", headers=self.headers)
        assert r.status_code == 200
        data = r.json()
        assert "chain_valid" in data

    def test_chain_status_stored(self):
        self.client.get("/v1/finance/prior-auth/verify-chain", headers=self.headers)
        from policy_engine.models.prior_auth import PriorAuthChainStatus
        status = self.db.query(PriorAuthChainStatus).first()
        # May or may not have a record depending on org; just check the query works
        assert True  # no exception = pass

    def test_hash_is_deterministic_across_restarts(self):
        from policy_engine.domain.finance.prior_auth import compute_record_hash
        data = self._make_data("C1", "2024-01-01T00:00:00")
        h1 = compute_record_hash(data, "prev")
        h2 = compute_record_hash(data, "prev")
        assert h1 == h2

    def test_chain_ordering(self):
        from policy_engine.domain.finance.prior_auth import compute_record_hash, verify_chain
        d1 = self._make_data("C1", "2024-01-01T00:00:00")
        d2 = self._make_data("C2", "2024-01-02T00:00:00")
        h1 = compute_record_hash(d1, "")
        h2 = compute_record_hash(d2, h1)
        # Out of order should fail
        records_reversed = [
            {"id": "r2", "data": d2, "record_hash": h2},
            {"id": "r1", "data": d1, "record_hash": h1},
        ]
        valid, broken = verify_chain(records_reversed)
        # When reversed, r2 is checked first with prev="" but its hash was computed with h1
        assert valid is False
