"""Per-event-handler payload assertions for /v1/billing/clinic/webhook."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest

from policy_engine.models.clinic import BillingEvent
from policy_engine.models.organization import (
    TIER_CLINIC_STANDARD,
    TIER_ENTERPRISE,
)
from tests.factories.billing import (
    checkout_session_completed,
    invoice_payment_failed,
    invoice_payment_succeeded,
    serialize_and_sign,
    subscription_deleted,
    subscription_updated,
)
from tests.factories.clinic import make_clinic_org


pytestmark = pytest.mark.billing


def _post(client, evt: dict) -> None:
    secret = os.environ["STRIPE_WEBHOOK_SECRET"]
    body, sig = serialize_and_sign(evt, secret=secret)
    return client.post(
        "/v1/billing/clinic/webhook",
        content=body,
        headers={"Content-Type": "application/json", "Stripe-Signature": sig},
    )


# ── checkout.session.completed ─────────────────────────────────────────


def test_checkout_completed_flips_tier_and_records_customer(client, db_session) -> None:
    org = make_clinic_org(
        db_session, tier=TIER_ENTERPRISE, baa_signed=False, slug="up-clinic"
    )
    evt = checkout_session_completed(
        customer="cus_test_chk1",
        subscription="sub_test_chk1",
        client_reference_id="clinic_standard",
        org_slug="up-clinic",
    )
    resp = _post(client, evt)
    assert resp.status_code == 200
    db_session.refresh(org)
    assert org.tier == "clinic_standard"
    billing = (org.settings or {}).get("billing") or {}
    assert billing["stripe_customer_id"] == "cus_test_chk1"
    assert billing["stripe_subscription_id"] == "sub_test_chk1"
    assert billing["subscription_status"] == "active"


def test_checkout_completed_skipped_when_no_org_match(client, db_session) -> None:
    """If org_slug missing AND no org has that customer id → skipped."""
    evt = checkout_session_completed(customer="cus_orphan_xyz")
    resp = _post(client, evt)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "skipped"


# ── customer.subscription.updated ──────────────────────────────────────


def test_subscription_updated_past_due(client, db_session) -> None:
    org = make_clinic_org(
        db_session, tier=TIER_CLINIC_STANDARD, slug="pastdue-clinic",
        stripe_customer_id="cus_pastdue", subscription_status="active"
    )
    evt = subscription_updated(customer="cus_pastdue", status="past_due")
    resp = _post(client, evt)
    assert resp.status_code == 200
    db_session.refresh(org)
    billing = (org.settings or {}).get("billing") or {}
    assert billing["subscription_status"] == "past_due"
    # Tier is NOT reverted on past_due (per BILLING_IMPLEMENTATION.md §11).
    assert org.tier == TIER_CLINIC_STANDARD


# ── customer.subscription.deleted ──────────────────────────────────────


def test_subscription_deleted_preserves_tier(client, db_session) -> None:
    """Cancellation marks status, but tier is preserved until period_end
    (the lifecycle job reverts after that — verified in services tests)."""
    org = make_clinic_org(
        db_session, tier=TIER_CLINIC_STANDARD, slug="canc-clinic",
        stripe_customer_id="cus_canc", subscription_status="active"
    )
    period_end_epoch = int((datetime.now(timezone.utc) + timedelta(days=15)).timestamp())
    evt = subscription_deleted(customer="cus_canc", current_period_end=period_end_epoch)
    resp = _post(client, evt)
    assert resp.status_code == 200
    db_session.refresh(org)
    billing = (org.settings or {}).get("billing") or {}
    assert billing["subscription_status"] == "canceled"
    assert billing["current_period_end"] == period_end_epoch
    # CRUCIAL: tier preserved during paid period.
    assert org.tier == TIER_CLINIC_STANDARD


# ── invoice.payment_failed / succeeded ─────────────────────────────────


def test_invoice_payment_failed_marks_past_due(client, db_session) -> None:
    org = make_clinic_org(
        db_session, tier=TIER_CLINIC_STANDARD, slug="invfail-clinic",
        stripe_customer_id="cus_invfail", subscription_status="active"
    )
    evt = invoice_payment_failed(customer="cus_invfail", invoice_id="in_v1")
    resp = _post(client, evt)
    assert resp.status_code == 200
    db_session.refresh(org)
    billing = (org.settings or {}).get("billing") or {}
    assert billing["subscription_status"] == "past_due"
    assert billing["last_failed_invoice_id"] == "in_v1"


def test_invoice_payment_succeeded_recovers_from_past_due(client, db_session) -> None:
    org = make_clinic_org(
        db_session, tier=TIER_CLINIC_STANDARD, slug="recover-clinic",
        stripe_customer_id="cus_recover", subscription_status="past_due"
    )
    evt = invoice_payment_succeeded(customer="cus_recover", invoice_id="in_recover")
    resp = _post(client, evt)
    assert resp.status_code == 200
    db_session.refresh(org)
    billing = (org.settings or {}).get("billing") or {}
    assert billing["subscription_status"] == "active"
    assert billing.get("last_failed_invoice_id") is None


# ── unhandled event types ──────────────────────────────────────────────


def test_unhandled_event_records_skipped(client, db_session) -> None:
    from tests.factories.billing import make_stripe_event
    evt = make_stripe_event("payout.created", object_data={"id": "po_test"})
    resp = _post(client, evt)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "skipped"
    # And we did persist a BillingEvent row for the audit trail.
    row = (
        db_session.query(BillingEvent)
        .filter(BillingEvent.stripe_event_id == evt["id"])
        .one()
    )
    assert row.event_type == "payout.created"
    assert row.status == "skipped"
