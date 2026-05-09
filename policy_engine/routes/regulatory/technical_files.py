"""Technical File routes — FDA 510(k) and EU MDR regulatory automation."""
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from policy_engine.auth.rbac import get_current_user
from policy_engine.database import get_db
from policy_engine.domain.regulatory.technical_file import (
    RegulatoryType,
    TechnicalFileEntity,
    TechnicalFileLifecycle,
    auto_generate_sections,
)
from policy_engine.models.technical_file import (
    RegulatoryTypeDB,
    TechnicalFile,
    TechnicalFileLifecycleDB,
    TechnicalFileSection,
    TechnicalFileVersion,
)
from policy_engine.models.user import has_permission

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class TechnicalFileCreate(BaseModel):
    title: str
    regulatory_type: str
    product_name: str
    device_version: str
    auto_generate: bool = False


class TechnicalFileUpdate(BaseModel):
    title: Optional[str] = None
    product_name: Optional[str] = None
    device_version: Optional[str] = None


class SectionCreate(BaseModel):
    section_type: str
    content: str
    order_index: int = 0


class SectionUpdate(BaseModel):
    content: Optional[str] = None
    order_index: Optional[int] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _file_to_dict(f: TechnicalFile) -> dict:
    return {
        "id": f.id,
        "title": f.title,
        "regulatory_type": f.regulatory_type,
        "product_name": f.product_name,
        "device_version": f.device_version,
        "lifecycle_stage": f.lifecycle_stage,
        "created_by": f.created_by,
        "organization_id": f.organization_id,
        "created_at": f.created_at.isoformat(),
        "updated_at": f.updated_at.isoformat() if f.updated_at else None,
    }


def _section_to_dict(s: TechnicalFileSection) -> dict:
    return {
        "id": s.id,
        "file_id": s.file_id,
        "section_type": s.section_type,
        "content": s.content,
        "order_index": s.order_index,
        "auto_generated": s.auto_generated,
        "created_at": s.created_at.isoformat(),
    }


def _get_file_or_404(db: Session, file_id: str, org_id: Optional[str]) -> TechnicalFile:
    f = db.query(TechnicalFile).filter(
        TechnicalFile.id == file_id,
        TechnicalFile.organization_id == org_id,
    ).first()
    if not f:
        raise HTTPException(404, "Technical file not found")
    return f


# ---------------------------------------------------------------------------
# Routes — specific paths MUST come before /{file_id}
# ---------------------------------------------------------------------------


@router.get("/technical-files/stats")
def technical_file_stats(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not has_permission(current_user.role, "technical_files", "read"):
        raise HTTPException(403, "Forbidden")

    files = db.query(TechnicalFile).filter(
        TechnicalFile.organization_id == current_user.organization_id
    ).all()

    by_lifecycle: dict = {}
    by_type: dict = {}
    for f in files:
        stage = str(f.lifecycle_stage)
        by_lifecycle[stage] = by_lifecycle.get(stage, 0) + 1
        rtype = str(f.regulatory_type)
        by_type[rtype] = by_type.get(rtype, 0) + 1

    return {
        "total_files": len(files),
        "by_lifecycle": by_lifecycle,
        "by_regulatory_type": by_type,
    }


@router.post("/technical-files", status_code=201)
def create_technical_file(
    body: TechnicalFileCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not has_permission(current_user.role, "technical_files", "create"):
        raise HTTPException(403, "Forbidden")

    # Validate regulatory_type
    try:
        reg_type = RegulatoryTypeDB(body.regulatory_type)
    except ValueError:
        raise HTTPException(400, f"Invalid regulatory_type: {body.regulatory_type}")

    now = datetime.utcnow()
    file_id = str(uuid.uuid4())

    tf = TechnicalFile(
        id=file_id,
        title=body.title,
        regulatory_type=reg_type,
        product_name=body.product_name,
        device_version=body.device_version,
        lifecycle_stage=TechnicalFileLifecycleDB.DRAFT,
        created_by=current_user.id,
        organization_id=current_user.organization_id,
        created_at=now,
        updated_at=now,
    )
    db.add(tf)

    # Optionally auto-generate sections
    if body.auto_generate:
        domain_type = RegulatoryType(body.regulatory_type)
        gen_sections = auto_generate_sections(
            domain_type, body.product_name, body.device_version
        )
        for s in gen_sections:
            db.add(TechnicalFileSection(
                id=str(uuid.uuid4()),
                file_id=file_id,
                section_type=s.section_type,
                content=s.content,
                order_index=s.order_index,
                auto_generated=s.auto_generated,
                created_at=now,
                updated_at=now,
            ))

    db.commit()
    db.refresh(tf)
    return _file_to_dict(tf)


@router.get("/technical-files")
def list_technical_files(
    regulatory_type: Optional[str] = Query(None),
    lifecycle_stage: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not has_permission(current_user.role, "technical_files", "read"):
        raise HTTPException(403, "Forbidden")

    q = db.query(TechnicalFile).filter(
        TechnicalFile.organization_id == current_user.organization_id
    )
    if regulatory_type:
        q = q.filter(TechnicalFile.regulatory_type == regulatory_type)
    if lifecycle_stage:
        q = q.filter(TechnicalFile.lifecycle_stage == lifecycle_stage)

    return [_file_to_dict(f) for f in q.order_by(TechnicalFile.created_at.desc()).all()]


@router.get("/technical-files/{file_id}")
def get_technical_file(
    file_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not has_permission(current_user.role, "technical_files", "read"):
        raise HTTPException(403, "Forbidden")
    return _file_to_dict(_get_file_or_404(db, file_id, current_user.organization_id))


@router.patch("/technical-files/{file_id}")
def update_technical_file(
    file_id: str,
    body: TechnicalFileUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not has_permission(current_user.role, "technical_files", "update"):
        raise HTTPException(403, "Forbidden")

    tf = _get_file_or_404(db, file_id, current_user.organization_id)

    if tf.lifecycle_stage not in (
        TechnicalFileLifecycleDB.DRAFT, TechnicalFileLifecycleDB.SUBMITTED
    ):
        raise HTTPException(409, "Cannot update a file that is under review, approved, or retired")

    if body.title is not None:
        tf.title = body.title
    if body.product_name is not None:
        tf.product_name = body.product_name
    if body.device_version is not None:
        tf.device_version = body.device_version
    tf.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(tf)
    return _file_to_dict(tf)


@router.post("/technical-files/{file_id}/submit")
def submit_technical_file(
    file_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Transition file from DRAFT → SUBMITTED."""
    if not has_permission(current_user.role, "technical_files", "update"):
        raise HTTPException(403, "Forbidden")

    tf = _get_file_or_404(db, file_id, current_user.organization_id)

    # Use domain entity for transition validation
    entity = TechnicalFileEntity(
        id=tf.id,
        title=tf.title,
        regulatory_type=RegulatoryType(tf.regulatory_type),
        product_name=tf.product_name,
        device_version=tf.device_version,
        lifecycle_stage=TechnicalFileLifecycle(tf.lifecycle_stage),
    )

    try:
        entity.transition_to(TechnicalFileLifecycle.SUBMITTED)
    except ValueError as exc:
        raise HTTPException(409, str(exc))

    tf.lifecycle_stage = TechnicalFileLifecycleDB.SUBMITTED
    tf.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(tf)
    return _file_to_dict(tf)


@router.post("/technical-files/{file_id}/sections", status_code=201)
def add_section(
    file_id: str,
    body: SectionCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not has_permission(current_user.role, "technical_files", "update"):
        raise HTTPException(403, "Forbidden")

    _get_file_or_404(db, file_id, current_user.organization_id)

    now = datetime.utcnow()
    section = TechnicalFileSection(
        id=str(uuid.uuid4()),
        file_id=file_id,
        section_type=body.section_type,
        content=body.content,
        order_index=body.order_index,
        auto_generated=False,
        created_at=now,
        updated_at=now,
    )
    db.add(section)
    db.commit()
    db.refresh(section)
    return _section_to_dict(section)


@router.get("/technical-files/{file_id}/sections")
def list_sections(
    file_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not has_permission(current_user.role, "technical_files", "read"):
        raise HTTPException(403, "Forbidden")

    _get_file_or_404(db, file_id, current_user.organization_id)

    sections = db.query(TechnicalFileSection).filter(
        TechnicalFileSection.file_id == file_id
    ).order_by(TechnicalFileSection.order_index).all()
    return [_section_to_dict(s) for s in sections]


@router.put("/technical-files/{file_id}/sections/{section_id}")
def update_section(
    file_id: str,
    section_id: str,
    body: SectionUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not has_permission(current_user.role, "technical_files", "update"):
        raise HTTPException(403, "Forbidden")

    _get_file_or_404(db, file_id, current_user.organization_id)

    section = db.query(TechnicalFileSection).filter(
        TechnicalFileSection.id == section_id,
        TechnicalFileSection.file_id == file_id,
    ).first()
    if not section:
        raise HTTPException(404, "Section not found")

    if body.content is not None:
        section.content = body.content
    if body.order_index is not None:
        section.order_index = body.order_index
    section.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(section)
    return _section_to_dict(section)


@router.post("/technical-files/{file_id}/versions", status_code=201)
def create_version_snapshot(
    file_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Create an immutable version snapshot of the current file state."""
    if not has_permission(current_user.role, "technical_files", "update"):
        raise HTTPException(403, "Forbidden")

    tf = _get_file_or_404(db, file_id, current_user.organization_id)

    # Determine version number
    last_version = db.query(TechnicalFileVersion).filter(
        TechnicalFileVersion.file_id == file_id
    ).order_by(TechnicalFileVersion.version_number.desc()).first()
    version_number = (last_version.version_number + 1) if last_version else 1

    # Gather all sections
    sections = db.query(TechnicalFileSection).filter(
        TechnicalFileSection.file_id == file_id
    ).order_by(TechnicalFileSection.order_index).all()

    snapshot = {
        "id": tf.id,
        "title": tf.title,
        "regulatory_type": str(tf.regulatory_type),
        "product_name": tf.product_name,
        "device_version": tf.device_version,
        "lifecycle_stage": str(tf.lifecycle_stage),
        "sections": [
            {
                "section_type": s.section_type,
                "content": s.content,
                "order_index": s.order_index,
                "auto_generated": s.auto_generated,
            }
            for s in sections
        ],
    }

    version = TechnicalFileVersion(
        id=str(uuid.uuid4()),
        file_id=file_id,
        version_number=version_number,
        snapshot_json=snapshot,
        created_by=current_user.id,
        created_at=datetime.utcnow(),
    )
    db.add(version)
    db.commit()
    db.refresh(version)

    return {
        "id": version.id,
        "file_id": version.file_id,
        "version_number": version.version_number,
        "snapshot_json": version.snapshot_json,
        "created_by": version.created_by,
        "created_at": version.created_at.isoformat(),
    }


@router.get("/technical-files/{file_id}/versions")
def list_versions(
    file_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not has_permission(current_user.role, "technical_files", "read"):
        raise HTTPException(403, "Forbidden")

    _get_file_or_404(db, file_id, current_user.organization_id)

    versions = db.query(TechnicalFileVersion).filter(
        TechnicalFileVersion.file_id == file_id
    ).order_by(TechnicalFileVersion.version_number.desc()).all()

    return [
        {
            "id": v.id,
            "file_id": v.file_id,
            "version_number": v.version_number,
            "created_by": v.created_by,
            "created_at": v.created_at.isoformat(),
        }
        for v in versions
    ]
