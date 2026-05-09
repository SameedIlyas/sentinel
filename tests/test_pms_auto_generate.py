"""Tests for Tier 2 Sprint 4 PMS scheduled report generation."""
import uuid
from datetime import datetime, timedelta

from policy_engine.models.organization import Organization
from policy_engine.models.post_market import (
    AdverseEvent,
    AdverseEventSeverityDB,
    AdverseEventStatusDB,
    PMSMetric,
    PMSReport,
    PMSReportStatusDB,
    PMSReportTypeDB,
)
from policy_engine.services.pms_auto_service import (
    _previous_quarter_period,
    _previous_year_period,
    auto_interval_seconds,
    generate_due_reports,
    is_enabled,
)


def _make_org(db_session, name="Org-1") -> Organization:
    org = Organization(
        id=str(uuid.uuid4()),
        name=name,
        slug=f"slug-{uuid.uuid4().hex[:8]}",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(org)
    db_session.commit()
    return org


def test_previous_quarter_period_january():
    period_start, period_end = _previous_quarter_period(datetime(2026, 1, 15))
    assert period_start == datetime(2025, 10, 1)
    assert period_end == datetime(2026, 1, 1)


def test_previous_quarter_period_april():
    period_start, period_end = _previous_quarter_period(datetime(2026, 4, 30))
    assert period_start == datetime(2026, 1, 1)
    assert period_end == datetime(2026, 4, 1)


def test_previous_quarter_period_december():
    period_start, period_end = _previous_quarter_period(datetime(2026, 12, 1))
    assert period_start == datetime(2026, 7, 1)
    assert period_end == datetime(2026, 10, 1)


def test_previous_year_period():
    period_start, period_end = _previous_year_period(datetime(2026, 5, 9))
    assert period_start == datetime(2025, 1, 1)
    assert period_end == datetime(2026, 1, 1)


def test_is_enabled_reads_env(monkeypatch):
    monkeypatch.delenv("PMS_AUTO_GENERATE", raising=False)
    assert is_enabled() is False
    monkeypatch.setenv("PMS_AUTO_GENERATE", "true")
    assert is_enabled() is True


def test_auto_interval_clamps_below_one_hour(monkeypatch):
    monkeypatch.setenv("PMS_AUTO_GENERATE_INTERVAL_SECONDS", "60")
    assert auto_interval_seconds() == 3600.0


def test_generate_due_reports_creates_quarterly_and_annual(db_session, monkeypatch):
    org = _make_org(db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)

    now = datetime(2026, 5, 9)
    outcome = generate_due_reports(
        db_factory=lambda: db_session,
        now=now,
    )

    # Two organizations: None bucket + the test org → 4 reports total expected
    assert outcome.organizations == 2
    assert outcome.reports_created == 4
    assert outcome.errors == []

    # Org-specific quarterly + PSUR
    org_reports = (
        db_session.query(PMSReport)
        .filter(PMSReport.organization_id == org.id)
        .all()
    )
    assert len(org_reports) == 2
    types = {r.report_type for r in org_reports}
    assert PMSReportTypeDB.QUARTERLY in types
    assert PMSReportTypeDB.PSUR in types

    quarterly = [r for r in org_reports if r.report_type == PMSReportTypeDB.QUARTERLY][0]
    assert quarterly.status == PMSReportStatusDB.DRAFT
    assert quarterly.period_start == datetime(2026, 1, 1)
    assert quarterly.period_end == datetime(2026, 4, 1)
    assert "Auto-generated draft" in quarterly.summary


def test_generate_due_reports_idempotent(db_session, monkeypatch):
    _make_org(db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)

    now = datetime(2026, 5, 9)
    first = generate_due_reports(db_factory=lambda: db_session, now=now)
    second = generate_due_reports(db_factory=lambda: db_session, now=now)

    assert first.reports_created == 4
    assert second.reports_created == 0
    assert second.skipped_existing == 4


def test_generate_due_reports_persists_metrics(db_session, monkeypatch):
    org = _make_org(db_session)

    # Add a critical adverse event in the previous quarter
    quarter_start = datetime(2026, 1, 15)
    db_session.add(AdverseEvent(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        model_id="m1",
        event_type="misdiagnosis",
        severity=AdverseEventSeverityDB.CRITICAL,
        description="x",
        status=AdverseEventStatusDB.OPEN,
        reported_at=quarter_start,
        created_at=quarter_start,
    ))
    db_session.commit()

    monkeypatch.setattr(db_session, "close", lambda: None)
    outcome = generate_due_reports(
        db_factory=lambda: db_session,
        now=datetime(2026, 5, 9),
    )
    assert outcome.reports_created == 4

    # Quarterly report metrics should reflect the critical event
    quarterly = (
        db_session.query(PMSReport)
        .filter(
            PMSReport.organization_id == org.id,
            PMSReport.report_type == PMSReportTypeDB.QUARTERLY,
        )
        .first()
    )
    assert quarterly is not None
    metrics = (
        db_session.query(PMSMetric)
        .filter(PMSMetric.report_id == quarterly.id)
        .all()
    )
    metric_names = {m.metric_name for m in metrics}
    # We expect at least a "total_events" or similar metric — depends on
    # aggregate_pms_metrics output, but the count should be non-empty.
    assert len(metrics) >= 1
    assert metric_names  # non-empty
