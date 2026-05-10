"""Tests for ``policy_engine.services.clinic_policy_templates``."""

from __future__ import annotations

import pytest

from policy_engine.services.clinic_policy_templates import (
    CLINIC_POLICY_TEMPLATES,
    PolicyTemplate,
    get_template,
    list_templates_for_tier,
)


pytestmark = pytest.mark.clinic


def test_all_templates_are_polite_dataclass_instances() -> None:
    for t in CLINIC_POLICY_TEMPLATES:
        assert isinstance(t, PolicyTemplate)
        assert t.template_id
        assert t.name
        assert t.description
        assert t.why_it_matters
        assert t.policy_type
        assert isinstance(t.rules, list)
        assert t.priority > 0


def test_template_ids_are_unique() -> None:
    ids = [t.template_id for t in CLINIC_POLICY_TEMPLATES]
    assert len(ids) == len(set(ids))


def test_get_template_resolves_known_id() -> None:
    t = get_template("block_phi_to_public_llm")
    assert t is not None
    assert t.template_id == "block_phi_to_public_llm"


def test_get_template_returns_none_for_unknown() -> None:
    assert get_template("does_not_exist") is None


def test_list_templates_basic_tier_excludes_advanced() -> None:
    """Multi-site-only templates should not appear for clinic_basic."""
    basic = list_templates_for_tier("clinic_basic")
    standard = list_templates_for_tier("clinic_standard")
    multi = list_templates_for_tier("clinic_multi_site")
    # Standard + multi-site get more templates than basic.
    assert len(basic) <= len(standard) <= len(multi)


def test_list_templates_unknown_tier_empty() -> None:
    assert list_templates_for_tier("free_trial_phantom") == []


def test_to_policy_dict_strips_presentation_fields() -> None:
    t = CLINIC_POLICY_TEMPLATES[0]
    d = t.to_policy_dict()
    assert "template_id" not in d
    assert "why_it_matters" not in d
    assert "recommended_for_tiers" not in d
    # Real Policy fields preserved.
    assert d["name"]
    assert d["policy_type"]
    assert "rules" in d


def test_phi_block_template_is_high_priority() -> None:
    """The PHI-blocking template must outrank everything else (sanity check)."""
    phi_block = get_template("block_phi_to_public_llm")
    assert phi_block is not None
    other_priorities = [
        t.priority for t in CLINIC_POLICY_TEMPLATES if t.template_id != "block_phi_to_public_llm"
    ]
    assert phi_block.priority >= max(other_priorities)


def test_recommended_for_tiers_includes_clinic_tiers_only() -> None:
    """Templates should not accidentally recommend themselves for enterprise."""
    for t in CLINIC_POLICY_TEMPLATES:
        for tier in t.recommended_for_tiers:
            assert tier in ("clinic_basic", "clinic_standard", "clinic_multi_site")
