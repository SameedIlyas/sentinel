"""Manual AI tool registry — clinic-tier feature.

A lightweight ``ModelCard`` alternative.  Single-clinic owners do not have
ML registries to sync from; they need a form they can fill in 30 seconds.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, ValidationInfo, field_validator
from sqlalchemy.orm import Session

from policy_engine.auth.rbac import get_current_user
from policy_engine.database import get_db
from policy_engine.models.alert import Alert, AlertSeverity
from policy_engine.models.clinic import (
    ClinicAiTool,
    ClinicAiToolCategory,
    ClinicAiToolModelTrainingStatus,
    ClinicAiToolPracticeOptOutState,
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

# Admin-only product roles permitted to write practice_opt_out_state == 'verified'.
# Matches HEALTH-5 / PRD.v2.md §6.8.2.a — only the practice owner can sign
# off on the verification, never staff.
_ADMIN_ROLES: frozenset[str] = frozenset({"admin", "system_admin"})

# Idempotency window for clinic.tool.trains_on_data alerts. Flipping the
# status field back and forth must not flood the queue (PRD.v2.md §6.8.2.c).
_TRAINS_ON_DATA_WINDOW = timedelta(days=30)
_TRAINS_ON_DATA_ALERT_TYPE = "clinic.tool.trains_on_data"


# ── Schemas ─────────────────────────────────────────────────────────────

def _check_admin_only_verified(
    value: ClinicAiToolPracticeOptOutState | None,
    info: ValidationInfo,
) -> ClinicAiToolPracticeOptOutState | None:
    """Shared validator — only Admin product-role may write 'verified'.

    Uses Pydantic ``ValidationInfo.context`` rather than a global so the
    rule is enforced at the schema boundary, before any DB write.
    Falls open (passes through) when no ``current_user`` is supplied in
    context — the route layer is responsible for actually calling
    ``model_validate(payload, context={...})``.
    """
    if value != ClinicAiToolPracticeOptOutState.VERIFIED:
        return value
    user = (info.context or {}).get("current_user") if info.context else None
    if user is None:
        return value
    role = getattr(user, "role", None)
    role_value = getattr(role, "value", role)
    if role_value not in _ADMIN_ROLES:
        raise ValueError("only Admin may mark opt-out verified")
    return value


class ToolCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    vendor: Optional[str] = Field(None, max_length=255)
    category: ClinicAiToolCategory = ClinicAiToolCategory.OTHER
    purpose: Optional[str] = Field(None, max_length=2000)
    handles_phi: bool = False
    risk_level: ClinicAiToolRisk = ClinicAiToolRisk.LOW
    notes: Optional[str] = Field(None, max_length=2000)
    model_training_status: ClinicAiToolModelTrainingStatus = (
        ClinicAiToolModelTrainingStatus.UNKNOWN
    )
    practice_opt_out_state: ClinicAiToolPracticeOptOutState = (
        ClinicAiToolPracticeOptOutState.NOT_APPLICABLE
    )
    model_training_status_evidence: Optional[str] = Field(None, max_length=2000)

    @field_validator("practice_opt_out_state")
    @classmethod
    def _admin_only_verified(cls, v, info):  # noqa: D401
        return _check_admin_only_verified(v, info)


class ToolUpdate(BaseModel):
    name: Optional[str] = None
    vendor: Optional[str] = None
    category: Optional[ClinicAiToolCategory] = None
    purpose: Optional[str] = None
    handles_phi: Optional[bool] = None
    risk_level: Optional[ClinicAiToolRisk] = None
    status: Optional[ClinicAiToolStatus] = None
    notes: Optional[str] = None
    model_training_status: Optional[ClinicAiToolModelTrainingStatus] = None
    practice_opt_out_state: Optional[ClinicAiToolPracticeOptOutState] = None
    model_training_status_evidence: Optional[str] = Field(None, max_length=2000)

    @field_validator("practice_opt_out_state")
    @classmethod
    def _admin_only_verified(cls, v, info):  # noqa: D401
        return _check_admin_only_verified(v, info)


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
    model_training_status: str
    practice_opt_out_state: str
    opt_out_verified_at: Optional[datetime]
    opt_out_verified_by_user_id: Optional[str]
    model_training_status_evidence: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


def _maybe_emit_trains_on_data_alert(
    db: Session, org_id: str, tool: ClinicAiTool
) -> None:
    """Emit a clinic.tool.trains_on_data alert, suppressing duplicates.

    PRD.v2.md §6.8.2.c — at most one alert per (org_id, tool_id) per
    30-day window. Suppression is implemented as a query on existing
    rows; we accept the small race window because alert dispatch is
    idempotent at the consumer side (HITL, Slack, email) and the
    operational cost of a duplicate alert is the same as missing one is
    intolerable. No flush is performed — the caller commits.
    """
    if (
        tool.model_training_status
        != ClinicAiToolModelTrainingStatus.TRAINS_ON_CUSTOMER_DATA
    ):
        return
    cutoff = datetime.utcnow() - _TRAINS_ON_DATA_WINDOW
    existing = (
        db.query(Alert)
        .filter(
            Alert.organization_id == org_id,
            Alert.alert_type == _TRAINS_ON_DATA_ALERT_TYPE,
            Alert.agent_id == tool.id,
            Alert.timestamp >= cutoff,
        )
        .first()
    )
    if existing is not None:
        return
    alert = Alert(
        id=str(uuid.uuid4()),
        timestamp=datetime.utcnow(),
        severity=AlertSeverity.MEDIUM,
        alert_type=_TRAINS_ON_DATA_ALERT_TYPE,
        agent_id=tool.id,
        description=(
            f"Tool '{tool.name}' marked as training on customer data."
        ),
        organization_id=org_id,
    )
    db.add(alert)


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
    payload_raw: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_clinic_tier_with_baa),
):
    # Validate with current_user in context so the admin-only verified
    # rule fires before any DB write (PRD.v2.md §6.8.2.a, HEALTH-5).
    try:
        payload = ToolCreate.model_validate(
            payload_raw, context={"current_user": current_user}
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    # HIPAA safeguard — refuse free-text fields that look like PHI before
    # we ever persist them.
    reject_if_phi_present(
        {
            "name": payload.name,
            "vendor": payload.vendor,
            "purpose": payload.purpose,
            "notes": payload.notes,
            "model_training_status_evidence": payload.model_training_status_evidence,
        }
    )
    now = datetime.utcnow()
    verified_at = None
    verified_by = None
    if payload.practice_opt_out_state == ClinicAiToolPracticeOptOutState.VERIFIED:
        verified_at = now
        verified_by = current_user.id
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
        model_training_status=payload.model_training_status,
        practice_opt_out_state=payload.practice_opt_out_state,
        opt_out_verified_at=verified_at,
        opt_out_verified_by_user_id=verified_by,
        model_training_status_evidence=payload.model_training_status_evidence,
        created_at=now,
        updated_at=now,
    )
    db.add(tool)
    _maybe_emit_trains_on_data_alert(db, org.id, tool)
    write_clinic_audit(
        db,
        user=current_user,
        org_id=org.id,
        action="clinic.tool.create",
        system="clinic.tools",
        data_touched=[tool.id],
        reason="Clinic AI tool registered",
        metadata={
            "category": payload.category.value,
            "handles_phi": payload.handles_phi,
            "model_training_status": payload.model_training_status.value,
            "practice_opt_out_state": payload.practice_opt_out_state.value,
        },
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
    payload_raw: dict,
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
    try:
        payload = ToolUpdate.model_validate(
            payload_raw, context={"current_user": current_user}
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    update_dict = payload.model_dump(exclude_unset=True)
    reject_if_phi_present(
        {
            "name": update_dict.get("name"),
            "vendor": update_dict.get("vendor"),
            "purpose": update_dict.get("purpose"),
            "notes": update_dict.get("notes"),
            "model_training_status_evidence": update_dict.get(
                "model_training_status_evidence"
            ),
        }
    )
    # Detect 'verified' transitions before applying the fields so we can
    # stamp provenance atomically with the state change.
    now = datetime.utcnow()
    new_opt_state = update_dict.get("practice_opt_out_state")
    if (
        new_opt_state == ClinicAiToolPracticeOptOutState.VERIFIED
        and tool.practice_opt_out_state != ClinicAiToolPracticeOptOutState.VERIFIED
    ):
        update_dict["opt_out_verified_at"] = now
        update_dict["opt_out_verified_by_user_id"] = current_user.id
    for field_name, value in update_dict.items():
        setattr(tool, field_name, value)
    tool.updated_at = now
    _maybe_emit_trains_on_data_alert(db, org.id, tool)
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
