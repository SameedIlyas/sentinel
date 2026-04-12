"""PMS Report routes — Periodic Safety Update Reports and FDA MDRs."""
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from policy_engine.auth.rbac import get_current_user
from policy_engine.database import get_db
from policy_engine.domain.regulatory.post_market import (
    aggregate_pms_metrics,
    generate_psur_summary,
)
from policy_engine.models.post_market import (
    AdverseEvent,
    PMSMetric,
    PMSReport,
    PMSReportStatusDB,
    PMSReportTypeDB,
)
from policy_engine.models.user import has_permission

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class PMSReportCreate(BaseModel):
    report_type: str
    period_start: str   # ISO-8601 date string
    period_end: str
    auto_generate_summary: bool = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _report_to_dict(r: PMSReport) -> dict:
    return {
        "id": r.id,
        "report_type": r.report_type,
        "status": r.status,
        "period_start": r.period_start.isoformat(),
        "period_end": r.period_end.isoformat(),
        "summary": r.summary,
        "generated_at": r.generated_at.isoformat() if r.generated_at else None,
        "created_by": r.created_by,
        "organization_id": r.organization_id,
        "created_at": r.created_at.isoformat(),
    }


def _get_report_or_404(db: Session, report_id: str, org_id: Optional[str]) -> PMSReport:
    r = db.query(PMSReport).filter(
        PMSReport.id == report_id,
        PMSReport.organization_id == org_id,
    ).first()
    if not r:
        raise HTTPException(404, "PMS report not found")
    return r


# ---------------------------------------------------------------------------
# Routes — specific paths BEFORE /{report_id}
# ---------------------------------------------------------------------------


@router.get("/pms-reports/stats")
def pms_report_stats(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not has_permission(current_user.role, "post_market", "read"):
        raise HTTPException(403, "Forbidden")

    reports = db.query(PMSReport).filter(
        PMSReport.organization_id == current_user.organization_id
    ).all()

    by_type: dict = {}
    by_status: dict = {}
    for r in reports:
        rtype = str(r.report_type)
        by_type[rtype] = by_type.get(rtype, 0) + 1
        status = str(r.status)
        by_status[status] = by_status.get(status, 0) + 1

    return {
        "total_reports": len(reports),
        "by_type": by_type,
        "by_status": by_status,
    }


@router.post("/pms-reports", status_code=201)
def create_pms_report(
    body: PMSReportCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not has_permission(current_user.role, "post_market", "create"):
        raise HTTPException(403, "Forbidden")

    try:
        report_type = PMSReportTypeDB(body.report_type)
    except ValueError:
        raise HTTPException(400, f"Invalid report_type: {body.report_type}")

    try:
        period_start = datetime.fromisoformat(body.period_start)
        period_end = datetime.fromisoformat(body.period_end)
    except ValueError:
        raise HTTPException(400, "Invalid date format. Use ISO-8601 (e.g. 2024-01-01)")

    if period_end <= period_start:
        raise HTTPException(400, "period_end must be after period_start")

    now = datetime.utcnow()
    report_id = str(uuid.uuid4())

    # Optionally auto-generate PSUR summary from adverse events in the period
    summary = None
    if body.auto_generate_summary:
        events = db.query(AdverseEvent).filter(
            AdverseEvent.organization_id == current_user.organization_id,
            AdverseEvent.reported_at >= period_start,
            AdverseEvent.reported_at <= period_end,
        ).all()

        event_dicts = [{"severity": str(ev.severity), "status": str(ev.status)} for ev in events]
        metrics = aggregate_pms_metrics(event_dicts)
        period_days = max(1, (period_end - period_start).days)
        summary = generate_psur_summary(metrics, period_days)

    report = PMSReport(
        id=report_id,
        organization_id=current_user.organization_id,
        report_type=report_type,
        status=PMSReportStatusDB.DRAFT,
        period_start=period_start,
        period_end=period_end,
        summary=summary,
        generated_at=now if summary else None,
        created_by=current_user.id,
        created_at=now,
        updated_at=now,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return _report_to_dict(report)


@router.get("/pms-reports")
def list_pms_reports(
    report_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not has_permission(current_user.role, "post_market", "read"):
        raise HTTPException(403, "Forbidden")

    q = db.query(PMSReport).filter(
        PMSReport.organization_id == current_user.organization_id
    )
    if report_type:
        q = q.filter(PMSReport.report_type == report_type)
    if status:
        q = q.filter(PMSReport.status == status)

    return [_report_to_dict(r) for r in q.order_by(PMSReport.created_at.desc()).all()]


@router.get("/pms-reports/{report_id}")
def get_pms_report(
    report_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not has_permission(current_user.role, "post_market", "read"):
        raise HTTPException(403, "Forbidden")
    return _report_to_dict(_get_report_or_404(db, report_id, current_user.organization_id))


@router.post("/pms-reports/{report_id}/publish")
def publish_pms_report(
    report_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Transition report from DRAFT → PUBLISHED."""
    if not has_permission(current_user.role, "post_market", "update"):
        raise HTTPException(403, "Forbidden")

    report = _get_report_or_404(db, report_id, current_user.organization_id)

    if report.status != PMSReportStatusDB.DRAFT:
        raise HTTPException(409, "Only DRAFT reports can be published")

    report.status = PMSReportStatusDB.PUBLISHED
    report.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(report)
    return _report_to_dict(report)


@router.get("/pms-reports/{report_id}/metrics")
def get_report_metrics(
    report_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return all metrics attached to a PMS report, computing them on demand if none exist."""
    if not has_permission(current_user.role, "post_market", "read"):
        raise HTTPException(403, "Forbidden")

    report = _get_report_or_404(db, report_id, current_user.organization_id)

    existing = db.query(PMSMetric).filter(PMSMetric.report_id == report_id).all()
    if existing:
        return [
            {
                "id": m.id,
                "report_id": m.report_id,
                "metric_name": m.metric_name,
                "metric_value": m.metric_value,
                "metric_unit": m.metric_unit,
                "computed_at": m.computed_at.isoformat(),
            }
            for m in existing
        ]

    # Compute metrics on demand from adverse events in period
    events = db.query(AdverseEvent).filter(
        AdverseEvent.organization_id == current_user.organization_id,
        AdverseEvent.reported_at >= report.period_start,
        AdverseEvent.reported_at <= report.period_end,
    ).all()

    event_dicts = [{"severity": str(ev.severity), "status": str(ev.status)} for ev in events]
    aggregated = aggregate_pms_metrics(event_dicts)

    now = datetime.utcnow()
    metric_rows = [
        ("total_events", float(aggregated["total_events"]), "count"),
        ("critical_rate", aggregated["critical_rate"], "ratio"),
        ("resolution_rate", aggregated["resolution_rate"], "ratio"),
        ("open_count", float(aggregated["open_count"]), "count"),
    ]

    created_metrics = []
    for name, value, unit in metric_rows:
        m = PMSMetric(
            id=str(uuid.uuid4()),
            report_id=report_id,
            metric_name=name,
            metric_value=value,
            metric_unit=unit,
            computed_at=now,
        )
        db.add(m)
        created_metrics.append(m)

    db.commit()

    return [
        {
            "id": m.id,
            "report_id": m.report_id,
            "metric_name": m.metric_name,
            "metric_value": m.metric_value,
            "metric_unit": m.metric_unit,
            "computed_at": m.computed_at.isoformat(),
        }
        for m in created_metrics
    ]
