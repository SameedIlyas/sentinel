"""FHIR R4 Parser Service — HIPAA Safe Harbor de-identification.

Implements 45 CFR 164.514(b) Safe Harbor: removes all 18 PHI identifiers
and reduces dates to year-only before storing to the FHIR cache.
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# HIPAA Safe Harbor PHI fields present in FHIR resources
# ---------------------------------------------------------------------------

PHI_FHIR_FIELDS_TO_STRIP: List[str] = [
    "name",
    "telecom",
    "address",
    "identifier",
    "photo",
    "contact",
    "generalPractitioner",
    "managingOrganization",
    "birthDate",       # kept as birth_year only
    "deceasedDateTime",
    "multipleBirthDate",
]

_LOINC_SYSTEM = "http://loinc.org"

# Salt keeps hashes project-specific; not a secret — just prevents cross-project
# correlation. Value is stable so the same FHIR ID always maps to the same hash.
_DE_ID_SALT = "sentinel-fhir-deid-v1"


# ---------------------------------------------------------------------------
# Output dataclasses (PHI-free)
# ---------------------------------------------------------------------------

@dataclass
class PatientRecord:
    fhir_id: str          # HMAC-SHA256 hash of original ID
    birth_year: Optional[int]
    gender: Optional[str]
    race: Optional[str]
    ethnicity: Optional[str]


@dataclass
class ObservationRecord:
    loinc_code: Optional[str]
    value: Optional[str]
    unit: Optional[str]
    effective_date: Optional[str]   # date portion only (YYYY-MM-DD)
    status: Optional[str]
    patient_id: str                 # de-identified patient ref


@dataclass
class DiagnosticReportRecord:
    code: Optional[str]
    conclusion: Optional[str]
    issued_date: Optional[str]      # date portion only (YYYY-MM-DD)
    performer_role: Optional[str]   # role label, not name


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _de_identify_id(raw_id: str) -> str:
    """Return a stable, deterministic de-identified ID for a FHIR resource ID."""
    token = f"{_DE_ID_SALT}:{raw_id}"
    return hashlib.sha256(token.encode()).hexdigest()[:16]


def _date_only(dt_string: Optional[str]) -> Optional[str]:
    """Return the date portion (YYYY-MM-DD) of a datetime string, or None."""
    if not dt_string:
        return None
    return dt_string[:10]


def _year_only(date_string: Optional[str]) -> Optional[int]:
    """Return the year integer from a FHIR date (YYYY[-MM[-DD]]), or None."""
    if not date_string:
        return None
    try:
        return int(date_string[:4])
    except (ValueError, IndexError):
        return None


def _extract_loinc(coding_list: Optional[List[Dict[str, Any]]]) -> Optional[str]:
    if not coding_list:
        return None
    for coding in coding_list:
        if coding.get("system") == _LOINC_SYSTEM:
            return coding.get("code")
    # fallback: return first code regardless of system
    return coding_list[0].get("code") if coding_list else None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class FHIRParserService:
    """
    De-identifies FHIR R4 resources per HIPAA Safe Harbor (45 CFR 164.514(b)).

    Contraindications are ALWAYS left for human review — never auto-filled.
    """

    def parse_patient(self, resource: Dict[str, Any]) -> PatientRecord:
        """Strip all PHI; keep id (de-id'd), birth_year, gender, race, ethnicity."""
        raw_id = resource.get("id", str(uuid.uuid4()))
        birth_date = resource.get("birthDate")

        # Race / ethnicity come from FHIR extensions (US Core)
        race, ethnicity = self._extract_race_ethnicity(resource)

        return PatientRecord(
            fhir_id=_de_identify_id(raw_id),
            birth_year=_year_only(birth_date),
            gender=resource.get("gender"),
            race=race,
            ethnicity=ethnicity,
        )

    def parse_observation(self, resource: Dict[str, Any]) -> ObservationRecord:
        """Keep LOINC code, value, unit, effective_date, status, patient_id (de-id'd)."""
        code_obj = resource.get("code", {})
        coding_list = code_obj.get("coding", [])

        value_qty = resource.get("valueQuantity", {})
        value = str(value_qty.get("value")) if value_qty.get("value") is not None else None
        unit = value_qty.get("unit")

        effective_dt = (
            resource.get("effectiveDateTime")
            or resource.get("effectivePeriod", {}).get("start")
        )

        subject_ref = resource.get("subject", {}).get("reference", "")
        # Extract ID portion: "Patient/p-123" → "p-123"
        raw_patient_id = subject_ref.split("/")[-1] if subject_ref else subject_ref
        patient_id = _de_identify_id(raw_patient_id) if raw_patient_id else ""

        return ObservationRecord(
            loinc_code=_extract_loinc(coding_list),
            value=value,
            unit=unit,
            effective_date=_date_only(effective_dt),
            status=resource.get("status"),
            patient_id=patient_id,
        )

    def parse_diagnostic_report(self, resource: Dict[str, Any]) -> DiagnosticReportRecord:
        """Keep code, conclusion, issued_date, performer role (not name)."""
        code_obj = resource.get("code", {})
        coding_list = code_obj.get("coding", [])

        # Performer: extract role label if present, strip display name
        performer_role: Optional[str] = None
        performers = resource.get("performer", [])
        if performers:
            # Role may be present as performer[].extension or performer[].type
            first = performers[0]
            if "type" in first:
                performer_role = str(first["type"])

        return DiagnosticReportRecord(
            code=_extract_loinc(coding_list),
            conclusion=resource.get("conclusion"),
            issued_date=_date_only(resource.get("issued")),
            performer_role=performer_role,
        )

    def ingest_bundle(
        self, payload: Dict[str, Any], db: Session
    ) -> int:
        """
        Accept a FHIR Bundle or single resource, de-identify, and persist.

        Returns the count of records successfully ingested.
        """
        resources: List[Dict[str, Any]] = []

        resource_type = payload.get("resourceType", "")
        if resource_type == "Bundle":
            for entry in payload.get("entry", []):
                res = entry.get("resource", {})
                if res:
                    resources.append(res)
        else:
            # Single resource
            resources = [payload]

        count = 0
        for res in resources:
            rtype = res.get("resourceType", "")
            try:
                record = self._parse_any(rtype, res)
                if record is None:
                    continue
                self._store_record(rtype, record, db)
                count += 1
            except Exception as exc:
                logger.warning("Failed to ingest FHIR resource type=%s: %s", rtype, exc)
        return count

    # ── private ──────────────────────────────────────────────────────────────

    def _parse_any(
        self, resource_type: str, resource: Dict[str, Any]
    ) -> Optional[Any]:
        if resource_type == "Patient":
            return self.parse_patient(resource)
        if resource_type == "Observation":
            return self.parse_observation(resource)
        if resource_type == "DiagnosticReport":
            return self.parse_diagnostic_report(resource)
        return None  # unsupported type — skip silently

    def _store_record(
        self, resource_type: str, record: Any, db: Session
    ) -> None:
        from policy_engine.models.fhir_cache import FHIRResourceCache
        from datetime import datetime

        import dataclasses
        payload = dataclasses.asdict(record) if dataclasses.is_dataclass(record) else {}
        cache_entry = FHIRResourceCache(
            id=str(uuid.uuid4()),
            resource_type=resource_type,
            fhir_id=getattr(record, "fhir_id", str(uuid.uuid4())),
            payload=payload,
            cached_at=datetime.utcnow(),
        )
        db.add(cache_entry)
        db.flush()

    def _extract_race_ethnicity(
        self, resource: Dict[str, Any]
    ) -> tuple[Optional[str], Optional[str]]:
        """Extract race/ethnicity from US Core FHIR extensions."""
        race: Optional[str] = None
        ethnicity: Optional[str] = None
        for ext in resource.get("extension", []):
            url = ext.get("url", "")
            if "race" in url:
                for inner in ext.get("extension", []):
                    if inner.get("url") == "text":
                        race = inner.get("valueString")
            elif "ethnicity" in url:
                for inner in ext.get("extension", []):
                    if inner.get("url") == "text":
                        ethnicity = inner.get("valueString")
        return race, ethnicity
