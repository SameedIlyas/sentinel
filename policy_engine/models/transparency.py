"""Transparency Portal SQLAlchemy models."""
from sqlalchemy import Column, String, DateTime, JSON, ForeignKey, Integer
from datetime import datetime
from policy_engine.database import Base


class TransparencyRecordModel(Base):
    __tablename__ = "transparency_records"
    id = Column(String, primary_key=True, index=True)
    model_name = Column(String, nullable=False)
    model_version = Column(String, nullable=False)
    algorithm_description = Column(String, nullable=True)
    plain_language_summary = Column(String, nullable=False)
    evidence_base = Column(String, nullable=True)
    intended_population = Column(String, nullable=False)
    known_limitations = Column(String, nullable=False)
    performance_summary = Column(JSON, default=dict, nullable=False)
    bias_considerations = Column(String, nullable=True)
    regulatory_status = Column(String, nullable=True)
    published_at = Column(DateTime, nullable=True)
    version_number = Column(Integer, default=1, nullable=False)
    organization_id = Column(String, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class TransparencyVersion(Base):
    __tablename__ = "transparency_versions"
    id = Column(String, primary_key=True, index=True)
    record_id = Column(String, ForeignKey("transparency_records.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    content_snapshot = Column(JSON, default=dict, nullable=False)
    change_summary = Column(String, nullable=True)
    published_by = Column(String, nullable=True)
    published_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class TransparencyAcknowledgment(Base):
    __tablename__ = "transparency_acknowledgments"
    id = Column(String, primary_key=True, index=True)
    record_id = Column(String, ForeignKey("transparency_records.id", ondelete="CASCADE"), nullable=False, index=True)
    acknowledged_by = Column(String, nullable=True)
    acknowledged_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    role_at_time = Column(String, nullable=True)
    ip_address_hash = Column(String, nullable=True)
