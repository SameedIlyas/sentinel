"""SQLAlchemy model for FHIR resource cache."""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String

from policy_engine.database import Base


class FHIRResourceCache(Base):
    """Caches FHIR R4 resource payloads to reduce external API calls."""

    __tablename__ = "fhir_resource_cache"

    id = Column(String, primary_key=True, index=True)
    resource_type = Column(String, nullable=False, index=True)
    fhir_id = Column(String, nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    org_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    cached_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
