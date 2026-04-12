"""Technical File database models — FDA 510(k) and EU MDR."""
import enum
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey,
    Integer, JSON, String, Text,
)

from policy_engine.database import Base


class TechnicalFileLifecycleDB(str, enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    RETIRED = "retired"


class RegulatoryTypeDB(str, enum.Enum):
    FDA_510K = "fda_510k"
    EU_MDR = "eu_mdr"
    BOTH = "both"


class TechnicalFile(Base):
    """Represents a regulatory technical file (FDA 510(k) or EU MDR)."""

    __tablename__ = "technical_files"

    id = Column(String, primary_key=True, index=True)
    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title = Column(String, nullable=False)
    regulatory_type = Column(Enum(RegulatoryTypeDB), nullable=False)
    product_name = Column(String, nullable=False)
    device_version = Column(String, nullable=False)
    lifecycle_stage = Column(
        Enum(TechnicalFileLifecycleDB),
        default=TechnicalFileLifecycleDB.DRAFT,
        nullable=False,
    )
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class TechnicalFileSection(Base):
    """A section within a TechnicalFile (e.g. device_description, labeling)."""

    __tablename__ = "technical_file_sections"

    id = Column(String, primary_key=True, index=True)
    file_id = Column(
        String,
        ForeignKey("technical_files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section_type = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    order_index = Column(Integer, default=0, nullable=False)
    auto_generated = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class TechnicalFileVersion(Base):
    """
    Immutable snapshot of a TechnicalFile at a point in time.
    Supports regulatory audit trail requirements.
    """

    __tablename__ = "technical_file_versions"

    id = Column(String, primary_key=True, index=True)
    file_id = Column(
        String,
        ForeignKey("technical_files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number = Column(Integer, nullable=False)
    snapshot_json = Column(JSON, nullable=False)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
