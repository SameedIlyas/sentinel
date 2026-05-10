"""Clinic onboarding wizard state.

Stored in ``Organization.settings.clinic_onboarding`` to avoid a new table
for what is effectively a one-shot, three-step boolean track.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from policy_engine.auth.rbac import get_current_user
from policy_engine.database import get_db
from policy_engine.models.organization import Organization
from policy_engine.models.user import User
from policy_engine.services.tier_filter import require_clinic_tier

router = APIRouter()


_DEFAULT = {
    "step": 0,            # 0=baa, 1=first_tool, 2=extension, 3=done
    "baa_accepted_at": None,
    "first_tool_registered": False,
    "extension_enabled": False,
    "completed_at": None,
}


def _state(org: Organization) -> dict:
    settings = org.settings or {}
    state = {**_DEFAULT, **(settings.get("clinic_onboarding") or {})}
    return state


class OnboardingState(BaseModel):
    step: int
    baa_accepted_at: Optional[datetime]
    first_tool_registered: bool
    extension_enabled: bool
    completed_at: Optional[datetime]


class StepAdvance(BaseModel):
    step: int  # 0..3


@router.get("/onboarding", response_model=OnboardingState)
def get_state(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_clinic_tier),
):
    return _state(org)


@router.post("/onboarding/advance", response_model=OnboardingState)
def advance(
    payload: StepAdvance,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_clinic_tier),
):
    settings = dict(org.settings or {})
    state = {**_DEFAULT, **(settings.get("clinic_onboarding") or {})}
    target = max(state["step"], min(payload.step, 3))
    state["step"] = target
    if target >= 3 and not state.get("completed_at"):
        state["completed_at"] = datetime.utcnow().isoformat() + "Z"
    settings["clinic_onboarding"] = state
    org.settings = settings
    flag_modified(org, "settings")
    db.commit()
    db.refresh(org)
    return _state(org)


@router.post("/onboarding/extension-enabled", response_model=OnboardingState)
def extension_enabled(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_clinic_tier),
):
    settings = dict(org.settings or {})
    state = {**_DEFAULT, **(settings.get("clinic_onboarding") or {})}
    state["extension_enabled"] = True
    settings["clinic_onboarding"] = state
    org.settings = settings
    flag_modified(org, "settings")
    db.commit()
    db.refresh(org)
    return _state(org)
