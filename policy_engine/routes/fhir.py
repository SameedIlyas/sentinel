"""FHIR R4 ingestion and cache routes."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from policy_engine.auth.rbac import get_current_user
from policy_engine.database import get_db
from policy_engine.models.user import User, UserRole
from policy_engine.services.fhir_service import FHIRParserService

router = APIRouter()

_ALLOWED_INGEST_ROLES = {UserRole.COMPLIANCE_OFFICER, UserRole.DATA_SCIENTIST}
_ALLOWED_READ_ROLES = {
    UserRole.COMPLIANCE_OFFICER,
    UserRole.DATA_SCIENTIST,
    UserRole.CMIO,
}


def _require_ingest_role(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in _ALLOWED_INGEST_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to ingest FHIR data",
        )
    return current_user


def _require_read_role(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in _ALLOWED_READ_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to read FHIR cache",
        )
    return current_user


class FHIRIngestResponse(BaseModel):
    count: int
    message: str


class FHIRCacheItem(BaseModel):
    id: str
    resource_type: str
    fhir_id: str
    payload: Dict[str, Any]


@router.post(
    "/fhir/ingest",
    response_model=FHIRIngestResponse,
    status_code=status.HTTP_200_OK,
)
def ingest_fhir(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_ingest_role),
) -> FHIRIngestResponse:
    """Ingest a FHIR Bundle or individual resource; de-identify and cache."""
    svc = FHIRParserService()
    try:
        count = svc.ingest_bundle(payload, db=db)
        db.commit()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"FHIR ingestion failed: {exc}",
        ) from exc
    return FHIRIngestResponse(
        count=count,
        message=f"Ingested {count} FHIR resource(s)",
    )


@router.get(
    "/fhir/cache",
    response_model=List[FHIRCacheItem],
    status_code=status.HTTP_200_OK,
)
def list_fhir_cache(
    skip: int = 0,
    limit: int = 50,
    resource_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_read_role),
) -> List[FHIRCacheItem]:
    """Return paginated, de-identified FHIR records from cache."""
    from policy_engine.models.fhir_cache import FHIRResourceCache

    query = db.query(FHIRResourceCache)
    if resource_type:
        query = query.filter(FHIRResourceCache.resource_type == resource_type)
    rows = query.offset(skip).limit(limit).all()
    return [
        FHIRCacheItem(
            id=row.id,
            resource_type=row.resource_type,
            fhir_id=row.fhir_id,
            payload=row.payload or {},
        )
        for row in rows
    ]
