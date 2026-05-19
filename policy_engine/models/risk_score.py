"""Risk Scoring Engine SQLAlchemy models."""
from sqlalchemy import Column, String, DateTime, Float, Boolean, JSON, ForeignKey, UniqueConstraint
from datetime import datetime
from policy_engine.database import Base


class RiskScore(Base):
    """Stores computed risk scores — one row per computation (supports history)."""
    __tablename__ = "risk_scores"

    id = Column(String, primary_key=True, index=True)
    organization_id = Column(
        String, ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=False, index=True,
    )
    model_id = Column(String, nullable=False, index=True)
    agent_id = Column(String, nullable=True, index=True)

    # Computed sub-scores
    severity_score = Column(Float, nullable=False)
    exposure_score = Column(Float, nullable=False)
    regulatory_penalty = Column(Float, nullable=False)
    total_risk = Column(Float, nullable=False, index=True)
    risk_level = Column(String, nullable=False)  # low/medium/high/critical

    # Raw factor snapshots (JSON for auditability)
    severity_factors = Column(JSON, nullable=False)
    exposure_factors = Column(JSON, nullable=False)
    regulatory_flags = Column(JSON, nullable=False)

    # Org-level multiplier applied at computation time
    org_multiplier = Column(Float, nullable=False, default=1.0)

    computed_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class RiskScoreHistory(Base):
    """Lightweight history entries for trend analysis."""
    __tablename__ = "risk_score_history"

    id = Column(String, primary_key=True, index=True)
    organization_id = Column(String, nullable=True, index=True)
    model_id = Column(String, nullable=False, index=True)
    total_risk = Column(Float, nullable=False)
    risk_level = Column(String, nullable=False)
    delta = Column(Float, nullable=True)   # change from previous score (positive = riskier)
    trend = Column(String, nullable=False, default="stable")  # up / down / stable
    computed_at = Column(DateTime, nullable=False)


class RiskConfiguration(Base):
    """Per-organisation risk scoring configuration."""
    __tablename__ = "risk_configurations"

    id = Column(String, primary_key=True, index=True)
    organization_id = Column(
        String, ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    regulatory_multiplier = Column(Float, nullable=False, default=1.0)
    critical_threshold = Column(Float, nullable=False, default=75.0)
    high_threshold = Column(Float, nullable=False, default=50.0)
    medium_threshold = Column(Float, nullable=False, default=25.0)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    __table_args__ = (
        UniqueConstraint("organization_id", name="uq_risk_config_org"),
    )


class RiskRegulatoryMapping(Base):
    """Maps a model_id to which regulatory regimes apply (per org)."""
    __tablename__ = "risk_regulatory_mapping"

    id = Column(String, primary_key=True, index=True)
    organization_id = Column(String, nullable=True, index=True)
    model_id = Column(String, nullable=False, index=True)
    regulation = Column(String, nullable=False)   # hipaa / fda_samd / cms_false_claims / onc_hti1
    applicable = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False)
