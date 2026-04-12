"""Post-Market Surveillance database models — adverse events, PMS reports, metrics."""
import enum
from datetime import datetime

from sqlalchemy import (
    Column, DateTime, Enum, Float, ForeignKey,
    String, Text,
)

from policy_engine.database import Base


class AdverseEventSeverityDB(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AdverseEventStatusDB(str, enum.Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    REPORTED_TO_FDA = "reported_to_fda"


class PMSReportTypeDB(str, enum.Enum):
    PSUR = "psur"
    MDR = "mdr"
    INCIDENT = "incident"
    QUARTERLY = "quarterly"


class PMSReportStatusDB(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    SUBMITTED = "submitted"


class AdverseEvent(Base):
    """
    Adverse event reported against an AI model.

    HIGH and CRITICAL severity events require FDA MDR filing within 30 days.
    """

    __tablename__ = "adverse_events"

    id = Column(String, primary_key=True, index=True)
    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    model_id = Column(String, nullable=False, index=True)
    agent_id = Column(String, nullable=True, index=True)
    event_type = Column(String, nullable=False)
    severity = Column(Enum(AdverseEventSeverityDB), nullable=False, index=True)
    description = Column(Text, nullable=False)
    patient_impact = Column(Text, nullable=True)
    reported_by = Column(String, nullable=True)
    status = Column(
        Enum(AdverseEventStatusDB),
        default=AdverseEventStatusDB.OPEN,
        nullable=False,
        index=True,
    )
    resolved_at = Column(DateTime, nullable=True)
    reported_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class PMSReport(Base):
    """
    Periodic Safety Update Report (PSUR) or FDA Medical Device Report.

    Aggregates adverse events over a reporting period and summarises
    the safety profile of AI-powered medical devices.
    """

    __tablename__ = "pms_reports"

    id = Column(String, primary_key=True, index=True)
    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    report_type = Column(Enum(PMSReportTypeDB), nullable=False)
    status = Column(
        Enum(PMSReportStatusDB),
        default=PMSReportStatusDB.DRAFT,
        nullable=False,
    )
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    summary = Column(Text, nullable=True)
    generated_at = Column(DateTime, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class PMSMetric(Base):
    """A single named metric computed as part of a PMS report."""

    __tablename__ = "pms_metrics"

    id = Column(String, primary_key=True, index=True)
    report_id = Column(
        String,
        ForeignKey("pms_reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    metric_name = Column(String, nullable=False)
    metric_value = Column(Float, nullable=False)
    metric_unit = Column(String, nullable=True)
    computed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
