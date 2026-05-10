"""Webhook idempotency — same Stripe event id arriving twice is a no-op."""

from __future__ import annotations

import os

import pytest

from policy_engine.models.clinic import BillingEvent
from tests.factories.billing import serialize_and_sign, subscription_updated


pytestmark = pytest.mark.billing


def test_duplicate_event_id_returns_skipped(client, db_session) -> None:
    secret = os.environ["STRIPE_WEBHOOK_SECRET"]
    evt = subscription_updated(customer="cus_no_org_yet", sub_id="sub_idem_test", status="active")
    body, sig = serialize_and_sign(evt, secret=secret)

    first = client.post(
        "/v1/billing/clinic/webhook",
        content=body,
        headers={"Content-Type": "application/json", "Stripe-Signature": sig},
    )
    assert first.status_code == 200

    second = client.post(
        "/v1/billing/clinic/webhook",
        content=body,
        headers={"Content-Type": "application/json", "Stripe-Signature": sig},
    )
    assert second.status_code == 200
    assert second.json()["status"] == "skipped"
    assert second.json()["reason"] == "duplicate"

    # Only one BillingEvent row was persisted.
    rows = (
        db_session.query(BillingEvent)
        .filter(BillingEvent.stripe_event_id == evt["id"])
        .all()
    )
    assert len(rows) == 1
