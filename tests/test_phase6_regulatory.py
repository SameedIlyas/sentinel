"""Phase 6 MedTech & Regulatory Automation tests — TDD"""
import os
import uuid
import pytest
from datetime import datetime

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_phase6.db")
os.environ.setdefault("SECRET_KEY", "test-secret-phase6-xyz-abc")


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
# TestTechnicalFileDomain (10 tests) — pure domain logic, no DB
# ---------------------------------------------------------------------------

class TestTechnicalFileDomain:
    def test_lifecycle_draft_to_submitted(self):
        from policy_engine.domain.regulatory.technical_file import (
            TechnicalFileEntity, TechnicalFileLifecycle, RegulatoryType,
        )
        entity = TechnicalFileEntity(
            id="tf1", title="FDA File", regulatory_type=RegulatoryType.FDA_510K,
            product_name="DiagAI", device_version="1.0",
        )
        entity.transition_to(TechnicalFileLifecycle.SUBMITTED)
        assert entity.lifecycle_stage == TechnicalFileLifecycle.SUBMITTED

    def test_lifecycle_invalid_transition_raises(self):
        from policy_engine.domain.regulatory.technical_file import (
            TechnicalFileEntity, TechnicalFileLifecycle, RegulatoryType,
        )
        entity = TechnicalFileEntity(
            id="tf2", title="FDA File", regulatory_type=RegulatoryType.FDA_510K,
            product_name="DiagAI", device_version="1.0",
        )
        with pytest.raises(ValueError, match="Cannot transition"):
            entity.transition_to(TechnicalFileLifecycle.APPROVED)

    def test_lifecycle_approved_to_retired(self):
        from policy_engine.domain.regulatory.technical_file import (
            TechnicalFileEntity, TechnicalFileLifecycle, RegulatoryType,
        )
        entity = TechnicalFileEntity(
            id="tf3", title="File", regulatory_type=RegulatoryType.EU_MDR,
            product_name="PredAI", device_version="2.0",
            lifecycle_stage=TechnicalFileLifecycle.APPROVED,
        )
        entity.transition_to(TechnicalFileLifecycle.RETIRED)
        assert entity.lifecycle_stage == TechnicalFileLifecycle.RETIRED

    def test_lifecycle_retired_no_transitions(self):
        from policy_engine.domain.regulatory.technical_file import (
            TechnicalFileEntity, TechnicalFileLifecycle, RegulatoryType,
        )
        entity = TechnicalFileEntity(
            id="tf4", title="File", regulatory_type=RegulatoryType.FDA_510K,
            product_name="X", device_version="1.0",
            lifecycle_stage=TechnicalFileLifecycle.RETIRED,
        )
        with pytest.raises(ValueError):
            entity.transition_to(TechnicalFileLifecycle.DRAFT)

    def test_required_sections_fda_510k(self):
        from policy_engine.domain.regulatory.technical_file import (
            TechnicalFileEntity, RegulatoryType, FDA_510K_SECTIONS,
        )
        entity = TechnicalFileEntity(
            id="tf5", title="F", regulatory_type=RegulatoryType.FDA_510K,
            product_name="X", device_version="1.0",
        )
        assert entity.required_sections() == FDA_510K_SECTIONS

    def test_required_sections_eu_mdr(self):
        from policy_engine.domain.regulatory.technical_file import (
            TechnicalFileEntity, RegulatoryType, EU_MDR_SECTIONS,
        )
        entity = TechnicalFileEntity(
            id="tf6", title="F", regulatory_type=RegulatoryType.EU_MDR,
            product_name="X", device_version="1.0",
        )
        assert entity.required_sections() == EU_MDR_SECTIONS

    def test_required_sections_both_is_union(self):
        from policy_engine.domain.regulatory.technical_file import (
            TechnicalFileEntity, RegulatoryType, FDA_510K_SECTIONS, EU_MDR_SECTIONS,
        )
        entity = TechnicalFileEntity(
            id="tf7", title="F", regulatory_type=RegulatoryType.BOTH,
            product_name="X", device_version="1.0",
        )
        expected = sorted(set(FDA_510K_SECTIONS) | set(EU_MDR_SECTIONS))
        assert entity.required_sections() == expected

    def test_missing_sections_empty_entity(self):
        from policy_engine.domain.regulatory.technical_file import (
            TechnicalFileEntity, RegulatoryType, FDA_510K_SECTIONS,
        )
        entity = TechnicalFileEntity(
            id="tf8", title="F", regulatory_type=RegulatoryType.FDA_510K,
            product_name="X", device_version="1.0",
        )
        # No sections added — all required are missing
        assert entity.missing_sections() == FDA_510K_SECTIONS

    def test_completeness_score_zero_when_no_sections(self):
        from policy_engine.domain.regulatory.technical_file import (
            TechnicalFileEntity, RegulatoryType,
        )
        entity = TechnicalFileEntity(
            id="tf9", title="F", regulatory_type=RegulatoryType.FDA_510K,
            product_name="X", device_version="1.0",
        )
        assert entity.completeness_score() == 0.0

    def test_auto_generate_sections_fda(self):
        from policy_engine.domain.regulatory.technical_file import (
            auto_generate_sections, RegulatoryType, FDA_510K_SECTIONS,
        )
        sections = auto_generate_sections(RegulatoryType.FDA_510K, "DiagAI", "1.0")
        assert len(sections) == len(FDA_510K_SECTIONS)
        assert all(s.auto_generated for s in sections)
        section_types = [s.section_type for s in sections]
        assert set(section_types) == set(FDA_510K_SECTIONS)


# ---------------------------------------------------------------------------
# TestPostMarketDomain (10 tests) — pure domain logic
# ---------------------------------------------------------------------------

class TestPostMarketDomain:
    def test_classify_severity_critical_patient_harm(self):
        from policy_engine.domain.regulatory.post_market import (
            classify_severity, AdverseEventSeverity,
        )
        result = classify_severity(patient_harm=True, system_failure=False,
                                   regulatory_violation=False, data_breach=False)
        assert result == AdverseEventSeverity.CRITICAL

    def test_classify_severity_critical_regulatory_and_system(self):
        from policy_engine.domain.regulatory.post_market import (
            classify_severity, AdverseEventSeverity,
        )
        result = classify_severity(patient_harm=False, system_failure=True,
                                   regulatory_violation=True, data_breach=False)
        assert result == AdverseEventSeverity.CRITICAL

    def test_classify_severity_high_system_failure(self):
        from policy_engine.domain.regulatory.post_market import (
            classify_severity, AdverseEventSeverity,
        )
        result = classify_severity(patient_harm=False, system_failure=True,
                                   regulatory_violation=False, data_breach=False)
        assert result == AdverseEventSeverity.HIGH

    def test_classify_severity_high_regulatory_violation(self):
        from policy_engine.domain.regulatory.post_market import (
            classify_severity, AdverseEventSeverity,
        )
        result = classify_severity(patient_harm=False, system_failure=False,
                                   regulatory_violation=True, data_breach=False)
        assert result == AdverseEventSeverity.HIGH

    def test_classify_severity_medium_data_breach(self):
        from policy_engine.domain.regulatory.post_market import (
            classify_severity, AdverseEventSeverity,
        )
        result = classify_severity(patient_harm=False, system_failure=False,
                                   regulatory_violation=False, data_breach=True)
        assert result == AdverseEventSeverity.MEDIUM

    def test_classify_severity_low_no_flags(self):
        from policy_engine.domain.regulatory.post_market import (
            classify_severity, AdverseEventSeverity,
        )
        result = classify_severity(patient_harm=False, system_failure=False,
                                   regulatory_violation=False, data_breach=False)
        assert result == AdverseEventSeverity.LOW

    def test_aggregate_pms_metrics_empty(self):
        from policy_engine.domain.regulatory.post_market import aggregate_pms_metrics
        metrics = aggregate_pms_metrics([])
        assert metrics["total_events"] == 0
        assert metrics["critical_rate"] == 0.0
        assert metrics["resolution_rate"] == 0.0
        assert metrics["open_count"] == 0

    def test_aggregate_pms_metrics_mixed(self):
        from policy_engine.domain.regulatory.post_market import aggregate_pms_metrics
        events = [
            {"severity": "critical", "status": "open"},
            {"severity": "high", "status": "resolved"},
            {"severity": "low", "status": "investigating"},
            {"severity": "medium", "status": "open"},
        ]
        metrics = aggregate_pms_metrics(events)
        assert metrics["total_events"] == 4
        assert metrics["by_severity"]["critical"] == 1
        assert metrics["by_severity"]["high"] == 1
        assert metrics["by_status"]["resolved"] == 1
        assert metrics["open_count"] == 3  # 2 open + 1 investigating
        assert metrics["critical_rate"] == 0.25
        assert metrics["resolution_rate"] == 0.25

    def test_generate_psur_summary_critical_risk(self):
        from policy_engine.domain.regulatory.post_market import generate_psur_summary
        metrics = {
            "total_events": 10,
            "critical_rate": 0.25,
            "resolution_rate": 0.5,
            "open_count": 5,
        }
        summary = generate_psur_summary(metrics, 90)
        assert "CRITICAL" in summary
        assert "90-day" in summary
        assert "10" in summary

    def test_generate_psur_summary_low_risk(self):
        from policy_engine.domain.regulatory.post_market import generate_psur_summary
        metrics = {
            "total_events": 2,
            "critical_rate": 0.0,
            "resolution_rate": 1.0,
            "open_count": 0,
        }
        summary = generate_psur_summary(metrics, 30)
        assert "LOW" in summary
        assert "30-day" in summary


# ---------------------------------------------------------------------------
# TestTechnicalFileRoutes (15 tests)
# ---------------------------------------------------------------------------

class TestTechnicalFileRoutes:
    def setup_method(self):
        _ensure_tables()
        self.client = _make_client()
        self.db = _get_test_db()
        self.org_id = str(uuid.uuid4())
        self.headers, self.user = _make_user_headers(
            self.db, "system_admin", self.org_id
        )

    def teardown_method(self):
        self.db.close()

    def test_create_technical_file_201(self):
        resp = self.client.post(
            "/v1/regulatory/technical-files",
            json={
                "title": "FDA 510k for DiagAI",
                "regulatory_type": "fda_510k",
                "product_name": "DiagAI",
                "device_version": "1.0",
            },
            headers=self.headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "FDA 510k for DiagAI"
        assert data["regulatory_type"] == "fda_510k"
        assert data["lifecycle_stage"] == "draft"

    def test_create_with_auto_generate(self):
        resp = self.client.post(
            "/v1/regulatory/technical-files",
            json={
                "title": "Auto File",
                "regulatory_type": "eu_mdr",
                "product_name": "ScribeAI",
                "device_version": "2.1",
                "auto_generate": True,
            },
            headers=self.headers,
        )
        assert resp.status_code == 201
        file_id = resp.json()["id"]

        # Sections should have been auto-generated
        sections_resp = self.client.get(
            f"/v1/regulatory/technical-files/{file_id}/sections",
            headers=self.headers,
        )
        assert sections_resp.status_code == 200
        sections = sections_resp.json()
        assert len(sections) > 0
        assert all(s["auto_generated"] for s in sections)

    def test_list_technical_files_200(self):
        # Create one first
        self.client.post(
            "/v1/regulatory/technical-files",
            json={"title": "T1", "regulatory_type": "fda_510k",
                  "product_name": "P1", "device_version": "1.0"},
            headers=self.headers,
        )
        resp = self.client.get("/v1/regulatory/technical-files", headers=self.headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_get_technical_file_by_id(self):
        create_resp = self.client.post(
            "/v1/regulatory/technical-files",
            json={"title": "Get Test", "regulatory_type": "eu_mdr",
                  "product_name": "AI", "device_version": "3.0"},
            headers=self.headers,
        )
        file_id = create_resp.json()["id"]

        resp = self.client.get(
            f"/v1/regulatory/technical-files/{file_id}", headers=self.headers
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == file_id

    def test_get_technical_file_not_found(self):
        resp = self.client.get(
            "/v1/regulatory/technical-files/nonexistent-id", headers=self.headers
        )
        assert resp.status_code == 404

    def test_update_technical_file(self):
        create_resp = self.client.post(
            "/v1/regulatory/technical-files",
            json={"title": "Old Title", "regulatory_type": "fda_510k",
                  "product_name": "AI", "device_version": "1.0"},
            headers=self.headers,
        )
        file_id = create_resp.json()["id"]

        resp = self.client.patch(
            f"/v1/regulatory/technical-files/{file_id}",
            json={"title": "New Title", "device_version": "1.1"},
            headers=self.headers,
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "New Title"
        assert resp.json()["device_version"] == "1.1"

    def test_submit_technical_file_changes_lifecycle(self):
        create_resp = self.client.post(
            "/v1/regulatory/technical-files",
            json={"title": "Submit Me", "regulatory_type": "fda_510k",
                  "product_name": "AI", "device_version": "1.0"},
            headers=self.headers,
        )
        file_id = create_resp.json()["id"]

        resp = self.client.post(
            f"/v1/regulatory/technical-files/{file_id}/submit",
            headers=self.headers,
        )
        assert resp.status_code == 200
        assert resp.json()["lifecycle_stage"] == "submitted"

    def test_submit_already_submitted_returns_409(self):
        create_resp = self.client.post(
            "/v1/regulatory/technical-files",
            json={"title": "Sub2", "regulatory_type": "fda_510k",
                  "product_name": "AI", "device_version": "1.0"},
            headers=self.headers,
        )
        file_id = create_resp.json()["id"]
        self.client.post(
            f"/v1/regulatory/technical-files/{file_id}/submit", headers=self.headers
        )

        resp = self.client.post(
            f"/v1/regulatory/technical-files/{file_id}/submit", headers=self.headers
        )
        assert resp.status_code == 409

    def test_add_section_201(self):
        create_resp = self.client.post(
            "/v1/regulatory/technical-files",
            json={"title": "Section Test", "regulatory_type": "fda_510k",
                  "product_name": "AI", "device_version": "1.0"},
            headers=self.headers,
        )
        file_id = create_resp.json()["id"]

        resp = self.client.post(
            f"/v1/regulatory/technical-files/{file_id}/sections",
            json={"section_type": "device_description",
                  "content": "This device uses ML to diagnose...", "order_index": 0},
            headers=self.headers,
        )
        assert resp.status_code == 201
        assert resp.json()["section_type"] == "device_description"
        assert not resp.json()["auto_generated"]

    def test_list_sections(self):
        create_resp = self.client.post(
            "/v1/regulatory/technical-files",
            json={"title": "T", "regulatory_type": "fda_510k",
                  "product_name": "AI", "device_version": "1.0"},
            headers=self.headers,
        )
        file_id = create_resp.json()["id"]
        self.client.post(
            f"/v1/regulatory/technical-files/{file_id}/sections",
            json={"section_type": "labeling", "content": "FDA cleared label.", "order_index": 1},
            headers=self.headers,
        )

        resp = self.client.get(
            f"/v1/regulatory/technical-files/{file_id}/sections", headers=self.headers
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_update_section(self):
        create_resp = self.client.post(
            "/v1/regulatory/technical-files",
            json={"title": "T", "regulatory_type": "fda_510k",
                  "product_name": "AI", "device_version": "1.0"},
            headers=self.headers,
        )
        file_id = create_resp.json()["id"]
        section_resp = self.client.post(
            f"/v1/regulatory/technical-files/{file_id}/sections",
            json={"section_type": "labeling", "content": "Draft label.", "order_index": 0},
            headers=self.headers,
        )
        section_id = section_resp.json()["id"]

        resp = self.client.put(
            f"/v1/regulatory/technical-files/{file_id}/sections/{section_id}",
            json={"content": "Final FDA-cleared label."},
            headers=self.headers,
        )
        assert resp.status_code == 200
        assert resp.json()["content"] == "Final FDA-cleared label."

    def test_create_version_snapshot(self):
        create_resp = self.client.post(
            "/v1/regulatory/technical-files",
            json={"title": "Version Test", "regulatory_type": "eu_mdr",
                  "product_name": "AI", "device_version": "1.0"},
            headers=self.headers,
        )
        file_id = create_resp.json()["id"]

        resp = self.client.post(
            f"/v1/regulatory/technical-files/{file_id}/versions",
            headers=self.headers,
        )
        assert resp.status_code == 201
        assert resp.json()["version_number"] == 1

    def test_list_versions(self):
        create_resp = self.client.post(
            "/v1/regulatory/technical-files",
            json={"title": "V Test", "regulatory_type": "fda_510k",
                  "product_name": "AI", "device_version": "1.0"},
            headers=self.headers,
        )
        file_id = create_resp.json()["id"]
        self.client.post(
            f"/v1/regulatory/technical-files/{file_id}/versions", headers=self.headers
        )

        resp = self.client.get(
            f"/v1/regulatory/technical-files/{file_id}/versions", headers=self.headers
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_stats_endpoint(self):
        self.client.post(
            "/v1/regulatory/technical-files",
            json={"title": "Stats Test", "regulatory_type": "fda_510k",
                  "product_name": "AI", "device_version": "1.0"},
            headers=self.headers,
        )
        resp = self.client.get(
            "/v1/regulatory/technical-files/stats", headers=self.headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "total_files" in data
        assert "by_lifecycle" in data
        assert "by_regulatory_type" in data

    def test_cross_org_isolation(self):
        """File created by org A is not visible to org B."""
        other_org_id = str(uuid.uuid4())
        other_headers, _ = _make_user_headers(self.db, "system_admin", other_org_id)

        create_resp = self.client.post(
            "/v1/regulatory/technical-files",
            json={"title": "Org A File", "regulatory_type": "fda_510k",
                  "product_name": "AI", "device_version": "1.0"},
            headers=self.headers,
        )
        file_id = create_resp.json()["id"]

        resp = self.client.get(
            f"/v1/regulatory/technical-files/{file_id}", headers=other_headers
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# TestAdverseEventRoutes (12 tests)
# ---------------------------------------------------------------------------

class TestAdverseEventRoutes:
    def setup_method(self):
        _ensure_tables()
        self.client = _make_client()
        self.db = _get_test_db()
        self.org_id = str(uuid.uuid4())
        self.headers, self.user = _make_user_headers(
            self.db, "system_admin", self.org_id
        )

    def teardown_method(self):
        self.db.close()

    def _create_event(self, severity="high", event_type="misdiagnosis"):
        return self.client.post(
            "/v1/regulatory/adverse-events",
            json={
                "model_id": "model-abc",
                "event_type": event_type,
                "severity": severity,
                "description": "Model provided incorrect diagnosis.",
                "patient_impact": "Patient received wrong treatment.",
            },
            headers=self.headers,
        )

    def test_create_adverse_event_201(self):
        resp = self._create_event()
        assert resp.status_code == 201
        data = resp.json()
        assert data["severity"] == "high"
        assert data["status"] == "open"
        assert data["organization_id"] == self.org_id

    def test_list_adverse_events(self):
        self._create_event()
        resp = self.client.get("/v1/regulatory/adverse-events", headers=self.headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_get_adverse_event_by_id(self):
        create_resp = self._create_event()
        event_id = create_resp.json()["id"]

        resp = self.client.get(
            f"/v1/regulatory/adverse-events/{event_id}", headers=self.headers
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == event_id

    def test_get_adverse_event_not_found(self):
        resp = self.client.get(
            "/v1/regulatory/adverse-events/nonexistent", headers=self.headers
        )
        assert resp.status_code == 404

    def test_resolve_adverse_event(self):
        create_resp = self._create_event()
        event_id = create_resp.json()["id"]

        resp = self.client.patch(
            f"/v1/regulatory/adverse-events/{event_id}/resolve",
            headers=self.headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "resolved"
        assert resp.json()["resolved_at"] is not None

    def test_resolve_already_resolved_returns_409(self):
        create_resp = self._create_event()
        event_id = create_resp.json()["id"]
        self.client.patch(
            f"/v1/regulatory/adverse-events/{event_id}/resolve", headers=self.headers
        )

        resp = self.client.patch(
            f"/v1/regulatory/adverse-events/{event_id}/resolve", headers=self.headers
        )
        assert resp.status_code == 409

    def test_classify_endpoint(self):
        resp = self.client.post(
            "/v1/regulatory/adverse-events/classify",
            json={"patient_harm": True, "system_failure": False,
                  "regulatory_violation": False, "data_breach": False},
            headers=self.headers,
        )
        assert resp.status_code == 200
        assert resp.json()["severity"] == "critical"

    def test_filter_by_severity(self):
        self._create_event(severity="critical")
        self._create_event(severity="low")

        resp = self.client.get(
            "/v1/regulatory/adverse-events?severity=critical", headers=self.headers
        )
        assert resp.status_code == 200
        assert all(ev["severity"] == "critical" for ev in resp.json())

    def test_filter_by_status(self):
        create_resp = self._create_event()
        event_id = create_resp.json()["id"]
        self.client.patch(
            f"/v1/regulatory/adverse-events/{event_id}/resolve", headers=self.headers
        )

        resp = self.client.get(
            "/v1/regulatory/adverse-events?status=resolved", headers=self.headers
        )
        assert resp.status_code == 200
        assert all(ev["status"] == "resolved" for ev in resp.json())

    def test_stats_endpoint(self):
        self._create_event(severity="critical")
        self._create_event(severity="high")

        resp = self.client.get("/v1/regulatory/adverse-events/stats", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_events" in data
        assert "by_severity" in data
        assert "by_status" in data

    def test_critical_severity_stored_correctly(self):
        resp = self._create_event(severity="critical")
        assert resp.status_code == 201
        assert resp.json()["severity"] == "critical"

    def test_cross_org_isolation(self):
        create_resp = self._create_event()
        event_id = create_resp.json()["id"]

        other_org_id = str(uuid.uuid4())
        other_headers, _ = _make_user_headers(self.db, "system_admin", other_org_id)

        resp = self.client.get(
            f"/v1/regulatory/adverse-events/{event_id}", headers=other_headers
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# TestPMSReportRoutes (10 tests)
# ---------------------------------------------------------------------------

class TestPMSReportRoutes:
    def setup_method(self):
        _ensure_tables()
        self.client = _make_client()
        self.db = _get_test_db()
        self.org_id = str(uuid.uuid4())
        self.headers, self.user = _make_user_headers(
            self.db, "system_admin", self.org_id
        )

    def teardown_method(self):
        self.db.close()

    def _create_report(self, report_type="psur", auto_generate=False):
        start = datetime(2024, 1, 1).isoformat()
        end = datetime(2024, 3, 31).isoformat()
        return self.client.post(
            "/v1/regulatory/pms-reports",
            json={
                "report_type": report_type,
                "period_start": start,
                "period_end": end,
                "auto_generate_summary": auto_generate,
            },
            headers=self.headers,
        )

    def test_create_pms_report_201(self):
        resp = self._create_report()
        assert resp.status_code == 201
        data = resp.json()
        assert data["report_type"] == "psur"
        assert data["status"] == "draft"
        assert data["organization_id"] == self.org_id

    def test_create_with_auto_summary(self):
        resp = self._create_report(auto_generate=True)
        assert resp.status_code == 201
        # Summary may or may not be generated depending on adverse events,
        # but the report should exist
        assert resp.json()["id"] is not None

    def test_list_pms_reports(self):
        self._create_report()
        resp = self.client.get("/v1/regulatory/pms-reports", headers=self.headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_get_pms_report_by_id(self):
        create_resp = self._create_report()
        report_id = create_resp.json()["id"]

        resp = self.client.get(
            f"/v1/regulatory/pms-reports/{report_id}", headers=self.headers
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == report_id

    def test_get_pms_report_not_found(self):
        resp = self.client.get(
            "/v1/regulatory/pms-reports/nonexistent", headers=self.headers
        )
        assert resp.status_code == 404

    def test_publish_pms_report(self):
        create_resp = self._create_report()
        report_id = create_resp.json()["id"]

        resp = self.client.post(
            f"/v1/regulatory/pms-reports/{report_id}/publish",
            headers=self.headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "published"

    def test_publish_already_published_returns_409(self):
        create_resp = self._create_report()
        report_id = create_resp.json()["id"]
        self.client.post(
            f"/v1/regulatory/pms-reports/{report_id}/publish", headers=self.headers
        )

        resp = self.client.post(
            f"/v1/regulatory/pms-reports/{report_id}/publish", headers=self.headers
        )
        assert resp.status_code == 409

    def test_get_report_metrics_computes_on_demand(self):
        create_resp = self._create_report()
        report_id = create_resp.json()["id"]

        resp = self.client.get(
            f"/v1/regulatory/pms-reports/{report_id}/metrics", headers=self.headers
        )
        assert resp.status_code == 200
        metrics = resp.json()
        assert len(metrics) >= 1
        metric_names = {m["metric_name"] for m in metrics}
        assert "total_events" in metric_names

    def test_stats_endpoint(self):
        self._create_report(report_type="psur")
        self._create_report(report_type="mdr")

        resp = self.client.get("/v1/regulatory/pms-reports/stats", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_reports" in data
        assert "by_type" in data
        assert "by_status" in data

    def test_filter_by_type(self):
        self._create_report(report_type="psur")
        self._create_report(report_type="mdr")

        resp = self.client.get(
            "/v1/regulatory/pms-reports?report_type=mdr", headers=self.headers
        )
        assert resp.status_code == 200
        assert all(r["report_type"] == "mdr" for r in resp.json())
