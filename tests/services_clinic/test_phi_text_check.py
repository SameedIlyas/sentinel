"""Tests for ``policy_engine.services.phi_text_check``.

Covers every pattern in ``_PATTERNS`` (table-driven), the
``reject_if_phi_present`` route helper, and the contract that error
messages NEVER echo the matched substring back to the client.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from policy_engine.services.phi_text_check import (
    PhiFinding,
    reject_if_phi_present,
    scan_for_phi,
)


pytestmark = pytest.mark.clinic


# Table-driven pattern coverage. Synthetic inputs only — none of these
# represent a real person.

PHI_POSITIVE_CASES: list[tuple[str, str, str]] = [
    # (label, input, expected pattern name)
    ("ssn", "Patient SSN: 123-45-6789", "ssn"),
    ("phone_dashed", "Call 555-867-5309 for follow-up", "phone"),
    ("phone_paren", "Call (555) 867-5309 for follow-up", "phone"),
    ("phone_dotted", "Call 555.867.5309 for follow-up", "phone"),
    ("email_simple", "Reach me at jdoe@example.com please", "email"),
    ("email_plus", "Reach me at jdoe+tag@example.co.uk please", "email"),
    ("dob_iso", "Born on 1985-03-14", "dob_iso"),
    ("dob_us_slash", "DOB 03/14/1985 confirmed", "dob_us"),
    ("dob_us_dash", "DOB 03-14-1985 confirmed", "dob_us"),
    # NOTE: 10-digit runs (e.g. "1234567890") match the phone regex first
    # because phone permits NO separators between groups. Use 11+ digits to
    # exclusively trigger long_digits; 9-digit (sub-phone) also works.
    ("mrn_long_digits_12", "MRN: 123456789012", "long_digits"),  # 12 digits
    ("account_long_digits", "Account 999999999", "long_digits"),  # 9 digits
]

PHI_NEGATIVE_CASES: list[tuple[str, str]] = [
    # Looks-like-but-isn't or below threshold.
    ("short_id_8_digits", "ID 12345678"),  # 8 digits — below 9-digit threshold
    ("year_only", "Last seen in 1985"),
    ("invalid_dob_month", "13/14/1985"),  # 13th month invalid
    ("invalid_dob_day", "03/32/1985"),  # day 32 invalid
    ("ssn_wrong_shape_8_digit", "1234-56-789"),  # not SSN shape
    ("brand_with_dot", "Acme.AI Health"),  # not an email
    ("phone_too_short", "555-867-530"),  # 9 digits, not 10
    ("plain_text", "The patient was seen last week."),  # nothing
    ("fictional_company", "Foo Valley Internal Medicine"),
]


@pytest.mark.parametrize("label,input_str,expected_pattern", PHI_POSITIVE_CASES)
def test_scan_for_phi_positive(label: str, input_str: str, expected_pattern: str) -> None:
    finding = scan_for_phi("notes", input_str)
    assert finding is not None, f"expected detection on {label}: {input_str!r}"
    assert finding.field == "notes"
    assert finding.pattern == expected_pattern, (
        f"{label}: expected pattern {expected_pattern!r}, got {finding.pattern!r}"
    )


@pytest.mark.parametrize("label,input_str", PHI_NEGATIVE_CASES)
def test_scan_for_phi_negative(label: str, input_str: str) -> None:
    finding = scan_for_phi("notes", input_str)
    assert finding is None, f"unexpected match on {label}: {input_str!r} -> {finding}"


def test_scan_for_phi_returns_none_for_empty() -> None:
    assert scan_for_phi("notes", None) is None
    assert scan_for_phi("notes", "") is None


def test_scan_for_phi_field_propagates() -> None:
    finding = scan_for_phi("purpose", "DOB 1990-01-01")
    assert finding is not None
    assert finding.field == "purpose"
    assert isinstance(finding, PhiFinding)


def test_reject_if_phi_present_raises_422() -> None:
    """The route helper raises a 422 with structured detail and never echoes
    the matched substring."""
    matched_string = "Contact (555) 867-5309 for the patient"
    with pytest.raises(HTTPException) as exc:
        reject_if_phi_present({"notes": matched_string})
    assert exc.value.status_code == 422
    detail = exc.value.detail
    assert isinstance(detail, dict)
    assert detail["error"] == "phi_in_freetext"
    assert detail["field"] == "notes"
    # Message must NOT echo the matched substring (HIPAA safeguard).
    assert "555" not in detail["message"]
    assert "867" not in detail["message"]
    assert "5309" not in detail["message"]


def test_reject_if_phi_present_first_match_wins() -> None:
    """When multiple fields contain PHI, the helper raises on the first
    finding rather than aggregating (current contract — pin it)."""
    with pytest.raises(HTTPException) as exc:
        reject_if_phi_present(
            {
                "name": "OK Brand Health",
                "purpose": "Has SSN 111-22-3333 oops",
                "notes": "And email leak@example.com",
            }
        )
    detail = exc.value.detail
    assert detail["field"] == "purpose"
    assert "ssn" not in detail["message"].lower() or "social security" in detail["message"].lower()


def test_reject_if_phi_present_passes_clean_input() -> None:
    """Clean input from PHI-safe factories must NOT raise."""
    # Should not raise.
    reject_if_phi_present(
        {
            "name": "Acme Scribe",
            "vendor": "Acme AI",
            "purpose": "General clinical note formatting.",
            "notes": "Reviewed by practice manager monthly.",
        }
    )


def test_reject_if_phi_present_skips_none_values() -> None:
    """Optional fields default to None — the helper must tolerate that."""
    reject_if_phi_present({"name": None, "vendor": None, "purpose": None, "notes": None})
