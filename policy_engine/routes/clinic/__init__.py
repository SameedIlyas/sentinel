"""Clinic-tier route handlers.

Every route under ``/v1/clinic/*`` is gated to ``Organization.tier in
CLINIC_TIERS`` via ``services.tier_filter.require_clinic_tier``.  Enterprise
users get a 403 — the existing hospital surface is untouched.
"""
