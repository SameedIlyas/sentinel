"""Tests for ``policy_engine.billing.stripe_client``."""

from __future__ import annotations

import pytest

from policy_engine.billing.stripe_client import (
    StripeUnavailable,
    billing_portal_return_url,
    get_stripe,
    secret_key,
    webhook_secret,
)


pytestmark = pytest.mark.billing


def test_secret_key_reads_env(monkeypatch) -> None:
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_xyz")
    assert secret_key() == "sk_test_xyz"
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    assert secret_key() is None


def test_webhook_secret_reads_env(monkeypatch) -> None:
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_xyz")
    assert webhook_secret() == "whsec_xyz"
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    assert webhook_secret() is None


def test_billing_portal_return_url_default(monkeypatch) -> None:
    monkeypatch.delenv("STRIPE_BILLING_PORTAL_RETURN_URL", raising=False)
    url = billing_portal_return_url()
    assert "/clinic/settings/billing" in url


def test_billing_portal_return_url_env_override(monkeypatch) -> None:
    monkeypatch.setenv("STRIPE_BILLING_PORTAL_RETURN_URL", "https://app.example.test/back")
    assert billing_portal_return_url() == "https://app.example.test/back"


def test_get_stripe_raises_when_secret_missing(monkeypatch) -> None:
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    with pytest.raises(StripeUnavailable):
        get_stripe()


def test_get_stripe_returns_module_when_configured(monkeypatch) -> None:
    """Stripe SDK is installed (via Phase 1 deps); module returns and api_key is set."""
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_loaded_for_test_only")
    mod = get_stripe()
    assert mod is not None
    assert mod.api_key == "sk_test_loaded_for_test_only"


def test_get_stripe_re_reads_env_each_call(monkeypatch) -> None:
    """Rotated secrets take effect without restart."""
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_v1")
    mod1 = get_stripe()
    assert mod1.api_key == "sk_v1"
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_v2")
    mod2 = get_stripe()
    assert mod2.api_key == "sk_v2"
