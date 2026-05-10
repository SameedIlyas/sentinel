"""Clinic compliance report endpoints — list + on-demand generate + download URL.

Generation is normally driven by the scheduler in ``services.clinic_pdf_report``.
The ``POST /generate`` endpoint exists for testing and for the "generate
now" button on the clinic dashboard.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from policy_engine.auth.rbac import get_current_user
from policy_engine.database import get_db
from policy_engine.models.clinic import ClinicReportArtifact
from policy_engine.models.organization import Organization
from policy_engine.models.user import User
from policy_engine.services.clinic_audit import write_clinic_audit
from policy_engine.services.clinic_pdf_report import generate_report_for_org
from policy_engine.services.tier_filter import (
    require_clinic_tier,
    require_clinic_tier_with_baa,
)

router = APIRouter()


class ReportArtifactResponse(BaseModel):
    id: str
    org_id: str
    period_start: datetime
    period_end: datetime
    storage_uri: str
    size_bytes: Optional[int]
    generated_at: datetime
    status: str
    download_url: Optional[str] = None

    class Config:
        from_attributes = True


def _to_response(artifact: ClinicReportArtifact) -> ReportArtifactResponse:
    return ReportArtifactResponse(
        id=artifact.id,
        org_id=artifact.org_id,
        period_start=artifact.period_start,
        period_end=artifact.period_end,
        storage_uri=artifact.storage_uri,
        size_bytes=artifact.size_bytes,
        generated_at=artifact.generated_at,
        status=artifact.status,
        download_url=f"/v1/clinic/reports/{artifact.id}/download",
    )


@router.get("/reports", response_model=list[ReportArtifactResponse])
def list_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_clinic_tier),
):
    rows = (
        db.query(ClinicReportArtifact)
        .filter(ClinicReportArtifact.org_id == org.id)
        .order_by(ClinicReportArtifact.period_end.desc())
        .limit(24)
        .all()
    )
    return [_to_response(r) for r in rows]


@router.get("/reports/latest", response_model=Optional[ReportArtifactResponse])
def latest_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_clinic_tier),
):
    row = (
        db.query(ClinicReportArtifact)
        .filter(
            ClinicReportArtifact.org_id == org.id,
            ClinicReportArtifact.status == "ready",
        )
        .order_by(ClinicReportArtifact.period_end.desc())
        .first()
    )
    if row is None:
        return None
    return _to_response(row)


@router.post("/reports/generate", response_model=ReportArtifactResponse)
def generate_now(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_clinic_tier_with_baa),
):
    """Generate a report for the previous calendar month (or current if mid-month).

    BAA-gated: the report aggregates org-scoped activity counts that
    would not be appropriate to compute and persist before a BAA is in
    force.
    """
    now = datetime.utcnow()
    first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    period_start = (first_of_month - timedelta(days=1)).replace(day=1)
    artifact = generate_report_for_org(db, org, period_start, first_of_month)
    write_clinic_audit(
        db,
        user=current_user,
        org_id=org.id,
        action="clinic.report.generate",
        system="clinic.reports",
        data_touched=[artifact.id],
        reason="Compliance report generated on demand",
        metadata={"period_end": first_of_month.isoformat()},
    )
    db.commit()
    return _to_response(artifact)


@router.get("/reports/{report_id}/download")
def download_report(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_clinic_tier),
):
    row = (
        db.query(ClinicReportArtifact)
        .filter(
            ClinicReportArtifact.id == report_id,
            ClinicReportArtifact.org_id == org.id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Report not found")
    if row.status != "ready":
        raise HTTPException(status_code=409, detail=f"Report status: {row.status}")

    if not row.storage_uri.startswith("file://"):
        # Future: signed URL for object storage backends.
        raise HTTPException(
            status_code=501,
            detail="Non-file storage backends not yet implemented",
        )
    path = Path(row.storage_uri[len("file://") :]).resolve()
    # Defense in depth: ensure the resolved path stays inside the
    # configured storage root so a malformed storage_uri cannot
    # exfiltrate arbitrary files (CWE-22).
    from policy_engine.services.clinic_pdf_report import _storage_root  # local import to avoid cycle
    storage_root = _storage_root().resolve()
    try:
        path.relative_to(storage_root)
    except ValueError:
        raise HTTPException(status_code=403, detail="Report path outside storage root")
    if not path.exists():
        raise HTTPException(status_code=410, detail="Report file no longer available")
    media_type = "application/pdf" if path.suffix.lower() == ".pdf" else "text/html"
    write_clinic_audit(
        db,
        user=current_user,
        org_id=org.id,
        action="clinic.report.download",
        system="clinic.reports",
        data_touched=[row.id],
        reason="Compliance report downloaded",
    )
    db.commit()
    return FileResponse(
        str(path),
        media_type=media_type,
        filename=f"{org.slug}-{row.period_end:%Y-%m}{path.suffix}",
    )
