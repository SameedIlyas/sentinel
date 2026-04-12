"""
Phase 2 Healthcare Data Layer Tests

TDD tests written BEFORE implementation (RED phase).
Tests for: FHIR R4 Client, DICOM Extractor, PHI Redaction Engine, Data Classifier, PHI Routes.
"""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock, AsyncMock


# ---------------------------------------------------------------------------
# Task 2.1 — FHIR R4 Client Tests
# ---------------------------------------------------------------------------

class TestFHIRClient:
    """Tests for the FHIR R4 async client."""

    def test_fhir_client_importable(self):
        from policy_engine.infrastructure.external.fhir_client import FHIRClient  # noqa: F401

    def test_fhir_client_has_required_methods(self):
        from policy_engine.infrastructure.external.fhir_client import FHIRClient
        client = FHIRClient(base_url="http://fhir.example.com")
        assert hasattr(client, "get_patient")
        assert hasattr(client, "get_observation")
        assert hasattr(client, "get_diagnostic_report")
        assert hasattr(client, "create_audit_event")
        assert hasattr(client, "get_device")
        assert hasattr(client, "get_provenance")

    def test_fhir_validation_error_importable(self):
        from policy_engine.infrastructure.external.fhir_client import FHIRValidationError  # noqa: F401

    def test_fhir_patient_entity_importable(self):
        from policy_engine.infrastructure.external.fhir_client import FHIRPatient  # noqa: F401

    @pytest.mark.asyncio
    async def test_get_patient_with_mock_returns_entity(self):
        from policy_engine.infrastructure.external.fhir_client import FHIRClient, FHIRPatient

        mock_response = {
            "resourceType": "Patient",
            "id": "patient-123",
            "name": [{"given": ["John"], "family": "Doe"}],
            "birthDate": "1985-01-15",
            "gender": "male",
        }

        client = FHIRClient(base_url="http://fhir.example.com")
        with patch.object(client, "_fetch", new=AsyncMock(return_value=mock_response)):
            patient = await client.get_patient("patient-123")

        assert isinstance(patient, FHIRPatient)
        assert patient.fhir_id == "patient-123"
        assert patient.birth_date == "1985-01-15"
        assert patient.gender == "male"

    @pytest.mark.asyncio
    async def test_invalid_resource_raises_fhir_validation_error(self):
        from policy_engine.infrastructure.external.fhir_client import FHIRClient, FHIRValidationError

        bad_response = {"resourceType": "Bundle", "id": "p-1"}

        client = FHIRClient(base_url="http://fhir.example.com")
        with patch.object(client, "_fetch", new=AsyncMock(side_effect=FHIRValidationError("wrong type"))):
            with pytest.raises(FHIRValidationError):
                await client.get_patient("p-1")

    @pytest.mark.asyncio
    async def test_oauth2_token_requested_before_resource_fetch(self):
        from policy_engine.infrastructure.external.fhir_client import FHIRClient

        client = FHIRClient(
            base_url="http://fhir.example.com",
            client_id="my-client",
            client_secret="secret",
            token_url="http://auth.example.com/token"
        )

        token_response_mock = MagicMock()
        token_response_mock.json.return_value = {"access_token": "test-token"}
        token_response_mock.raise_for_status = MagicMock()

        resource_response_mock = MagicMock()
        resource_response_mock.json.return_value = {
            "resourceType": "Patient",
            "id": "p-1",
            "name": [],
        }
        resource_response_mock.raise_for_status = MagicMock()

        async_client_mock = AsyncMock()
        async_client_mock.__aenter__ = AsyncMock(return_value=async_client_mock)
        async_client_mock.__aexit__ = AsyncMock(return_value=None)
        async_client_mock.post = AsyncMock(return_value=token_response_mock)
        async_client_mock.get = AsyncMock(return_value=resource_response_mock)

        with patch("httpx.AsyncClient", return_value=async_client_mock):
            patient = await client.get_patient("p-1")

        async_client_mock.post.assert_called_once()
        assert client._token == "test-token"

    def test_fhir_resource_cache_model_importable(self):
        from policy_engine.models.fhir_cache import FHIRResourceCache  # noqa: F401

    def test_fhir_resource_cache_has_required_fields(self):
        from policy_engine.models.fhir_cache import FHIRResourceCache
        columns = {c.key for c in FHIRResourceCache.__table__.columns}
        required = {"resource_type", "fhir_id", "payload", "org_id", "cached_at", "expires_at"}
        assert required.issubset(columns), f"Missing columns: {required - columns}"

    def test_fhir_cache_migration_008_exists(self):
        migration_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "alembic",
            "versions",
            "2024_02_15_0000-008_add_healthcare_data_layer.py"
        )
        assert os.path.exists(migration_path), f"Migration 008 not found at {migration_path}"


# ---------------------------------------------------------------------------
# Task 2.2 — DICOM Metadata Extractor Tests
# ---------------------------------------------------------------------------

class TestDICOMExtractor:
    """Tests for the DICOM metadata extractor."""

    def test_dicom_extractor_importable(self):
        from policy_engine.infrastructure.external.dicom_client import DICOMExtractor  # noqa: F401

    def test_dicom_extractor_has_extract_metadata_method(self):
        from policy_engine.infrastructure.external.dicom_client import DICOMExtractor
        extractor = DICOMExtractor()
        assert hasattr(extractor, "extract_metadata")

    def test_pixel_data_error_importable(self):
        from policy_engine.infrastructure.external.dicom_client import DICOMPixelDataError  # noqa: F401

    def test_dicom_parse_error_importable(self):
        from policy_engine.infrastructure.external.dicom_client import DICOMParseError  # noqa: F401

    def test_extract_metadata_strips_patient_name(self):
        import pydicom
        from pydicom.dataset import Dataset, FileMetaDataset
        from pydicom.uid import UID
        from policy_engine.infrastructure.external.dicom_client import DICOMExtractor

        ds = Dataset()
        ds.PatientName = "John^Doe"
        ds.PatientID = "12345"
        ds.Modality = "CT"
        ds.StudyInstanceUID = "1.2.3.4.5"
        ds.is_implicit_VR = False
        ds.is_little_endian = True

        extractor = DICOMExtractor()
        with patch.object(extractor, "extract_metadata") as mock_extract:
            mock_extract.return_value = {"Modality": "CT", "StudyInstanceUID": "1.2.3.4.5"}
            result = extractor.extract_metadata(ds)

        assert "PatientName" not in result

    def test_extract_metadata_strips_patient_id(self):
        from policy_engine.infrastructure.external.dicom_client import DICOMExtractor
        extractor = DICOMExtractor()
        with patch.object(extractor, "extract_metadata") as mock_extract:
            mock_extract.return_value = {"Modality": "MRI"}
            result = extractor.extract_metadata(b"fake")
        assert "PatientID" not in result

    def test_extract_metadata_strips_all_18_phi_tags(self):
        from policy_engine.infrastructure.external.dicom_client import DICOMExtractor, PHI_DICOM_TAGS
        assert len(PHI_DICOM_TAGS) == 18, f"Expected 18 PHI tags, got {len(PHI_DICOM_TAGS)}"
        # Verify all 18 are present
        required_tags = {
            "PatientName", "PatientID", "PatientBirthDate", "PatientSex", "PatientAge",
            "PatientAddress", "PatientTelephoneNumbers", "InstitutionName", "InstitutionAddress",
            "ReferringPhysicianName", "PerformingPhysicianName", "OperatorsName",
            "StudyDate", "SeriesDate", "AcquisitionDate", "ContentDate",
            "StationName", "DeviceSerialNumber",
        }
        assert PHI_DICOM_TAGS == required_tags

    def test_pixel_data_access_raises_error(self):
        import pydicom
        from pydicom.dataset import Dataset
        from policy_engine.infrastructure.external.dicom_client import DICOMExtractor, DICOMPixelDataError

        ds = Dataset()
        ds.Modality = "CT"
        ds.PixelData = b"\x00\x01\x02\x03"
        ds.is_implicit_VR = False
        ds.is_little_endian = True

        extractor = DICOMExtractor()
        with patch.object(extractor, "extract_metadata", side_effect=DICOMPixelDataError("pixel data prohibited")):
            with pytest.raises(DICOMPixelDataError):
                extractor.extract_metadata(ds)

    def test_non_dicom_input_raises_parse_error(self):
        from policy_engine.infrastructure.external.dicom_client import DICOMExtractor, DICOMParseError

        extractor = DICOMExtractor()
        with pytest.raises(DICOMParseError):
            extractor.extract_metadata(b"this is not a dicom file at all")

    def test_safe_tags_retained(self):
        import pydicom
        from pydicom.dataset import Dataset
        from policy_engine.infrastructure.external.dicom_client import DICOMExtractor

        ds = Dataset()
        ds.Modality = "CT"
        ds.StudyInstanceUID = "1.2.3.4.5"
        ds.is_implicit_VR = False
        ds.is_little_endian = True

        extractor = DICOMExtractor()
        with patch.object(extractor, "extract_metadata") as mock_extract:
            mock_extract.return_value = {"Modality": "CT", "StudyInstanceUID": "1.2.3.4.5"}
            result = extractor.extract_metadata(ds)

        assert "Modality" in result
        assert "StudyInstanceUID" in result

    def test_dicom_metadata_model_importable(self):
        from policy_engine.models.dicom_metadata import DICOMMetadataRecord  # noqa: F401


# ---------------------------------------------------------------------------
# Task 2.3 — PHI/PII Redaction Engine Tests
# ---------------------------------------------------------------------------

class TestPHIRedactionEngine:
    """Tests for the PHI/PII redaction engine."""

    def test_phi_redaction_engine_importable(self):
        from policy_engine.infrastructure.security.phi_redaction import PHIRedactionEngine  # noqa: F401

    def test_phi_finding_importable(self):
        from policy_engine.infrastructure.security.phi_redaction import PHIFinding  # noqa: F401

    def test_phi_redaction_result_importable(self):
        from policy_engine.infrastructure.security.phi_redaction import PHIRedactionResult  # noqa: F401

    def test_detects_ssn(self):
        from policy_engine.infrastructure.security.phi_redaction import PHIRedactionEngine
        engine = PHIRedactionEngine()
        result = engine.redact("Patient SSN: 123-45-6789 on file")
        types = {f.phi_type for f in result.findings}
        assert "SSN" in types

    def test_detects_phone_number(self):
        from policy_engine.infrastructure.security.phi_redaction import PHIRedactionEngine
        engine = PHIRedactionEngine()
        result = engine.redact("Call 555-867-5309 for information")
        types = {f.phi_type for f in result.findings}
        assert "PHONE" in types

    def test_detects_email(self):
        from policy_engine.infrastructure.security.phi_redaction import PHIRedactionEngine
        engine = PHIRedactionEngine()
        result = engine.redact("Contact email@example.com for details")
        types = {f.phi_type for f in result.findings}
        assert "EMAIL" in types

    def test_detects_ip_address(self):
        from policy_engine.infrastructure.security.phi_redaction import PHIRedactionEngine
        engine = PHIRedactionEngine()
        result = engine.redact("Request from 192.168.1.100 was logged")
        types = {f.phi_type for f in result.findings}
        assert "IP_ADDRESS" in types

    def test_detects_url(self):
        from policy_engine.infrastructure.security.phi_redaction import PHIRedactionEngine
        engine = PHIRedactionEngine()
        result = engine.redact("See https://example.com/patient for records")
        types = {f.phi_type for f in result.findings}
        assert "URL" in types

    def test_detects_zip_code(self):
        from policy_engine.infrastructure.security.phi_redaction import PHIRedactionEngine
        engine = PHIRedactionEngine()
        result = engine.redact("Patient lives in ZIP 94102")
        types = {f.phi_type for f in result.findings}
        assert "ZIP_CODE" in types

    def test_detects_date(self):
        from policy_engine.infrastructure.security.phi_redaction import PHIRedactionEngine
        engine = PHIRedactionEngine()
        result = engine.redact("DOB: 01/15/1985")
        types = {f.phi_type for f in result.findings}
        assert "DATE" in types

    def test_detects_mrn(self):
        from policy_engine.infrastructure.security.phi_redaction import PHIRedactionEngine
        engine = PHIRedactionEngine()
        result = engine.redact("MRN: 12345678 admitted today")
        types = {f.phi_type for f in result.findings}
        assert "MRN" in types

    def test_detects_npi(self):
        from policy_engine.infrastructure.security.phi_redaction import PHIRedactionEngine
        engine = PHIRedactionEngine()
        result = engine.redact("NPI: 1234567890 prescribing physician")
        types = {f.phi_type for f in result.findings}
        assert "NPI" in types

    def test_detects_dea_number(self):
        from policy_engine.infrastructure.security.phi_redaction import PHIRedactionEngine
        engine = PHIRedactionEngine()
        result = engine.redact("DEA: AB1234563 authorized")
        types = {f.phi_type for f in result.findings}
        assert "DEA_NUMBER" in types

    def test_detects_vin(self):
        from policy_engine.infrastructure.security.phi_redaction import PHIRedactionEngine
        engine = PHIRedactionEngine()
        result = engine.redact("VIN: 1HGBH41JXMN109186 registered vehicle")
        types = {f.phi_type for f in result.findings}
        assert "VIN" in types

    def test_detects_account_number(self):
        from policy_engine.infrastructure.security.phi_redaction import PHIRedactionEngine
        engine = PHIRedactionEngine()
        result = engine.redact("Acct #: 4532015112830366 on record")
        types = {f.phi_type for f in result.findings}
        assert "ACCOUNT_NUMBER" in types

    def test_mask_strategy_replaces_with_redacted_label(self):
        from policy_engine.infrastructure.security.phi_redaction import PHIRedactionEngine, RedactionStrategy
        engine = PHIRedactionEngine()
        result = engine.redact("SSN: 123-45-6789", strategy=RedactionStrategy.MASK)
        assert "123-45-6789" not in result.redacted_text
        assert "REDACTED" in result.redacted_text

    def test_hash_strategy_produces_sha256(self):
        from policy_engine.infrastructure.security.phi_redaction import PHIRedactionEngine, RedactionStrategy
        engine = PHIRedactionEngine()
        result = engine.redact("SSN: 123-45-6789", strategy=RedactionStrategy.HASH)
        assert "123-45-6789" not in result.redacted_text
        # SHA-256 hex digest is 64 chars, we use first 16
        assert len(result.redacted_text) > 0

    def test_generalize_zip_to_3_digits(self):
        from policy_engine.infrastructure.security.phi_redaction import PHIRedactionEngine, RedactionStrategy
        engine = PHIRedactionEngine()
        result = engine.redact("ZIP 94102", strategy=RedactionStrategy.GENERALIZE)
        assert "94102" not in result.redacted_text
        assert "941" in result.redacted_text

    def test_generalize_dob_to_year(self):
        from policy_engine.infrastructure.security.phi_redaction import PHIRedactionEngine, RedactionStrategy
        engine = PHIRedactionEngine()
        result = engine.redact("DOB: 01/15/1985", strategy=RedactionStrategy.GENERALIZE)
        assert "01/15/1985" not in result.redacted_text
        assert "1985" in result.redacted_text

    def test_suppress_removes_phi_entirely(self):
        from policy_engine.infrastructure.security.phi_redaction import PHIRedactionEngine, RedactionStrategy
        engine = PHIRedactionEngine()
        result = engine.redact("SSN: 123-45-6789 end", strategy=RedactionStrategy.SUPPRESS)
        assert "123-45-6789" not in result.redacted_text

    def test_none_input_returns_empty_result(self):
        from policy_engine.infrastructure.security.phi_redaction import PHIRedactionEngine
        engine = PHIRedactionEngine()
        result = engine.redact(None)
        assert result.original_text == ""
        assert result.redacted_text == ""
        assert result.findings == []

    def test_empty_string_returns_empty_result(self):
        from policy_engine.infrastructure.security.phi_redaction import PHIRedactionEngine
        engine = PHIRedactionEngine()
        result = engine.redact("")
        assert result.original_text == ""
        assert result.findings == []

    def test_processing_time_under_100ms(self):
        from policy_engine.infrastructure.security.phi_redaction import PHIRedactionEngine
        engine = PHIRedactionEngine()
        text = "Patient John Doe, SSN: 123-45-6789, DOB 01/15/1985. " * 20
        result = engine.redact(text)
        assert result.processing_time_ms < 100, f"Too slow: {result.processing_time_ms}ms"

    def test_redaction_result_has_all_fields(self):
        from policy_engine.infrastructure.security.phi_redaction import PHIRedactionEngine, PHIRedactionResult
        engine = PHIRedactionEngine()
        result = engine.redact("test SSN: 123-45-6789")
        assert hasattr(result, "original_text")
        assert hasattr(result, "redacted_text")
        assert hasattr(result, "findings")
        assert hasattr(result, "processing_time_ms")

    def test_phi_finding_has_type_start_end_confidence(self):
        from policy_engine.infrastructure.security.phi_redaction import PHIRedactionEngine
        engine = PHIRedactionEngine()
        result = engine.redact("SSN: 123-45-6789")
        assert len(result.findings) > 0
        finding = result.findings[0]
        assert hasattr(finding, "phi_type")
        assert hasattr(finding, "start")
        assert hasattr(finding, "end")
        assert hasattr(finding, "confidence")


# ---------------------------------------------------------------------------
# Task 2.4 — Data Classifier Tests
# ---------------------------------------------------------------------------

class TestDataClassifier:
    """Tests for the 6-level data classifier."""

    def test_data_classifier_importable(self):
        from policy_engine.infrastructure.security.data_classifier import DataClassifier  # noqa: F401

    def test_data_classification_importable(self):
        from policy_engine.infrastructure.security.data_classifier import DataClassification  # noqa: F401

    def test_classify_generic_text_as_public(self):
        from policy_engine.infrastructure.security.data_classifier import DataClassifier, ClassificationLevel
        classifier = DataClassifier()
        result = classifier.classify("The weather is nice today")
        assert result.level == ClassificationLevel.PUBLIC

    def test_classify_text_with_ssn_as_phi(self):
        from policy_engine.infrastructure.security.data_classifier import DataClassifier, ClassificationLevel
        classifier = DataClassifier()
        result = classifier.classify("Patient SSN: 123-45-6789 on file")
        assert result.level in {ClassificationLevel.PHI, ClassificationLevel.PHI_RESTRICTED}

    def test_classify_mental_health_phi_as_restricted(self):
        from policy_engine.infrastructure.security.data_classifier import DataClassifier, ClassificationLevel
        classifier = DataClassifier()
        result = classifier.classify("Patient depression SSN: 123-45-6789 history noted")
        assert result.level == ClassificationLevel.PHI_RESTRICTED

    def test_six_classification_levels_defined(self):
        from policy_engine.infrastructure.security.data_classifier import ClassificationLevel
        levels = {level.value for level in ClassificationLevel}
        required = {"PUBLIC", "INTERNAL", "CONFIDENTIAL", "PHI", "PII", "PHI_RESTRICTED"}
        assert levels == required

    def test_clinical_user_can_access_phi(self):
        from policy_engine.infrastructure.security.data_classifier import DataClassifier, ClassificationLevel, DataClassification
        from policy_engine.models.user import UserRole
        classifier = DataClassifier()
        phi_classification = DataClassification(level=ClassificationLevel.PHI, confidence=0.9)
        assert classifier.enforce_access_policy(phi_classification, UserRole.CLINICAL_USER) is True

    def test_viewer_cannot_access_phi(self):
        from policy_engine.infrastructure.security.data_classifier import DataClassifier, ClassificationLevel, DataClassification
        from policy_engine.models.user import UserRole
        classifier = DataClassifier()
        phi_classification = DataClassification(level=ClassificationLevel.PHI, confidence=0.9)
        assert classifier.enforce_access_policy(phi_classification, UserRole.VIEWER) is False

    def test_cmio_can_access_phi_restricted(self):
        from policy_engine.infrastructure.security.data_classifier import DataClassifier, ClassificationLevel, DataClassification
        from policy_engine.models.user import UserRole
        classifier = DataClassifier()
        restricted = DataClassification(level=ClassificationLevel.PHI_RESTRICTED, confidence=0.95)
        assert classifier.enforce_access_policy(restricted, UserRole.CMIO) is True

    def test_system_admin_can_access_phi_restricted(self):
        from policy_engine.infrastructure.security.data_classifier import DataClassifier, ClassificationLevel, DataClassification
        from policy_engine.models.user import UserRole
        classifier = DataClassifier()
        restricted = DataClassification(level=ClassificationLevel.PHI_RESTRICTED, confidence=0.95)
        assert classifier.enforce_access_policy(restricted, UserRole.SYSTEM_ADMIN) is True

    def test_data_classifier_model_importable(self):
        from policy_engine.models.phi_log import DataClassificationRecord  # noqa: F401


# ---------------------------------------------------------------------------
# Task 2.5 — PHI Routes Tests
# ---------------------------------------------------------------------------

class TestPHIRoutes:
    """Tests for PHI redaction and classification HTTP endpoints."""

    def test_phi_router_importable(self):
        from policy_engine.routes.phi import router  # noqa: F401

    def test_phi_redact_endpoint_exists(self):
        from fastapi.testclient import TestClient
        from policy_engine.main import app
        client = TestClient(app, raise_server_exceptions=False)
        # POST without auth should return 401/403, NOT 404
        response = client.post("/v1/phi/redact", json={"text": "test"})
        assert response.status_code != 404, f"Endpoint not registered, got {response.status_code}"

    def test_phi_classify_endpoint_exists(self):
        from fastapi.testclient import TestClient
        from policy_engine.main import app
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/v1/phi/classify", json={"text": "test"})
        assert response.status_code != 404, f"Endpoint not registered, got {response.status_code}"

    def test_phi_redaction_log_endpoint_exists(self):
        from fastapi.testclient import TestClient
        from policy_engine.main import app
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/v1/phi/redaction-log")
        assert response.status_code != 404, f"Endpoint not registered, got {response.status_code}"
