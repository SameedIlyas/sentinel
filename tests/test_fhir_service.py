"""TDD tests for FHIR R4 Parser Service — Phase 5.

Write tests FIRST (RED), then implement to make them GREEN.
"""
from __future__ import annotations

from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Helpers: minimal valid FHIR R4 resource payloads
# ---------------------------------------------------------------------------

def _patient_resource(
    fhir_id: str = "p-123",
    name_given: str = "John",
    name_family: str = "Doe",
    birth_date: str = "1985-06-15",
    gender: str = "male",
    phone: str = "555-867-5309",
    address_city: str = "Springfield",
) -> dict:
    return {
        "resourceType": "Patient",
        "id": fhir_id,
        "name": [{"given": [name_given], "family": name_family}],
        "birthDate": birth_date,
        "gender": gender,
        "telecom": [{"system": "phone", "value": phone}],
        "address": [{"city": address_city, "state": "IL", "postalCode": "62701"}],
        "identifier": [{"system": "urn:ssn", "value": "123-45-6789"}],
    }


def _observation_resource(
    fhir_id: str = "obs-456",
    patient_ref: str = "Patient/p-123",
    loinc_code: str = "29463-7",
    value: str = "72.5",
    unit: str = "kg",
    effective_date: str = "2024-03-15",
    status: str = "final",
) -> dict:
    return {
        "resourceType": "Observation",
        "id": fhir_id,
        "subject": {"reference": patient_ref},
        "code": {
            "coding": [{"system": "http://loinc.org", "code": loinc_code}]
        },
        "valueQuantity": {"value": float(value), "unit": unit},
        "effectiveDateTime": f"{effective_date}T00:00:00Z",
        "status": status,
    }


def _diagnostic_report_resource(
    fhir_id: str = "dr-789",
    code: str = "58410-2",
    conclusion: str = "No acute findings",
    issued: str = "2024-03-15T10:30:00Z",
    performer_display: str = "Dr. House",
) -> dict:
    return {
        "resourceType": "DiagnosticReport",
        "id": fhir_id,
        "code": {"coding": [{"system": "http://loinc.org", "code": code}]},
        "conclusion": conclusion,
        "issued": issued,
        "performer": [{"display": performer_display}],
        "result": [{"reference": "Observation/obs-456"}],
    }


def _fhir_bundle(resources: list) -> dict:
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [{"resource": r} for r in resources],
    }


# ---------------------------------------------------------------------------
# FHIRParserService unit tests
# ---------------------------------------------------------------------------

class TestFHIRPatientParsing:
    def setup_method(self) -> None:
        from policy_engine.services.fhir_service import FHIRParserService
        self.svc = FHIRParserService()

    def test_patient_resource_strips_phi_fields(self) -> None:
        """Patient name, phone, address, and identifier must not appear in output."""
        record = self.svc.parse_patient(_patient_resource())
        # PHI fields MUST be absent from the dataclass
        assert not hasattr(record, "name") or record.name is None  # type: ignore[attr-defined]
        assert not hasattr(record, "phone") or record.phone is None  # type: ignore[attr-defined]
        assert not hasattr(record, "address") or record.address is None  # type: ignore[attr-defined]
        assert not hasattr(record, "identifier") or record.identifier is None  # type: ignore[attr-defined]
        # No raw PHI strings in the serialised repr
        raw = str(record)
        assert "John" not in raw
        assert "Doe" not in raw
        assert "555-867-5309" not in raw
        assert "123-45-6789" not in raw

    def test_patient_resource_preserves_birth_year_only(self) -> None:
        """Full birthDate must be reduced to year only."""
        record = self.svc.parse_patient(_patient_resource(birth_date="1985-06-15"))
        assert record.birth_year == 1985
        # The full date must not appear anywhere
        assert "1985-06-15" not in str(record)

    def test_patient_resource_preserves_gender(self) -> None:
        """Gender is NOT a Safe Harbor identifier and must be preserved."""
        record = self.svc.parse_patient(_patient_resource(gender="female"))
        assert record.gender == "female"

    def test_patient_id_is_de_identified(self) -> None:
        """Raw FHIR ID must be replaced with a deterministic de-identified hash."""
        record = self.svc.parse_patient(_patient_resource(fhir_id="p-123"))
        assert record.fhir_id != "p-123"
        assert len(record.fhir_id) >= 8  # must be a real hash, not empty

    def test_patient_id_is_deterministic(self) -> None:
        """Same FHIR ID always produces the same de-identified ID."""
        r1 = self.svc.parse_patient(_patient_resource(fhir_id="p-SAME"))
        r2 = self.svc.parse_patient(_patient_resource(fhir_id="p-SAME"))
        assert r1.fhir_id == r2.fhir_id

    def test_different_patient_ids_produce_different_hashes(self) -> None:
        r1 = self.svc.parse_patient(_patient_resource(fhir_id="p-AAA"))
        r2 = self.svc.parse_patient(_patient_resource(fhir_id="p-BBB"))
        assert r1.fhir_id != r2.fhir_id


class TestFHIRObservationParsing:
    def setup_method(self) -> None:
        from policy_engine.services.fhir_service import FHIRParserService
        self.svc = FHIRParserService()

    def test_observation_resource_preserves_loinc_code(self) -> None:
        """LOINC code must be preserved in the output."""
        record = self.svc.parse_observation(_observation_resource(loinc_code="29463-7"))
        assert record.loinc_code == "29463-7"

    def test_observation_preserves_value_and_unit(self) -> None:
        record = self.svc.parse_observation(
            _observation_resource(value="72.5", unit="kg")
        )
        assert record.value == "72.5"
        assert record.unit == "kg"

    def test_observation_effective_date_date_only(self) -> None:
        """Full datetime must be truncated to date portion only."""
        record = self.svc.parse_observation(
            _observation_resource(effective_date="2024-03-15")
        )
        # Should be "2024-03-15", not "2024-03-15T00:00:00Z"
        assert record.effective_date == "2024-03-15"
        assert "T" not in (record.effective_date or "")

    def test_observation_patient_id_is_de_identified(self) -> None:
        record = self.svc.parse_observation(
            _observation_resource(patient_ref="Patient/p-123")
        )
        assert record.patient_id != "p-123"
        assert record.patient_id != "Patient/p-123"

    def test_observation_preserves_status(self) -> None:
        record = self.svc.parse_observation(_observation_resource(status="final"))
        assert record.status == "final"


class TestFHIRDiagnosticReportParsing:
    def setup_method(self) -> None:
        from policy_engine.services.fhir_service import FHIRParserService
        self.svc = FHIRParserService()

    def test_diagnostic_report_preserves_code(self) -> None:
        record = self.svc.parse_diagnostic_report(
            _diagnostic_report_resource(code="58410-2")
        )
        assert record.code == "58410-2"

    def test_diagnostic_report_preserves_conclusion(self) -> None:
        record = self.svc.parse_diagnostic_report(
            _diagnostic_report_resource(conclusion="No acute findings")
        )
        assert record.conclusion == "No acute findings"

    def test_diagnostic_report_issued_date_only(self) -> None:
        """Full issued datetime must be truncated to date only."""
        record = self.svc.parse_diagnostic_report(
            _diagnostic_report_resource(issued="2024-03-15T10:30:00Z")
        )
        assert record.issued_date == "2024-03-15"

    def test_diagnostic_report_performer_name_stripped(self) -> None:
        """Performer display name (PHI) must not appear in output."""
        record = self.svc.parse_diagnostic_report(
            _diagnostic_report_resource(performer_display="Dr. House")
        )
        assert "Dr. House" not in str(record)


# ---------------------------------------------------------------------------
# Bundle ingestion + DB storage
# ---------------------------------------------------------------------------

class TestFHIRBundleIngestion:
    def setup_method(self) -> None:
        from policy_engine.services.fhir_service import FHIRParserService
        self.svc = FHIRParserService()

    def test_fhir_bundle_ingestion_returns_count(self) -> None:
        """ingest_bundle() must return the number of records stored."""
        bundle = _fhir_bundle([
            _patient_resource(),
            _observation_resource(),
        ])
        mock_db = MagicMock()
        count = self.svc.ingest_bundle(bundle, db=mock_db)
        assert count == 2

    def test_fhir_bundle_ingestion_ignores_unknown_resource_types(self) -> None:
        """Resources with unsupported resourceType must be skipped gracefully."""
        bundle = _fhir_bundle([
            _patient_resource(),
            {"resourceType": "Medication", "id": "med-1"},
        ])
        mock_db = MagicMock()
        count = self.svc.ingest_bundle(bundle, db=mock_db)
        assert count == 1  # only Patient counted

    def test_fhir_empty_bundle_returns_zero(self) -> None:
        bundle = _fhir_bundle([])
        mock_db = MagicMock()
        count = self.svc.ingest_bundle(bundle, db=mock_db)
        assert count == 0

    def test_fhir_direct_resource_ingestion(self) -> None:
        """A single resource (not a Bundle) should also be accepted."""
        mock_db = MagicMock()
        count = self.svc.ingest_bundle(_patient_resource(), db=mock_db)
        assert count == 1


# ---------------------------------------------------------------------------
# Route integration tests
# ---------------------------------------------------------------------------

import uuid as _uuid
from datetime import datetime as _dt


def _make_headers(db, role) -> dict:
    """Create a user in DB and return auth headers with CSRF bypass."""
    from policy_engine.models.user import User
    from policy_engine.auth.jwt_utils import create_access_token, get_password_hash

    uid = str(_uuid.uuid4())
    user = User(
        id=uid,
        username=f"{role.value}_{uid[:8]}",
        email=f"{role.value}_{uid[:8]}@test.local",
        password_hash=get_password_hash("TestPass123!"),
        role=role,
        full_name=f"Test {role.value}",
        is_active=True,
        created_at=_dt.utcnow(),
        updated_at=_dt.utcnow(),
    )
    db.add(user)
    db.commit()
    token = create_access_token({"user_id": uid, "username": user.username, "role": role.value})
    return {"Authorization": f"Bearer {token}", "X-API-Key": "dummy-bypass-csrf"}


class TestFHIRRoutes:
    def test_fhir_ingest_requires_auth(self, client) -> None:
        """POST /v1/fhir/ingest without auth must return 401 or 403."""
        resp = client.post("/v1/fhir/ingest", json=_patient_resource())
        assert resp.status_code in (401, 403)

    def test_fhir_ingest_accepted_by_compliance_officer(
        self, client, db_session
    ) -> None:
        """compliance_officer role must be allowed to ingest FHIR data."""
        from policy_engine.models.user import UserRole
        headers = _make_headers(db_session, UserRole.COMPLIANCE_OFFICER)
        resp = client.post("/v1/fhir/ingest", json=_patient_resource(), headers=headers)
        assert resp.status_code in (200, 201)
        body = resp.json()
        assert "count" in body
        assert body["count"] >= 1

    def test_fhir_ingest_accepted_by_data_scientist(
        self, client, db_session
    ) -> None:
        from policy_engine.models.user import UserRole
        headers = _make_headers(db_session, UserRole.DATA_SCIENTIST)
        resp = client.post("/v1/fhir/ingest", json=_patient_resource(), headers=headers)
        assert resp.status_code in (200, 201)

    def test_fhir_ingest_bundle(self, client, db_session) -> None:
        """A FHIR Bundle payload must be accepted and count all resources."""
        from policy_engine.models.user import UserRole
        headers = _make_headers(db_session, UserRole.COMPLIANCE_OFFICER)
        bundle = _fhir_bundle([_patient_resource(), _observation_resource()])
        resp = client.post("/v1/fhir/ingest", json=bundle, headers=headers)
        assert resp.status_code in (200, 201)
        assert resp.json()["count"] == 2

    def test_fhir_cache_get_requires_auth(self, client) -> None:
        resp = client.get("/v1/fhir/cache")
        assert resp.status_code in (401, 403)

    def test_fhir_cache_get_returns_list(self, client, db_session) -> None:
        from policy_engine.models.user import UserRole
        headers = _make_headers(db_session, UserRole.COMPLIANCE_OFFICER)
        resp = client.get("/v1/fhir/cache", headers=headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
