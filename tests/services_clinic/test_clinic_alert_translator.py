"""Tests for ``policy_engine.services.clinic_alert_translator``.

Translator is pure (no DB), so tests are fast table-driven cases.
"""

from __future__ import annotations

import pytest

from policy_engine.services.clinic_alert_translator import (
    TranslatedAlert,
    translate_alert,
)


pytestmark = pytest.mark.clinic


def test_enterprise_tier_returns_canonical_wording() -> None:
    out = translate_alert(
        tier="enterprise",
        alert_type="phi_in_prompt",
        severity="high",
        description="Original technical alert text",
    )
    assert isinstance(out, TranslatedAlert)
    assert out.is_translated is False
    assert out.title == "phi_in_prompt"
    assert out.description == "Original technical alert text"
    assert out.next_step is None


def test_clinic_tier_translates_known_alert_type() -> None:
    out = translate_alert(
        tier="clinic_standard",
        alert_type="phi_in_prompt",
        severity="high",
        description="Whatever the canonical text is",
        tool_name="ChatGPT",
    )
    assert out.is_translated is True
    assert out.title == "Patient info caught in a prompt"
    assert "ChatGPT" in out.description
    assert out.next_step is not None


def test_template_substitutes_tool_and_system() -> None:
    out = translate_alert(
        tier="clinic_basic",
        alert_type="blocked_access",
        severity="medium",
        description="...",
        system_name="Epic",
        tool_name="ScribeAI",
    )
    assert "Epic" in out.description


def test_unsubstituted_placeholders_stripped() -> None:
    """If a template references {{tool}} but no tool_name is passed, the
    placeholder must be replaced with a sane default — never shown raw."""
    out = translate_alert(
        tier="clinic_basic",
        alert_type="drift_warning",
        severity="medium",
        description="",
        tool_name=None,  # explicitly missing
    )
    assert "{{" not in out.description
    assert "}}" not in out.description
    assert out.description  # non-empty fallback


def test_description_pattern_fallback_phi() -> None:
    """When alert_type isn't in the table, regex fallback over description fires."""
    out = translate_alert(
        tier="clinic_standard",
        alert_type="custom_unknown",
        severity="low",
        description="Detected PHI in outbound payload",
    )
    assert out.is_translated is True
    assert "Patient info" in out.title


def test_description_pattern_fallback_block() -> None:
    out = translate_alert(
        tier="clinic_standard",
        alert_type="custom_unknown",
        severity="low",
        description="Action was blocked by policy",
    )
    assert out.is_translated is True
    assert out.title == "Action blocked"


def test_no_translation_match_keeps_canonical_text() -> None:
    """No alert_type match, no description rule match → canonical fallback
    with informational next step (never blank)."""
    out = translate_alert(
        tier="clinic_basic",
        alert_type="totally_made_up",
        severity="low",
        description="Some technical thing happened",
    )
    assert out.is_translated is False
    assert out.description == "Some technical thing happened"
    assert out.next_step  # non-None fallback


@pytest.mark.parametrize(
    "severity,expected_substr",
    [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
        ("LOW", "Low"),  # case-insensitive
    ],
)
def test_severity_label_phrasing(severity: str, expected_substr: str) -> None:
    out = translate_alert(
        tier="clinic_basic",
        alert_type="phi_in_prompt",
        severity=severity,
        description="x",
    )
    assert expected_substr in out.severity_label


def test_unknown_severity_falls_through() -> None:
    out = translate_alert(
        tier="clinic_basic",
        alert_type="phi_in_prompt",
        severity="extreme",
        description="x",
    )
    # Unknown severity passes through verbatim rather than going to "Info".
    assert out.severity_label == "extreme"


def test_none_tier_treated_as_enterprise() -> None:
    out = translate_alert(
        tier=None,
        alert_type="phi_in_prompt",
        severity="low",
        description="x",
    )
    assert out.is_translated is False
