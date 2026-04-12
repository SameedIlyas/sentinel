"""Organization model for multi-tenancy."""

import enum
from datetime import datetime

from sqlalchemy import (
    Column, String, DateTime, Boolean, JSON, Enum, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship

from policy_engine.database import Base


class OrgType(str, enum.Enum):
    """Healthcare organization type."""
    HOSPITAL = "hospital"
    PAYER = "payer"
    MEDTECH = "medtech"


class Organization(Base):
    """
    Represents a tenant (hospital, payer, or MedTech company).

    All platform resources are scoped to an organization.  The `slug` is
    URL-safe and unique — used for subdomain routing and display.
    """
    __tablename__ = "organizations"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False, index=True)
    org_type = Column(Enum(OrgType), nullable=False, default=OrgType.HOSPITAL)
    settings = Column(JSON, nullable=True, default=dict)
    hipaa_baa_signed = Column(Boolean, nullable=False, default=False)
    hipaa_baa_date = Column(DateTime, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    members = relationship("OrganizationMember", back_populates="organization", cascade="all, delete-orphan")


class OrganizationMember(Base):
    """Maps users to organizations with a role."""
    __tablename__ = "organization_members"

    id = Column(String, primary_key=True, index=True)
    org_id = Column(String, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String, nullable=False, default="member")
    invited_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    joined_at = Column(DateTime, nullable=True)

    organization = relationship("Organization", back_populates="members")

    __table_args__ = (
        UniqueConstraint("org_id", "user_id", name="uq_org_member"),
    )
