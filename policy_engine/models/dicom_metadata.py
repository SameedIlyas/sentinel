"""SQLAlchemy model for de-identified DICOM metadata records."""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String

from policy_engine.database import Base


class DICOMMetadataRecord(Base):
    """Stores de-identified DICOM study metadata (no PHI)."""

    __tablename__ = "dicom_metadata"

    id = Column(String, primary_key=True, index=True)
    study_uid = Column(String, nullable=True, index=True)
    series_uid = Column(String, nullable=True, index=True)
    modality = Column(String, nullable=True)
    safe_metadata = Column(JSON, nullable=False, default=dict)
    org_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    extracted_at = Column(DateTime, nullable=False, default=datetime.utcnow)
