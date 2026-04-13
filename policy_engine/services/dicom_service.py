"""DICOM De-Identification Service — PS3.15 Annex E Basic Profile.

Strips all PHI per DICOM PS3.15 Annex E, with one deliberate exception:
PatientSex is PRESERVED because it is NOT a HIPAA Safe Harbor identifier
and is required by the CHAI specification for subgroup performance analysis.
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import pydicom

from policy_engine.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class DICOMParseError(Exception):
    """Raised when the input cannot be parsed as a valid DICOM file."""


class FileTooLargeError(Exception):
    """Raised when the uploaded file exceeds DICOM_MAX_FILE_SIZE_MB."""


# ---------------------------------------------------------------------------
# Tags stripped per DICOM PS3.15 Annex E Basic De-identification Profile
# PatientSex is intentionally EXCLUDED from this list (see module docstring).
# ---------------------------------------------------------------------------

_PHI_TAGS_TO_STRIP = frozenset({
    "PatientName",
    "PatientID",
    "PatientBirthDate",
    "PatientAge",
    "PatientAddress",
    "PatientTelephoneNumbers",
    "PatientMotherBirthName",
    "OtherPatientIDs",
    "OtherPatientNames",
    "InstitutionName",
    "InstitutionAddress",
    "InstitutionalDepartmentName",
    "ReferringPhysicianName",
    "ReferringPhysicianAddress",
    "PerformingPhysicianName",
    "NameOfPhysiciansReadingStudy",
    "OperatorsName",
    "AdmittingDiagnosesDescription",
    "DerivationDescription",
    "SeriesDescription",
    "StationName",
    "DeviceSerialNumber",
    "StudyID",
    "AccessionNumber",
    "RequestedProcedureID",
    "ScheduledProcedureStepID",
})

# Tags kept for AI/CHAI relevance (non-PHI)
_KEEP_TAGS = frozenset({
    "Modality",
    "Manufacturer",
    "ManufacturerModelName",
    "StudyDescription",
    "SOPClassUID",
    "SOPInstanceUID",
    "StudyInstanceUID",
    "SeriesInstanceUID",
    "StudyDate",       # kept as year only
    "PatientSex",      # intentionally preserved — see module docstring
    "ImageType",
    "PhotometricInterpretation",
    "Rows",
    "Columns",
    "BitsAllocated",
    "BitsStored",
    "HighBit",
    "PixelRepresentation",
    "SamplesPerPixel",
    "NumberOfFrames",
    "SliceThickness",
    "SpacingBetweenSlices",
    "KVP",
    "ExposureTime",
    "XRayTubeCurrent",
    "BodyPartExamined",
    "ViewPosition",
    "ContrastBolusAgent",
    "AcquisitionNumber",
    "InstanceNumber",
})


# ---------------------------------------------------------------------------
# Output dataclasses
# ---------------------------------------------------------------------------

@dataclass
class DICOMMetadataResult:
    """De-identified DICOM metadata safe for storage and API responses."""
    modality: Optional[str] = None
    manufacturer: Optional[str] = None
    study_description: Optional[str] = None
    sop_class_uid: Optional[str] = None
    study_year: Optional[int] = None          # StudyDate → year only
    patient_sex: Optional[str] = None         # preserved per CHAI spec
    body_part: Optional[str] = None
    additional_tags: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AIMetadata:
    """Subset of DICOM metadata most relevant for AI model analysis."""
    modality: Optional[str] = None
    manufacturer: Optional[str] = None
    body_part: Optional[str] = None
    patient_sex: Optional[str] = None
    study_year: Optional[int] = None
    sop_class_uid: Optional[str] = None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class DICOMDeidentificationService:
    """
    De-identifies DICOM metadata per PS3.15 Annex E Basic Profile.

    Never returns pixel data. Always preserves PatientSex.
    """

    def deidentify_metadata(self, dicom_file_bytes: bytes) -> DICOMMetadataResult:
        """
        Parse DICOM bytes, strip PHI, and return safe metadata.

        Raises:
            FileTooLargeError: input exceeds DICOM_MAX_FILE_SIZE_MB.
            DICOMParseError: input is not a valid DICOM file.
        """
        max_bytes = settings.DICOM_MAX_FILE_SIZE_MB * 1024 * 1024
        if len(dicom_file_bytes) > max_bytes:
            raise FileTooLargeError(
                f"File size {len(dicom_file_bytes)} bytes exceeds "
                f"{settings.DICOM_MAX_FILE_SIZE_MB} MB limit"
            )

        try:
            ds = pydicom.dcmread(
                io.BytesIO(dicom_file_bytes),
                stop_before_pixels=True,
                force=False,
            )
        except Exception as exc:
            raise DICOMParseError(f"Failed to parse DICOM input: {exc}") from exc

        return self._extract_safe_metadata(ds)

    def extract_ai_relevant_metadata(
        self, record: DICOMMetadataResult
    ) -> AIMetadata:
        """Return the AI-relevant subset of de-identified metadata."""
        return AIMetadata(
            modality=record.modality,
            manufacturer=record.manufacturer,
            body_part=record.body_part,
            patient_sex=record.patient_sex,
            study_year=record.study_year,
            sop_class_uid=record.sop_class_uid,
        )

    # ── private ──────────────────────────────────────────────────────────────

    def _extract_safe_metadata(self, ds: pydicom.Dataset) -> DICOMMetadataResult:
        additional: Dict[str, Any] = {}

        for elem in ds:
            keyword = elem.keyword
            if not keyword:
                continue
            if keyword == "PixelData":
                # Never touch pixel data — skip entirely
                continue
            if keyword in _PHI_TAGS_TO_STRIP:
                continue
            if keyword not in _KEEP_TAGS:
                continue
            try:
                additional[keyword] = str(elem.value)
            except Exception:
                additional[keyword] = None

        # StudyDate: keep year only
        study_year: Optional[int] = None
        raw_study_date = additional.pop("StudyDate", None)
        if raw_study_date and len(str(raw_study_date)) >= 4:
            try:
                study_year = int(str(raw_study_date)[:4])
            except ValueError:
                pass

        return DICOMMetadataResult(
            modality=additional.pop("Modality", None),
            manufacturer=additional.pop("Manufacturer", None),
            study_description=additional.pop("StudyDescription", None),
            sop_class_uid=additional.pop("SOPClassUID", None),
            study_year=study_year,
            patient_sex=additional.pop("PatientSex", None),
            body_part=additional.pop("BodyPartExamined", None),
            additional_tags=additional,
        )
