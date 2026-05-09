"""Tests for Tier 3 LLM-based scribe fact-checker (deterministic fallback path)."""
from policy_engine.services.scribe_auditor import (
    _extract_claims,
    _completeness,
    _deterministic_attribution,
    audit_note,
)


# ---------------------------------------------------------------------------
# Claim extraction
# ---------------------------------------------------------------------------

def test_extract_claims_skips_short_fragments_and_headers():
    note = """
HPI:
The patient is a 65-year-old male with a history of hypertension.
Hi.
He presents with chest pain that started two hours ago.
"""
    claims = _extract_claims(note)
    assert len(claims) == 2
    assert "65-year-old" in claims[0]
    assert "chest pain" in claims[1]


def test_extract_claims_caps_count():
    note = ". ".join(["This is a long sentence with content."] * 200) + "."
    claims = _extract_claims(note, max_claims=10)
    assert len(claims) == 10


# ---------------------------------------------------------------------------
# Completeness checklist
# ---------------------------------------------------------------------------

def test_completeness_full_note():
    note = """
HPI: chest pain.
Vitals: BP 130/80.
Assessment: likely angina.
Plan: aspirin and nitro.
Medications: metoprolol 25 mg.
"""
    score, missing = _completeness(note)
    assert score == 100.0
    assert missing == []


def test_completeness_missing_sections():
    note = "HPI: chest pain. Plan: aspirin."
    score, missing = _completeness(note)
    assert score == 40.0  # 2/5 sections
    assert "Vitals" in missing
    assert "Assessment" in missing
    assert "Medications" in missing


def test_completeness_empty_note():
    score, missing = _completeness("")
    assert score == 0.0
    assert len(missing) == 5


# ---------------------------------------------------------------------------
# Deterministic attribution fallback
# ---------------------------------------------------------------------------

def test_deterministic_attribution_supported_claim():
    transcript = (
        "Patient says he has been having chest pain for the last two hours. "
        "Pain radiates to the left arm and is associated with shortness of breath."
    )
    claim = "The patient reports chest pain radiating to the left arm."
    assert _deterministic_attribution(claim, transcript) is True


def test_deterministic_attribution_unsupported_claim():
    transcript = "Patient denies any abdominal pain or nausea."
    claim = (
        "Patient reports severe abdominal cramping localized to the right "
        "lower quadrant for the past three days, similar to his prior episode."
    )
    # Most claim tokens not in transcript → should be unattributed
    assert _deterministic_attribution(claim, transcript) is False


def test_deterministic_attribution_numeric_anchor_required():
    transcript = "Blood pressure was 120 over 80."
    # Number 200 is not in transcript — should fail attribution
    assert _deterministic_attribution(
        "Blood pressure was 200 over 100.", transcript,
    ) is False


# ---------------------------------------------------------------------------
# End-to-end audit_note (deterministic path — no ANTHROPIC_API_KEY)
# ---------------------------------------------------------------------------

def test_audit_note_passes_clean_attributed_note(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    transcript = (
        "Patient is a 65-year-old male with hypertension. He presents with "
        "chest pain that started two hours ago. Pain radiates to the left arm. "
        "Vital signs are blood pressure 130 over 80, heart rate 80. "
        "Plan: start aspirin and nitroglycerin. Continue metoprolol 25 mg. "
        "Assessment: likely unstable angina."
    )
    note = (
        "HPI: 65-year-old male with hypertension presenting with chest pain "
        "for two hours, radiating to the left arm.\n"
        "Vitals: BP 130 over 80, HR 80.\n"
        "Assessment: likely unstable angina.\n"
        "Plan: aspirin and nitroglycerin.\n"
        "Medications: continue metoprolol 25 mg."
    )

    outcome = audit_note(
        session_id="s-1",
        transcript=transcript,
        generated_note=note,
        ai_model_used="ambient-scribe-v1",
    )
    assert outcome.method == "deterministic"
    assert outcome.result.completeness_score == 100.0
    assert outcome.result.attribution_score >= 80.0
    assert outcome.result.audit_score >= 70.0


def test_audit_note_flags_hallucination_in_unattributed_claim(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    transcript = "Patient reports mild headache for one day. No fever."
    # Note adds clearly unsupported claims
    note = (
        "HPI: Patient with severe headache and high fever for five days, "
        "vomiting and photophobia.\n"
        "Vitals: temperature 39.5 and stiff neck noted.\n"
        "Assessment: bacterial meningitis suspected.\n"
        "Plan: lumbar puncture.\n"
        "Medications: ceftriaxone 2g IV started in ED."
    )
    outcome = audit_note(
        session_id="s-2",
        transcript=transcript,
        generated_note=note,
    )
    assert outcome.result.hallucination_detected is True
    finding_types = {f.finding_type for f in outcome.result.findings}
    assert "unattributed" in finding_types or "hallucination" in finding_types
    # Attribution should be low because most claims aren't in transcript
    assert outcome.result.attribution_score < 60.0


def test_audit_note_flags_missing_sections(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    transcript = "Patient reports chest pain."
    note = "HPI: chest pain."  # missing 4 of 5 sections
    outcome = audit_note(
        session_id="s-3",
        transcript=transcript,
        generated_note=note,
    )
    omissions = [f for f in outcome.result.findings if f.finding_type == "omission"]
    assert len(omissions) == 4


def test_audit_note_records_redaction_findings(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    transcript = (
        "Patient John Doe, MRN 12345678, presents with chest pain. "
        "Phone 555-123-4567. SSN 123-45-6789."
    )
    note = "HPI: 65-year-old with chest pain. Plan: aspirin."
    outcome = audit_note(
        session_id="s-redact",
        transcript=transcript,
        generated_note=note,
    )
    # PHI engine should find at least the SSN, MRN, phone number
    assert outcome.redaction_findings >= 2
    assert outcome.elapsed_ms >= 0


def test_audit_note_empty_inputs_does_not_crash(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    outcome = audit_note(
        session_id="s-empty",
        transcript="",
        generated_note="",
    )
    assert outcome.result.completeness_score == 0.0
    assert outcome.result.audit_score >= 0.0


# ---------------------------------------------------------------------------
# LLM path — patches the Anthropic client
# ---------------------------------------------------------------------------

def _install_fake_anthropic(monkeypatch, json_response: str):
    """Inject a fake `anthropic` module into sys.modules with a stub Anthropic
    class whose .messages.create() returns content[0].text == json_response."""
    import sys
    import types

    captured = {}

    class _StubBlock:
        def __init__(self, text: str) -> None:
            self.text = text

    class _StubMessage:
        def __init__(self, json_str: str) -> None:
            self.content = [_StubBlock(json_str)]

    class _StubMessages:
        def create(self, **kwargs):
            captured["kwargs"] = kwargs
            return _StubMessage(json_response)

    class _StubAnthropic:
        def __init__(self, api_key: str) -> None:
            self.messages = _StubMessages()

    fake_module = types.ModuleType("anthropic")
    fake_module.Anthropic = _StubAnthropic  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "anthropic", fake_module)
    return captured


def test_audit_note_uses_llm_when_api_key_present(monkeypatch):
    """When ANTHROPIC_API_KEY is set we route to the LLM verdict path."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    captured = _install_fake_anthropic(
        monkeypatch,
        '{"verdicts": ['
        '{"index": 0, "attributed": true, "evidence": "patient says chest pain", "confidence": 0.9},'
        '{"index": 1, "attributed": false, "evidence": null, "confidence": 0.85}'
        ']}',
    )

    transcript = "Patient reports chest pain."
    note = (
        "HPI: Patient reports chest pain for two hours. "
        "Plan: Plan to start IV thrombolytics immediately."
    )
    outcome = audit_note(
        session_id="s-llm",
        transcript=transcript,
        generated_note=note,
    )
    assert outcome.method == "llm"
    assert captured["kwargs"]["model"]
    assert outcome.result.hallucination_detected is True
    assert any(
        f.finding_type in ("hallucination", "unattributed")
        for f in outcome.result.findings
    )


def test_audit_note_falls_back_when_llm_returns_garbage(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    _install_fake_anthropic(monkeypatch, "this is not JSON")

    outcome = audit_note(
        session_id="s-fb",
        transcript="Patient denies pain.",
        generated_note="HPI: chest pain. Plan: aspirin and metoprolol. Vitals 120/80. Assessment: angina. Medications: continue.",
    )
    assert outcome.method == "deterministic"
