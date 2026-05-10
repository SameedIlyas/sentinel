"""Tests for ``policy_engine.billing.plans``."""

from __future__ import annotations

import pytest

from policy_engine.billing.plans import (
    CLINIC_PLAN_NAMES,
    PLANS,
    Plan,
    get_plan,
    is_clinic_plan,
    stripe_payment_link,
)
from policy_engine.models.organization import (
    TIER_CLINIC_BASIC,
    TIER_CLINIC_MULTI_SITE,
    TIER_CLINIC_STANDARD,
    TIER_ENTERPRISE,
)


pytestmark = pytest.mark.billing


def test_plans_table_has_all_clinic_tiers() -> None:
    assert TIER_CLINIC_BASIC in PLANS
    assert TIER_CLINIC_STANDARD in PLANS
    assert TIER_CLINIC_MULTI_SITE in PLANS
    assert TIER_ENTERPRISE in PLANS


def test_plan_caps_are_strictly_ascending() -> None:
    """Tool / seat caps must scale with tier price."""
    basic = PLANS[TIER_CLINIC_BASIC]
    standard = PLANS[TIER_CLINIC_STANDARD]
    multi = PLANS[TIER_CLINIC_MULTI_SITE]
    assert basic.tool_cap < standard.tool_cap < multi.tool_cap
    assert basic.seat_cap < standard.seat_cap < multi.seat_cap
    assert basic.audit_retention_days <= standard.audit_retention_days <= multi.audit_retention_days
    assert basic.locations_cap <= standard.locations_cap <= multi.locations_cap


def test_plan_prices_match_pricing_doc() -> None:
    assert PLANS[TIER_CLINIC_BASIC].monthly_price_usd == 199
    assert PLANS[TIER_CLINIC_STANDARD].monthly_price_usd == 349
    assert PLANS[TIER_CLINIC_MULTI_SITE].monthly_price_usd == 699
    assert PLANS[TIER_ENTERPRISE].monthly_price_usd == 0  # sales-led


def test_baa_modes_match_blueprint() -> None:
    assert PLANS[TIER_CLINIC_BASIC].baa_mode == "click_through"
    assert PLANS[TIER_CLINIC_STANDARD].baa_mode == "executed_bundled"
    assert PLANS[TIER_CLINIC_MULTI_SITE].baa_mode == "executed_bundled"
    assert PLANS[TIER_ENTERPRISE].baa_mode == "negotiated"


def test_get_plan_returns_enterprise_for_unknown() -> None:
    p = get_plan("never_existed")
    assert isinstance(p, Plan)
    assert p.name == TIER_ENTERPRISE


def test_get_plan_returns_enterprise_for_none() -> None:
    assert get_plan(None).name == TIER_ENTERPRISE


def test_is_clinic_plan() -> None:
    for name in CLINIC_PLAN_NAMES:
        assert is_clinic_plan(name)
    assert not is_clinic_plan(TIER_ENTERPRISE)
    assert not is_clinic_plan("starter")
    assert not is_clinic_plan(None)


def test_stripe_payment_link_resolves_env(monkeypatch) -> None:
    monkeypatch.setenv("STRIPE_PAYMENT_LINK_CLINIC_BASIC", "https://buy.example.test/basic")
    assert stripe_payment_link(TIER_CLINIC_BASIC) == "https://buy.example.test/basic"


def test_stripe_payment_link_returns_none_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("STRIPE_PAYMENT_LINK_CLINIC_BASIC", raising=False)
    assert stripe_payment_link(TIER_CLINIC_BASIC) is None


def test_stripe_payment_link_none_for_enterprise() -> None:
    """Enterprise has no env-driven link (sales-led)."""
    assert stripe_payment_link(TIER_ENTERPRISE) is None


def test_stripe_payment_link_unknown_plan_none() -> None:
    assert stripe_payment_link("free_trial_phantom") is None
