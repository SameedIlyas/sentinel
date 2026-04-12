"""Model Card SQLAlchemy models."""
from sqlalchemy import Column, String, DateTime, JSON, Enum, Float, ForeignKey, Integer
from datetime import datetime
import enum
from policy_engine.database import Base


class LifecycleStageDB(str, enum.Enum):
    DRAFT = "draft"
    REVIEW = "review"
    PUBLISHED = "published"
    RETIRED = "retired"


class ReviewDecision(str, enum.Enum):
    APPROVE = "approve"
    REJECT = "reject"
    REVISE = "revise"


class ModelCard(Base):
    __tablename__ = "model_cards"
    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    version = Column(String, default="1.0", nullable=False)
    lifecycle_stage = Column(String, default="draft", nullable=False)
    intended_use = Column(String, nullable=True)
    clinical_indications = Column(String, nullable=True)
    contraindications = Column(String, nullable=True)
    training_data_source = Column(String, nullable=True)
    performance_metrics = Column(JSON, default=dict, nullable=False)
    bias_summary = Column(JSON, default=dict, nullable=False)
    fda_status = Column(String, nullable=True)
    chai_version = Column(String, default="1.0", nullable=False)
    organization_id = Column(String, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class ModelCardVersion(Base):
    __tablename__ = "model_card_versions"
    id = Column(String, primary_key=True, index=True)
    model_card_id = Column(String, ForeignKey("model_cards.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(String, nullable=False)
    content = Column(JSON, default=dict, nullable=False)
    published_by = Column(String, nullable=True)
    published_at = Column(DateTime, nullable=True)
    changelog = Column(String, nullable=True)


class ModelCardMetric(Base):
    __tablename__ = "model_card_metrics"
    id = Column(String, primary_key=True, index=True)
    model_card_id = Column(String, ForeignKey("model_cards.id", ondelete="CASCADE"), nullable=False, index=True)
    metric_name = Column(String, nullable=False)
    metric_value = Column(Float, nullable=False)
    metric_type = Column(String, nullable=True)
    subgroup = Column(String, nullable=True)
    evaluation_date = Column(DateTime, nullable=True)


class ModelCardReview(Base):
    __tablename__ = "model_card_reviews"
    id = Column(String, primary_key=True, index=True)
    model_card_id = Column(String, ForeignKey("model_cards.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_id = Column(String, nullable=False)
    reviewer_role = Column(String, nullable=False)
    decision = Column(String, nullable=False)
    comments = Column(String, nullable=True)
    reviewed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
