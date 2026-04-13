"""DICOM de-identification and metadata routes."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from policy_engine.auth.rbac import get_current_user
from policy_engine.config import settings
from policy_engine.database import get_db
from policy_engine.models.user import User, UserRole
from policy_engine.services.dicom_service import (
    DICOMDeidentificationService,
    DICOMParseError,
    FileTooLargeError,
)

router = APIRouter()

_ALLOWED_EXTRACT_ROLES = {UserRole.DATA_SCIENTIST, UserRole.CMIO}
_ALLOWED_READ_ROLES = {
    UserRole.DATA_SCIENTIST,
    UserRole.CMIO,
    UserRole.COMPLIANCE_OFFICER,
}

_DICOM_CONTENT_TYPE = "application/dicom"


def _require_extract_role(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in _ALLOWED_EXTRACT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to extract DICOM metadata",
        )
    return current_user


def _require_read_role(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in _ALLOWED_READ_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to read DICOM metadata",
        )
    return current_user


class DICOMExtractResponse(BaseModel):
    id: str
    modality: Optional[str]
    manufacturer: Optional[str]
    study_description: Optional[str]
    sop_class_uid: Optional[str]
    study_year: Optional[int]
    patient_sex: Optional[str]
    body_part: Optional[str]
    additional_tags: Dict[str, Any] = {}


class DICOMMetadataListItem(BaseModel):
    id: str
    modality: Optional[str]
    safe_metadata: Dict[str, Any]
    extracted_at: datetime


@router.post(
    "/dicom/extract",
    response_model=DICOMExtractResponse,
    status_code=status.HTTP_200_OK,
)
async def extract_dicom_metadata(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_extract_role),
) -> DICOMExtractResponse:
    """Upload a DICOM file; returns de-identified metadata. Never returns pixel data."""
    # Content-type guard
    content_type = file.content_type or ""
    if content_type != _DICOM_CONTENT_TYPE:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Expected content-type {_DICOM_CONTENT_TYPE!r}, got {content_type!r}",
        )

    raw_bytes = await file.read()

    svc = DICOMDeidentificationService()
    try:
        result = svc.deidentify_metadata(raw_bytes)
    except FileTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(exc),
        ) from exc
    except DICOMParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    # Persist to dicom_metadata table
    record_id = str(uuid.uuid4())
    _persist_dicom_record(record_id, result, db)

    return DICOMExtractResponse(
        id=record_id,
        modality=result.modality,
        manufacturer=result.manufacturer,
        study_description=result.study_description,
        sop_class_uid=result.sop_class_uid,
        study_year=result.study_year,
        patient_sex=result.patient_sex,
        body_part=result.body_part,
        additional_tags=result.additional_tags,
    )


@router.get(
    "/dicom/metadata",
    response_model=List[DICOMMetadataListItem],
    status_code=status.HTTP_200_OK,
)
def list_dicom_metadata(
    skip: int = 0,
    limit: int = 50,
    modality: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_read_role),
) -> List[DICOMMetadataListItem]:
    """Return paginated de-identified DICOM metadata records."""
    from policy_engine.models.dicom_metadata import DICOMMetadataRecord

    query = db.query(DICOMMetadataRecord)
    if modality:
        query = query.filter(DICOMMetadataRecord.modality == modality)
    rows = query.offset(skip).limit(limit).all()
    return [
        DICOMMetadataListItem(
            id=row.id,
            modality=row.modality,
            safe_metadata=row.safe_metadata or {},
            extracted_at=row.extracted_at,
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _persist_dicom_record(
    record_id: str,
    result: Any,
    db: Session,
) -> None:
    from policy_engine.models.dicom_metadata import DICOMMetadataRecord

    safe_meta: Dict[str, Any] = {
        "modality": result.modality,
        "manufacturer": result.manufacturer,
        "study_description": result.study_description,
        "sop_class_uid": result.sop_class_uid,
        "study_year": result.study_year,
        "patient_sex": result.patient_sex,
        "body_part": result.body_part,
        **result.additional_tags,
    }
    record = DICOMMetadataRecord(
        id=record_id,
        modality=result.modality,
        safe_metadata=safe_meta,
        extracted_at=datetime.utcnow(),
    )
    db.add(record)
    db.commit()
