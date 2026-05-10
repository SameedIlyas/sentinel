"""Click-through BAA acceptance for clinic_basic; status display for Standard+."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from policy_engine.auth.rbac import get_current_user
from policy_engine.database import get_db
from policy_engine.models.organization import Organization
from policy_engine.models.user import User
from policy_engine.services.clinic_audit import write_clinic_audit
from policy_engine.services.tier_filter import require_clinic_tier
from policy_engine.billing.plans import get_plan

router = APIRouter()


class BaaStatus(BaseModel):
    signed: bool
    signed_at: Optional[datetime]
    mode: str  # click_through | executed_bundled | negotiated
    plan: str
    plan_display_name: str
    can_self_accept: bool


class AcceptBody(BaseModel):
    organization_legal_name: str
    accepter_full_name: str
    accepter_title: str


@router.get("/baa/status", response_model=BaaStatus)
def status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_clinic_tier),
):
    plan = get_plan(org.tier)
    return BaaStatus(
        signed=org.hipaa_baa_signed,
        signed_at=org.hipaa_baa_date,
        mode=plan.baa_mode,
        plan=org.tier,
        plan_display_name=plan.display_name,
        can_self_accept=plan.baa_mode == "click_through",
    )


@router.post("/baa/accept", response_model=BaaStatus)
def accept(
    body: AcceptBody,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_clinic_tier),
):
    plan = get_plan(org.tier)
    if plan.baa_mode != "click_through":
        raise HTTPException(
            status_code=409,
            detail=(
                "Your plan uses an executed BAA — your account manager will "
                "send a copy for signature. No click-through is required."
            ),
        )
    if org.hipaa_baa_signed:
        return BaaStatus(
            signed=True,
            signed_at=org.hipaa_baa_date,
            mode=plan.baa_mode,
            plan=org.tier,
            plan_display_name=plan.display_name,
            can_self_accept=False,
        )

    now = datetime.utcnow()
    # Capture IP + user-agent for non-repudiation of the click-through
    # signature (GDPR Art. 7(1) demonstrability of consent).
    client_ip = (
        request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (request.client.host if request.client else "unknown")
    )[:64]
    user_agent = (request.headers.get("user-agent") or "")[:256]

    org.hipaa_baa_signed = True
    org.hipaa_baa_date = now
    settings = dict(org.settings or {})
    settings["baa"] = {
        "source": "click_through",
        "organization_legal_name": body.organization_legal_name,
        "accepter_full_name": body.accepter_full_name,
        "accepter_title": body.accepter_title,
        "accepter_user_id": current_user.id,
        "accepter_username": current_user.username,
        "accepted_at": now.isoformat() + "Z",
        "accepter_ip": client_ip,
        "accepter_user_agent": user_agent,
    }
    org.settings = settings
    flag_modified(org, "settings")
    write_clinic_audit(
        db,
        user=current_user,
        org_id=org.id,
        action="clinic.baa.accept",
        system="clinic.compliance",
        data_touched=[org.id],
        reason="Click-through BAA accepted",
        metadata={
            "source": "click_through",
            "organization_legal_name": body.organization_legal_name,
            "accepter_title": body.accepter_title,
        },
    )
    db.commit()
    db.refresh(org)

    return BaaStatus(
        signed=True,
        signed_at=org.hipaa_baa_date,
        mode=plan.baa_mode,
        plan=org.tier,
        plan_display_name=plan.display_name,
        can_self_accept=False,
    )
