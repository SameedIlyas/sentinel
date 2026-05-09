"""Organizations CRUD endpoints for multi-tenancy."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid
from datetime import datetime

from policy_engine.database import get_db
from policy_engine.auth.rbac import get_current_user
from policy_engine.models.organization import Organization, OrganizationMember
from policy_engine.models.user import User, UserRole
from pydantic import BaseModel

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class OrganizationCreate(BaseModel):
    name: str
    slug: str
    org_type: str = "hospital"
    hipaa_baa_signed: bool = False
    settings: Optional[dict] = None


class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    org_type: Optional[str] = None
    hipaa_baa_signed: Optional[bool] = None
    is_active: Optional[bool] = None
    settings: Optional[dict] = None


class OrganizationResponse(BaseModel):
    id: str
    name: str
    slug: str
    org_type: str
    hipaa_baa_signed: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MemberAddRequest(BaseModel):
    user_id: str
    role: str = "member"


class MemberResponse(BaseModel):
    id: str
    org_id: str
    user_id: str
    role: str
    invited_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_admin(current_user: User) -> None:
    admin_roles = {UserRole.SYSTEM_ADMIN, UserRole.ORG_ADMIN}
    if current_user.role not in admin_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("", response_model=List[OrganizationResponse])
def list_organizations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all organizations (admin sees all; others see their own)."""
    if current_user.role == UserRole.SYSTEM_ADMIN:
        return db.query(Organization).all()
    if current_user.organization_id:
        org = db.query(Organization).filter(Organization.id == current_user.organization_id).first()
        return [org] if org else []
    return []


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: OrganizationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new organization (admin only)."""
    _require_admin(current_user)
    existing = db.query(Organization).filter(Organization.slug == payload.slug).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slug already in use")

    now = datetime.utcnow()
    org = Organization(
        id=str(uuid.uuid4()),
        name=payload.name,
        slug=payload.slug,
        org_type=payload.org_type,
        hipaa_baa_signed=payload.hipaa_baa_signed,
        settings=payload.settings or {},
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


@router.get("/{org_id}", response_model=OrganizationResponse)
def get_organization(
    org_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single organization by ID."""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return org


@router.put("/{org_id}", response_model=OrganizationResponse)
def update_organization(
    org_id: str,
    payload: OrganizationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an organization (admin only)."""
    _require_admin(current_user)
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    update_data = payload.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(org, field, value)
    org.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(org)
    return org


@router.delete("/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_organization(
    org_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an organization (admin only)."""
    _require_admin(current_user)
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    db.delete(org)
    db.commit()


@router.post("/{org_id}/members", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
def add_member(
    org_id: str,
    payload: MemberAddRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a user to an organization."""
    _require_admin(current_user)
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    existing = (
        db.query(OrganizationMember)
        .filter(OrganizationMember.org_id == org_id, OrganizationMember.user_id == payload.user_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already a member")

    member = OrganizationMember(
        id=str(uuid.uuid4()),
        org_id=org_id,
        user_id=payload.user_id,
        role=payload.role,
        invited_at=datetime.utcnow(),
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return member
