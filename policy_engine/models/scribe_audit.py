"""Scribe Audit SQLAlchemy models."""
from sqlalchemy import Column, String, DateTime, Float, ForeignKey, Boolean
from datetime import datetime
from policy_engine.database import Base


class ScribeAuditModel(Base):
    __tablename__ = "scribe_audits"
    id = Column(String, primary_key=True, index=True)
    session_id = Column(String, unique=True, nullable=False, index=True)
    patient_context_hash = Column(String, nullable=True)
    ai_model_used = Column(String, nullable=True)
    generated_note_hash = Column(String, nullable=True)
    audit_score = Column(Float, default=0.0, nullable=False)
    hallucination_detected = Column(Boolean, default=False, nullable=False)
    completeness_score = Column(Float, default=0.0, nullable=False)
    attribution_score = Column(Float, default=100.0, nullable=False)
    status = Column(String, default="pending", nullable=False)
    organization_id = Column(String, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)
    audited_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)


class ScribeAuditFinding(Base):
    __tablename__ = "scribe_audit_findings"
    id = Column(String, primary_key=True, index=True)
    audit_id = Column(String, ForeignKey("scribe_audits.id", ondelete="CASCADE"), nullable=False, index=True)
    finding_type = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    description = Column(String, nullable=False)
    suggested_correction = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
