"""HITL Validation Portal SQLAlchemy models."""
from sqlalchemy import Column, String, DateTime, JSON, Float, ForeignKey
from datetime import datetime
import enum
from policy_engine.database import Base


class HITLStatusDB(str, enum.Enum):
    PENDING = "pending"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"


class HITLPriorityDB(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class HITLReview(Base):
    __tablename__ = "hitl_reviews"
    id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    ai_decision = Column(JSON, default=dict, nullable=False)
    risk_score = Column(Float, default=0.0, nullable=False)
    status = Column(String, default="pending", nullable=False)
    priority = Column(String, default="medium", nullable=False)
    assigned_to = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    sla_deadline = Column(DateTime, nullable=True)
    organization_id = Column(String, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class HITLAssignment(Base):
    __tablename__ = "hitl_assignments"
    id = Column(String, primary_key=True, index=True)
    review_id = Column(String, ForeignKey("hitl_reviews.id", ondelete="CASCADE"), nullable=False, index=True)
    assigned_to = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assigned_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assigned_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)


class HITLAuditTrail(Base):
    __tablename__ = "hitl_audit_trail"
    id = Column(String, primary_key=True, index=True)
    review_id = Column(String, ForeignKey("hitl_reviews.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String, nullable=False)
    old_status = Column(String, nullable=True)
    new_status = Column(String, nullable=True)
    comments = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    # CRIT-002 — entry_hash has no default and is NOT NULL. Every
    # legitimate append computes a real hash from the previous
    # persisted entry; an empty-string default papered over the bug.
    entry_hash = Column(String, nullable=False)
