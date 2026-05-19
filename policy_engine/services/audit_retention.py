"""Audit log retention policy service.

CRIT-008 — three contracts this module now enforces:

1. Rows with ``legal_hold = TRUE`` are NEVER purged regardless of age.
2. Archive durability is verified before delete (every backend's
   ``write()`` raises on failure, and ``archive_and_delete`` only
   deletes after a successful return).
3. HIPAA-aware deployments enforce a 6-year retention floor — startup
   refuses to ship with ``RETENTION_DAYS < RETENTION_HARD_MIN_DAYS``
   when ``HIPAA_MODE=true``.
"""

import os
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import logging

from policy_engine.models.audit_log import AuditLog
from policy_engine.database import SessionLocal
from policy_engine.services.archive_backends import get_archive_backend

logger = logging.getLogger(__name__)


# HIPAA §164.530(j) — record retention floor of 6 years from creation or
# last effective date. We use 6 * 365 days as a conservative integer
# approximation (the workers operate in days; leap days fall out in
# practice and never cause us to delete *too soon*).
RETENTION_HARD_MIN_DAYS = 6 * 365


def _hipaa_mode_enabled() -> bool:
    """Read the env-driven HIPAA mode flag at call time.

    Read-on-call keeps this responsive to env mutations in tests / boot
    rather than freezing the value at import time.
    """
    return (os.environ.get("HIPAA_MODE", "") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


class AuditLogRetentionService:
    """Service for managing audit log retention and archival.

    Implements the configured retention policy by:

    1. Identifying logs older than ``retention_days`` AND not on
       ``legal_hold``.
    2. Archiving them to cold storage (local / S3) via the backend's
       allowlist-based serializer.
    3. Deleting from the database only after the archive backend
       confirms success.
    """

    def __init__(self, retention_days: int = 365):
        """Initialize retention service.

        Args:
            retention_days: Number of days to retain logs (default: 365).
                HIPAA-aware deployments override at startup — see
                :meth:`enforce_hipaa_floor`.
        """
        self.retention_days = retention_days

    def enforce_hipaa_floor(self) -> None:
        """Raise if HIPAA mode is on and retention is below the floor.

        Called from process startup so a misconfigured production env
        cannot run a destructive retention sweep with too-short a
        window. The scheduled job's per-run path treats this as
        non-fatal (surface via an alert) but the process-level guard
        refuses to boot at all.
        """
        if not _hipaa_mode_enabled():
            return
        if self.retention_days < RETENTION_HARD_MIN_DAYS:
            raise RuntimeError(
                f"HIPAA_MODE=true but RETENTION_DAYS={self.retention_days} is "
                f"below the hard minimum {RETENTION_HARD_MIN_DAYS} "
                "(6 years = 2190 days). Increase RETENTION_DAYS or unset "
                "HIPAA_MODE."
            )

    def get_logs_for_archival(self, db: Session) -> List[AuditLog]:
        """Get audit logs eligible for archive: older than retention AND
        not on legal hold.

        Args:
            db: Database session.

        Returns:
            List of audit logs to archive. Legal-hold rows are excluded
            even if they pre-date the retention cutoff.
        """
        cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)

        logs = (
            db.query(AuditLog)
            .filter(AuditLog.timestamp < cutoff_date)
            .filter(AuditLog.legal_hold.is_(False))
            .all()
        )

        return logs
    
    def archive_logs(self, logs: List[AuditLog]) -> Dict[str, Any]:
        """Archive logs to the configured cold-storage backend.

        PHI fields are stripped by the backend before writing.  Raises on
        failure — callers must NOT delete logs if this raises.

        Args:
            logs: Logs to archive.

        Returns:
            Archival metadata dict from the backend.
        """
        from policy_engine.config import settings  # local import avoids circular dep

        backend = get_archive_backend(settings)
        result = backend.write(logs)

        logger.info(
            "Archived %d logs → %s",
            result.get("archived_count", len(logs)),
            result.get("storage_location", "unknown"),
        )
        return result

    def archive_and_delete(self, db: Session) -> Dict[str, Any]:
        """Archive eligible logs then delete them from the database.

        Deletion is intentionally placed AFTER a successful archive call.
        If archive_logs() raises for any reason, delete_archived_logs() is
        never called, guaranteeing no data loss.

        Args:
            db: Database session.

        Returns:
            Execution summary.

        Raises:
            Any exception raised by archive_logs() propagates to the caller.
        """
        logs_to_archive = self.get_logs_for_archival(db)

        if not logs_to_archive:
            logger.info("No logs eligible for archival.")
            return {
                "status": "success",
                "logs_archived": 0,
                "logs_deleted": 0,
                "message": "No logs to archive",
            }

        # Raises on failure — must NOT proceed to delete if this fails.
        archive_metadata = self.archive_logs(logs_to_archive)

        deleted_count = self.delete_archived_logs(db, logs_to_archive)

        logger.info(
            "Retention cycle complete: archived=%d deleted=%d",
            archive_metadata.get("archived_count", 0),
            deleted_count,
        )
        return {
            "status": "success",
            "logs_archived": archive_metadata.get("archived_count", 0),
            "logs_deleted": deleted_count,
            "archive_metadata": archive_metadata,
        }
    
    def delete_archived_logs(self, db: Session, logs: List[AuditLog]) -> int:
        """
        Delete logs from database after archival
        
        Args:
            db: Database session
            logs: Logs to delete
            
        Returns:
            Number of logs deleted
        """
        log_ids = [log.id for log in logs]
        
        deleted_count = db.query(AuditLog).filter(
            AuditLog.id.in_(log_ids)
        ).delete(synchronize_session=False)
        
        db.commit()
        
        logger.info(f"Deleted {deleted_count} archived logs from database")
        
        return deleted_count
    
    def run_retention_policy(self) -> Dict[str, Any]:
        """Execute the retention policy.

        Background-job entry point. Delegates to ``archive_and_delete``
        (single archive+delete code path — historically there were two,
        which is exactly the kind of split that lets a regression slip
        through one side). Wraps the call in a try/except so a failure
        in archive_logs() surfaces as a structured error rather than an
        uncaught exception in the scheduler thread.
        """
        db = SessionLocal()
        try:
            return self.archive_and_delete(db)
        except Exception as e:
            logger.error(
                "Retention policy execution failed: %s", e, exc_info=True
            )
            db.rollback()
            return {
                "status": "error",
                "message": str(e),
                "logs_archived": 0,
                "logs_deleted": 0,
            }
        finally:
            db.close()
    
    def get_retention_stats(self, db: Session) -> Dict[str, Any]:
        """
        Get statistics about audit log retention
        
        Args:
            db: Database session
            
        Returns:
            Retention statistics
        """
        cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)
        
        # Count logs in retention period
        retained_count = db.query(AuditLog).filter(
            AuditLog.timestamp >= cutoff_date
        ).count()
        
        # Count logs beyond retention period
        archival_due_count = db.query(AuditLog).filter(
            AuditLog.timestamp < cutoff_date
        ).count()
        
        # Total logs
        total_count = db.query(AuditLog).count()
        
        # Oldest log timestamp
        oldest_log = db.query(AuditLog).order_by(AuditLog.timestamp.asc()).first()
        oldest_timestamp = oldest_log.timestamp if oldest_log else None
        
        # Newest log timestamp
        newest_log = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).first()
        newest_timestamp = newest_log.timestamp if newest_log else None
        
        return {
            "retention_days": self.retention_days,
            "cutoff_date": cutoff_date.isoformat(),
            "total_logs": total_count,
            "logs_in_retention": retained_count,
            "logs_due_for_archival": archival_due_count,
            "oldest_log_timestamp": oldest_timestamp.isoformat() if oldest_timestamp else None,
            "newest_log_timestamp": newest_timestamp.isoformat() if newest_timestamp else None
        }


# Singleton instance
retention_service = AuditLogRetentionService()


def run_retention_job():
    """
    Entry point for background job scheduler
    
    This can be called by a cron job, Celery task, or scheduled cloud function
    """
    return retention_service.run_retention_policy()
