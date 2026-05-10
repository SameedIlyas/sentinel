"""Clinic dashboard summary — the four-tile read.

Returns the aggregate counts the clinic_basic landing page renders without
making four separate round-trips.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from policy_engine.auth.rbac import get_current_user
from policy_engine.billing.plans import get_plan
from policy_engine.database import get_db
from policy_engine.models.alert import Alert
from policy_engine.models.audit_log import AuditLog
from policy_engine.models.clinic import (
    ClinicAiObservation,
    ClinicAiTool,
    ClinicReportArtifact,
)
from policy_engine.models.organization import Organization
from policy_engine.models.user import User
from policy_engine.services.tier_filter import require_clinic_tier

router = APIRouter()


class TileCounts(BaseModel):
    tools_total: int
    tools_high_risk: int
    alerts_open: int
    alerts_critical: int
    blocked_today: int
    shadow_observations_open: int


class LatestReport(BaseModel):
    id: str
    period_end: datetime
    download_url: str


class OnboardingTeaser(BaseModel):
    step: int
    completed: bool


class BillingStatus(BaseModel):
    subscription_status: Optional[str]  # active | past_due | canceled | trialing
    cancel_at: Optional[str]
    current_period_end: Optional[str]
    has_payment_method: bool


class DashboardSummary(BaseModel):
    org_name: str
    tier: str
    tier_display_name: str
    baa_signed: bool
    counts: TileCounts
    latest_report: Optional[LatestReport]
    onboarding: OnboardingTeaser
    billing: BillingStatus


@router.get("/dashboard/summary", response_model=DashboardSummary)
def summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_clinic_tier),
):
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    tools_total = db.query(ClinicAiTool).filter(ClinicAiTool.org_id == org.id).count()
    tools_high_risk = (
        db.query(ClinicAiTool)
        .filter(ClinicAiTool.org_id == org.id, ClinicAiTool.risk_level == "high")
        .count()
    )
    alerts_open = (
        db.query(Alert)
        .filter(
            Alert.organization_id == org.id,
            Alert.acknowledged == False,  # noqa: E712
        )
        .count()
    )
    alerts_critical = (
        db.query(Alert)
        .filter(
            Alert.organization_id == org.id,
            Alert.acknowledged == False,  # noqa: E712
            Alert.severity == "critical",
        )
        .count()
    )
    blocked_today = (
        db.query(AuditLog)
        .filter(
            AuditLog.organization_id == org.id,
            AuditLog.timestamp >= today_start,
            AuditLog.decision == "blocked",
        )
        .count()
    )
    shadow_observations_open = (
        db.query(ClinicAiObservation)
        .filter(
            ClinicAiObservation.org_id == org.id,
            ClinicAiObservation.acknowledged == False,  # noqa: E712
        )
        .count()
    )

    latest = (
        db.query(ClinicReportArtifact)
        .filter(
            ClinicReportArtifact.org_id == org.id,
            ClinicReportArtifact.status == "ready",
        )
        .order_by(ClinicReportArtifact.period_end.desc())
        .first()
    )
    latest_payload = (
        LatestReport(
            id=latest.id,
            period_end=latest.period_end,
            download_url=f"/v1/clinic/reports/{latest.id}/download",
        )
        if latest
        else None
    )

    onboarding_state = (org.settings or {}).get("clinic_onboarding") or {}
    billing_state = (org.settings or {}).get("billing") or {}
    plan = get_plan(org.tier)

    def _stringify(raw: Any) -> Optional[str]:
        if raw is None:
            return None
        if isinstance(raw, (int, float)):
            return datetime.fromtimestamp(raw).isoformat() + "Z"
        return str(raw)

    return DashboardSummary(
        org_name=org.name,
        tier=org.tier,
        tier_display_name=plan.display_name,
        baa_signed=org.hipaa_baa_signed,
        counts=TileCounts(
            tools_total=tools_total,
            tools_high_risk=tools_high_risk,
            alerts_open=alerts_open,
            alerts_critical=alerts_critical,
            blocked_today=blocked_today,
            shadow_observations_open=shadow_observations_open,
        ),
        latest_report=latest_payload,
        onboarding=OnboardingTeaser(
            step=onboarding_state.get("step", 0),
            completed=bool(onboarding_state.get("completed_at")),
        ),
        billing=BillingStatus(
            subscription_status=billing_state.get("subscription_status"),
            cancel_at=_stringify(billing_state.get("cancel_at")),
            current_period_end=_stringify(billing_state.get("current_period_end")),
            has_payment_method=bool(billing_state.get("stripe_customer_id")),
        ),
    )
