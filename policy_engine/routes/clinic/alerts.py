"""Clinic-tier alert feed — wraps the canonical alerts table with the
plain-English translator and orders by recency.

Read-only.  No new alert table — this is purely a presentation layer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from policy_engine.auth.rbac import get_current_user
from policy_engine.database import get_db
from policy_engine.models.alert import Alert
from policy_engine.models.organization import Organization
from policy_engine.models.user import User
from policy_engine.services.clinic_alert_translator import (
    TranslatedAlert,
    translate_alert,
)
from policy_engine.services.tier_filter import require_clinic_tier

router = APIRouter()


class ClinicAlertResponse(BaseModel):
    id: str
    timestamp: datetime
    severity: str
    severity_label: str
    title: str
    description: str
    next_step: Optional[str]
    is_translated: bool
    acknowledged: bool


@router.get("/alerts", response_model=list[ClinicAlertResponse])
def list_alerts(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_clinic_tier),
):
    # Tenant scope is mandatory — without it a clinic_basic user would
    # see alerts from every other tenant on the platform.  See
    # alembic/versions/...017_clinic_compliance.py for the org_id backfill.
    rows = (
        db.query(Alert)
        .filter(Alert.organization_id == org.id)
        .order_by(Alert.timestamp.desc())
        .limit(min(limit, 200))
        .all()
    )
    out: list[ClinicAlertResponse] = []
    for row in rows:
        translated: TranslatedAlert = translate_alert(
            tier=org.tier,
            alert_type=row.alert_type,
            severity=row.severity.value if hasattr(row.severity, "value") else str(row.severity),
            description=row.description,
        )
        out.append(
            ClinicAlertResponse(
                id=row.id,
                timestamp=row.timestamp,
                severity=row.severity.value if hasattr(row.severity, "value") else str(row.severity),
                severity_label=translated.severity_label,
                title=translated.title,
                description=translated.description,
                next_step=translated.next_step,
                is_translated=translated.is_translated,
                acknowledged=row.acknowledged,
            )
        )
    return out
