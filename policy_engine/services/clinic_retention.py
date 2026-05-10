"""GDPR Art. 5(e) storage-limitation sweep for clinic-tier data.

Every retention bound is configurable via env so a customer's BAA or
DPA can override defaults without a code change.

Tables swept:

* ``billing_events``           — audit of Stripe events.  Default 730d.
* ``clinic_ai_observations``   — extension detections.  Default per-tier
                                 (basic=365, standard=1095, multi=2190).
* ``clinic_report_artifacts``  — monthly PDF/HTML artifacts.  Default
                                 730d in storage, row stays for ledger
                                 purposes.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from policy_engine.database import SessionLocal
from policy_engine.models.clinic import (
    BillingEvent,
    ClinicAiObservation,
    ClinicReportArtifact,
)
from policy_engine.models.organization import (
    Organization,
    TIER_CLINIC_BASIC,
    TIER_CLINIC_STANDARD,
    TIER_CLINIC_MULTI_SITE,
)

logger = logging.getLogger(__name__)


def _env_int(key: str, default: int) -> int:
    raw = os.environ.get(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def billing_event_retention_days() -> int:
    return _env_int("CLINIC_BILLING_EVENT_RETENTION_DAYS", 730)


def report_artifact_retention_days() -> int:
    return _env_int("CLINIC_REPORT_RETENTION_DAYS", 730)


def observation_retention_for_tier(tier: str) -> int:
    if tier == TIER_CLINIC_BASIC:
        return _env_int("CLINIC_OBSERVATION_RETENTION_BASIC_DAYS", 365)
    if tier == TIER_CLINIC_STANDARD:
        return _env_int("CLINIC_OBSERVATION_RETENTION_STANDARD_DAYS", 1095)
    if tier == TIER_CLINIC_MULTI_SITE:
        return _env_int("CLINIC_OBSERVATION_RETENTION_MULTI_DAYS", 2190)
    return 365


def _sweep_billing_events(db: Session, now: datetime) -> int:
    cutoff = now - timedelta(days=billing_event_retention_days())
    deleted = (
        db.query(BillingEvent)
        .filter(BillingEvent.processed_at < cutoff)
        .delete(synchronize_session=False)
    )
    return deleted or 0


def _sweep_observations(db: Session, now: datetime) -> int:
    deleted_total = 0
    for org in db.query(Organization).filter(
        Organization.tier.in_(
            (TIER_CLINIC_BASIC, TIER_CLINIC_STANDARD, TIER_CLINIC_MULTI_SITE)
        )
    ):
        cutoff = now - timedelta(days=observation_retention_for_tier(org.tier))
        deleted = (
            db.query(ClinicAiObservation)
            .filter(
                ClinicAiObservation.org_id == org.id,
                ClinicAiObservation.observed_at < cutoff,
            )
            .delete(synchronize_session=False)
        )
        deleted_total += deleted or 0
    return deleted_total


def _sweep_report_artifacts(db: Session, now: datetime) -> int:
    cutoff = now - timedelta(days=report_artifact_retention_days())
    expired = (
        db.query(ClinicReportArtifact)
        .filter(ClinicReportArtifact.generated_at < cutoff)
        .all()
    )
    deleted = 0
    for artifact in expired:
        # Best-effort filesystem cleanup — never fail the sweep on a
        # missing file (it's already gone from a user's perspective).
        if artifact.storage_uri.startswith("file://"):
            path = Path(artifact.storage_uri[len("file://") :])
            try:
                if path.exists():
                    path.unlink()
            except OSError as exc:  # pragma: no cover — disk-level failure
                logger.warning(
                    "Could not delete expired report %s: %s", path, exc
                )
        db.delete(artifact)
        deleted += 1
    return deleted


def run_retention_sweep() -> dict[str, int]:
    """Single entry point used by the scheduler and ad-hoc admin scripts."""
    now = datetime.utcnow()
    db = SessionLocal()
    summary: dict[str, int] = {}
    try:
        summary["billing_events"] = _sweep_billing_events(db, now)
        summary["clinic_ai_observations"] = _sweep_observations(db, now)
        summary["clinic_report_artifacts"] = _sweep_report_artifacts(db, now)
        db.commit()
    except Exception:  # pragma: no cover — log + abort
        db.rollback()
        logger.exception("Retention sweep failed")
        raise
    finally:
        db.close()
    if any(summary.values()):
        logger.info("Clinic retention sweep deleted: %s", summary)
    return summary


def make_retention_job():
    def _job() -> None:
        try:
            run_retention_sweep()
        except Exception:  # pragma: no cover — handled in run_retention_sweep
            pass

    return _job


def is_enabled() -> bool:
    return os.environ.get("CLINIC_RETENTION_AUTO", "true").lower() == "true"


def interval_seconds() -> float:
    return float(os.environ.get("CLINIC_RETENTION_INTERVAL_SECONDS", 86400))
