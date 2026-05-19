"""Pure tier-resolution helpers for Stripe subscription events (CRIT-006).

Historically only ``checkout.session.completed`` set ``org.tier``, so a
customer who created their subscription via the Stripe Customer Portal
(which fires ``customer.subscription.created`` / ``customer.subscription.updated``
but no checkout event) ended up on the wrong tier — typically left at
``enterprise`` regardless of what they paid for.

This module exposes a pure ``resolve_tier(subscription_dict)`` that
inspects the ``plan.metadata.tier`` / ``product.metadata.tier`` / item
``price.metadata.tier`` / plan-level ``nickname`` chain and returns a
canonical clinic tier when it can. It is independent of the Stripe SDK
so unit tests can exercise it with fixture dicts.

The resolver intentionally returns ``None`` for ambiguous or
non-clinic plans rather than guessing — the caller decides what to do
on a miss (typically: leave tier alone, log a warning).
"""
from __future__ import annotations

from typing import Optional

from policy_engine.billing.plans import CLINIC_PLAN_NAMES, is_clinic_plan


# Accept fields that Stripe and our own internal tooling have used at
# various points to convey the tier intent.
_TIER_METADATA_KEYS = ("tier", "plan", "sku")


def _coerce_tier(value: object) -> Optional[str]:
    """Return ``value`` only if it is a known clinic tier."""
    if not isinstance(value, str):
        return None
    if is_clinic_plan(value):
        return value
    return None


def _scan_metadata(blob: object) -> Optional[str]:
    """Look for a tier in any ``{tier, plan, sku}`` key of a metadata dict."""
    if not isinstance(blob, dict):
        return None
    for k in _TIER_METADATA_KEYS:
        tier = _coerce_tier(blob.get(k))
        if tier is not None:
            return tier
    return None


def resolve_tier(subscription: object) -> Optional[str]:
    """Resolve the clinic tier that this Stripe subscription represents.

    Inspection order (first hit wins):

    1. ``subscription.metadata.tier``
    2. ``subscription.items.data[0].price.metadata.tier``
    3. ``subscription.items.data[0].plan.metadata.tier``
    4. ``subscription.items.data[0].plan.product.metadata.tier``
    5. ``subscription.plan.metadata.tier`` (legacy single-plan shape)
    6. ``subscription.plan.nickname`` (used by internally-managed plans
       that don't set metadata but do use a canonical nickname)

    Returns ``None`` if none of the above yields a known clinic tier.
    Production callers should leave ``org.tier`` untouched on ``None``
    rather than guess.
    """
    if not isinstance(subscription, dict):
        return None

    # 1. Top-level metadata
    tier = _scan_metadata(subscription.get("metadata"))
    if tier is not None:
        return tier

    # 2-4. items[0].{price, plan, plan.product}.metadata
    items = subscription.get("items") or {}
    data = items.get("data") if isinstance(items, dict) else None
    first = data[0] if isinstance(data, list) and data else None
    if isinstance(first, dict):
        for path in (
            ("price", "metadata"),
            ("plan", "metadata"),
        ):
            node: object = first
            for step in path:
                if not isinstance(node, dict):
                    node = None
                    break
                node = node.get(step)
            tier = _scan_metadata(node)
            if tier is not None:
                return tier
        plan_obj = first.get("plan") if isinstance(first, dict) else None
        if isinstance(plan_obj, dict):
            product = plan_obj.get("product")
            if isinstance(product, dict):
                tier = _scan_metadata(product.get("metadata"))
                if tier is not None:
                    return tier

    # 5. Legacy single-plan shape
    plan = subscription.get("plan")
    if isinstance(plan, dict):
        tier = _scan_metadata(plan.get("metadata"))
        if tier is not None:
            return tier
        nickname = plan.get("nickname")
        tier = _coerce_tier(nickname)
        if tier is not None:
            return tier

    return None


# Statuses where it is safe to apply tier transitions. ``canceled``,
# ``unpaid``, ``incomplete``, ``incomplete_expired`` deliberately fall
# out — those are handled by the existing subscription-lifecycle path
# which reverts tier after the current period.
TIER_ACTIVE_STATUSES = frozenset({"active", "trialing"})


def should_apply_tier(status: object) -> bool:
    """True if a ``status`` value warrants applying a fresh tier."""
    return isinstance(status, str) and status in TIER_ACTIVE_STATUSES


__all__ = (
    "CLINIC_PLAN_NAMES",
    "TIER_ACTIVE_STATUSES",
    "resolve_tier",
    "should_apply_tier",
)
