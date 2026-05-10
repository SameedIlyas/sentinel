"""GDPR Art. 5(c) data minimisation — the webhook persists redacted events.

Covers the FULL ``_REDACT_DETAIL_KEYS`` tuple
(address, phone, tax_ids, tax_exempt, tax_id_data) AND the in-place
mutation contract of ``_redact_event_for_audit``.
"""

from __future__ import annotations

import copy
import os

import pytest

from policy_engine.models.clinic import BillingEvent
from policy_engine.routes.billing.clinic import _redact_event_for_audit
from tests.factories.billing import serialize_and_sign, make_stripe_event


pytestmark = pytest.mark.billing


def _build_event_with_pii(event_id: str = "evt_redact_test") -> dict:
    return make_stripe_event(
        "checkout.session.completed",
        event_id=event_id,
        object_data={
            "id": "cs_test_redact",
            "customer": "cus_redact",
            "customer_email": "billing@example.test",
            "customer_details": {
                "email": "billing@example.test",
                "name": "Acme Health LLC",
                "address": {"line1": "1 Privacy Way", "city": "Foo"},
                "phone": "555-0001-2222",
                "tax_ids": [{"type": "us_ein", "value": "12-3456789"}],
                "tax_exempt": "exempt",
                "tax_id_data": [{"type": "us_ein", "value": "12-3456789"}],
            },
            "address": {"line1": "1 Privacy Way", "city": "Foo"},
            "phone": "555-0001-2222",
            "tax_ids": [{"type": "us_ein", "value": "12-3456789"}],
            "tax_exempt": "exempt",
            "tax_id_data": [{"type": "us_ein", "value": "12-3456789"}],
            "payment_method_details": {
                "type": "card",
                "card": {"last4": "4242", "fingerprint": "Xt5EWLLDS7FJjR1c"},
            },
            "metadata": {"org_slug": "no-such-org-skipped"},
        },
    )


def test_redact_drops_all_redact_keys(client, db_session) -> None:
    secret = os.environ["STRIPE_WEBHOOK_SECRET"]
    evt = _build_event_with_pii()
    body, sig = serialize_and_sign(evt, secret=secret)
    resp = client.post(
        "/v1/billing/clinic/webhook",
        content=body,
        headers={"Content-Type": "application/json", "Stripe-Signature": sig},
    )
    assert resp.status_code == 200

    row = (
        db_session.query(BillingEvent)
        .filter(BillingEvent.stripe_event_id == evt["id"])
        .one()
    )
    persisted = row.payload
    obj = persisted["data"]["object"]

    # Every redact key must be GONE in BOTH locations.
    for key in ("address", "phone", "tax_ids", "tax_exempt", "tax_id_data"):
        assert key not in obj, f"{key} not redacted at top level"
        assert key not in obj["customer_details"], f"{key} not redacted under customer_details"

    # Email + name are KEPT (used for org resolution / customer support).
    assert obj["customer_details"]["email"] == "billing@example.test"
    assert obj["customer_details"]["name"] == "Acme Health LLC"

    # Card details collapsed to {type: ...}.
    assert obj["payment_method_details"] == {"type": "card"}


def test_redact_event_for_audit_mutation_contract() -> None:
    """``_redact_event_for_audit`` mutates in place and returns the same dict.

    Pin the contract so a future refactor to "return a copy" surfaces as
    a test failure rather than silently double-redacting upstream callers.
    """
    evt = _build_event_with_pii()
    original = copy.deepcopy(evt)

    redacted = _redact_event_for_audit(evt)
    # Same identity (in-place mutation).
    assert redacted is evt
    # The original snapshot still has the PII (deepcopy isolation).
    assert "address" in original["data"]["object"]
    # The mutated event no longer has the PII.
    assert "address" not in evt["data"]["object"]
    assert "tax_exempt" not in evt["data"]["object"]
    assert "tax_id_data" not in evt["data"]["object"]
