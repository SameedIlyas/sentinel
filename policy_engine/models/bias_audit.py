"""Bias Audit SQLAlchemy models."""
from sqlalchemy import Column, String, DateTime, Float, ForeignKey, Boolean, Integer
from datetime import datetime
import enum
from policy_engine.database import Base


class BiasAuditStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class BiasAuditModel(Base):
    __tablename__ = "bias_audits"
    id = Column(String, primary_key=True, index=True)
    model_card_id = Column(String, ForeignKey("model_cards.id", ondelete="SET NULL"), nullable=True, index=True)
    audit_name = Column(String, nullable=False)
    status = Column(String, default="pending", nullable=False)
    dataset_description = Column(String, nullable=True)
    organization_id = Column(String, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=False, index=True)
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)


class BiasAuditSubgroup(Base):
    __tablename__ = "bias_audit_subgroups"
    id = Column(String, primary_key=True, index=True)
    audit_id = Column(String, ForeignKey("bias_audits.id", ondelete="CASCADE"), nullable=False, index=True)
    subgroup_name = Column(String, nullable=False)
    subgroup_type = Column(String, nullable=False)
    sample_size = Column(Integer, default=0, nullable=False)


class BiasAuditResultModel(Base):
    __tablename__ = "bias_audit_results"
    id = Column(String, primary_key=True, index=True)
    audit_id = Column(String, ForeignKey("bias_audits.id", ondelete="CASCADE"), nullable=False, index=True)
    subgroup_id = Column(String, ForeignKey("bias_audit_subgroups.id", ondelete="CASCADE"), nullable=True, index=True)
    metric_name = Column(String, nullable=False)
    metric_value = Column(Float, nullable=False)
    reference_value = Column(Float, nullable=False)
    disparity_ratio = Column(Float, nullable=False)
    passes_threshold = Column(Boolean, default=True, nullable=False)
    threshold_used = Column(Float, default=0.8, nullable=False)
