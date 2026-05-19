"""Shadow AI SQLAlchemy models."""
from sqlalchemy import Column, String, DateTime, Float, ForeignKey, Integer
from datetime import datetime
from policy_engine.database import Base


class ShadowAIDetectionModel(Base):
    __tablename__ = "shadow_ai_detections"
    id = Column(String, primary_key=True, index=True)
    detected_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    source_ip = Column(String, nullable=True)
    destination_host = Column(String, nullable=False)
    destination_port = Column(Integer, default=443, nullable=False)
    ai_provider = Column(String, nullable=True)
    confidence_score = Column(Float, default=1.0, nullable=False)
    staff_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    department = Column(String, nullable=True)
    phi_risk_level = Column(String, default="none", nullable=False)
    status = Column(String, default="detected", nullable=False)
    notes = Column(String, nullable=True)
    organization_id = Column(String, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ShadowAIAllowlist(Base):
    __tablename__ = "shadow_ai_allowlist"
    id = Column(String, primary_key=True, index=True)
    host_pattern = Column(String, nullable=False)
    reason = Column(String, nullable=True)
    approved_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    organization_id = Column(String, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
