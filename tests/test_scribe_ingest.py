"""Tests for Tier 3 vendor-agnostic scribe ingest + adapters."""
import pytest

from policy_engine.models.scribe_audit import (
    ScribeAuditFinding as ScribeAuditFindingModel,
    ScribeAuditModel,
)
from policy_engine.services.scribe_ingest import (
    ScribeIngestRecord,
    VENDOR_ADAPTERS,
    _adapt_abridge,
    _adapt_deepscribe,
    _adapt_mock,
    _adapt_nabla,
    ingest_scribe_record,
    ingest_vendor_payload,
)


# ---------------------------------------------------------------------------
# Adapters
# ---------------------------------------------------------------------------

def test_adapt_mock_identity():
    payload = {
        "session_id": "s-1",
        "transcript": "Patient reports chest pain.",
        "generated_note": "HPI: chest pain.",
        "ai_model_used": "model-x",
        "clinician_id": "doc-1",
        "encounter_id": "enc-1",
    }
    record = _adapt_mock(payload)
    assert record.session_id == "s-1"
    assert record.transcript.startswith("Patient")
    assert record.generated_note.startswith("HPI")
    assert record.ai_model_used == "model-x"
    assert record.clinician_id == "doc-1"
    assert record.vendor == "mock"


def test_adapt_mock_requires_transcript_and_note():
    with pytest.raises(ValueError):
        _adapt_mock({"session_id": "s-1", "transcript": "x"})
    with pytest.raises(ValueError):
        _adapt_mock({"session_id": "s-1", "generated_note": "x"})


def test_adapt_mock_generates_session_id_when_missing():
    record = _adapt_mock({
        "transcript": "Patient.",
        "generated_note": "Note.",
    })
    assert record.session_id  # auto-generated UUID


def test_adapt_abridge_canonical_payload():
    payload = {
        "event": "note.finalized",
        "session": {"id": "abx-001", "encounter_id": "ENC-99"},
        "note": {"text": "HPI: cough.", "model": "abridge-v3"},
        "transcript": {"text": "Patient says cough."},
        "clinician": {"id": "doc-7", "npi": "12345"},
    }
    record = _adapt_abridge(payload)
    assert record.session_id == "abx-001"
    assert record.transcript == "Patient says cough."
    assert record.generated_note == "HPI: cough."
    assert record.ai_model_used == "abridge-v3"
    assert record.clinician_id == "doc-7"
    assert record.vendor == "abridge"
    assert record.encounter_id == "ENC-99"


def test_adapt_abridge_rejects_missing_fields():
    with pytest.raises(ValueError):
        _adapt_abridge({"session": {"id": "x"}, "note": {"text": "y"}})  # no transcript


def test_adapt_nabla_canonical_payload():
    payload = {
        "type": "note.finalized",
        "note_id": "nbl-1",
        "encounter_id": "ENC-77",
        "soap_note": "HPI: rash.",
        "transcript": "Patient says rash on arms.",
        "user": {"id": "doc-3"},
        "model_version": "nabla-2.1",
    }
    record = _adapt_nabla(payload)
    assert record.session_id == "nbl-1"
    assert record.ai_model_used == "nabla-2.1"
    assert record.clinician_id == "doc-3"
    assert record.vendor == "nabla"


def test_adapt_nabla_rejects_missing_fields():
    with pytest.raises(ValueError):
        _adapt_nabla({"note_id": "x", "transcript": "y"})  # no soap_note


def test_adapt_deepscribe_with_nested_data():
    payload = {
        "session_id": "ds-1",
        "encounter_id": "ENC-44",
        "note_data": {"text": "HPI: knee pain."},
        "audio_data": {"transcript": "Patient says knee pain."},
        "model": "deepscribe-v5",
        "provider": {"id": "doc-9"},
    }
    record = _adapt_deepscribe(payload)
    assert record.session_id == "ds-1"
    assert record.ai_model_used == "deepscribe-v5"
    assert record.vendor == "deepscribe"


# ---------------------------------------------------------------------------
# ingest_scribe_record persistence
# ---------------------------------------------------------------------------

def test_ingest_scribe_record_persists_audit_and_findings(db_session, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    transcript = "Patient denies any pain."
    note = (
        "HPI: severe headache and high fever for five days, vomiting and photophobia.\n"
        "Vitals: temperature 39.5 noted.\n"
        "Assessment: bacterial meningitis.\n"
        "Plan: lumbar puncture.\n"
        "Medications: ceftriaxone."
    )
    record = ScribeIngestRecord(
        session_id="ingest-1",
        transcript=transcript,
        generated_note=note,
        ai_model_used="vendor-x",
        vendor="mock",
    )

    outcome = ingest_scribe_record(db_session, record)
    assert outcome.audit_id is not None
    assert outcome.deduplicated is False
    assert outcome.method == "deterministic"
    assert outcome.audit_score is not None
    assert outcome.hallucination_detected is True

    audits = db_session.query(ScribeAuditModel).all()
    assert len(audits) == 1
    assert audits[0].session_id == "ingest-1"
    assert audits[0].ai_model_used == "vendor-x"

    findings = db_session.query(ScribeAuditFindingModel).all()
    assert len(findings) >= 1


def test_ingest_scribe_record_idempotent_for_same_session(db_session, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    record = ScribeIngestRecord(
        session_id="ingest-2",
        transcript="Patient reports chest pain.",
        generated_note="HPI: chest pain. Plan: aspirin. Vitals BP 120/80. Assessment: angina. Medications: continue meds.",
        ai_model_used="m",
    )
    first = ingest_scribe_record(db_session, record)
    second = ingest_scribe_record(db_session, record)
    assert first.deduplicated is False
    assert second.deduplicated is True
    assert second.audit_id == first.audit_id
    assert db_session.query(ScribeAuditModel).count() == 1


def test_ingest_vendor_payload_routes_to_correct_adapter(db_session, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    payload = {
        "session": {"id": "abx-99"},
        "note": {"text": "HPI: cough. Plan: rest. Vitals stable. Assessment: viral. Medications: none."},
        "transcript": {"text": "Patient says he has a mild cough."},
    }
    outcome = ingest_vendor_payload(
        db_session, vendor="abridge", payload=payload,
    )
    assert outcome.audit_id is not None
    audit = db_session.query(ScribeAuditModel).first()
    assert audit.session_id == "abx-99"


def test_ingest_vendor_payload_unsupported_raises():
    import sqlalchemy
    with pytest.raises(ValueError):
        ingest_vendor_payload(
            db=None, vendor="splunk", payload={},
        )


# ---------------------------------------------------------------------------
# Endpoint coverage
# ---------------------------------------------------------------------------

def test_ingest_endpoint_canonical(authed_client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    client, _agent_id = authed_client
    resp = client.post(
        "/v1/admin/scribe-audits/ingest",
        json={
            "session_id": "api-1",
            "transcript": "Patient reports chest pain.",
            "generated_note": (
                "HPI: chest pain. Vitals BP 120/80. "
                "Assessment: angina. Plan: aspirin. Medications: continue."
            ),
            "ai_model_used": "vendor-x",
        },
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["audit_id"]
    assert body["method"] == "deterministic"


def test_ingest_endpoint_vendor_abridge(authed_client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    client, _agent_id = authed_client
    resp = client.post(
        "/v1/admin/scribe-audits/ingest/vendor",
        json={
            "vendor": "abridge",
            "payload": {
                "session": {"id": "abx-200"},
                "note": {"text": (
                    "HPI: rash. Vitals normal. "
                    "Assessment: contact derm. Plan: topical. Medications: hydrocortisone."
                )},
                "transcript": {"text": "Patient reports rash on arms after gardening."},
                "clinician": {"id": "doc-1"},
            },
        },
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["vendor"] == "abridge"
    assert body["audit_id"]


def test_ingest_endpoint_vendor_unsupported_returns_400(authed_client):
    client, _agent_id = authed_client
    resp = client.post(
        "/v1/admin/scribe-audits/ingest/vendor",
        json={"vendor": "epic", "payload": {}},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "unsupported_vendor"


def test_ingest_endpoint_vendor_invalid_payload_returns_422(authed_client):
    client, _agent_id = authed_client
    resp = client.post(
        "/v1/admin/scribe-audits/ingest/vendor",
        json={"vendor": "nabla", "payload": {"note_id": "x"}},  # missing transcript + soap_note
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"] == "invalid_payload"


def test_ingest_endpoint_validates_required_fields(authed_client):
    client, _agent_id = authed_client
    resp = client.post(
        "/v1/admin/scribe-audits/ingest",
        json={"session_id": "x", "transcript": "y"},  # missing generated_note
    )
    assert resp.status_code == 422


def test_vendor_adapters_registry_contains_expected():
    assert {"mock", "abridge", "nabla", "deepscribe"} <= set(VENDOR_ADAPTERS.keys())
