"""Ambient Scribe Auditing domain logic — pure Python."""
import re
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional

REQUIRED_SECTIONS = [
    "HPI",
    "History of Present Illness",
    "Assessment",
    "Plan",
    "Medication",
    "Vital",
]

# Deduplicated logical sections (either "HPI" or "History of Present Illness" counts as 1)
LOGICAL_SECTIONS = 5  # HPI, Assessment, Plan, Medications, Vitals

ICD10_PATTERN = re.compile(r'^[A-Z][0-9]{2}(\.[A-Z0-9]{1,4})?$')
CPT_PATTERN = re.compile(r'^\d{5}$')


@dataclass
class ScribeAuditFinding:
    finding_type: str
    severity: str
    description: str
    suggested_correction: Optional[str] = None


@dataclass
class ScribeAuditResult:
    session_id: str
    completeness_score: float
    hallucination_detected: bool
    audit_score: float
    findings: List[ScribeAuditFinding] = field(default_factory=list)
    attribution_score: float = 100.0


class ScribeAuditEngine:
    def check_completeness(self, note_text: str) -> float:
        """Score = sections found / 5 * 100. Logical deduplication: HPI or HOPI = 1 section."""
        if not note_text:
            return 0.0

        note_lower = note_text.lower()
        found = 0

        # HPI section (either keyword counts as 1)
        if "hpi" in note_lower or "history of present illness" in note_lower:
            found += 1
        # Assessment
        if "assessment" in note_lower:
            found += 1
        # Plan
        if "plan" in note_lower:
            found += 1
        # Medications
        if "medication" in note_lower:
            found += 1
        # Vitals
        if "vital" in note_lower:
            found += 1

        return (found / LOGICAL_SECTIONS) * 100.0

    def detect_hallucination_patterns(self, note_text: str, source_data: dict) -> List[str]:
        """Find numeric values in note not present in source_data."""
        suspicious = []
        # Extract all numbers from note
        note_numbers = set(re.findall(r'\b\d+\.?\d*\b', note_text))
        # Collect all string values from source_data
        source_values = set()
        for v in source_data.values():
            source_values.add(str(v))

        for num in note_numbers:
            if num not in source_values and float(num) > 10:  # ignore small common numbers
                suspicious.append(num)

        return suspicious

    def validate_icd_format(self, code: str) -> bool:
        """Validate ICD-10 code format."""
        return bool(ICD10_PATTERN.match(code.strip().upper()))

    def validate_cpt_format(self, code: str) -> bool:
        """Validate CPT code format (5 digits)."""
        return bool(CPT_PATTERN.match(code.strip()))

    def compute_audit_score(self, completeness: float, hallucination_count: int, attribution_errors: int) -> float:
        """Compute combined audit score."""
        score = completeness * 0.5 - (hallucination_count * 15) - (attribution_errors * 10)
        return max(0.0, min(100.0, score))

    def run_audit(self, session_id: str, note_text: str, source_data: dict) -> ScribeAuditResult:
        """Run a full audit on a scribe-generated note."""
        completeness = self.check_completeness(note_text)
        hallucinations = self.detect_hallucination_patterns(note_text, source_data)
        hallucination_count = len(hallucinations)
        audit_score = self.compute_audit_score(completeness, hallucination_count, 0)

        findings = []
        for h in hallucinations:
            findings.append(ScribeAuditFinding(
                finding_type="hallucination",
                severity="high",
                description=f"Value {h!r} in note not found in source data",
                suggested_correction="Verify this value against the source clinical data",
            ))

        if completeness < 60:
            findings.append(ScribeAuditFinding(
                finding_type="omission",
                severity="medium",
                description=f"Note completeness score is {completeness:.0f}% — missing required sections",
            ))

        return ScribeAuditResult(
            session_id=session_id,
            completeness_score=completeness,
            hallucination_detected=hallucination_count > 0,
            audit_score=audit_score,
            findings=findings,
        )


def content_hash(text: str) -> str:
    """SHA-256 hash of text content."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
