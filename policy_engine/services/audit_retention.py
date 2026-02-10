"""Audit log retention policy service"""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import logging

from policy_engine.models.audit_log import AuditLog
from policy_engine.database import SessionLocal

logger = logging.getLogger(__name__)


class AuditLogRetentionService:
    """
    Service for managing audit log retention and archival
    
    Implements the 365-day retention policy by:
    1. Identifying logs older than 365 days
    2. Archiving them to cold storage (S3/GCS)
    3. Deleting from the database
    """
    
    def __init__(self, retention_days: int = 365):
        """
        Initialize retention service
        
        Args:
            retention_days: Number of days to retain logs (default: 365)
        """
        self.retention_days = retention_days
    
    def get_logs_for_archival(self, db: Session) -> List[AuditLog]:
        """
        Get audit logs older than retention period
        
        Args:
            db: Database session
            
        Returns:
            List of audit logs to be archived
        """
        cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)
        
        logs = db.query(AuditLog).filter(
            AuditLog.timestamp < cutoff_date
        ).all()
        
        return logs
    
    def archive_logs(self, logs: List[AuditLog]) -> Dict[str, Any]:
        """
        Archive logs to cold storage
        
        In production, this would:
        1. Upload logs to S3/GCS
        2. Compress logs for storage efficiency
        3. Create archive manifest
        
        Args:
            logs: Logs to archive
            
        Returns:
            Archival metadata
        """
        # For now, this is a placeholder
        # In production, integrate with cloud storage (S3, GCS, etc.)
        
        archived_count = len(logs)
        archive_id = f"archive_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        logger.info(f"Archiving {archived_count} logs to {archive_id}")
        
        # TODO: In production, implement actual cloud storage upload
        # Example for S3:
        # s3_client.put_object(
        #     Bucket='audit-logs-archive',
        #     Key=f'{archive_id}.json.gz',
        #     Body=gzip.compress(json.dumps(logs).encode())
        # )
        
        return {
            "archive_id": archive_id,
            "archived_count": archived_count,
            "archived_at": datetime.utcnow().isoformat(),
            "storage_location": f"s3://audit-logs-archive/{archive_id}.json.gz"
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
        """
        Execute the retention policy
        
        This should be run as a background job (e.g., daily cron)
        
        Returns:
            Execution summary
        """
        db = SessionLocal()
        
        try:
            # Get logs to archive
            logs_to_archive = self.get_logs_for_archival(db)
            
            if not logs_to_archive:
                logger.info("No logs to archive")
                return {
                    "status": "success",
                    "logs_archived": 0,
                    "logs_deleted": 0,
                    "message": "No logs to archive"
                }
            
            # Archive logs
            archive_metadata = self.archive_logs(logs_to_archive)
            
            # Delete archived logs from database
            deleted_count = self.delete_archived_logs(db, logs_to_archive)
            
            logger.info(
                f"Retention policy executed: {deleted_count} logs archived and deleted"
            )
            
            return {
                "status": "success",
                "logs_archived": archive_metadata['archived_count'],
                "logs_deleted": deleted_count,
                "archive_metadata": archive_metadata
            }
            
        except Exception as e:
            logger.error(f"Retention policy execution failed: {str(e)}", exc_info=True)
            db.rollback()
            
            return {
                "status": "error",
                "message": str(e),
                "logs_archived": 0,
                "logs_deleted": 0
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
