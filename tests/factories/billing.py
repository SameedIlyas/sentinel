"""Stripe webhook payload + signature helpers.

Mirrors the format Stripe sends so the production verification path
(``stripe.Webhook.construct_event``) parses our fixtures identically to
real webhooks. We sign every fixture so the negative path
(missing/incorrect signature) is exercisable too.

NEVER hit the real Stripe API in these helpers — pure local construction.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from typing import Any


def make_stripe_event(
    event_type: str,
    *,
    object_data: dict[str, Any] | None = None,
    event_id: str | None = None,
) -> dict[str, Any]:
    """Build a minimal Stripe event JSON shape.

    Callers pass ``object_data`` for the ``data.object`` payload that the
    real Stripe API would send (a Subscription, Invoice, CheckoutSession,
    etc.). Defaults are intentionally minimal — tests should override
    fields they assert on.
    """
    return {
        "id": event_id or f"evt_test_{uuid.uuid4().hex[:24]}",
        "object": "event",
        "api_version": "2024-04-10",
        "created": int(time.time()),
        "type": event_type,
        "livemode": False,
        "pending_webhooks": 0,
        "request": {"id": None, "idempotency_key": None},
        "data": {"object": object_data or {}},
    }


def sign_webhook_payload(
    body: bytes,
    secret: str,
    timestamp: int | None = None,
) -> str:
    """Produce a Stripe-Signature header value for ``body``.

    Stripe's signature scheme is HMAC-SHA256 over ``f"{timestamp}.{body}"``
    with the webhook secret. Output format: ``t=<ts>,v1=<sig>`` — exactly
    what ``stripe.Webhook.construct_event`` parses.
    """
    ts = timestamp if timestamp is not None else int(time.time())
    signed_payload = f"{ts}.{body.decode('utf-8') if isinstance(body, bytes) else body}"
    sig = hmac.new(
        secret.encode("utf-8"),
        signed_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"t={ts},v1={sig}"


def serialize_and_sign(
    event: dict[str, Any],
    secret: str,
    timestamp: int | None = None,
) -> tuple[bytes, str]:
    """Convenience: JSON-serialize and sign in one call. Returns (body, header)."""
    body = json.dumps(event, separators=(",", ":")).encode("utf-8")
    return body, sign_webhook_payload(body, secret, timestamp=timestamp)


# ── Common event-shape helpers (used across Phase 3 tests) ─────────────


def checkout_session_completed(
    *,
    customer: str = "cus_test_123",
    subscription: str = "sub_test_123",
    client_reference_id: str = "clinic_standard",
    org_slug: str | None = None,
    customer_email: str = "billing@example.test",
) -> dict[str, Any]:
    obj = {
        "id": f"cs_test_{uuid.uuid4().hex[:24]}",
        "object": "checkout.session",
        "customer": customer,
        "subscription": subscription,
        "client_reference_id": client_reference_id,
        "customer_email": customer_email,
        "customer_details": {"email": customer_email, "name": "Acme Health LLC"},
        "metadata": {"org_slug": org_slug} if org_slug else {},
        "payment_link": None,
    }
    return make_stripe_event("checkout.session.completed", object_data=obj)


def subscription_updated(
    *,
    customer: str = "cus_test_123",
    sub_id: str = "sub_test_123",
    status: str = "active",
    cancel_at_period_end: bool = False,
    current_period_end: int | None = None,
    cancel_at: int | None = None,
) -> dict[str, Any]:
    obj = {
        "id": sub_id,
        "object": "subscription",
        "customer": customer,
        "status": status,
        "cancel_at_period_end": cancel_at_period_end,
        "current_period_end": current_period_end,
        "cancel_at": cancel_at,
    }
    return make_stripe_event("customer.subscription.updated", object_data=obj)


def subscription_deleted(
    *,
    customer: str = "cus_test_123",
    sub_id: str = "sub_test_123",
    current_period_end: int | None = None,
) -> dict[str, Any]:
    obj = {
        "id": sub_id,
        "object": "subscription",
        "customer": customer,
        "status": "canceled",
        "current_period_end": current_period_end,
        "cancel_at": current_period_end,
        "canceled_at": int(time.time()),
    }
    return make_stripe_event("customer.subscription.deleted", object_data=obj)


def invoice_payment_failed(
    *,
    customer: str = "cus_test_123",
    invoice_id: str = "in_test_123",
) -> dict[str, Any]:
    obj = {"id": invoice_id, "object": "invoice", "customer": customer}
    return make_stripe_event("invoice.payment_failed", object_data=obj)


def invoice_payment_succeeded(
    *,
    customer: str = "cus_test_123",
    invoice_id: str = "in_test_123",
) -> dict[str, Any]:
    obj = {"id": invoice_id, "object": "invoice", "customer": customer}
    return make_stripe_event("invoice.payment_succeeded", object_data=obj)


__all__ = [
    "make_stripe_event",
    "sign_webhook_payload",
    "serialize_and_sign",
    "checkout_session_completed",
    "subscription_updated",
    "subscription_deleted",
    "invoice_payment_failed",
    "invoice_payment_succeeded",
]
