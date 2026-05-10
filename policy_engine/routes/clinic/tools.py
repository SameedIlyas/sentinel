"""Manual AI tool registry — clinic-tier feature.

A lightweight ``ModelCard`` alternative.  Single-clinic owners do not have
ML registries to sync from; they need a form they can fill in 30 seconds.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from policy_engine.auth.rbac import get_current_user
from policy_engine.database import get_db
from policy_engine.models.clinic import (
    ClinicAiTool,
    ClinicAiToolCategory,
    ClinicAiToolRisk,
    ClinicAiToolStatus,
)
from policy_engine.models.organization import Organization
from policy_engine.models.user import User
from policy_engine.services.clinic_audit import write_clinic_audit
from policy_engine.services.phi_text_check import reject_if_phi_present
from policy_engine.services.tier_filter import (
    require_clinic_tier,
    require_clinic_tier_with_baa,
)

router = APIRouter()


# ── Schemas ─────────────────────────────────────────────────────────────

class ToolCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    vendor: Optional[str] = Field(None, max_length=255)
    category: ClinicAiToolCategory = ClinicAiToolCategory.OTHER
    purpose: Optional[str] = Field(None, max_length=2000)
    handles_phi: bool = False
    risk_level: ClinicAiToolRisk = ClinicAiToolRisk.LOW
    notes: Optional[str] = Field(None, max_length=2000)


class ToolUpdate(BaseModel):
    name: Optional[str] = None
    vendor: Optional[str] = None
    category: Optional[ClinicAiToolCategory] = None
    purpose: Optional[str] = None
    handles_phi: Optional[bool] = None
    risk_level: Optional[ClinicAiToolRisk] = None
    status: Optional[ClinicAiToolStatus] = None
    notes: Optional[str] = None


class ToolResponse(BaseModel):
    id: str
    org_id: str
    name: str
    vendor: Optional[str]
    category: str
    purpose: Optional[str]
    handles_phi: bool
    risk_level: str
    status: str
    owner_user_id: Optional[str]
    notes: Optional[str]
    source: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ── Routes ──────────────────────────────────────────────────────────────

@router.get("/tools", response_model=list[ToolResponse])
def list_tools(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_clinic_tier),
):
    return (
        db.query(ClinicAiTool)
        .filter(ClinicAiTool.org_id == org.id)
        .order_by(ClinicAiTool.created_at.desc())
        .all()
    )


@router.post(
    "/tools",
    response_model=ToolResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_tool(
    payload: ToolCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_clinic_tier_with_baa),
):
    # HIPAA safeguard — refuse free-text fields that look like PHI before
    # we ever persist them.
    reject_if_phi_present(
        {
            "name": payload.name,
            "vendor": payload.vendor,
            "purpose": payload.purpose,
            "notes": payload.notes,
        }
    )
    now = datetime.utcnow()
    tool = ClinicAiTool(
        id=str(uuid.uuid4()),
        org_id=org.id,
        name=payload.name,
        vendor=payload.vendor,
        category=payload.category,
        purpose=payload.purpose,
        handles_phi=payload.handles_phi,
        risk_level=payload.risk_level,
        status=ClinicAiToolStatus.ACTIVE,
        owner_user_id=current_user.id,
        notes=payload.notes,
        source="manual",
        created_at=now,
        updated_at=now,
    )
    db.add(tool)
    write_clinic_audit(
        db,
        user=current_user,
        org_id=org.id,
        action="clinic.tool.create",
        system="clinic.tools",
        data_touched=[tool.id],
        reason="Clinic AI tool registered",
        metadata={"category": payload.category.value, "handles_phi": payload.handles_phi},
    )
    db.commit()
    db.refresh(tool)
    return tool


@router.get("/tools/{tool_id}", response_model=ToolResponse)
def get_tool(
    tool_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_clinic_tier),
):
    tool = (
        db.query(ClinicAiTool)
        .filter(ClinicAiTool.id == tool_id, ClinicAiTool.org_id == org.id)
        .first()
    )
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return tool


@router.put("/tools/{tool_id}", response_model=ToolResponse)
def update_tool(
    tool_id: str,
    payload: ToolUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_clinic_tier_with_baa),
):
    tool = (
        db.query(ClinicAiTool)
        .filter(ClinicAiTool.id == tool_id, ClinicAiTool.org_id == org.id)
        .first()
    )
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    update_dict = payload.dict(exclude_unset=True)
    reject_if_phi_present(
        {
            "name": update_dict.get("name"),
            "vendor": update_dict.get("vendor"),
            "purpose": update_dict.get("purpose"),
            "notes": update_dict.get("notes"),
        }
    )
    for field_name, value in update_dict.items():
        setattr(tool, field_name, value)
    tool.updated_at = datetime.utcnow()
    write_clinic_audit(
        db,
        user=current_user,
        org_id=org.id,
        action="clinic.tool.update",
        system="clinic.tools",
        data_touched=[tool.id],
        reason="Clinic AI tool updated",
        metadata={"fields": sorted(update_dict.keys())},
    )
    db.commit()
    db.refresh(tool)
    return tool


@router.delete("/tools/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tool(
    tool_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_clinic_tier),
):
    tool = (
        db.query(ClinicAiTool)
        .filter(ClinicAiTool.id == tool_id, ClinicAiTool.org_id == org.id)
        .first()
    )
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    db.delete(tool)
    write_clinic_audit(
        db,
        user=current_user,
        org_id=org.id,
        action="clinic.tool.delete",
        system="clinic.tools",
        data_touched=[tool_id],
        reason="Clinic AI tool removed",
    )
    db.commit()
