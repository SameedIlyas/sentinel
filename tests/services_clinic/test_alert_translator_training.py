"""Tests for the new clinic.tool.trains_on_data alert translation
(PRD.v2.md §6.8.2.c).
"""

from __future__ import annotations

import pytest

from policy_engine.services.clinic_alert_translator import translate_alert


pytestmark = pytest.mark.clinic


def test_clinic_trains_on_data_translation() -> None:
    out = translate_alert(
        tier="clinic_basic",
        alert_type="clinic.tool.trains_on_data",
        severity="medium",
        description="trains on customer prompts",
        tool_name="ChatGPT",
    )
    assert out.is_translated is True
    assert out.title == "Tool may train on your data"
    assert "ChatGPT" in out.description
    assert "train" in out.description.lower()
    assert out.next_step is not None
    assert "BAA" in out.next_step or "Sentinel-approved" in out.description


def test_clinic_trains_on_data_substitutes_default_tool() -> None:
    out = translate_alert(
        tier="clinic_standard",
        alert_type="clinic.tool.trains_on_data",
        severity="medium",
        description=None,
        tool_name=None,
    )
    assert "{{" not in out.description
    assert "}}" not in out.description


def test_enterprise_tier_skips_translation() -> None:
    out = translate_alert(
        tier="enterprise",
        alert_type="clinic.tool.trains_on_data",
        severity="medium",
        description="trains on customer prompts",
    )
    assert out.is_translated is False
    assert out.title == "clinic.tool.trains_on_data"
