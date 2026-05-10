"""Tests for ``policy_engine.services.subscription_lifecycle``.

Verifies the canceled-but-paid-period preservation and idempotent revert
behavior. Uses freezegun for deterministic clock control.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from freezegun import freeze_time

from policy_engine.models.organization import (
    Organization,
    TIER_CLINIC_STANDARD,
    TIER_ENTERPRISE,
)
from policy_engine.services import subscription_lifecycle

from tests.factories.clinic import make_clinic_org


pytestmark = pytest.mark.clinic


def _set_billing(db_session, org: Organization, **billing_fields) -> None:
    settings = dict(org.settings or {})
    billing = dict(settings.get("billing") or {})
    billing.update(billing_fields)
    settings["billing"] = billing
    org.settings = settings
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(org, "settings")
    db_session.commit()


@freeze_time("2026-05-10T00:00:00Z")
def test_revert_skips_active_subscriptions(db_session, monkeypatch) -> None:
    org = make_clinic_org(db_session, tier=TIER_CLINIC_STANDARD)
    _set_billing(db_session, org, subscription_status="active",
                 current_period_end=datetime.now(timezone.utc).timestamp() + 86400)

    monkeypatch.setattr(subscription_lifecycle, "SessionLocal", lambda: db_session)
    # Override SessionLocal so the function uses our test session, but
    # also override db.close() to no-op so our fixture session survives.
    original_close = db_session.close
    db_session.close = lambda: None
    try:
        n = subscription_lifecycle.revert_expired_canceled_orgs()
    finally:
        db_session.close = original_close

    assert n == 0
    db_session.refresh(org)
    assert org.tier == TIER_CLINIC_STANDARD


@freeze_time("2026-05-10T00:00:00Z")
def test_revert_preserves_canceled_within_grace_period(db_session, monkeypatch) -> None:
    """current_period_end in the future → tier preserved, no revert."""
    org = make_clinic_org(db_session, tier=TIER_CLINIC_STANDARD)
    future = datetime.now(timezone.utc) + timedelta(days=15)
    _set_billing(db_session, org, subscription_status="canceled",
                 current_period_end=future.timestamp())

    monkeypatch.setattr(subscription_lifecycle, "SessionLocal", lambda: db_session)
    original_close = db_session.close
    db_session.close = lambda: None
    try:
        n = subscription_lifecycle.revert_expired_canceled_orgs()
    finally:
        db_session.close = original_close

    assert n == 0
    db_session.refresh(org)
    assert org.tier == TIER_CLINIC_STANDARD


@freeze_time("2026-05-10T00:00:00Z")
def test_revert_flips_canceled_after_period_end(db_session, monkeypatch) -> None:
    """current_period_end in the past → tier reverts to enterprise."""
    org = make_clinic_org(db_session, tier=TIER_CLINIC_STANDARD)
    past = datetime.now(timezone.utc) - timedelta(days=1)
    _set_billing(db_session, org, subscription_status="canceled",
                 current_period_end=past.timestamp(), plan=TIER_CLINIC_STANDARD)

    monkeypatch.setattr(subscription_lifecycle, "SessionLocal", lambda: db_session)
    original_close = db_session.close
    db_session.close = lambda: None
    try:
        n = subscription_lifecycle.revert_expired_canceled_orgs()
    finally:
        db_session.close = original_close

    assert n == 1
    db_session.refresh(org)
    assert org.tier == TIER_ENTERPRISE
    billing = (org.settings or {}).get("billing") or {}
    assert billing["plan"] == TIER_ENTERPRISE
    assert billing["previous_tier"] == TIER_CLINIC_STANDARD
    assert billing["reverted_at"]


@freeze_time("2026-05-10T00:00:00Z")
def test_revert_is_idempotent(db_session, monkeypatch) -> None:
    """A second pass over an already-reverted org reverts nothing more."""
    org = make_clinic_org(db_session, tier=TIER_CLINIC_STANDARD)
    past = datetime.now(timezone.utc) - timedelta(days=1)
    _set_billing(db_session, org, subscription_status="canceled",
                 current_period_end=past.timestamp(), plan=TIER_CLINIC_STANDARD)

    monkeypatch.setattr(subscription_lifecycle, "SessionLocal", lambda: db_session)
    original_close = db_session.close
    db_session.close = lambda: None
    try:
        first = subscription_lifecycle.revert_expired_canceled_orgs()
        second = subscription_lifecycle.revert_expired_canceled_orgs()
    finally:
        db_session.close = original_close

    assert first == 1
    assert second == 0


@freeze_time("2026-05-10T00:00:00Z")
def test_revert_handles_iso_string_period_end(db_session, monkeypatch) -> None:
    """current_period_end can be an ISO string (legacy shape) — must parse."""
    org = make_clinic_org(db_session, tier=TIER_CLINIC_STANDARD)
    past = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat() + "Z"
    _set_billing(db_session, org, subscription_status="canceled",
                 current_period_end=past)

    monkeypatch.setattr(subscription_lifecycle, "SessionLocal", lambda: db_session)
    original_close = db_session.close
    db_session.close = lambda: None
    try:
        n = subscription_lifecycle.revert_expired_canceled_orgs()
    finally:
        db_session.close = original_close

    assert n == 1


@freeze_time("2026-05-10T00:00:00Z")
def test_revert_defensive_no_period_end(db_session, monkeypatch) -> None:
    """Canceled with no current_period_end → revert immediately (defensive)."""
    org = make_clinic_org(db_session, tier=TIER_CLINIC_STANDARD)
    _set_billing(db_session, org, subscription_status="canceled")  # no period_end

    monkeypatch.setattr(subscription_lifecycle, "SessionLocal", lambda: db_session)
    original_close = db_session.close
    db_session.close = lambda: None
    try:
        n = subscription_lifecycle.revert_expired_canceled_orgs()
    finally:
        db_session.close = original_close

    assert n == 1
    db_session.refresh(org)
    assert org.tier == TIER_ENTERPRISE


def test_is_enabled_reads_env(monkeypatch) -> None:
    monkeypatch.setenv("CLINIC_LIFECYCLE_AUTO", "false")
    assert subscription_lifecycle.is_enabled() is False
    monkeypatch.setenv("CLINIC_LIFECYCLE_AUTO", "true")
    assert subscription_lifecycle.is_enabled() is True
    monkeypatch.delenv("CLINIC_LIFECYCLE_AUTO", raising=False)
    assert subscription_lifecycle.is_enabled() is True  # default true
