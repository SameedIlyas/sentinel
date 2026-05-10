"""Clinic policy template library — list + apply.

Materializing a template creates a real ``Policy`` row using the same
schema as enterprise policies.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from policy_engine.auth.rbac import get_current_user
from policy_engine.database import get_db
from policy_engine.models.organization import Organization
from policy_engine.models.policy import Policy
from policy_engine.models.user import User
from policy_engine.services.clinic_audit import write_clinic_audit
from policy_engine.services.clinic_policy_templates import (
    CLINIC_POLICY_TEMPLATES,
    get_template,
    list_templates_for_tier,
)
from policy_engine.services.tier_filter import (
    require_clinic_tier,
    require_clinic_tier_with_baa,
)

router = APIRouter()


class TemplateResponse(BaseModel):
    template_id: str
    name: str
    description: str
    why_it_matters: str
    policy_type: str
    priority: int
    recommended_for_tiers: list[str]


class ApplyRequest(BaseModel):
    template_id: str
    name_override: str | None = None


class ApplyResponse(BaseModel):
    policy_id: str
    template_id: str


@router.get("/policy-templates", response_model=list[TemplateResponse])
def list_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_clinic_tier),
):
    return [
        TemplateResponse(
            template_id=t.template_id,
            name=t.name,
            description=t.description,
            why_it_matters=t.why_it_matters,
            policy_type=t.policy_type,
            priority=t.priority,
            recommended_for_tiers=list(t.recommended_for_tiers),
        )
        for t in CLINIC_POLICY_TEMPLATES
    ]


@router.post(
    "/policy-templates/apply",
    response_model=ApplyResponse,
    status_code=status.HTTP_201_CREATED,
)
def apply_template(
    payload: ApplyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_clinic_tier_with_baa),
):
    template = get_template(payload.template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    if org.tier not in template.recommended_for_tiers:
        raise HTTPException(
            status_code=403,
            detail=f"Template not available on {org.tier} plan",
        )

    spec: dict[str, Any] = template.to_policy_dict()
    now = datetime.utcnow()
    policy = Policy(
        id=str(uuid.uuid4()),
        name=payload.name_override or spec["name"],
        description=spec["description"],
        policy_type=spec["policy_type"],
        rules=spec["rules"],
        applies_to=spec["applies_to"],
        priority=spec["priority"],
        enabled=spec["enabled"],
        created_by=current_user.id,
        created_at=now,
        updated_at=now,
        organization_id=org.id,
    )
    db.add(policy)
    write_clinic_audit(
        db,
        user=current_user,
        org_id=org.id,
        action="clinic.policy.apply_template",
        system="clinic.policies",
        data_touched=[policy.id],
        reason=f"Applied template {template.template_id}",
        metadata={"template_id": template.template_id, "policy_type": spec["policy_type"]},
    )
    db.commit()
    db.refresh(policy)
    return ApplyResponse(policy_id=policy.id, template_id=template.template_id)
