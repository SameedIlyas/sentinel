"""Tests for tier_resolver — pure tier-resolution from Stripe payloads.

CRIT-006 — these tests use fixture dicts only; the Stripe SDK is not a
dependency. The resolver must be safe to call from any handler that
receives a Stripe-shaped event dict.
"""
from __future__ import annotations

import pytest

from policy_engine.billing.tier_resolver import (
    resolve_tier,
    should_apply_tier,
)


def _sub_with_item_plan_metadata(tier_value: object) -> dict:
    """Subscription shape used by the modern Stripe API."""
    return {
        "id": "sub_test",
        "status": "active",
        "customer": "cus_test",
        "items": {
            "data": [
                {
                    "plan": {
                        "id": "plan_x",
                        "metadata": {"tier": tier_value},
                    },
                }
            ]
        },
    }


def _sub_with_item_price_metadata(tier_value: object) -> dict:
    return {
        "id": "sub_test",
        "status": "trialing",
        "customer": "cus_test",
        "items": {
            "data": [
                {
                    "price": {
                        "id": "price_x",
                        "metadata": {"tier": tier_value},
                    },
                }
            ]
        },
    }


def _sub_with_product_metadata(tier_value: object) -> dict:
    return {
        "id": "sub_test",
        "status": "active",
        "customer": "cus_test",
        "items": {
            "data": [
                {
                    "plan": {
                        "id": "plan_x",
                        "product": {
                            "id": "prod_x",
                            "metadata": {"tier": tier_value},
                        },
                    },
                }
            ]
        },
    }


class TestResolveTier:
    @pytest.mark.parametrize(
        "tier",
        ["clinic_basic", "clinic_standard", "clinic_multi_site"],
    )
    def test_item_plan_metadata_each_clinic_tier(self, tier: str):
        assert resolve_tier(_sub_with_item_plan_metadata(tier)) == tier

    @pytest.mark.parametrize(
        "tier",
        ["clinic_basic", "clinic_standard", "clinic_multi_site"],
    )
    def test_item_price_metadata_each_clinic_tier(self, tier: str):
        assert resolve_tier(_sub_with_item_price_metadata(tier)) == tier

    @pytest.mark.parametrize(
        "tier",
        ["clinic_basic", "clinic_standard", "clinic_multi_site"],
    )
    def test_product_metadata_each_clinic_tier(self, tier: str):
        assert resolve_tier(_sub_with_product_metadata(tier)) == tier

    def test_top_level_subscription_metadata_wins(self):
        sub = {
            "id": "sub_test",
            "status": "active",
            "metadata": {"tier": "clinic_standard"},
            "items": {
                "data": [
                    {"plan": {"metadata": {"tier": "clinic_basic"}}}
                ]
            },
        }
        # Subscription-level metadata is the most explicit signal.
        assert resolve_tier(sub) == "clinic_standard"

    def test_legacy_single_plan_nickname(self):
        sub = {
            "id": "sub_test",
            "status": "active",
            "plan": {"nickname": "clinic_multi_site"},
        }
        assert resolve_tier(sub) == "clinic_multi_site"

    def test_unknown_tier_returns_none(self):
        assert resolve_tier(_sub_with_item_plan_metadata("platinum")) is None

    def test_enterprise_returns_none(self):
        # ``enterprise`` is not a clinic tier — leave org.tier alone.
        assert resolve_tier(_sub_with_item_plan_metadata("enterprise")) is None

    def test_empty_subscription_returns_none(self):
        assert resolve_tier({}) is None

    def test_none_input_returns_none(self):
        assert resolve_tier(None) is None  # type: ignore[arg-type]

    def test_non_string_metadata_value_returns_none(self):
        # Defensive: schema-fail rather than crash.
        assert resolve_tier(_sub_with_item_plan_metadata(42)) is None

    def test_handles_missing_items_array(self):
        sub = {"id": "sub_test", "status": "active"}
        assert resolve_tier(sub) is None


class TestShouldApplyTier:
    @pytest.mark.parametrize("status", ["active", "trialing"])
    def test_paying_statuses_apply_tier(self, status: str):
        assert should_apply_tier(status) is True

    @pytest.mark.parametrize(
        "status",
        ["canceled", "past_due", "unpaid", "incomplete", "incomplete_expired", ""],
    )
    def test_non_paying_statuses_do_not_apply_tier(self, status: str):
        assert should_apply_tier(status) is False

    def test_non_string_status(self):
        assert should_apply_tier(None) is False
        assert should_apply_tier(42) is False


class TestIntegrationWithHandler:
    """End-to-end shape that ``_handle_subscription_updated`` produces."""

    def test_resolver_round_trip_with_active_subscription(self):
        sub = _sub_with_item_plan_metadata("clinic_standard")
        assert should_apply_tier(sub["status"]) is True
        assert resolve_tier(sub) == "clinic_standard"

    def test_resolver_skipped_when_status_canceled(self):
        sub = _sub_with_item_plan_metadata("clinic_standard")
        sub["status"] = "canceled"
        # Even though we *can* resolve a tier, should_apply_tier returns
        # False so the handler will not flip org.tier — lifecycle worker
        # reverts after current_period_end.
        assert should_apply_tier(sub["status"]) is False
        assert resolve_tier(sub) == "clinic_standard"
