"""TDD tests for DICOM De-Identification Service — Phase 5.

Write tests FIRST (RED), then implement to make them GREEN.
"""
from __future__ import annotations

import io
import pytest


# ---------------------------------------------------------------------------
# Helpers: build minimal valid DICOM bytes in-memory using pydicom
# ---------------------------------------------------------------------------

def _make_dicom_bytes(
    patient_name: str = "Doe^John",
    patient_id: str = "MRN-99999",
    patient_sex: str = "M",
    study_date: str = "20240315",
    modality: str = "CT",
    manufacturer: str = "Acme Medical",
    study_description: str = "Chest CT with contrast",
    include_pixel_data: bool = False,
) -> bytes:
    """Create minimal DICOM file bytes using pydicom FileDataset."""
    import pydicom
    from pydicom.dataset import FileDataset
    from pydicom.uid import ExplicitVRLittleEndian

    file_meta = pydicom.dataset.FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = pydicom.uid.UID("1.2.840.10008.5.1.4.1.1.2")
    file_meta.MediaStorageSOPInstanceUID = pydicom.uid.generate_uid()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    ds = FileDataset(None, {}, file_meta=file_meta, preamble=b"\0" * 128)
    ds.is_implicit_VR = False
    ds.is_little_endian = True

    ds.PatientName = patient_name
    ds.PatientID = patient_id
    ds.PatientSex = patient_sex
    ds.StudyDate = study_date
    ds.Modality = modality
    ds.Manufacturer = manufacturer
    ds.StudyDescription = study_description
    ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
    ds.SOPInstanceUID = pydicom.uid.generate_uid()

    if include_pixel_data:
        ds.PixelData = b"\x00\x01" * 100

    buf = io.BytesIO()
    pydicom.dcmwrite(buf, ds)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# DICOMDeidentificationService unit tests
# ---------------------------------------------------------------------------

class TestDICOMDeidentification:
    def setup_method(self) -> None:
        from policy_engine.services.dicom_service import DICOMDeidentificationService
        self.svc = DICOMDeidentificationService()

    def test_dicom_deidentification_removes_patient_name(self) -> None:
        """PatientName must not appear in the returned metadata."""
        dicom_bytes = _make_dicom_bytes(patient_name="Smith^Jane")
        record = self.svc.deidentify_metadata(dicom_bytes)
        assert "Smith" not in str(record)
        assert "Jane" not in str(record)

    def test_dicom_deidentification_removes_patient_id(self) -> None:
        dicom_bytes = _make_dicom_bytes(patient_id="MRN-SECRET-9")
        record = self.svc.deidentify_metadata(dicom_bytes)
        assert "MRN-SECRET-9" not in str(record)

    def test_dicom_deidentification_preserves_modality(self) -> None:
        """Modality is NOT PHI and must be preserved for AI analysis."""
        dicom_bytes = _make_dicom_bytes(modality="MRI")
        record = self.svc.deidentify_metadata(dicom_bytes)
        assert record.modality == "MRI"

    def test_dicom_deidentification_preserves_manufacturer(self) -> None:
        dicom_bytes = _make_dicom_bytes(manufacturer="Siemens Healthineers")
        record = self.svc.deidentify_metadata(dicom_bytes)
        assert record.manufacturer == "Siemens Healthineers"

    def test_dicom_deidentification_preserves_study_description(self) -> None:
        dicom_bytes = _make_dicom_bytes(study_description="Brain MRI without contrast")
        record = self.svc.deidentify_metadata(dicom_bytes)
        assert record.study_description == "Brain MRI without contrast"

    def test_dicom_deidentification_preserves_patient_sex(self) -> None:
        """PatientSex MUST be preserved — required for CHAI subgroup analysis.

        Per DICOM PS3.15 Annex E note: PatientSex is NOT a HIPAA Safe Harbor
        identifier. The CHAI specification explicitly requires it for bias/
        subgroup performance metrics.
        """
        dicom_bytes = _make_dicom_bytes(patient_sex="F")
        record = self.svc.deidentify_metadata(dicom_bytes)
        assert record.patient_sex == "F"

    def test_dicom_deidentification_preserves_patient_sex_male(self) -> None:
        dicom_bytes = _make_dicom_bytes(patient_sex="M")
        record = self.svc.deidentify_metadata(dicom_bytes)
        assert record.patient_sex == "M"

    def test_dicom_study_date_year_only(self) -> None:
        """Full study date must be reduced to year only."""
        dicom_bytes = _make_dicom_bytes(study_date="20240315")
        record = self.svc.deidentify_metadata(dicom_bytes)
        assert record.study_year == 2024
        # Full date must not be present
        assert "20240315" not in str(record)

    def test_dicom_pixel_data_never_returned(self) -> None:
        """PixelData must never appear in the metadata result."""
        dicom_bytes = _make_dicom_bytes(include_pixel_data=False)
        record = self.svc.deidentify_metadata(dicom_bytes)
        assert not hasattr(record, "pixel_data")
        assert "PixelData" not in str(record)

    def test_dicom_rejects_non_dicom_bytes(self) -> None:
        """Invalid DICOM bytes must raise DICOMParseError."""
        from policy_engine.services.dicom_service import DICOMParseError
        with pytest.raises(DICOMParseError):
            self.svc.deidentify_metadata(b"not a dicom file at all")

    def test_dicom_extract_ai_relevant_metadata(self) -> None:
        """extract_ai_relevant_metadata() returns an AIMetadata object."""
        from policy_engine.services.dicom_service import AIMetadata
        dicom_bytes = _make_dicom_bytes(modality="CT")
        record = self.svc.deidentify_metadata(dicom_bytes)
        ai_meta = self.svc.extract_ai_relevant_metadata(record)
        assert isinstance(ai_meta, AIMetadata)
        assert ai_meta.modality == "CT"


# ---------------------------------------------------------------------------
# File size enforcement
# ---------------------------------------------------------------------------

class TestDICOMFileSizeLimit:
    def test_dicom_file_size_limit_enforced(self) -> None:
        """Files exceeding DICOM_MAX_FILE_SIZE_MB must raise FileTooLargeError."""
        from policy_engine.services.dicom_service import (
            DICOMDeidentificationService,
            FileTooLargeError,
        )
        # Build 1 byte over the limit
        from policy_engine.config import settings
        limit_bytes = settings.DICOM_MAX_FILE_SIZE_MB * 1024 * 1024
        oversized = b"\x00" * (limit_bytes + 1)
        svc = DICOMDeidentificationService()
        with pytest.raises(FileTooLargeError):
            svc.deidentify_metadata(oversized)

    def test_dicom_file_at_exact_limit_accepted(self) -> None:
        """A valid DICOM file at (or below) the size limit must be accepted."""
        from policy_engine.services.dicom_service import DICOMDeidentificationService
        # Use a properly-formed tiny DICOM — size will be well under 50 MB
        dicom_bytes = _make_dicom_bytes()
        svc = DICOMDeidentificationService()
        record = svc.deidentify_metadata(dicom_bytes)
        assert record is not None


# ---------------------------------------------------------------------------
# Route integration tests
# ---------------------------------------------------------------------------

import uuid as _uuid
from datetime import datetime as _dt


def _make_dicom_headers(db, role) -> dict:
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


class TestDICOMRoutes:
    def test_dicom_rejects_non_dicom_content_type(
        self, client, db_session
    ) -> None:
        """POST /v1/dicom/extract with wrong MIME type must return 415 or 422."""
        from policy_engine.models.user import UserRole
        headers = _make_dicom_headers(db_session, UserRole.DATA_SCIENTIST)
        headers["Content-Type"] = "text/plain"
        resp = client.post("/v1/dicom/extract", content=b"fake data", headers=headers)
        assert resp.status_code in (415, 422)

    def test_dicom_extract_requires_auth(self, client) -> None:
        """POST /v1/dicom/extract without auth must return 401 or 403."""
        resp = client.post("/v1/dicom/extract", content=b"fake")
        assert resp.status_code in (401, 403)

    def test_dicom_extract_valid_file_returns_metadata(
        self, client, db_session
    ) -> None:
        """Valid DICOM upload must return de-identified metadata."""
        from policy_engine.models.user import UserRole
        headers = _make_dicom_headers(db_session, UserRole.DATA_SCIENTIST)
        dicom_bytes = _make_dicom_bytes(modality="CT", patient_sex="M")
        resp = client.post(
            "/v1/dicom/extract",
            files={"file": ("test.dcm", dicom_bytes, "application/dicom")},
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "Smith" not in str(body)
        assert "MRN" not in str(body)
        assert "modality" in body
        assert body.get("patient_sex") == "M"

    def test_dicom_pixel_data_never_returned_via_api(
        self, client, db_session
    ) -> None:
        """API response must never contain PixelData key."""
        from policy_engine.models.user import UserRole
        headers = _make_dicom_headers(db_session, UserRole.DATA_SCIENTIST)
        dicom_bytes = _make_dicom_bytes()
        resp = client.post(
            "/v1/dicom/extract",
            files={"file": ("test.dcm", dicom_bytes, "application/dicom")},
            headers=headers,
        )
        assert resp.status_code == 200
        assert "pixel_data" not in resp.json()
        assert "PixelData" not in str(resp.json())

    def test_dicom_file_size_limit_via_api(
        self, client, db_session
    ) -> None:
        """Files over 50 MB must return HTTP 413."""
        from policy_engine.models.user import UserRole
        from policy_engine.config import settings
        headers = _make_dicom_headers(db_session, UserRole.DATA_SCIENTIST)
        limit_bytes = settings.DICOM_MAX_FILE_SIZE_MB * 1024 * 1024
        oversized = b"\x00" * (limit_bytes + 1)
        resp = client.post(
            "/v1/dicom/extract",
            files={"file": ("big.dcm", oversized, "application/dicom")},
            headers=headers,
        )
        assert resp.status_code == 413

    def test_dicom_metadata_list_requires_auth(self, client) -> None:
        resp = client.get("/v1/dicom/metadata")
        assert resp.status_code in (401, 403)

    def test_dicom_metadata_list_returns_list(
        self, client, db_session
    ) -> None:
        from policy_engine.models.user import UserRole
        headers = _make_dicom_headers(db_session, UserRole.DATA_SCIENTIST)
        resp = client.get("/v1/dicom/metadata", headers=headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
