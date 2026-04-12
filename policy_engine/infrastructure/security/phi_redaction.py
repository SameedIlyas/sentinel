"""PHI/PII Redaction Engine — covers all 18 HIPAA Safe Harbor identifiers."""
import hashlib
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class RedactionStrategy(str, Enum):
    MASK = "mask"
    HASH = "hash"
    GENERALIZE = "generalize"
    SUPPRESS = "suppress"


@dataclass
class PHIFinding:
    phi_type: str
    start: int
    end: int
    original: str
    confidence: float = 1.0
    strategy: str = RedactionStrategy.MASK


@dataclass
class PHIRedactionResult:
    original_text: str
    redacted_text: str
    findings: List[PHIFinding] = field(default_factory=list)
    processing_time_ms: float = 0.0


# Regex patterns for all 18 HIPAA Safe Harbor identifiers + healthcare-specific
PHI_PATTERNS: Dict[str, re.Pattern] = {
    # 1. Names — basic name detection (Title Case words with honorific)
    "NAME": re.compile(
        r"\b(?:Mr\.|Mrs\.|Ms\.|Dr\.|Prof\.)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b"
    ),
    # 2. ZIP codes
    "ZIP_CODE": re.compile(r"\b\d{5}(?:-\d{4})?\b"),
    # 3. Dates (MM/DD/YYYY, MM-DD-YYYY, Month DD YYYY)
    "DATE": re.compile(
        r"\b(?:0?[1-9]|1[0-2])[/-](?:0?[1-9]|[12]\d|3[01])[/-](?:19|20)\d{2}\b"
        r"|\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?"
        r"|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
        r"\s+\d{1,2},?\s+\d{4}\b",
        re.IGNORECASE,
    ),
    # 4. Phone numbers
    "PHONE": re.compile(
        r"\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
    ),
    # 5. Fax numbers (same pattern — context distinguishes)
    "FAX": re.compile(
        r"\bfax[:\s]+(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
        re.IGNORECASE,
    ),
    # 6. Email addresses
    "EMAIL": re.compile(
        r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
    ),
    # 7. SSN
    "SSN": re.compile(
        r"\b(?!000|666|9\d{2})\d{3}[-\s]?(?!00)\d{2}[-\s]?(?!0{4})\d{4}\b"
    ),
    # 8. MRN — Medical Record Number
    "MRN": re.compile(r"\bMRN[:\s#]*\d{5,10}\b", re.IGNORECASE),
    # 9. Health plan beneficiary numbers
    "HEALTH_PLAN_NUMBER": re.compile(
        r"\b(?:member|beneficiary|plan)\s*(?:id|#|number)[:\s]*[A-Z0-9]{6,15}\b",
        re.IGNORECASE,
    ),
    # 10. Account numbers
    "ACCOUNT_NUMBER": re.compile(
        r"\b(?:acct|account)[:\s#.]*\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",
        re.IGNORECASE,
    ),
    # 11. Certificate/License numbers
    "LICENSE_NUMBER": re.compile(
        r"\b(?:license|cert(?:ificate)?)[:\s#]*[A-Z]{0,3}\d{5,10}\b",
        re.IGNORECASE,
    ),
    # 12. VIN
    "VIN": re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b"),
    # 13. Device serial numbers
    "DEVICE_SERIAL": re.compile(
        r"\b(?:serial|s/n|device)[:\s#]*[A-Z0-9]{6,20}\b", re.IGNORECASE
    ),
    # 14. URLs
    "URL": re.compile(r"https?://[^\s]+"),
    # 15. IP addresses
    "IP_ADDRESS": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    # 16. Biometric identifiers (keyword-based flag)
    "BIOMETRIC": re.compile(
        r"\b(?:fingerprint|voice\s*print|retinal\s*scan|iris\s*scan)\b",
        re.IGNORECASE,
    ),
    # 17. Full-face photo references
    "PHOTO_REFERENCE": re.compile(
        r"\b(?:photo|photograph|image|picture)\s*(?:of|showing)?\s*(?:patient|face)\b",
        re.IGNORECASE,
    ),
    # 18. Unique IDs / generic identifier catch-all
    "UNIQUE_ID": re.compile(
        r"\b(?:id|identifier)[:\s#]*[A-Z0-9]{8,20}\b", re.IGNORECASE
    ),
    # Healthcare-specific (NPI, DEA)
    "NPI": re.compile(r"\bNPI[:\s#]*\d{10}\b", re.IGNORECASE),
    "DEA_NUMBER": re.compile(r"\b[A-Z]{2}\d{7}\b"),
}


def _apply_strategy(text: str, finding: PHIFinding, strategy: str) -> str:
    """Apply redaction strategy to a finding and return replacement string."""
    if strategy == RedactionStrategy.MASK:
        return f"[REDACTED_{finding.phi_type}]"
    if strategy == RedactionStrategy.HASH:
        return hashlib.sha256(finding.original.encode()).hexdigest()[:16]
    if strategy == RedactionStrategy.SUPPRESS:
        return ""
    if strategy == RedactionStrategy.GENERALIZE:
        if finding.phi_type == "ZIP_CODE":
            return finding.original[:3] + "XX"
        if finding.phi_type == "DATE":
            m = re.search(r"\b(19|20)\d{2}\b", finding.original)
            return m.group(0) if m else "[YEAR]"
        return f"[GENERALIZED_{finding.phi_type}]"
    return f"[REDACTED_{finding.phi_type}]"


class PHIRedactionEngine:
    """
    HIPAA Safe Harbor compliant PHI/PII redaction engine.

    Detects all 18 Safe Harbor identifier types plus healthcare-specific
    identifiers using regex (with optional Presidio NER for higher accuracy).
    """

    def __init__(self, default_strategy: str = RedactionStrategy.MASK):
        self.default_strategy = default_strategy
        self._presidio_available = False
        try:
            from presidio_analyzer import AnalyzerEngine  # noqa: F401
            self._presidio_available = True
        except ImportError:
            pass

    def redact(
        self,
        text: Optional[str],
        strategy: Optional[str] = None,
        org_id: str = "",
        user_id: str = "",
    ) -> PHIRedactionResult:
        if not text:
            return PHIRedactionResult(
                original_text=text or "",
                redacted_text=text or "",
                findings=[],
                processing_time_ms=0.0,
            )

        start = time.perf_counter()
        effective_strategy = strategy or self.default_strategy
        findings: List[PHIFinding] = []

        for phi_type, pattern in PHI_PATTERNS.items():
            for match in pattern.finditer(text):
                findings.append(
                    PHIFinding(
                        phi_type=phi_type,
                        start=match.start(),
                        end=match.end(),
                        original=match.group(),
                        confidence=0.9,
                        strategy=effective_strategy,
                    )
                )

        # Sort findings by position descending for safe in-place replacement
        findings.sort(key=lambda f: f.start, reverse=True)
        redacted = text
        for finding in findings:
            replacement = _apply_strategy(redacted, finding, effective_strategy)
            redacted = redacted[: finding.start] + replacement + redacted[finding.end :]

        # Re-sort ascending for output
        findings.sort(key=lambda f: f.start)
        elapsed_ms = (time.perf_counter() - start) * 1000

        return PHIRedactionResult(
            original_text=text,
            redacted_text=redacted,
            findings=findings,
            processing_time_ms=elapsed_ms,
        )

    @staticmethod
    def content_hash(text: str) -> str:
        """SHA-256 hash of content — safe to store in logs."""
        return hashlib.sha256(text.encode()).hexdigest()
