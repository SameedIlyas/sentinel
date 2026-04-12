"""SQLAlchemy models for PHI redaction logs and data classification records."""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String

from policy_engine.database import Base


class PHIRedactionLog(Base):
    """
    Audit log for PHI redaction events.

    IMPORTANT: Never stores original text — only SHA-256 content hash.
    """

    __tablename__ = "phi_redaction_log"

    id = Column(String, primary_key=True, index=True)
    org_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # SHA-256 hash only — NEVER store plaintext PHI
    content_hash = Column(String, nullable=False, index=True)
    phi_types_found = Column(JSON, nullable=False, default=list)
    strategy_used = Column(String, nullable=False)
    finding_count = Column(Integer, nullable=False, default=0)
    processed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    user_id = Column(String, nullable=True, index=True)


class DataClassificationRecord(Base):
    """Stores data classification decisions for audit purposes."""

    __tablename__ = "data_classifications"

    id = Column(String, primary_key=True, index=True)
    content_hash = Column(String, nullable=False, index=True)
    classification_level = Column(String, nullable=False)
    confidence = Column(String, nullable=True)
    org_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    classified_at = Column(DateTime, nullable=False, default=datetime.utcnow)
