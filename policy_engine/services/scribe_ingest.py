"""Vendor-agnostic scribe-audit ingest pipeline.

Tier 3 §2 — companion to `scribe_auditor.audit_note`. Receives a vendor's
webhook payload (or a hand-fed JSON for design partners), normalises it to
the canonical `ScribeIngestRecord` shape, runs the LLM-backed audit, and
persists the result + findings.

Adapters supported today:
  - `mock`      — vendor-agnostic; payload IS the canonical shape
  - `abridge`   — Abridge Partner API webhook payload
  - `nabla`     — Nabla note-finalization webhook payload
  - `deepscribe` — DeepScribe webhook payload (best-effort)

Each adapter is a pure function `dict -> ScribeIngestRecord` so adding a new
vendor is one entry in `VENDOR_ADAPTERS`. The audit pipeline stays a single
code path.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from sqlalchemy.orm import Session

from policy_engine.models.scribe_audit import (
    ScribeAuditFinding as ScribeAuditFindingModel,
    ScribeAuditModel,
)
from policy_engine.services.scribe_auditor import audit_note, content_hash

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Canonical record + outcome
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ScribeIngestRecord:
    """Vendor-agnostic shape consumed by the ingest pipeline."""
    session_id: str
    transcript: str
    generated_note: str
    ai_model_used: Optional[str] = None
    clinician_id: Optional[str] = None
    vendor: Optional[str] = None
    encounter_id: Optional[str] = None


@dataclass
class ScribeIngestOutcome:
    audit_id: Optional[str] = None
    audit_score: Optional[float] = None
    hallucination_detected: Optional[bool] = None
    findings_count: int = 0
    deduplicated: bool = False
    method: Optional[str] = None
    elapsed_ms: int = 0


# ---------------------------------------------------------------------------
# Vendor adapters
# ---------------------------------------------------------------------------

def _adapt_mock(payload: Dict[str, Any]) -> ScribeIngestRecord:
    """Identity adapter for design-partner pilots — JSON payload IS the shape."""
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")
    session_id = payload.get("session_id") or str(uuid.uuid4())
    transcript = payload.get("transcript") or ""
    generated_note = payload.get("generated_note") or payload.get("note_text") or ""
    if not transcript or not generated_note:
        raise ValueError("transcript + generated_note are required")
    return ScribeIngestRecord(
        session_id=session_id,
        transcript=transcript,
        generated_note=generated_note,
        ai_model_used=payload.get("ai_model_used"),
        clinician_id=payload.get("clinician_id"),
        vendor="mock",
        encounter_id=payload.get("encounter_id"),
    )


def _adapt_abridge(payload: Dict[str, Any]) -> ScribeIngestRecord:
    """Abridge partner-API webhook.

    Documented payload (representative — Abridge customises per partner):
      {
        "event": "note.finalized",
        "session": {"id": "abx-...", "encounter_id": "ENC-..."},
        "note": {"text": "...", "model": "abridge-vN"},
        "transcript": {"text": "..."},
        "clinician": {"npi": "...", "id": "..."}
      }
    """
    session = payload.get("session") or {}
    note = payload.get("note") or {}
    transcript = payload.get("transcript") or {}
    clinician = payload.get("clinician") or {}

    note_text = note.get("text") or note.get("body") or ""
    transcript_text = transcript.get("text") or transcript.get("body") or ""
    if not note_text or not transcript_text:
        raise ValueError("Abridge payload missing note.text or transcript.text")

    return ScribeIngestRecord(
        session_id=session.get("id") or payload.get("id") or str(uuid.uuid4()),
        transcript=transcript_text,
        generated_note=note_text,
        ai_model_used=note.get("model") or "abridge",
        clinician_id=clinician.get("id") or clinician.get("npi"),
        vendor="abridge",
        encounter_id=session.get("encounter_id"),
    )


def _adapt_nabla(payload: Dict[str, Any]) -> ScribeIngestRecord:
    """Nabla note-finalization webhook.

    Representative shape:
      {
        "type": "note.finalized",
        "note_id": "nbl-...",
        "encounter_id": "ENC-...",
        "soap_note": "...",
        "transcript": "...",
        "user": {"id": "..."},
        "model_version": "..."
      }
    """
    note_text = (
        payload.get("soap_note")
        or payload.get("note")
        or payload.get("note_text")
        or ""
    )
    transcript = payload.get("transcript") or payload.get("transcript_text") or ""
    if not note_text or not transcript:
        raise ValueError("Nabla payload missing soap_note or transcript")

    user = payload.get("user") or {}
    return ScribeIngestRecord(
        session_id=payload.get("note_id") or payload.get("session_id") or str(uuid.uuid4()),
        transcript=transcript,
        generated_note=note_text,
        ai_model_used=payload.get("model_version") or "nabla",
        clinician_id=user.get("id"),
        vendor="nabla",
        encounter_id=payload.get("encounter_id"),
    )


def _adapt_deepscribe(payload: Dict[str, Any]) -> ScribeIngestRecord:
    """Best-effort DeepScribe webhook (schema varies by deployment)."""
    note_text = (
        payload.get("clinical_note")
        or payload.get("note")
        or (payload.get("note_data") or {}).get("text")
        or ""
    )
    transcript = (
        payload.get("transcript")
        or payload.get("audio_transcript")
        or (payload.get("audio_data") or {}).get("transcript")
        or ""
    )
    if not note_text or not transcript:
        raise ValueError("DeepScribe payload missing note or transcript")
    return ScribeIngestRecord(
        session_id=payload.get("session_id") or str(uuid.uuid4()),
        transcript=transcript,
        generated_note=note_text,
        ai_model_used=payload.get("model") or "deepscribe",
        clinician_id=(payload.get("provider") or {}).get("id"),
        vendor="deepscribe",
        encounter_id=payload.get("encounter_id"),
    )


VENDOR_ADAPTERS: Dict[str, Callable[[Dict[str, Any]], ScribeIngestRecord]] = {
    "mock": _adapt_mock,
    "abridge": _adapt_abridge,
    "nabla": _adapt_nabla,
    "deepscribe": _adapt_deepscribe,
}


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _existing_audit_for_session(
    db: Session, session_id: str
) -> Optional[ScribeAuditModel]:
    return (
        db.query(ScribeAuditModel)
        .filter(ScribeAuditModel.session_id == session_id)
        .first()
    )


def ingest_scribe_record(
    db: Session,
    record: ScribeIngestRecord,
    *,
    organization_id: Optional[str] = None,
    audited_by: Optional[str] = None,
) -> ScribeIngestOutcome:
    """Run the audit + persist results. Idempotent per `session_id`."""
    outcome = ScribeIngestOutcome()

    existing = _existing_audit_for_session(db, record.session_id)
    if existing is not None:
        outcome.audit_id = existing.id
        outcome.audit_score = existing.audit_score
        outcome.hallucination_detected = existing.hallucination_detected
        outcome.deduplicated = True
        return outcome

    audit_outcome = audit_note(
        session_id=record.session_id,
        transcript=record.transcript,
        generated_note=record.generated_note,
        ai_model_used=record.ai_model_used,
    )
    result = audit_outcome.result

    now = datetime.utcnow()
    audit_id = str(uuid.uuid4())
    audit = ScribeAuditModel(
        id=audit_id,
        session_id=record.session_id,
        patient_context_hash=content_hash(record.transcript),
        ai_model_used=record.ai_model_used,
        generated_note_hash=content_hash(record.generated_note),
        audit_score=result.audit_score,
        hallucination_detected=result.hallucination_detected,
        completeness_score=result.completeness_score,
        attribution_score=result.attribution_score,
        status="pending",
        organization_id=organization_id,
        audited_by=audited_by,
        created_at=now,
    )
    db.add(audit)
    db.flush()

    for f in result.findings:
        db.add(ScribeAuditFindingModel(
            id=str(uuid.uuid4()),
            audit_id=audit_id,
            finding_type=f.finding_type,
            severity=f.severity,
            description=f.description,
            suggested_correction=f.suggested_correction,
            created_at=now,
        ))
    db.commit()

    outcome.audit_id = audit_id
    outcome.audit_score = result.audit_score
    outcome.hallucination_detected = result.hallucination_detected
    outcome.findings_count = len(result.findings)
    outcome.method = audit_outcome.method
    outcome.elapsed_ms = audit_outcome.elapsed_ms
    return outcome


def ingest_vendor_payload(
    db: Session,
    *,
    vendor: str,
    payload: Dict[str, Any],
    organization_id: Optional[str] = None,
    audited_by: Optional[str] = None,
) -> ScribeIngestOutcome:
    """Translate a vendor payload to canonical shape and run the pipeline."""
    adapter = VENDOR_ADAPTERS.get((vendor or "").lower())
    if adapter is None:
        raise ValueError(f"unsupported_vendor: {vendor}")
    record = adapter(payload)
    return ingest_scribe_record(
        db, record,
        organization_id=organization_id,
        audited_by=audited_by,
    )


__all__ = [
    "ScribeIngestRecord",
    "ScribeIngestOutcome",
    "VENDOR_ADAPTERS",
    "ingest_scribe_record",
    "ingest_vendor_payload",
]
