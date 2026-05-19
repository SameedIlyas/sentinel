"""Regression tests for CRIT-008 — retention + legal-hold + durability.

Three contracts the retention service must hold:

1. A row with ``legal_hold = TRUE`` is NEVER purged, even when older
   than the retention window.
2. ``archive_and_delete`` deletes from the DB ONLY after the archive
   backend's ``write()`` returns successfully. A failing write must
   propagate and leave the rows in the DB.
3. ``enforce_hipaa_floor`` raises when ``HIPAA_MODE=true`` is set with
   a ``retention_days`` shorter than the 6-year HIPAA floor.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from policy_engine.models.audit_log import AuditLog
from policy_engine.services.audit_retention import (
    RETENTION_HARD_MIN_DAYS,
    AuditLogRetentionService,
)


def _make_log(
    log_id: str,
    *,
    days_old: int = 400,
    legal_hold: bool = False,
) -> AuditLog:
    return AuditLog(
        id=log_id,
        agent_id="probe-agent",
        agent_name="probe",
        user_id="user-1",
        tool_name="probe.tool",
        arguments={},
        system_accessed="probe",
        data_touched=[],
        decision="allowed",
        policy_ids=[],
        reason="probe",
        log_metadata={},
        timestamp=datetime.utcnow() - timedelta(days=days_old),
        legal_hold=legal_hold,
        organization_id="probe-org",
    )


# ---------------------------------------------------------------------------
# Legal-hold exemption
# ---------------------------------------------------------------------------

class TestLegalHoldExemption:
    def test_legal_hold_row_excluded_from_archival_list(self, db_session):
        """get_logs_for_archival skips legal_hold=TRUE rows."""
        ordinary = _make_log("ordinary-1", days_old=400, legal_hold=False)
        held = _make_log("held-1", days_old=400, legal_hold=True)
        db_session.add_all([ordinary, held])
        db_session.commit()

        svc = AuditLogRetentionService(retention_days=365)
        eligible = svc.get_logs_for_archival(db_session)
        eligible_ids = {l.id for l in eligible}

        assert "ordinary-1" in eligible_ids
        assert "held-1" not in eligible_ids, "legal_hold row leaked into purge set"

    def test_archive_and_delete_does_not_delete_legal_hold(
        self, db_session, tmp_path: Path
    ):
        """End-to-end: legal_hold survives a full archive_and_delete pass."""
        os.environ["ARCHIVE_BACKEND"] = "local"
        os.environ["ARCHIVE_LOCAL_PATH"] = str(tmp_path)

        ordinary = _make_log("ordinary-1", days_old=400)
        held = _make_log("held-1", days_old=400, legal_hold=True)
        db_session.add_all([ordinary, held])
        db_session.commit()

        # archive_and_delete uses settings at runtime. Re-import is the
        # cleanest way to pick up the env change.
        from policy_engine.config import Settings
        from policy_engine.services import audit_retention as ar

        # Patch the settings instance the retention service sees.
        ar_settings = Settings()
        ar_settings.ARCHIVE_BACKEND = "local"
        ar_settings.ARCHIVE_LOCAL_PATH = str(tmp_path)

        # The archive backend reads settings at construction time —
        # AuditLogRetentionService passes its own local import. Easiest
        # path: monkey-patch the get_archive_backend factory.
        from policy_engine.services.archive_backends import LocalArchiveBackend

        backend = LocalArchiveBackend(archive_dir=str(tmp_path))
        from unittest.mock import patch

        with patch(
            "policy_engine.services.audit_retention.get_archive_backend",
            return_value=backend,
        ):
            svc = AuditLogRetentionService(retention_days=365)
            result = svc.archive_and_delete(db_session)

        assert result["status"] == "success"
        assert result["logs_archived"] == 1, (
            "Only the ordinary row should have been archived"
        )
        assert result["logs_deleted"] == 1

        surviving = db_session.query(AuditLog).all()
        surviving_ids = {l.id for l in surviving}
        assert "held-1" in surviving_ids, "legal_hold row was purged"
        assert "ordinary-1" not in surviving_ids


# ---------------------------------------------------------------------------
# Archive durability — failure must abort delete
# ---------------------------------------------------------------------------

class TestArchiveDurability:
    def test_archive_failure_aborts_delete(self, db_session, tmp_path: Path):
        """If the backend raises, the DB row stays."""
        ordinary = _make_log("ordinary-2", days_old=400)
        db_session.add(ordinary)
        db_session.commit()

        class _FailingBackend:
            def write(self, _logs):
                raise IOError("simulated archive failure")

        from unittest.mock import patch

        with patch(
            "policy_engine.services.audit_retention.get_archive_backend",
            return_value=_FailingBackend(),
        ):
            svc = AuditLogRetentionService(retention_days=365)
            with pytest.raises(IOError):
                svc.archive_and_delete(db_session)

        # Row must still exist.
        survived = (
            db_session.query(AuditLog).filter(AuditLog.id == "ordinary-2").first()
        )
        assert survived is not None, (
            "archive failure must NOT delete DB rows — CRIT-008 contract"
        )


# ---------------------------------------------------------------------------
# HIPAA floor enforcement
# ---------------------------------------------------------------------------

class TestHipaaFloor:
    def test_floor_constant_is_six_years(self):
        assert RETENTION_HARD_MIN_DAYS == 2190

    def test_hipaa_mode_with_short_retention_raises(self, monkeypatch):
        monkeypatch.setenv("HIPAA_MODE", "true")
        svc = AuditLogRetentionService(retention_days=365)
        with pytest.raises(RuntimeError, match="HIPAA_MODE"):
            svc.enforce_hipaa_floor()

    def test_hipaa_mode_with_floor_or_above_passes(self, monkeypatch):
        monkeypatch.setenv("HIPAA_MODE", "true")
        svc = AuditLogRetentionService(retention_days=RETENTION_HARD_MIN_DAYS)
        svc.enforce_hipaa_floor()  # must not raise

    def test_hipaa_mode_off_skips_floor(self, monkeypatch):
        monkeypatch.delenv("HIPAA_MODE", raising=False)
        svc = AuditLogRetentionService(retention_days=30)
        svc.enforce_hipaa_floor()  # must not raise


# ---------------------------------------------------------------------------
# Alert.audit_log_id is set NULL on parent purge (not dangling)
# ---------------------------------------------------------------------------

class TestAlertCascadeOnPurge:
    def test_alert_audit_log_id_set_null_after_parent_delete(
        self, db_session, tmp_path: Path
    ):
        """When an audit row is purged, alerts.audit_log_id becomes NULL,
        never dangling."""
        # First — ensure the new FK exists on the SQLite test DB. The
        # conftest builds Base.metadata; the FK is declared in the model
        # so create_all() picks it up.
        from policy_engine.models.alert import Alert, AlertSeverity

        parent = _make_log("parent-1", days_old=400)
        db_session.add(parent)
        db_session.flush()
        alert = Alert(
            id="alert-1",
            timestamp=datetime.utcnow(),
            severity=AlertSeverity.MEDIUM,
            alert_type="probe",
            agent_id="probe",
            description="probe",
            audit_log_id=parent.id,
            acknowledged=False,
            organization_id="probe-org",
        )
        db_session.add(alert)
        db_session.commit()

        # Enable SQLite FK enforcement for this test (off by default).
        db_session.execute(__import__("sqlalchemy").text("PRAGMA foreign_keys=ON"))
        db_session.commit()

        from unittest.mock import patch

        class _OkBackend:
            def write(self, logs):
                return {
                    "archive_id": "x",
                    "archived_count": len(logs),
                    "storage_location": str(tmp_path),
                }

        with patch(
            "policy_engine.services.audit_retention.get_archive_backend",
            return_value=_OkBackend(),
        ):
            svc = AuditLogRetentionService(retention_days=365)
            svc.archive_and_delete(db_session)

        db_session.expire_all()
        survived = (
            db_session.query(Alert).filter(Alert.id == "alert-1").first()
        )
        assert survived is not None
        assert survived.audit_log_id is None, (
            "alerts.audit_log_id should be NULL after parent purge, not dangling"
        )
