"""Thin Stripe SDK wrapper.

The SDK's global ``stripe.api_key`` is a process-wide setting.  We init
it lazily so importing this module is cheap, and we re-check the env on
every call so a deploy-time secret rotation does not require a restart.

If the SDK is missing (e.g., in CI without billing deps installed),
``get_stripe()`` raises ``StripeUnavailable`` which the calling routes
translate into a 503.  The clinic webhook signature path tolerates the
missing import on its own — see ``routes/billing/clinic.py``.
"""

from __future__ import annotations

import os
from typing import Any


class StripeUnavailable(RuntimeError):
    """Raised when the Stripe SDK or API key is not configured."""


def secret_key() -> str | None:
    return os.environ.get("STRIPE_SECRET_KEY")


def webhook_secret() -> str | None:
    return os.environ.get("STRIPE_WEBHOOK_SECRET")


def billing_portal_return_url() -> str:
    return os.environ.get(
        "STRIPE_BILLING_PORTAL_RETURN_URL",
        "http://localhost:5173/clinic/settings/billing",
    )


def get_stripe() -> Any:
    """Return the configured ``stripe`` module or raise ``StripeUnavailable``."""
    try:
        import stripe  # type: ignore
    except ImportError as exc:  # pragma: no cover — surfaced as 503
        raise StripeUnavailable(
            "stripe SDK not installed. Add 'stripe' to requirements.txt."
        ) from exc

    key = secret_key()
    if not key:
        raise StripeUnavailable(
            "STRIPE_SECRET_KEY is not set. Configure it in the policy "
            "engine's environment to enable billing."
        )
    # Re-set every call so rotated secrets take effect without restart.
    stripe.api_key = key
    return stripe
