"""Transparency Portal routes — /v1/transparency/*"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import uuid

from policy_engine.database import get_db
from policy_engine.auth.rbac import get_current_user, get_current_user_optional
from policy_engine.models.user import User, UserRole
from policy_engine.models.transparency import (
    TransparencyRecordModel,
    TransparencyVersion,
    TransparencyAcknowledgment,
)
from policy_engine.domain.admin.transparency import (
    TransparencyRecord as TransparencyRecordDomain,
    validate_record,
    generate_version_snapshot,
)
from pydantic import BaseModel, validator

router = APIRouter(prefix="/transparency", tags=["transparency"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class TransparencyCreate(BaseModel):
    model_name: str
    model_version: str
    algorithm_description: Optional[str] = None
    plain_language_summary: str
    evidence_base: Optional[str] = None
    intended_population: str
    known_limitations: str
    performance_summary: Optional[dict] = None
    bias_considerations: Optional[str] = None
    regulatory_status: Optional[str] = None

    @validator("plain_language_summary")
    def summary_min_length(cls, v: str) -> str:
        if len(v) < 50:
            raise ValueError("plain_language_summary must be at least 50 characters")
        return v


class AcknowledgeRequest(BaseModel):
    user_id: Optional[str] = None
    role: Optional[str] = None


class TransparencyResponse(BaseModel):
    id: str
    model_name: str
    model_version: str
    algorithm_description: Optional[str]
    plain_language_summary: str
    evidence_base: Optional[str]
    intended_population: str
    known_limitations: str
    performance_summary: Optional[dict]
    bias_considerations: Optional[str]
    regulatory_status: Optional[str]
    published_at: Optional[datetime]
    version_number: int
    organization_id: Optional[str]
    created_by: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class VersionResponse(BaseModel):
    id: str
    record_id: str
    version_number: int
    content_snapshot: dict
    change_summary: Optional[str]
    published_by: Optional[str]
    published_at: datetime

    class Config:
        from_attributes = True


class AcknowledgmentResponse(BaseModel):
    id: str
    record_id: str
    acknowledged_by: Optional[str]
    acknowledged_at: datetime
    role_at_time: Optional[str]

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_admin(current_user: Optional[User]) -> None:
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    admin_roles = {UserRole.SYSTEM_ADMIN, UserRole.ORG_ADMIN}
    if current_user.role not in admin_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required to manage transparency records",
        )


def _to_domain(payload: TransparencyCreate) -> TransparencyRecordDomain:
    return TransparencyRecordDomain(
        model_name=payload.model_name,
        model_version=payload.model_version,
        algorithm_description=payload.algorithm_description or "",
        plain_language_summary=payload.plain_language_summary,
        evidence_base=payload.evidence_base or "",
        intended_population=payload.intended_population,
        known_limitations=payload.known_limitations,
        performance_summary=payload.performance_summary or {},
        bias_considerations=payload.bias_considerations,
        regulatory_status=payload.regulatory_status,
    )


# ---------------------------------------------------------------------------
# Routes — specific paths BEFORE parameterized /{record_id}
# ---------------------------------------------------------------------------

@router.get("", response_model=List[TransparencyResponse])
def list_transparency_records(
    db: Session = Depends(get_db),
):
    """List all published transparency records. No authentication required."""
    return (
        db.query(TransparencyRecordModel)
        .filter(TransparencyRecordModel.published_at.isnot(None))
        .order_by(TransparencyRecordModel.published_at.desc())
        .all()
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=TransparencyResponse)
def create_transparency_record(
    payload: TransparencyCreate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Create a transparency record. Requires admin role."""
    _require_admin(current_user)

    domain_record = _to_domain(payload)
    errors = validate_record(domain_record)
    if errors:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=errors)

    now = datetime.utcnow()
    record = TransparencyRecordModel(
        id=str(uuid.uuid4()),
        model_name=payload.model_name,
        model_version=payload.model_version,
        algorithm_description=payload.algorithm_description,
        plain_language_summary=payload.plain_language_summary,
        evidence_base=payload.evidence_base,
        intended_population=payload.intended_population,
        known_limitations=payload.known_limitations,
        performance_summary=payload.performance_summary or {},
        bias_considerations=payload.bias_considerations,
        regulatory_status=payload.regulatory_status,
        published_at=None,
        version_number=1,
        organization_id=current_user.organization_id,
        created_by=current_user.id,
        created_at=now,
        updated_at=now,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.post("/{record_id}/publish", response_model=TransparencyResponse)
def publish_transparency_record(
    record_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Publish a transparency record and create a version snapshot."""
    _require_admin(current_user)

    record = db.query(TransparencyRecordModel).filter(TransparencyRecordModel.id == record_id).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")

    now = datetime.utcnow()
    record.published_at = now
    record.updated_at = now

    # Create version snapshot
    domain_record = TransparencyRecordDomain(
        model_name=record.model_name,
        model_version=record.model_version,
        algorithm_description=record.algorithm_description or "",
        plain_language_summary=record.plain_language_summary,
        evidence_base=record.evidence_base or "",
        intended_population=record.intended_population,
        known_limitations=record.known_limitations,
        performance_summary=record.performance_summary or {},
        bias_considerations=record.bias_considerations,
        regulatory_status=record.regulatory_status,
    )
    snapshot = generate_version_snapshot(domain_record)

    version = TransparencyVersion(
        id=str(uuid.uuid4()),
        record_id=record.id,
        version_number=record.version_number,
        content_snapshot=snapshot,
        change_summary="Initial publication",
        published_by=current_user.id,
        published_at=now,
    )
    db.add(version)
    db.commit()
    db.refresh(record)
    return record


@router.post("/{record_id}/acknowledge", status_code=status.HTTP_201_CREATED)
def acknowledge_transparency_record(
    record_id: str,
    payload: AcknowledgeRequest,
    db: Session = Depends(get_db),
):
    """Acknowledge a transparency record. No authentication required."""
    record = db.query(TransparencyRecordModel).filter(TransparencyRecordModel.id == record_id).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")

    now = datetime.utcnow()
    ack = TransparencyAcknowledgment(
        id=str(uuid.uuid4()),
        record_id=record_id,
        acknowledged_by=payload.user_id,
        acknowledged_at=now,
        role_at_time=payload.role,
    )
    db.add(ack)
    db.commit()
    db.refresh(ack)
    return {
        "id": ack.id,
        "record_id": ack.record_id,
        "acknowledged_by": ack.acknowledged_by,
        "acknowledged_at": ack.acknowledged_at,
        "role_at_time": ack.role_at_time,
    }


@router.get("/{record_id}/versions", response_model=List[VersionResponse])
def get_versions(
    record_id: str,
    db: Session = Depends(get_db),
):
    """Get all version snapshots for a record. No authentication required."""
    record = db.query(TransparencyRecordModel).filter(TransparencyRecordModel.id == record_id).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")

    return (
        db.query(TransparencyVersion)
        .filter(TransparencyVersion.record_id == record_id)
        .order_by(TransparencyVersion.version_number)
        .all()
    )


@router.get("/{record_id}", response_model=TransparencyResponse)
def get_transparency_record(
    record_id: str,
    db: Session = Depends(get_db),
):
    """Get a single transparency record. No authentication required."""
    record = db.query(TransparencyRecordModel).filter(TransparencyRecordModel.id == record_id).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    return record


@router.put("/{record_id}", response_model=TransparencyResponse)
def update_transparency_record(
    record_id: str,
    payload: TransparencyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a transparency record and create a version snapshot."""
    _require_admin(current_user)

    record = db.query(TransparencyRecordModel).filter(TransparencyRecordModel.id == record_id).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")

    domain_record = _to_domain(payload)
    errors = validate_record(domain_record)
    if errors:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=errors)

    # Update fields
    record.model_name = payload.model_name
    record.model_version = payload.model_version
    record.algorithm_description = payload.algorithm_description
    record.plain_language_summary = payload.plain_language_summary
    record.evidence_base = payload.evidence_base
    record.intended_population = payload.intended_population
    record.known_limitations = payload.known_limitations
    record.performance_summary = payload.performance_summary or {}
    record.bias_considerations = payload.bias_considerations
    record.regulatory_status = payload.regulatory_status
    record.updated_at = datetime.utcnow()

    # Create version snapshot
    snapshot = generate_version_snapshot(domain_record)
    version = TransparencyVersion(
        id=str(uuid.uuid4()),
        record_id=record.id,
        version_number=record.version_number,
        content_snapshot=snapshot,
        change_summary="Record updated",
        published_by=current_user.id,
        published_at=datetime.utcnow(),
    )
    db.add(version)
    db.commit()
    db.refresh(record)
    return record
