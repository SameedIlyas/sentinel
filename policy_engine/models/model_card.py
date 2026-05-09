"""Model Card SQLAlchemy models."""
from sqlalchemy import Column, String, DateTime, JSON, Float, ForeignKey
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

    # ─── Pinned artifact lineage (CHAI requires identity to be immutable) ───
    # When any of these change, a new card version is required before publish.
    model_artifact_uri = Column(String, nullable=True)        # e.g. mlflow://runs/abc123/model or s3://bucket/path/model.pkl
    training_dataset_sha256 = Column(String, nullable=True)   # 64-char hex of training data manifest
    evaluation_dataset_sha256 = Column(String, nullable=True) # 64-char hex of eval data manifest
    git_commit_sha = Column(String, nullable=True)            # full or short commit SHA of training code
    framework_version = Column(String, nullable=True)         # e.g. "PyTorch 2.1.0+cu118"

    # ─── External validation + monitoring (CHAI sections 5 & 9) ─────────────
    external_validation = Column(JSON, default=dict, nullable=False)  # {sites:[], dates:[], n:[], auc:[]}
    monitoring_plan = Column(JSON, default=dict, nullable=False)      # {drift_baseline_id, cadence, owner}
    pccp = Column(JSON, default=dict, nullable=False)                  # Predetermined Change Control Plan

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
