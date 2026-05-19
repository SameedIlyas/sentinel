"""Revenue Cycle SQLAlchemy models."""
from sqlalchemy import Column, String, DateTime, JSON, Float, ForeignKey
from datetime import datetime
from policy_engine.database import Base


class RevenueCycleAudit(Base):
    __tablename__ = "revenue_cycle_audits"
    id = Column(String, primary_key=True, index=True)
    claim_id = Column(String, unique=True, nullable=False, index=True)
    claim_date = Column(String, nullable=True)
    provider_id = Column(String, nullable=True, index=True)
    payer_id = Column(String, nullable=True)
    primary_diagnosis_code = Column(String, nullable=True)
    procedure_codes = Column(JSON, default=list, nullable=False)
    modifiers = Column(JSON, default=list, nullable=False)
    billed_amount = Column(Float, default=0.0, nullable=False)
    expected_amount_range = Column(JSON, default=dict, nullable=False)
    risk_score = Column(Float, default=0.0, nullable=False)
    findings = Column(JSON, default=list, nullable=False)
    status = Column(String, default="clean", nullable=False)
    reviewed_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    organization_id = Column(String, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class RevenueCycleFinding(Base):
    __tablename__ = "revenue_cycle_findings"
    id = Column(String, primary_key=True, index=True)
    audit_id = Column(String, ForeignKey("revenue_cycle_audits.id", ondelete="CASCADE"), nullable=False, index=True)
    finding_type = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    description = Column(String, nullable=False)
    affected_codes = Column(JSON, default=list, nullable=False)
    estimated_overbilling = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class CodingBenchmark(Base):
    __tablename__ = "coding_benchmarks"
    id = Column(String, primary_key=True, index=True)
    procedure_code = Column(String, nullable=False, index=True)
    specialty = Column(String, nullable=True)
    p25_amount = Column(Float, nullable=False)
    p50_amount = Column(Float, nullable=False)
    p75_amount = Column(Float, nullable=False)
    p90_amount = Column(Float, nullable=False)
    national_frequency_per_1000 = Column(Float, nullable=True)
    last_updated = Column(DateTime, default=datetime.utcnow, nullable=False)
    source = Column(String, nullable=False)
    organization_id = Column(String, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)
