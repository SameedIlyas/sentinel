"""Scheduled PMS report generation.

Tier 2 Sprint 4 — auto-generates Post-Market Surveillance reports on the
regulatory cadences required by EU MDR (annual PSUR) and FDA MDR-equivalent
(quarterly aggregate). Reports are saved as `status=draft` so a compliance
officer reviews them before submission.

Job runs daily; on each pass:
  - For each organization, computes the *current* required-cadence period
    (Q1 2026, full year 2025, etc.).
  - Skips if a report for the same (org, report_type, period) already exists.
  - Otherwise generates a fresh draft report from adverse events in that
    period plus the existing post_market.aggregate_pms_metrics helper.
"""
from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, List, Optional, Tuple

from sqlalchemy.orm import Session

from policy_engine.database import SessionLocal
from policy_engine.domain.regulatory.post_market import (
    aggregate_pms_metrics,
    generate_psur_summary,
)
from policy_engine.models.organization import Organization
from policy_engine.models.post_market import (
    AdverseEvent,
    PMSMetric,
    PMSReport,
    PMSReportStatusDB,
    PMSReportTypeDB,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _env_flag(name: str, default: bool = False) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.lower() in ("1", "true", "yes", "on")


def is_enabled() -> bool:
    return _env_flag("PMS_AUTO_GENERATE", default=False)


def auto_interval_seconds() -> float:
    raw = os.environ.get("PMS_AUTO_GENERATE_INTERVAL_SECONDS", "86400")
    try:
        return max(3600.0, float(raw))
    except (TypeError, ValueError):
        return 86400.0


# ---------------------------------------------------------------------------
# Period derivation
# ---------------------------------------------------------------------------

def _previous_quarter_period(now: datetime) -> Tuple[datetime, datetime]:
    """Return (period_start, period_end) for the most recently *completed* quarter.

    e.g. on 2026-04-15 → (2026-01-01, 2026-04-01), the calendar Q1 2026.
    """
    quarter = (now.month - 1) // 3  # 0..3 — current quarter
    if quarter == 0:
        # We are in Q1 of `now.year` → previous quarter is Q4 of (year-1)
        return (datetime(now.year - 1, 10, 1), datetime(now.year, 1, 1))
    start_month = (quarter - 1) * 3 + 1
    end_month = quarter * 3 + 1
    return (
        datetime(now.year, start_month, 1),
        datetime(now.year, end_month, 1),
    )


def _previous_year_period(now: datetime) -> Tuple[datetime, datetime]:
    """Most-recently completed calendar year."""
    return (
        datetime(now.year - 1, 1, 1),
        datetime(now.year, 1, 1),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@dataclass
class GenerationOutcome:
    organizations: int = 0
    reports_created: int = 0
    skipped_existing: int = 0
    errors: List[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []


def _existing_report(
    db: Session,
    *,
    organization_id: Optional[str],
    report_type: PMSReportTypeDB,
    period_start: datetime,
    period_end: datetime,
) -> Optional[PMSReport]:
    return (
        db.query(PMSReport)
        .filter(
            PMSReport.organization_id == organization_id,
            PMSReport.report_type == report_type,
            PMSReport.period_start == period_start,
            PMSReport.period_end == period_end,
        )
        .first()
    )


def _materialise_report(
    db: Session,
    *,
    organization_id: Optional[str],
    report_type: PMSReportTypeDB,
    period_start: datetime,
    period_end: datetime,
) -> Optional[PMSReport]:
    """Generate one report; idempotent for the same (org, type, period)."""
    if _existing_report(
        db,
        organization_id=organization_id,
        report_type=report_type,
        period_start=period_start,
        period_end=period_end,
    ):
        return None

    events = (
        db.query(AdverseEvent)
        .filter(
            AdverseEvent.organization_id == organization_id,
            AdverseEvent.reported_at >= period_start,
            AdverseEvent.reported_at < period_end,
        )
        .all()
    )

    event_dicts = [
        {"severity": str(ev.severity), "status": str(ev.status)}
        for ev in events
    ]
    metrics = aggregate_pms_metrics(event_dicts)
    period_days = max(1, (period_end - period_start).days)
    summary = generate_psur_summary(metrics, period_days)
    summary = (
        f"[Auto-generated draft — review required]\n\n{summary}\n\n"
        "This report was created by the scheduled PMS generator. A "
        "compliance officer must review and finalize before submission."
    )

    now = datetime.utcnow()
    report_id = str(uuid.uuid4())
    report = PMSReport(
        id=report_id,
        organization_id=organization_id,
        report_type=report_type,
        status=PMSReportStatusDB.DRAFT,
        period_start=period_start,
        period_end=period_end,
        summary=summary,
        generated_at=now,
        created_by="system:pms_auto_generate",
        created_at=now,
        updated_at=now,
    )
    db.add(report)

    # Persist key metrics so the dashboard can show trends
    for name, value in metrics.items():
        if isinstance(value, (int, float)):
            db.add(PMSMetric(
                id=str(uuid.uuid4()),
                report_id=report_id,
                metric_name=name,
                metric_value=float(value),
                metric_unit=None,
                computed_at=now,
            ))

    db.commit()
    return report


def generate_due_reports(
    *,
    db_factory: Optional[Any] = None,
    now: Optional[datetime] = None,
) -> GenerationOutcome:
    """Create draft PMS reports for organizations that don't have the latest
    quarterly + annual cycle on file. Idempotent.
    """
    db_factory = db_factory or SessionLocal
    now = now or datetime.utcnow()
    outcome = GenerationOutcome()
    db = db_factory()
    try:
        # Always include the "no organization" bucket (single-tenant deployments)
        org_ids: List[Optional[str]] = [None]
        for org in db.query(Organization).all():
            org_ids.append(org.id)
        outcome.organizations = len(org_ids)

        q_start, q_end = _previous_quarter_period(now)
        y_start, y_end = _previous_year_period(now)

        for org_id in org_ids:
            for report_type, period_start, period_end in (
                (PMSReportTypeDB.QUARTERLY, q_start, q_end),
                (PMSReportTypeDB.PSUR, y_start, y_end),
            ):
                try:
                    if _existing_report(
                        db,
                        organization_id=org_id,
                        report_type=report_type,
                        period_start=period_start,
                        period_end=period_end,
                    ):
                        outcome.skipped_existing += 1
                        continue
                    created = _materialise_report(
                        db,
                        organization_id=org_id,
                        report_type=report_type,
                        period_start=period_start,
                        period_end=period_end,
                    )
                    if created is not None:
                        outcome.reports_created += 1
                        logger.info(
                            "PMS auto-generate: created %s report id=%s "
                            "org=%s period=%s..%s",
                            report_type.value, created.id, org_id,
                            period_start.date(), period_end.date(),
                        )
                except Exception as exc:
                    msg = (
                        f"PMS auto-generate failed for org={org_id} "
                        f"type={report_type}: {exc}"
                    )
                    outcome.errors.append(msg)
                    logger.error(msg, exc_info=True)
                    try:
                        db.rollback()
                    except Exception:
                        pass
    finally:
        db.close()

    logger.info(
        "PMS auto-generate pass: orgs=%d created=%d skipped=%d errors=%d",
        outcome.organizations, outcome.reports_created,
        outcome.skipped_existing, len(outcome.errors),
    )
    return outcome


def make_auto_generate_job():
    def _job() -> None:
        try:
            generate_due_reports()
        except Exception as exc:
            logger.error("PMS auto-generate job failed: %s", exc, exc_info=True)
    return _job
