"""Tests for audit log archival — Task 1.3 (Phase 1).

RED phase: archive_backends.py does not exist yet, archive_logs() is a stub,
and config.py has no ARCHIVE_* fields.  All tests will FAIL until GREEN.
"""
import gzip
import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from policy_engine.models.audit_log import AuditLog


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_audit_log(log_id: str, days_old: int = 400) -> AuditLog:
    """Return an unsaved AuditLog ORM object.

    organization_id is NOT NULL after migration 020 (CRIT-010) — every
    helper sets a probe tenant so the row can be inserted. The retention
    tests do not exercise scope, so a single fixed sentinel is fine.
    """
    return AuditLog(
        id=log_id,
        agent_id="agent-archive-test",
        agent_name="Archive Test Agent",
        user_id="user-1",
        tool_name="read_patient_record",
        arguments={"patient_id": "PHI-001", "ssn": "123-45-6789"},
        system_accessed="EHR",
        data_touched=["patient_record_PHI"],
        decision="allowed",
        policy_ids=[],
        reason="Allowed by policy",
        log_metadata={},
        timestamp=datetime.utcnow() - timedelta(days=days_old),
        organization_id="probe-org",
    )


# ---------------------------------------------------------------------------
# LocalArchiveBackend — file output
# ---------------------------------------------------------------------------

def test_local_archive_writes_gzip_json_file(tmp_path: Path, db_session):
    """LocalArchiveBackend.write() must create a .json.gz file in the archive dir."""
    from policy_engine.services.archive_backends import LocalArchiveBackend

    log = _make_audit_log("log-gzip-001")
    db_session.add(log)
    db_session.commit()
    db_session.refresh(log)

    backend = LocalArchiveBackend(archive_dir=str(tmp_path))
    result = backend.write([log])

    assert result["archived_count"] == 1

    # Exactly one .json.gz file must have been created
    gz_files = list(tmp_path.glob("*.json.gz"))
    assert len(gz_files) == 1, f"Expected 1 .json.gz, found {gz_files}"

    # File must be valid gzip-compressed JSON
    with gzip.open(gz_files[0], "rt", encoding="utf-8") as fh:
        records = json.load(fh)
    assert isinstance(records, list)
    assert len(records) == 1
    assert records[0]["id"] == "log-gzip-001"


def test_local_archive_strips_phi_fields(tmp_path: Path, db_session):
    """LocalArchiveBackend.write() must remove PHI fields (arguments, data_touched)."""
    from policy_engine.services.archive_backends import (
        LocalArchiveBackend,
        AUDIT_LOG_PHI_FIELDS,
    )

    log = _make_audit_log("log-phi-strip-001")
    db_session.add(log)
    db_session.commit()
    db_session.refresh(log)

    backend = LocalArchiveBackend(archive_dir=str(tmp_path))
    backend.write([log])

    gz_files = list(tmp_path.glob("*.json.gz"))
    with gzip.open(gz_files[0], "rt", encoding="utf-8") as fh:
        records = json.load(fh)

    record = records[0]
    for phi_field in AUDIT_LOG_PHI_FIELDS:
        assert phi_field not in record, (
            f"PHI field '{phi_field}' must be stripped from archive output"
        )


# ---------------------------------------------------------------------------
# archive_and_delete — atomicity guarantee
# ---------------------------------------------------------------------------

def test_archive_and_delete_does_not_delete_if_archive_fails(db_session):
    """If archive raises, delete must NOT be called (data safety guarantee)."""
    from policy_engine.services.audit_retention import AuditLogRetentionService

    log = _make_audit_log("log-safety-001", days_old=400)
    db_session.add(log)
    db_session.commit()

    svc = AuditLogRetentionService(retention_days=365)

    failing_backend = MagicMock()
    failing_backend.write.side_effect = RuntimeError("S3 unreachable")

    with patch(
        "policy_engine.services.audit_retention.get_archive_backend",
        return_value=failing_backend,
    ):
        with pytest.raises(RuntimeError):
            svc.archive_and_delete(db_session)

    # Log must still exist in DB
    still_there = db_session.query(AuditLog).filter(
        AuditLog.id == "log-safety-001"
    ).first()
    assert still_there is not None, (
        "Log must NOT be deleted when archival fails"
    )


# ---------------------------------------------------------------------------
# get_archive_backend factory
# ---------------------------------------------------------------------------

def test_get_archive_backend_returns_local_for_local_setting(tmp_path):
    """get_archive_backend() returns LocalArchiveBackend when ARCHIVE_BACKEND=local."""
    from policy_engine.services.archive_backends import (
        LocalArchiveBackend,
        get_archive_backend,
    )

    cfg = MagicMock()
    cfg.ARCHIVE_BACKEND = "local"
    cfg.ARCHIVE_LOCAL_PATH = str(tmp_path)

    backend = get_archive_backend(cfg)
    assert isinstance(backend, LocalArchiveBackend)


def test_get_archive_backend_raises_for_unknown_backend():
    """get_archive_backend() raises ValueError for unknown backend names."""
    from policy_engine.services.archive_backends import get_archive_backend

    cfg = MagicMock()
    cfg.ARCHIVE_BACKEND = "gcs"

    with pytest.raises(ValueError, match="Unknown ARCHIVE_BACKEND"):
        get_archive_backend(cfg)


def test_local_archive_backend_raises_when_path_empty():
    """LocalArchiveBackend raises ValueError when archive_dir is empty string."""
    from policy_engine.services.archive_backends import LocalArchiveBackend

    with pytest.raises(ValueError, match="ARCHIVE_LOCAL_PATH"):
        LocalArchiveBackend(archive_dir="")


# ---------------------------------------------------------------------------
# AuditLogRetentionService — direct method coverage
# ---------------------------------------------------------------------------

def test_archive_logs_calls_backend_write(tmp_path, db_session):
    """archive_logs() must delegate to the configured backend and return metadata."""
    from policy_engine.services.audit_retention import AuditLogRetentionService

    log = _make_audit_log("log-delegate-001", days_old=400)
    db_session.add(log)
    db_session.commit()
    db_session.refresh(log)

    svc = AuditLogRetentionService(retention_days=365)

    mock_backend = MagicMock()
    mock_backend.write.return_value = {
        "archive_id": "test-archive",
        "archived_count": 1,
        "storage_location": str(tmp_path / "test.json.gz"),
        "archived_at": "2024-01-01T00:00:00",
    }

    with patch(
        "policy_engine.services.audit_retention.get_archive_backend",
        return_value=mock_backend,
    ):
        result = svc.archive_logs([log])

    mock_backend.write.assert_called_once_with([log])
    assert result["archived_count"] == 1


def test_delete_archived_logs_removes_records(db_session):
    """delete_archived_logs() must delete the specified logs from the DB."""
    from policy_engine.services.audit_retention import AuditLogRetentionService

    log1 = _make_audit_log("log-del-001", days_old=400)
    log2 = _make_audit_log("log-del-002", days_old=400)
    db_session.add_all([log1, log2])
    db_session.commit()
    db_session.refresh(log1)
    db_session.refresh(log2)

    svc = AuditLogRetentionService(retention_days=365)
    deleted = svc.delete_archived_logs(db_session, [log1, log2])

    assert deleted == 2
    remaining = db_session.query(AuditLog).filter(
        AuditLog.id.in_(["log-del-001", "log-del-002"])
    ).count()
    assert remaining == 0


def test_archive_and_delete_no_logs_returns_success(db_session):
    """archive_and_delete() returns success status when no logs are eligible."""
    from policy_engine.services.audit_retention import AuditLogRetentionService

    # Insert a recent log that is NOT past the retention cutoff
    recent_log = _make_audit_log("log-recent-001", days_old=10)
    db_session.add(recent_log)
    db_session.commit()

    svc = AuditLogRetentionService(retention_days=365)
    result = svc.archive_and_delete(db_session)

    assert result["status"] == "success"
    assert result["logs_archived"] == 0
    assert result["logs_deleted"] == 0


def test_get_logs_for_archival_returns_old_logs(db_session):
    """get_logs_for_archival() returns only logs older than retention_days."""
    from policy_engine.services.audit_retention import AuditLogRetentionService

    old_log = _make_audit_log("log-old-001", days_old=400)
    new_log = _make_audit_log("log-new-001", days_old=10)
    db_session.add_all([old_log, new_log])
    db_session.commit()

    svc = AuditLogRetentionService(retention_days=365)
    eligible = svc.get_logs_for_archival(db_session)

    ids = [log.id for log in eligible]
    assert "log-old-001" in ids
    assert "log-new-001" not in ids


def test_archive_and_delete_success_path_deletes_logs(db_session):
    """archive_and_delete() success path: logs are archived then deleted from DB."""
    from policy_engine.services.audit_retention import AuditLogRetentionService

    old_log = _make_audit_log("log-success-path-001", days_old=400)
    db_session.add(old_log)
    db_session.commit()

    svc = AuditLogRetentionService(retention_days=365)

    mock_backend = MagicMock()
    mock_backend.write.return_value = {
        "archive_id": "archive-success",
        "archived_count": 1,
        "storage_location": "/tmp/archive-success.json.gz",
        "archived_at": "2024-01-01T00:00:00",
    }

    with patch(
        "policy_engine.services.audit_retention.get_archive_backend",
        return_value=mock_backend,
    ):
        result = svc.archive_and_delete(db_session)

    assert result["status"] == "success"
    assert result["logs_archived"] == 1
    assert result["logs_deleted"] == 1

    # Log must be gone from DB
    gone = db_session.query(AuditLog).filter(
        AuditLog.id == "log-success-path-001"
    ).first()
    assert gone is None, "Log should be deleted after successful archival"


# ---------------------------------------------------------------------------
# S3ArchiveBackend — validation
# ---------------------------------------------------------------------------

def test_s3_archive_backend_raises_when_bucket_empty():
    """S3ArchiveBackend raises ValueError when bucket name is empty."""
    from policy_engine.services.archive_backends import S3ArchiveBackend

    with pytest.raises(ValueError, match="ARCHIVE_S3_BUCKET"):
        S3ArchiveBackend(bucket="")


def test_get_archive_backend_raises_for_s3_missing_bucket():
    """get_archive_backend() raises ValueError for s3 backend with no bucket."""
    from policy_engine.services.archive_backends import get_archive_backend

    cfg = MagicMock()
    cfg.ARCHIVE_BACKEND = "s3"
    cfg.ARCHIVE_S3_BUCKET = ""
    cfg.ARCHIVE_S3_PREFIX = "audit-logs/"

    with pytest.raises(ValueError, match="ARCHIVE_S3_BUCKET"):
        get_archive_backend(cfg)
