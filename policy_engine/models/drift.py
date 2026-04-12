"""Drift Detection SQLAlchemy models."""
from sqlalchemy import Column, String, DateTime, JSON, Float, ForeignKey, Boolean
from datetime import datetime
import enum
from policy_engine.database import Base


class DriftAlertSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DriftBaseline(Base):
    __tablename__ = "drift_baselines"
    id = Column(String, primary_key=True, index=True)
    model_id = Column(String, nullable=False, index=True)
    baseline_name = Column(String, nullable=False)
    feature_distributions = Column(JSON, default=dict, nullable=False)
    performance_baseline = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    organization_id = Column(String, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)


class DriftMeasurementModel(Base):
    __tablename__ = "drift_measurements"
    id = Column(String, primary_key=True, index=True)
    baseline_id = Column(String, ForeignKey("drift_baselines.id", ondelete="CASCADE"), nullable=False, index=True)
    measurement_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    feature_distributions = Column(JSON, default=dict, nullable=False)
    psi_scores = Column(JSON, default=dict, nullable=False)
    ks_scores = Column(JSON, default=dict, nullable=False)
    performance_current = Column(JSON, default=dict, nullable=False)
    drift_detected = Column(Boolean, default=False, nullable=False)
    drift_magnitude = Column(Float, default=0.0, nullable=False)


class DriftAlert(Base):
    __tablename__ = "drift_alerts"
    id = Column(String, primary_key=True, index=True)
    measurement_id = Column(String, ForeignKey("drift_measurements.id", ondelete="CASCADE"), nullable=False, index=True)
    alert_type = Column(String, nullable=False)
    severity = Column(String, default="low", nullable=False)
    message = Column(String, nullable=False)
    acknowledged = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
