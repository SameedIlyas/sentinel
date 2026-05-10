"""PLANS table — single source of truth for tier metadata.

Mirrors the data shape proposed in ``BILLING_IMPLEMENTATION.md`` §4 so that
when the full billing system lands the clinic SKUs slot in without a schema
or symbol migration.  Only clinic plans + a placeholder enterprise entry
are defined here today; Starter / Pro / Enterprise SKUs will be added when
the hospital billing surface is built.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal

from policy_engine.models.organization import (
    TIER_ENTERPRISE,
    TIER_CLINIC_BASIC,
    TIER_CLINIC_STANDARD,
    TIER_CLINIC_MULTI_SITE,
)

PlanName = Literal[
    "enterprise",
    "clinic_basic",
    "clinic_standard",
    "clinic_multi_site",
]

CLINIC_PLAN_NAMES: tuple[PlanName, ...] = (
    TIER_CLINIC_BASIC,
    TIER_CLINIC_STANDARD,
    TIER_CLINIC_MULTI_SITE,
)


# Module key sets — keep names in sync with `dashboard/src/i18n/dict/*` so
# the navigation predicate and the backend gate share one vocabulary.
CLINIC_BASIC_MODULES = frozenset({"clinic_core", "clinic_tools", "clinic_alerts"})
CLINIC_STANDARD_MODULES = CLINIC_BASIC_MODULES | {
    "clinic_policy_templates",
    "clinic_shadow_lite",
    "clinic_reports",
}
CLINIC_MULTI_SITE_MODULES = CLINIC_STANDARD_MODULES | {
    "clinic_multi_location",
    "clinic_role_management",
}
ENTERPRISE_MODULES = frozenset(
    {
        "core",
        "clinical",
        "risk",
        "admin_governance",
        "financial",
        "regulatory",
        "settings_advanced",
    }
)


@dataclass(frozen=True)
class Plan:
    name: PlanName
    display_name: str
    monthly_price_usd: int  # 0 = custom / enterprise sales-led
    tool_cap: int
    seat_cap: int
    audit_retention_days: int
    modules: frozenset[str]
    baa_mode: str  # "click_through" | "executed_bundled" | "negotiated"
    stripe_payment_link_env: str | None = None
    stripe_price_id_monthly: str | None = None  # forward-compat with full billing
    description: str = ""
    locations_cap: int = 1


PLANS: dict[PlanName, Plan] = {
    "enterprise": Plan(
        name="enterprise",
        display_name="Enterprise",
        monthly_price_usd=0,  # custom — sales-led, see PRICING.md
        tool_cap=10**9,
        seat_cap=10**9,
        audit_retention_days=2190,  # 6 years
        modules=ENTERPRISE_MODULES,
        baa_mode="negotiated",
        description="Hospital / health-system tier (Starter / Pro / Enterprise SKUs).",
        locations_cap=10**9,
    ),
    TIER_CLINIC_BASIC: Plan(
        name=TIER_CLINIC_BASIC,
        display_name="Clinic Basic",
        monthly_price_usd=199,
        tool_cap=10,
        seat_cap=5,
        audit_retention_days=365,
        modules=CLINIC_BASIC_MODULES,
        baa_mode="click_through",
        stripe_payment_link_env="STRIPE_PAYMENT_LINK_CLINIC_BASIC",
        description="Single-clinic, click-through BAA, 5 seats, 10 tools, 1-year retention.",
        locations_cap=1,
    ),
    TIER_CLINIC_STANDARD: Plan(
        name=TIER_CLINIC_STANDARD,
        display_name="Clinic Standard",
        monthly_price_usd=349,
        tool_cap=25,
        seat_cap=15,
        audit_retention_days=1095,  # 3 years
        modules=CLINIC_STANDARD_MODULES,
        baa_mode="executed_bundled",
        stripe_payment_link_env="STRIPE_PAYMENT_LINK_CLINIC_STANDARD",
        description="Single-location practice, executed BAA, 15 seats, 25 tools, 3-year retention.",
        locations_cap=1,
    ),
    TIER_CLINIC_MULTI_SITE: Plan(
        name=TIER_CLINIC_MULTI_SITE,
        display_name="Clinic Multi-Site",
        monthly_price_usd=699,
        tool_cap=75,
        seat_cap=40,
        audit_retention_days=2190,  # 6 years
        modules=CLINIC_MULTI_SITE_MODULES,
        baa_mode="executed_bundled",
        stripe_payment_link_env="STRIPE_PAYMENT_LINK_CLINIC_MULTI_SITE",
        description="Up to 5 locations, executed BAA, 40 seats, 75 tools, HIPAA-grade retention.",
        locations_cap=5,
    ),
}


def get_plan(plan_name: str | None) -> Plan:
    """Return the Plan for a tier name, defaulting to enterprise for unknown values."""
    if plan_name is None:
        return PLANS["enterprise"]
    return PLANS.get(plan_name, PLANS["enterprise"])


def is_clinic_plan(plan_name: str | None) -> bool:
    return plan_name in CLINIC_PLAN_NAMES


def stripe_payment_link(plan_name: str) -> str | None:
    """Resolve the Stripe Payment Link URL for a clinic plan.

    Returns None for enterprise (sales-led) or when the env var is unset.
    """
    plan = PLANS.get(plan_name)
    if plan is None or plan.stripe_payment_link_env is None:
        return None
    return os.environ.get(plan.stripe_payment_link_env)
