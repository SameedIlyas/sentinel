"""End-to-end subscription cancellation lifecycle (review H2).

Closes the gap between the webhook (Phase 3) and the lifecycle service
test (Phase 2): a regression where the webhook accidentally reverts tier
AND the lifecycle job is a no-op would let both tests pass in isolation
but ship a bug. This test exercises the handoff explicitly.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from freezegun import freeze_time

from policy_engine.models.organization import (
    TIER_CLINIC_STANDARD,
    TIER_ENTERPRISE,
)
from policy_engine.services import subscription_lifecycle
from tests.factories.billing import serialize_and_sign, subscription_deleted
from tests.factories.clinic import make_clinic_org


pytestmark = pytest.mark.billing


def test_e2e_cancellation_then_revert(client, db_session, monkeypatch) -> None:
    secret = os.environ["STRIPE_WEBHOOK_SECRET"]

    with freeze_time("2026-05-10T00:00:00Z"):
        org = make_clinic_org(
            db_session,
            tier=TIER_CLINIC_STANDARD,
            slug="e2e-cancel-clinic",
            stripe_customer_id="cus_e2e",
            subscription_status="active",
        )
        period_end = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp())
        evt = subscription_deleted(customer="cus_e2e", current_period_end=period_end)
        body, sig = serialize_and_sign(evt, secret=secret)
        resp = client.post(
            "/v1/billing/clinic/webhook",
            content=body,
            headers={"Content-Type": "application/json", "Stripe-Signature": sig},
        )
        assert resp.status_code == 200
        db_session.refresh(org)
        # Inside the paid period — tier preserved.
        assert org.tier == TIER_CLINIC_STANDARD
        billing = (org.settings or {}).get("billing") or {}
        assert billing["subscription_status"] == "canceled"

    # Advance the clock past period_end and run the lifecycle sweep.
    monkeypatch.setattr(subscription_lifecycle, "SessionLocal", lambda: db_session)
    db_session.close = lambda: None  # keep fixture session alive

    with freeze_time("2026-06-15T00:00:00Z"):  # > 30 days later
        n = subscription_lifecycle.revert_expired_canceled_orgs()
        assert n == 1
        db_session.refresh(org)
        assert org.tier == TIER_ENTERPRISE
        billing = (org.settings or {}).get("billing") or {}
        assert billing["plan"] == TIER_ENTERPRISE
        assert billing["previous_tier"] == TIER_CLINIC_STANDARD


def test_e2e_no_revert_inside_grace_window(client, db_session, monkeypatch) -> None:
    """Webhook arrives, but lifecycle job runs while still inside paid period:
    must NOT revert."""
    secret = os.environ["STRIPE_WEBHOOK_SECRET"]
    with freeze_time("2026-05-10T00:00:00Z"):
        org = make_clinic_org(
            db_session,
            tier=TIER_CLINIC_STANDARD,
            slug="e2e-grace-clinic",
            stripe_customer_id="cus_grace",
            subscription_status="active",
        )
        period_end = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp())
        evt = subscription_deleted(customer="cus_grace", current_period_end=period_end)
        body, sig = serialize_and_sign(evt, secret=secret)
        client.post(
            "/v1/billing/clinic/webhook",
            content=body,
            headers={"Content-Type": "application/json", "Stripe-Signature": sig},
        )

    monkeypatch.setattr(subscription_lifecycle, "SessionLocal", lambda: db_session)
    db_session.close = lambda: None

    with freeze_time("2026-05-15T00:00:00Z"):  # only 5 days later
        n = subscription_lifecycle.revert_expired_canceled_orgs()
        assert n == 0
        db_session.refresh(org)
        assert org.tier == TIER_CLINIC_STANDARD
