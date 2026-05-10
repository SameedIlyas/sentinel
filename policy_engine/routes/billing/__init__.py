"""Billing surface — clinic-tier stub today, full Stripe surface later.

See ``BILLING_IMPLEMENTATION.md`` for the full design.  Today this module
ships only the minimum needed for clinic SKUs:

* ``GET  /v1/billing/clinic/payment-link?plan=clinic_basic`` — returns the
  pre-configured Stripe Payment Link URL.
* ``POST /v1/billing/clinic/webhook`` — minimal webhook that flips
  ``Organization.tier`` on ``checkout.session.completed`` and writes a
  ``billing_events`` row.

The webhook signature shape is forward-compatible with the full handler
in ``BILLING_IMPLEMENTATION.md`` §5.2 — when the real billing system
ships, this handler is replaced, not migrated.
"""
