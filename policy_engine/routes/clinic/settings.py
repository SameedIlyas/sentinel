"""Clinic settings — practice info + plan info."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from policy_engine.auth.rbac import get_current_user
from policy_engine.billing.plans import get_plan, stripe_payment_link
from policy_engine.database import get_db
from policy_engine.models.organization import Organization
from policy_engine.models.user import User
from policy_engine.services.tier_filter import require_clinic_tier

router = APIRouter()


class PracticeInfo(BaseModel):
    name: str
    address: Optional[str] = None
    phone: Optional[str] = None
    primary_specialty: Optional[str] = None
    locations_count: int = 1


class PracticeUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    address: Optional[str] = Field(None, max_length=500)
    phone: Optional[str] = Field(None, max_length=50)
    primary_specialty: Optional[str] = Field(None, max_length=120)


class PlanInfo(BaseModel):
    tier: str
    display_name: str
    monthly_price_usd: int
    tool_cap: int
    seat_cap: int
    audit_retention_days: int
    locations_cap: int
    baa_mode: str
    description: str
    payment_link_url: Optional[str]
    upgrade_options: list[str]


_UPGRADE_PATH = {
    "clinic_basic": ["clinic_standard", "clinic_multi_site"],
    "clinic_standard": ["clinic_multi_site"],
    "clinic_multi_site": [],
}


@router.get("/settings/practice", response_model=PracticeInfo)
def get_practice(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_clinic_tier),
):
    practice = (org.settings or {}).get("practice", {})
    return PracticeInfo(
        name=org.name,
        address=practice.get("address"),
        phone=practice.get("phone"),
        primary_specialty=practice.get("primary_specialty"),
        locations_count=practice.get("locations_count", 1),
    )


@router.put("/settings/practice", response_model=PracticeInfo)
def update_practice(
    payload: PracticeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_clinic_tier),
):
    settings = dict(org.settings or {})
    practice = dict(settings.get("practice", {}))
    if payload.name:
        org.name = payload.name
    for key in ("address", "phone", "primary_specialty"):
        value = getattr(payload, key)
        if value is not None:
            practice[key] = value
    settings["practice"] = practice
    org.settings = settings
    flag_modified(org, "settings")
    org.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(org)
    return get_practice(db, current_user, org)  # type: ignore[arg-type]


@router.get("/settings/plan", response_model=PlanInfo)
def get_plan_info(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_clinic_tier),
):
    plan = get_plan(org.tier)
    return PlanInfo(
        tier=plan.name,
        display_name=plan.display_name,
        monthly_price_usd=plan.monthly_price_usd,
        tool_cap=plan.tool_cap,
        seat_cap=plan.seat_cap,
        audit_retention_days=plan.audit_retention_days,
        locations_cap=plan.locations_cap,
        baa_mode=plan.baa_mode,
        description=plan.description,
        payment_link_url=stripe_payment_link(plan.name),
        upgrade_options=_UPGRADE_PATH.get(plan.name, []),
    )
