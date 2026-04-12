"""DICOM metadata extractor — strips all PHI tags per PS3.15 Annex E."""
import logging
from dataclasses import dataclass
from typing import Any, Dict, Union

logger = logging.getLogger(__name__)

# All 18 PHI DICOM tags to strip (PS3.15 Annex E Basic De-identification Profile)
PHI_DICOM_TAGS = {
    "PatientName",
    "PatientID",
    "PatientBirthDate",
    "PatientSex",
    "PatientAge",
    "PatientAddress",
    "PatientTelephoneNumbers",
    "InstitutionName",
    "InstitutionAddress",
    "ReferringPhysicianName",
    "PerformingPhysicianName",
    "OperatorsName",
    "StudyDate",
    "SeriesDate",
    "AcquisitionDate",
    "ContentDate",
    "StationName",
    "DeviceSerialNumber",
}


class DICOMPixelDataError(Exception):
    """Raised when pixel data access is attempted."""


class DICOMParseError(Exception):
    """Raised when input cannot be parsed as DICOM."""


class DICOMExtractor:
    """Extracts de-identified metadata from DICOM files."""

    def extract_metadata(self, source: Union[str, bytes]) -> Dict[str, Any]:
        try:
            import pydicom
            from pydicom.errors import InvalidDicomError
        except ImportError:
            raise NotImplementedError(
                "Install pydicom to use DICOM extraction: pip install pydicom"
            )

        try:
            if isinstance(source, (bytes, bytearray)):
                import io
                ds = pydicom.dcmread(io.BytesIO(source), stop_before_pixels=True)
            else:
                ds = pydicom.dcmread(source, stop_before_pixels=True)
        except Exception as e:
            raise DICOMParseError(f"Failed to parse DICOM input: {e}")

        # Build safe metadata dict, skipping all PHI tags
        safe: Dict[str, Any] = {}
        for elem in ds:
            keyword = elem.keyword
            if not keyword:
                continue
            if keyword == "PixelData":
                raise DICOMPixelDataError(
                    "Pixel data access is prohibited — PHI risk"
                )
            if keyword in PHI_DICOM_TAGS:
                continue
            try:
                safe[keyword] = str(elem.value)
            except Exception:
                safe[keyword] = None
        return safe
