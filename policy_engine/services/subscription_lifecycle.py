"""Subscription-lifecycle housekeeping.

The clinic billing surface flips ``Organization.tier`` on
``checkout.session.completed`` but *does not* immediately revert tier on
``customer.subscription.deleted`` — customers keep read access until
their paid period ends (per BILLING_IMPLEMENTATION.md §11 risks).

This module owns the scheduled job that walks the canceled-subscription
fleet daily and reverts tier to ``enterprise`` once
``current_period_end`` has passed.

Past-due handling is *not* lockout in v1: we only set the
``subscription_status`` so the dashboard can render a banner.  Hard
write-revoke arrives with the full ``BILLING_IMPLEMENTATION.md`` §11
grace-period logic.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy.orm.attributes import flag_modified

from policy_engine.database import SessionLocal
from policy_engine.models.organization import (
    Organization,
    TIER_ENTERPRISE,
    is_clinic_tier,
)

logger = logging.getLogger(__name__)


def _to_aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _parse_period_end(billing: dict) -> datetime | None:
    """Read current_period_end out of the billing blob.

    Stripe gives epoch seconds; we may also have stored an ISO string.
    Tolerate both shapes.
    """
    raw = billing.get("current_period_end") or billing.get("cancel_at")
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return datetime.fromtimestamp(raw, tz=timezone.utc)
    if isinstance(raw, str):
        # Strip the trailing 'Z' if present.
        candidate = raw.rstrip("Z")
        try:
            return datetime.fromisoformat(candidate).replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    if isinstance(raw, datetime):
        return _to_aware(raw)
    return None


def revert_expired_canceled_orgs() -> int:
    """Walk canceled clinic subs and revert tier once the paid period ended.

    Returns the number of orgs reverted.  Idempotent — already-enterprise
    orgs are skipped.
    """
    now = datetime.now(timezone.utc)
    reverted = 0
    db = SessionLocal()
    try:
        clinics = (
            db.query(Organization)
            .filter(
                Organization.tier.in_(
                    ("clinic_basic", "clinic_standard", "clinic_multi_site")
                )
            )
            .all()
        )
        for org in clinics:
            billing = (org.settings or {}).get("billing") or {}
            sub_status = billing.get("subscription_status")
            if sub_status != "canceled":
                continue
            period_end = _parse_period_end(billing)
            if period_end is None:
                # Defensive: cancel without an end → revert immediately.
                logger.warning(
                    "Org %s canceled with no current_period_end — reverting now",
                    org.id,
                )
            elif period_end > now:
                continue  # still inside grace window

            # Revert tier; keep audit fields so the history is queryable.
            org.tier = TIER_ENTERPRISE
            settings = dict(org.settings or {})
            billing = dict(settings.get("billing") or {})
            billing["reverted_at"] = now.isoformat()
            billing["previous_tier"] = (
                billing.get("previous_tier") or billing.get("plan")
            )
            billing["plan"] = TIER_ENTERPRISE
            settings["billing"] = billing
            org.settings = settings
            flag_modified(org, "settings")
            org.updated_at = now.replace(tzinfo=None)
            reverted += 1
        if reverted:
            db.commit()
            logger.info("Reverted %d expired clinic subscriptions", reverted)
    finally:
        db.close()
    return reverted


def make_lifecycle_job():
    """Returns a callable for the scheduler."""
    def _job() -> None:
        try:
            revert_expired_canceled_orgs()
        except Exception:  # pragma: no cover — logged + scheduler retries
            logger.exception("Subscription lifecycle job failed")
    return _job


def is_enabled() -> bool:
    return os.environ.get("CLINIC_LIFECYCLE_AUTO", "true").lower() == "true"


def interval_seconds() -> float:
    return float(os.environ.get("CLINIC_LIFECYCLE_INTERVAL_SECONDS", 21600))  # 6h
