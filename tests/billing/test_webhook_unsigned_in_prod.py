"""Production fail-closed — unsigned webhooks rejected when APP_ENV=production.

Caveat from the v2 plan: only ``_is_production_env()`` reads
``os.environ`` directly, so env monkeypatch is sufficient. Other code
paths gated on ``settings.APP_ENV`` may be cached via Pydantic's
``Settings`` and would need explicit cache invalidation. Pinning the
behavior here so future settings-cached gates don't drift.
"""

from __future__ import annotations

import os

import pytest

from tests.factories.billing import serialize_and_sign, subscription_updated


pytestmark = pytest.mark.billing


def test_unsigned_webhook_rejected_in_production(client, monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    body, _ = serialize_and_sign(
        subscription_updated(), secret="whsec_irrelevant_will_be_ignored"
    )
    resp = client.post(
        "/v1/billing/clinic/webhook",
        content=body,
        headers={"Content-Type": "application/json"},  # no Stripe-Signature
    )
    assert resp.status_code == 400


def test_signed_webhook_with_no_secret_in_production_still_rejected(
    client, monkeypatch
) -> None:
    """Even WITH a Stripe-Signature header, no configured webhook secret in
    production must fail-closed (a misplaced rotation cannot become a
    tier-flip vector)."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    body, sig = serialize_and_sign(subscription_updated(), secret="whsec_anything")
    resp = client.post(
        "/v1/billing/clinic/webhook",
        content=body,
        headers={"Content-Type": "application/json", "Stripe-Signature": sig},
    )
    assert resp.status_code == 400
