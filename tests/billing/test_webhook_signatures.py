"""Webhook signature verification — production fail-closed branch.

Strategy: sign every fixture with the .env.test STRIPE_WEBHOOK_SECRET so
the production code path runs as it does in prod. Then test the negative
shapes: missing header, tampered body, wrong secret.
"""

from __future__ import annotations

import os

import pytest

from tests.factories.billing import serialize_and_sign, subscription_updated


pytestmark = pytest.mark.billing


def _post_webhook(client, body: bytes, headers: dict) -> None:
    return client.post(
        "/v1/billing/clinic/webhook",
        content=body,
        headers={"Content-Type": "application/json", **headers},
    )


def test_valid_signature_processes(client) -> None:
    secret = os.environ["STRIPE_WEBHOOK_SECRET"]
    evt = subscription_updated(customer="cus_no_org", status="active")
    body, sig = serialize_and_sign(evt, secret=secret)
    resp = _post_webhook(client, body, {"Stripe-Signature": sig})
    # 200 expected — no org matches cus_no_org so handler returns 'skipped'
    # but the signature passed.
    assert resp.status_code == 200, resp.text


def test_missing_signature_400(client) -> None:
    secret = os.environ["STRIPE_WEBHOOK_SECRET"]
    evt = subscription_updated()
    body, _sig = serialize_and_sign(evt, secret=secret)
    resp = _post_webhook(client, body, {})  # no Stripe-Signature
    assert resp.status_code == 400
    assert "Invalid signature" in resp.text


def test_tampered_body_400(client) -> None:
    secret = os.environ["STRIPE_WEBHOOK_SECRET"]
    evt = subscription_updated()
    body, sig = serialize_and_sign(evt, secret=secret)
    # Tamper the body AFTER signing — signature no longer matches.
    tampered = body.replace(b'"active"', b'"trialing"')
    resp = _post_webhook(client, tampered, {"Stripe-Signature": sig})
    assert resp.status_code == 400


def test_wrong_secret_400(client) -> None:
    """Signing with a secret that doesn't match the configured one → 400."""
    evt = subscription_updated()
    body, sig = serialize_and_sign(evt, secret="whsec_completely_different_secret")
    resp = _post_webhook(client, body, {"Stripe-Signature": sig})
    assert resp.status_code == 400


def test_malformed_signature_header_400(client) -> None:
    evt = subscription_updated()
    body, _sig = serialize_and_sign(evt, secret=os.environ["STRIPE_WEBHOOK_SECRET"])
    resp = _post_webhook(client, body, {"Stripe-Signature": "garbage_not_a_sig"})
    assert resp.status_code == 400
