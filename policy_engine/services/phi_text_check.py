"""Server-side PHI / direct-identifier sniffing for free-text fields.

Backstop for HIPAA §164.530(c)(1) administrative safeguards and GDPR
Art. 25 (privacy by design): the platform should not silently absorb
patient identifiers pasted into free-text fields like
``ClinicAiTool.notes`` or ``purpose``.

The detector is intentionally **conservative-loud**: it errs on the
side of false positives because a clinician retyping a sentence is a
trivial cost compared to PHI silently entering a non-encrypted column.
Patterns covered:

* US Social Security number (``###-##-####``)
* Long contiguous digit runs typical of MRN/account numbers
* Plausible US dates of birth (``MM/DD/YYYY``, ``YYYY-MM-DD``)
* Phone numbers (``###-###-####`` and parenthesised variants)
* Email addresses (PII not PHI, but a frequent direct identifier)
"""

from __future__ import annotations

import re
from dataclasses import dataclass


_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "ssn",
        re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "what looks like a Social Security number",
    ),
    (
        "phone",
        re.compile(r"\b(?:\(?\d{3}\)?[\s\-.]?)\d{3}[\s\-.]?\d{4}\b"),
        "what looks like a phone number",
    ),
    (
        "email",
        re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"),
        "an email address",
    ),
    (
        "dob_iso",
        re.compile(r"\b(?:19|20)\d{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])\b"),
        "what looks like a date of birth",
    ),
    (
        "dob_us",
        re.compile(r"\b(?:0[1-9]|1[0-2])[/\-](?:0[1-9]|[12]\d|3[01])[/\-](?:19|20)\d{2}\b"),
        "what looks like a date of birth",
    ),
    (
        "long_digits",
        # 9+ contiguous digits — covers MRNs, account numbers, etc.
        re.compile(r"\b\d{9,}\b"),
        "a long number that looks like a record or account identifier",
    ),
)


@dataclass(frozen=True)
class PhiFinding:
    field: str
    pattern: str
    description: str


def scan_for_phi(field: str, value: str | None) -> PhiFinding | None:
    """Return the first PHI-shaped finding in ``value``, or None.

    ``field`` is the form field name; only used to make the error
    message helpful.  ``value`` may be None (treated as no finding).
    """
    if not value:
        return None
    for name, pattern, human in _PATTERNS:
        if pattern.search(value):
            return PhiFinding(field=field, pattern=name, description=human)
    return None


def reject_if_phi_present(fields: dict[str, str | None]) -> None:
    """Raise ``HTTPException(422)`` when any field looks like PHI.

    Called from the route handlers so the constraint is enforced server-
    side regardless of what the client does.  The error message names
    the offending field and what was detected — never echoes the matched
    text back to the client.
    """
    from fastapi import HTTPException, status

    for field, value in fields.items():
        finding = scan_for_phi(field, value)
        if finding is None:
            continue
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "phi_in_freetext",
                "field": finding.field,
                "message": (
                    f"The '{finding.field}' field contains {finding.description}. "
                    "Please remove patient identifiers — this field is for "
                    "describing the AI tool, not patient information."
                ),
            },
        )
