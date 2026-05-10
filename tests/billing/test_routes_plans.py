"""Integration tests for /v1/billing/clinic/plans and /payment-link."""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.billing


def test_list_clinic_plans(client) -> None:
    resp = client.get("/v1/billing/clinic/plans")
    assert resp.status_code == 200
    body = resp.json()
    tiers = {p["tier"] for p in body}
    assert "clinic_basic" in tiers
    assert "clinic_standard" in tiers
    assert "clinic_multi_site" in tiers
    # Enterprise is sales-led and must NOT show up in the public plans list.
    assert "enterprise" not in tiers
    # Each plan has the canonical fields.
    for p in body:
        assert "monthly_price_usd" in p
        assert "display_name" in p
        assert "description" in p
        assert "payment_link_url" in p


def test_payment_link_for_known_plan(client) -> None:
    resp = client.get("/v1/billing/clinic/payment-link", params={"plan": "clinic_basic"})
    # .env.test has the payment link set, so should be 200.
    assert resp.status_code == 200
    body = resp.json()
    assert body["plan"] == "clinic_basic"
    assert body["url"].startswith("https://")


def test_payment_link_unknown_plan_400(client) -> None:
    resp = client.get("/v1/billing/clinic/payment-link", params={"plan": "starter"})
    assert resp.status_code == 400


def test_payment_link_503_when_env_unset(client, monkeypatch) -> None:
    """If the corresponding STRIPE_PAYMENT_LINK_* env is unset → 503."""
    monkeypatch.delenv("STRIPE_PAYMENT_LINK_CLINIC_BASIC", raising=False)
    resp = client.get("/v1/billing/clinic/payment-link", params={"plan": "clinic_basic"})
    assert resp.status_code == 503
