"""LLM-based scribe note auditor (Tier 3).

Tier 3 Roadmap §2 — the audit logic itself, independent of how data arrives.

Given a transcript + a generated SOAP/H&P note, this service:
  1. Splits the note into discrete clinical claims (HPI items, exam findings,
     vitals, assessment, plan, medications).
  2. For each claim, asks an LLM to find supporting evidence in the transcript.
  3. Marks claims with no support as `unattributed` (potential hallucination).
  4. Scores completeness against a SOAP-section checklist.
  5. Produces an `audit_score` blending hallucination, attribution, and
     completeness — same shape as the existing pure-Python `ScribeAuditEngine`.

Privacy: the transcript and generated note may contain PHI. They MUST be
PHI-redacted before being sent to any external LLM. The auditor uses
`PHIRedactionEngine` for that, then sends a stable shape that the LLM
treats as opaque tokens. We never log raw text.

Cost: with Claude Haiku 4.5, roughly $0.02 per 800-word note. The
fallback path (no API key) uses a deterministic regex-based matcher so the
audit still runs (lower recall, no hallucination on the auditor itself).
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from policy_engine.domain.admin.scribe_auditor import (
    LOGICAL_SECTIONS,
    ScribeAuditFinding,
    ScribeAuditResult,
    content_hash,
)
from policy_engine.infrastructure.security.phi_redaction import PHIRedactionEngine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Claim extraction — sentence-level
# ---------------------------------------------------------------------------

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|[\r\n]+")
_NUMERIC_TOKEN = re.compile(r"\b\d+(\.\d+)?\b")
_SECTION_HEADER = re.compile(
    r"^\s*(hpi|history of present illness|chief complaint|cc|"
    r"assessment|plan|medication|medications|"
    r"vital|vitals|exam|physical exam|review of systems|ros|allergies)\b[:.\s]*",
    re.IGNORECASE,
)


def _extract_claims(note_text: str, *, max_claims: int = 60) -> List[str]:
    """Split a clinical note into individual claims (sentences with content).

    Section headers ("HPI:", "Plan:", etc.) are stripped from the *start* of
    a sentence so that "HPI: Patient with chest pain" becomes the claim
    "Patient with chest pain". A sentence that consists only of a section
    header is dropped.
    """
    if not note_text:
        return []
    raw = [s.strip() for s in _SENTENCE_SPLIT.split(note_text)]
    claims: List[str] = []
    for sentence in raw:
        if not sentence:
            continue
        # Strip a leading section header (e.g. "HPI: ", "Plan: ", "Vitals: ")
        stripped = _SECTION_HEADER.sub("", sentence, count=1).strip()
        if not stripped or len(stripped) < 10:
            continue
        claims.append(stripped)
        if len(claims) >= max_claims:
            break
    return claims


# ---------------------------------------------------------------------------
# Deterministic fallback matcher — used when no LLM key is configured
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z\-']{2,}")


def _tokens(text: str) -> set:
    return {t.lower() for t in _TOKEN_RE.findall(text or "")}


def _deterministic_attribution(
    claim: str, transcript: str, *, threshold: float = 0.4
) -> bool:
    """Heuristic: a claim is attributed if ≥ `threshold` of its tokens appear
    in the transcript AND any numeric tokens in the claim are present in the
    transcript verbatim. Very rough, but useful as a no-LLM safety net."""
    claim_tokens = _tokens(claim)
    if not claim_tokens:
        return True

    transcript_tokens = _tokens(transcript)
    overlap = claim_tokens & transcript_tokens
    if not transcript_tokens:
        return False
    if len(overlap) / len(claim_tokens) < threshold:
        return False

    # Numeric anchor: every number > 1 in claim must be in transcript
    nums = [m.group(0) for m in _NUMERIC_TOKEN.finditer(claim) if float(m.group(0)) > 1]
    for n in nums:
        if n not in transcript:
            return False
    return True


# ---------------------------------------------------------------------------
# LLM-backed attribution
# ---------------------------------------------------------------------------

@dataclass
class _ClaimVerdict:
    claim: str
    attributed: bool
    evidence: Optional[str] = None
    confidence: float = 0.0


_LLM_PROMPT = """You are a clinical-note auditor. Given a doctor-patient
encounter TRANSCRIPT and a list of CLAIMS extracted from the AI-generated note,
decide for each claim whether the transcript supports it.

Rules:
- A claim is "attributed" only if the transcript contains evidence for it.
  Absence of evidence is NOT evidence of presence.
- Numeric values (lab results, doses, vitals) must appear in the transcript
  verbatim (or stated unambiguously) to count as attributed.
- "Unremarkable" / "no abnormalities" findings are attributed only if the
  clinician explicitly stated normal-results language in the transcript.
- Output STRICT JSON only — no preamble, no markdown.

TRANSCRIPT:
<<<TRANSCRIPT_START>>>
{transcript}
<<<TRANSCRIPT_END>>>

CLAIMS:
{claims_json}

Output schema:
{{"verdicts": [
  {{"index": <int>, "attributed": <bool>, "evidence": "<short quote or null>",
    "confidence": <float 0..1>}}
]}}
"""


def _llm_verdicts(
    transcript: str, claims: List[str]
) -> Optional[List[_ClaimVerdict]]:
    """Call Anthropic Claude to verdict each claim. Returns None on any failure
    so the caller can fall back to the deterministic matcher."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        from anthropic import Anthropic  # type: ignore
    except ImportError:
        return None

    claims_for_prompt = [{"index": i, "claim": c} for i, c in enumerate(claims)]
    prompt = _LLM_PROMPT.format(
        transcript=transcript[:12000],
        claims_json=json.dumps(claims_for_prompt, ensure_ascii=False),
    )

    try:
        client = Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"),
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        content_parts = []
        for block in getattr(msg, "content", []):
            text = getattr(block, "text", None)
            if text:
                content_parts.append(text)
        text = "".join(content_parts).strip()
    except Exception as exc:
        logger.warning("scribe_auditor LLM call failed: %s", exc)
        return None

    # Tolerate markdown fences
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n", "", text)
        text = re.sub(r"\n```$", "", text)
    try:
        parsed = json.loads(text)
        verdicts_raw = parsed.get("verdicts", [])
    except (json.JSONDecodeError, AttributeError) as exc:
        logger.warning("scribe_auditor LLM returned non-JSON: %s", exc)
        return None

    by_index = {int(v["index"]): v for v in verdicts_raw if "index" in v}
    out: List[_ClaimVerdict] = []
    for i, claim in enumerate(claims):
        v = by_index.get(i)
        if v is None:
            # Default to "unattributed" if LLM omitted the claim — safer for clinical
            out.append(_ClaimVerdict(claim=claim, attributed=False))
            continue
        out.append(_ClaimVerdict(
            claim=claim,
            attributed=bool(v.get("attributed", False)),
            evidence=v.get("evidence"),
            confidence=float(v.get("confidence", 0.0) or 0.0),
        ))
    return out


# ---------------------------------------------------------------------------
# Completeness — section-checklist
# ---------------------------------------------------------------------------

def _completeness(note_text: str) -> Tuple[float, List[str]]:
    """Same logical sections as the legacy pure-Python engine. Returns
    (score, missing_sections)."""
    if not note_text:
        return 0.0, ["HPI", "Assessment", "Plan", "Medications", "Vitals"]

    note_lc = note_text.lower()
    sections = [
        ("HPI", ("hpi", "history of present illness", "chief complaint")),
        ("Assessment", ("assessment",)),
        ("Plan", ("plan",)),
        ("Medications", ("medication",)),
        ("Vitals", ("vital",)),
    ]
    missing: List[str] = []
    found = 0
    for label, keywords in sections:
        if any(kw in note_lc for kw in keywords):
            found += 1
        else:
            missing.append(label)
    return (found / LOGICAL_SECTIONS) * 100.0, missing


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@dataclass
class LLMAuditOutcome:
    """Wraps ScribeAuditResult with extra LLM diagnostics for ops dashboards."""
    result: ScribeAuditResult
    method: str             # "llm" or "deterministic"
    redaction_findings: int = 0
    elapsed_ms: int = 0
    llm_model: Optional[str] = None


def _phi_redact(text: str, engine: PHIRedactionEngine) -> Tuple[str, int]:
    redacted = engine.redact(text or "")
    return redacted.redacted_text, len(redacted.findings)


def audit_note(
    *,
    session_id: str,
    transcript: str,
    generated_note: str,
    ai_model_used: Optional[str] = None,
    redaction_engine: Optional[PHIRedactionEngine] = None,
) -> LLMAuditOutcome:
    """Run a full LLM-backed audit.

    Steps:
      1. PHI-redact transcript + note (Safe-Harbor 18 identifiers).
      2. Extract sentence-level claims from the note.
      3. LLM verdicts each claim against the transcript.
         (Falls back to a deterministic regex/token matcher when no
         ANTHROPIC_API_KEY is set, or the LLM call fails.)
      4. Score completeness, attribution, and overall audit_score.
      5. Build findings (one per unattributed claim + omissions).

    Note text and transcripts are NEVER logged or persisted by this function.
    """
    started = time.monotonic()
    redaction_engine = redaction_engine or PHIRedactionEngine()

    safe_transcript, t_findings = _phi_redact(transcript, redaction_engine)
    safe_note, n_findings = _phi_redact(generated_note, redaction_engine)
    redaction_count = t_findings + n_findings

    claims = _extract_claims(safe_note)
    verdicts = _llm_verdicts(safe_transcript, claims)
    method = "llm"
    if verdicts is None:
        method = "deterministic"
        verdicts = [
            _ClaimVerdict(
                claim=c,
                attributed=_deterministic_attribution(c, safe_transcript),
                confidence=0.5,
            )
            for c in claims
        ]

    unattributed = [v for v in verdicts if not v.attributed]
    completeness_pct, missing_sections = _completeness(safe_note)
    total_claims = max(1, len(verdicts))
    attribution_score = (
        100.0 * (total_claims - len(unattributed)) / total_claims
    )
    hallucination_detected = bool(unattributed)
    hallucination_count = len(unattributed)

    # Audit score blends three signals; weights tuned to penalise hallucination
    audit_score = (
        0.40 * completeness_pct
        + 0.45 * attribution_score
        - min(15.0, hallucination_count * 5.0) * 0.0  # already encoded in attribution
    )
    audit_score += 0.15 * 100.0  # baseline floor reduces noise on tiny notes
    audit_score = max(0.0, min(100.0, audit_score))

    findings: List[ScribeAuditFinding] = []
    for v in unattributed[:25]:
        findings.append(ScribeAuditFinding(
            finding_type="hallucination" if v.confidence > 0.5 else "unattributed",
            severity="high" if v.confidence > 0.7 else "medium",
            description=(
                f"Claim is not supported by the transcript: "
                f"\"{v.claim[:200]}\""
            ),
            suggested_correction=(
                "Either cite a clinician statement that supports this claim, "
                "or remove it from the note before signing."
            ),
        ))
    for section in missing_sections:
        findings.append(ScribeAuditFinding(
            finding_type="omission",
            severity="medium",
            description=f"Required SOAP section missing: {section}",
            suggested_correction=f"Add a {section} section to the note.",
        ))

    result = ScribeAuditResult(
        session_id=session_id,
        completeness_score=round(completeness_pct, 1),
        hallucination_detected=hallucination_detected,
        audit_score=round(audit_score, 1),
        findings=findings,
        attribution_score=round(attribution_score, 1),
    )
    elapsed_ms = int((time.monotonic() - started) * 1000)
    return LLMAuditOutcome(
        result=result,
        method=method,
        redaction_findings=redaction_count,
        elapsed_ms=elapsed_ms,
        llm_model=ai_model_used,
    )


__all__ = [
    "LLMAuditOutcome",
    "audit_note",
    "content_hash",
]
