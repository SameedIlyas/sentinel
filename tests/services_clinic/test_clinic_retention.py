"""Tests for ``policy_engine.services.clinic_retention``."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from freezegun import freeze_time

from policy_engine.models.clinic import (
    BillingEvent,
    ClinicAiObservation,
    ClinicReportArtifact,
)
from policy_engine.models.organization import (
    TIER_CLINIC_BASIC,
    TIER_CLINIC_MULTI_SITE,
    TIER_CLINIC_STANDARD,
)
from policy_engine.services import clinic_retention

from tests.factories.clinic import (
    make_billing_event,
    make_clinic_observation,
    make_clinic_org,
    make_report_artifact,
)


pytestmark = pytest.mark.clinic


def test_retention_days_per_tier() -> None:
    assert clinic_retention.observation_retention_for_tier(TIER_CLINIC_BASIC) == 365
    assert clinic_retention.observation_retention_for_tier(TIER_CLINIC_STANDARD) == 1095
    assert clinic_retention.observation_retention_for_tier(TIER_CLINIC_MULTI_SITE) == 2190
    assert clinic_retention.observation_retention_for_tier("enterprise") == 365  # default


def test_retention_days_env_override(monkeypatch) -> None:
    monkeypatch.setenv("CLINIC_OBSERVATION_RETENTION_BASIC_DAYS", "30")
    assert clinic_retention.observation_retention_for_tier(TIER_CLINIC_BASIC) == 30
    monkeypatch.setenv("CLINIC_OBSERVATION_RETENTION_BASIC_DAYS", "not-a-number")
    # Bad value → fall back to default.
    assert clinic_retention.observation_retention_for_tier(TIER_CLINIC_BASIC) == 365


@freeze_time("2026-05-10T00:00:00Z")
def test_sweep_billing_events_drops_stale(db_session, monkeypatch) -> None:
    org = make_clinic_org(db_session)
    recent = make_billing_event(db_session, org, event_type="checkout.session.completed")
    stale = make_billing_event(db_session, org, event_type="invoice.payment_succeeded")
    stale.processed_at = datetime.utcnow() - timedelta(days=1000)
    db_session.commit()
    # Capture IDs upfront — `synchronize_session=False` in run_retention_sweep
    # detaches deleted rows so any later .id access raises ObjectDeletedError.
    recent_id, stale_id = recent.id, stale.id

    monkeypatch.setattr(clinic_retention, "SessionLocal", lambda: db_session)
    db_session.close = lambda: None  # keep fixture session alive

    summary = clinic_retention.run_retention_sweep()
    assert summary["billing_events"] == 1
    remaining_ids = {b.id for b in db_session.query(BillingEvent).all()}
    assert recent_id in remaining_ids
    assert stale_id not in remaining_ids


@freeze_time("2026-05-10T00:00:00Z")
def test_sweep_observations_per_tier(db_session, monkeypatch) -> None:
    org_basic = make_clinic_org(db_session, tier=TIER_CLINIC_BASIC, slug="basic-clinic")
    org_multi = make_clinic_org(db_session, tier=TIER_CLINIC_MULTI_SITE, slug="multi-clinic")

    obs_basic_stale = make_clinic_observation(db_session, org_basic)
    obs_basic_stale.observed_at = datetime.utcnow() - timedelta(days=400)
    obs_basic_fresh = make_clinic_observation(db_session, org_basic)
    obs_multi_inside = make_clinic_observation(db_session, org_multi)
    obs_multi_inside.observed_at = datetime.utcnow() - timedelta(days=400)
    db_session.commit()
    stale_id = obs_basic_stale.id
    fresh_id = obs_basic_fresh.id
    multi_id = obs_multi_inside.id

    monkeypatch.setattr(clinic_retention, "SessionLocal", lambda: db_session)
    db_session.close = lambda: None

    summary = clinic_retention.run_retention_sweep()
    remaining = {o.id for o in db_session.query(ClinicAiObservation).all()}
    assert stale_id not in remaining
    assert fresh_id in remaining
    assert multi_id in remaining
    assert summary["clinic_ai_observations"] == 1


@freeze_time("2026-05-10T00:00:00Z")
def test_sweep_report_artifacts(db_session, monkeypatch, tmp_path) -> None:
    org = make_clinic_org(db_session)
    # Create a real on-disk file and a stale row pointing to it.
    f = tmp_path / "old_report.pdf"
    f.write_bytes(b"%PDF-1.4 stub\n")
    stale = make_report_artifact(db_session, org, storage_uri=f"file://{f}")
    stale.generated_at = datetime.utcnow() - timedelta(days=1000)
    fresh = make_report_artifact(db_session, org)
    db_session.commit()
    stale_id, fresh_id = stale.id, fresh.id

    monkeypatch.setattr(clinic_retention, "SessionLocal", lambda: db_session)
    db_session.close = lambda: None

    summary = clinic_retention.run_retention_sweep()
    assert summary["clinic_report_artifacts"] == 1
    remaining = {a.id for a in db_session.query(ClinicReportArtifact).all()}
    assert stale_id not in remaining
    assert fresh_id in remaining
    # File deleted from disk.
    assert not f.exists()


def test_is_enabled_reads_env(monkeypatch) -> None:
    monkeypatch.setenv("CLINIC_RETENTION_AUTO", "false")
    assert clinic_retention.is_enabled() is False
    monkeypatch.setenv("CLINIC_RETENTION_AUTO", "TRUE")
    assert clinic_retention.is_enabled() is True
