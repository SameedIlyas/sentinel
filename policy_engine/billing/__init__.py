"""Billing surface — single source of truth for tier metadata.

Currently scoped to the clinic-tier stub-billing path.  Designed so that the
full Stripe / plan-gating surface in ``BILLING_IMPLEMENTATION.md`` lands as
a strict superset of the symbols here — no migration of clinic SKUs needed
when real billing ships.
"""

from policy_engine.billing.plans import (
    PLANS,
    Plan,
    PlanName,
    get_plan,
    is_clinic_plan,
    CLINIC_PLAN_NAMES,
)
from policy_engine.billing.stripe_client import (
    StripeUnavailable,
    get_stripe,
    secret_key,
    webhook_secret,
    billing_portal_return_url,
)

__all__ = [
    "PLANS",
    "Plan",
    "PlanName",
    "get_plan",
    "is_clinic_plan",
    "CLINIC_PLAN_NAMES",
    "StripeUnavailable",
    "get_stripe",
    "secret_key",
    "webhook_secret",
    "billing_portal_return_url",
]
