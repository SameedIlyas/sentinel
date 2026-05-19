"""Prior Authorization SQLAlchemy models — append-only."""
from sqlalchemy import Column, String, DateTime, Float, ForeignKey, Boolean, Integer
from datetime import datetime
from policy_engine.database import Base


class PriorAuthRecord(Base):
    __tablename__ = "prior_auth_records"
    # NO updated_at — append-only table
    id = Column(String, primary_key=True, index=True)
    patient_id_hash = Column(String, nullable=False)
    claim_id = Column(String, nullable=False, index=True)
    service_type = Column(String, nullable=True)
    request_date = Column(String, nullable=True)
    decision_date = Column(String, nullable=True)
    ai_recommendation = Column(String, nullable=False)
    ai_confidence = Column(Float, default=0.0, nullable=False)
    human_reviewer_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    human_review_timestamp = Column(DateTime, nullable=True)
    final_decision = Column(String, nullable=False)
    denial_reason_code = Column(String, nullable=True)
    ai_rationale = Column(String, nullable=True)
    override_reason = Column(String, nullable=True)
    prev_record_hash = Column(String, nullable=False, default="")
    record_hash = Column(String, nullable=False)
    organization_id = Column(String, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class PriorAuthChainStatus(Base):
    __tablename__ = "prior_auth_chain_status"
    id = Column(String, primary_key=True, index=True)
    organization_id = Column(String, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=False, index=True)
    last_verified_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    total_records = Column(Integer, default=0, nullable=False)
    chain_valid = Column(Boolean, default=True, nullable=False)
    broken_at_record_id = Column(String, nullable=True)
    verification_duration_ms = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
