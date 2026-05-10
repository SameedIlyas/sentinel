"""Monthly clinic compliance PDF report.

Run by the existing ``services.scheduler`` once per month.  Produces a
self-contained PDF (WeasyPrint when installed; HTML fallback otherwise) and
writes it to the configured storage backend.

Design constraints (per blueprint):

* PHI never leaves the Policy Engine — the report contains *only*
  aggregated counts (tools, policies, alerts, BAA status).  No patient
  rows, no agent payloads.
* Output is dashboard-only.  No email is sent in v1.
* WeasyPrint is an optional dependency.  When missing, we still produce an
  HTML artifact so test environments and dev machines work without the
  system libraries WeasyPrint requires.
"""

from __future__ import annotations

import logging
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

from sqlalchemy import func
from sqlalchemy.orm import Session

from policy_engine.database import SessionLocal
from policy_engine.models.alert import Alert
from policy_engine.models.audit_log import AuditLog
from policy_engine.models.clinic import (
    ClinicAiTool,
    ClinicAiObservation,
    ClinicReportArtifact,
)
from policy_engine.models.organization import (
    Organization,
    is_clinic_tier,
)
from policy_engine.models.policy import Policy

logger = logging.getLogger(__name__)


# ── Storage backend ─────────────────────────────────────────────────────

def _storage_root() -> Path:
    root = os.environ.get(
        "CLINIC_REPORT_STORAGE_DIR",
        str(Path.cwd() / "var" / "clinic-reports"),
    )
    path = Path(root)
    path.mkdir(parents=True, exist_ok=True)
    return path


_SAFE_ID = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")


def _artifact_path(org_id: str, period_end: datetime) -> Path:
    # Defense in depth: org_ids are server-generated UUIDs today, but
    # validating against an allowlist before use prevents any future
    # caller from passing user-controllable input into the path.
    if not _SAFE_ID.match(org_id or ""):
        raise ValueError(f"Unsafe org_id for storage path: {org_id!r}")
    return _storage_root() / org_id / f"{period_end:%Y-%m}.pdf"


# ── Data collection (read-only, aggregated) ─────────────────────────────

@dataclass(frozen=True)
class ReportData:
    org_name: str
    org_tier: str
    period_start: datetime
    period_end: datetime
    tools_total: int
    tools_active: int
    tools_under_review: int
    tools_high_risk: int
    policies_total: int
    policies_enabled: int
    alerts_total: int
    alerts_critical: int
    alerts_high: int
    alerts_acknowledged: int
    audit_log_count: int
    blocked_count: int
    shadow_observations_total: int
    baa_signed: bool
    baa_date: datetime | None


def _collect(db: Session, org: Organization, period_start: datetime, period_end: datetime) -> ReportData:
    tool_q = db.query(ClinicAiTool).filter(ClinicAiTool.org_id == org.id)
    tools_total = tool_q.count()
    tools_active = tool_q.filter(ClinicAiTool.status == "active").count()
    tools_under_review = tool_q.filter(ClinicAiTool.status == "under_review").count()
    tools_high_risk = tool_q.filter(ClinicAiTool.risk_level == "high").count()

    pol_q = db.query(Policy).filter(Policy.organization_id == org.id)
    policies_total = pol_q.count()
    policies_enabled = pol_q.filter(Policy.enabled == True).count()  # noqa: E712

    # Tenant scope is mandatory; Alert.organization_id was added in
    # migration 017 so legacy NULL rows are filtered out for clinic-tier
    # reads.  Without this filter, the report would aggregate alerts
    # from every other tenant on the platform — a HIPAA breach.
    alert_q = db.query(Alert).filter(
        Alert.organization_id == org.id,
        Alert.timestamp >= period_start,
        Alert.timestamp < period_end,
    )
    alerts_total = alert_q.count()
    alerts_critical = alert_q.filter(Alert.severity == "critical").count()
    alerts_high = alert_q.filter(Alert.severity == "high").count()
    alerts_acknowledged = alert_q.filter(Alert.acknowledged == True).count()  # noqa: E712

    audit_q = db.query(AuditLog).filter(
        AuditLog.timestamp >= period_start,
        AuditLog.timestamp < period_end,
        AuditLog.organization_id == org.id,
    )
    audit_log_count = audit_q.count()
    blocked_count = audit_q.filter(AuditLog.decision == "blocked").count()

    obs_q = db.query(ClinicAiObservation).filter(
        ClinicAiObservation.org_id == org.id,
        ClinicAiObservation.observed_at >= period_start,
        ClinicAiObservation.observed_at < period_end,
    )
    shadow_observations_total = obs_q.count()

    return ReportData(
        org_name=org.name,
        org_tier=org.tier,
        period_start=period_start,
        period_end=period_end,
        tools_total=tools_total,
        tools_active=tools_active,
        tools_under_review=tools_under_review,
        tools_high_risk=tools_high_risk,
        policies_total=policies_total,
        policies_enabled=policies_enabled,
        alerts_total=alerts_total,
        alerts_critical=alerts_critical,
        alerts_high=alerts_high,
        alerts_acknowledged=alerts_acknowledged,
        audit_log_count=audit_log_count,
        blocked_count=blocked_count,
        shadow_observations_total=shadow_observations_total,
        baa_signed=org.hipaa_baa_signed,
        baa_date=org.hipaa_baa_date,
    )


# ── Rendering ───────────────────────────────────────────────────────────

_CSS = """
* { box-sizing: border-box; }
body { font-family: -apple-system, "Segoe UI", Roboto, sans-serif; color: #1a1f36; margin: 0; padding: 32px; }
h1 { font-size: 22px; margin: 0 0 4px; }
h2 { font-size: 14px; margin: 24px 0 8px; color: #635bff; text-transform: uppercase; letter-spacing: 0.05em; }
.subtitle { color: #697386; font-size: 13px; margin-bottom: 24px; }
.grid { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 16px; }
.tile { flex: 1 1 30%; border: 1px solid #e3e8ee; border-radius: 8px; padding: 12px 16px; background: #ffffff; }
.tile .label { font-size: 11px; color: #697386; text-transform: uppercase; letter-spacing: 0.05em; }
.tile .value { font-size: 22px; font-weight: 700; margin-top: 4px; }
.tile.warn { border-color: #f5a62355; background: #fff8eb; }
.tile.bad  { border-color: #df1b4155; background: #fff1f3; }
.foot { margin-top: 32px; padding-top: 16px; border-top: 1px solid #e3e8ee; font-size: 11px; color: #8b8fa3; }
.kv { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #f0f2f5; font-size: 13px; }
.kv:last-child { border-bottom: 0; }
.kv .k { color: #697386; }
.kv .v { color: #1a1f36; font-weight: 600; }
"""


def _render_html(data: ReportData) -> str:
    baa = "On file" if data.baa_signed else "Not signed"
    if data.baa_signed and data.baa_date:
        baa = f"On file (signed {data.baa_date:%b %d, %Y})"

    def tile(label: str, value: str | int, kind: str = "") -> str:
        return (
            f'<div class="tile {kind}">'
            f'<div class="label">{label}</div>'
            f'<div class="value">{value}</div>'
            f"</div>"
        )

    tile_grid = "".join(
        [
            tile("AI tools", data.tools_total),
            tile("Active", data.tools_active),
            tile("High risk", data.tools_high_risk, "warn" if data.tools_high_risk else ""),
            tile("Practice rules", data.policies_enabled),
            tile("Alerts", data.alerts_total),
            tile("Critical", data.alerts_critical, "bad" if data.alerts_critical else ""),
        ]
    )

    return f"""<!doctype html>
<html><head><meta charset="utf-8"/>
<title>{data.org_name} — Monthly Compliance Report</title>
<style>{_CSS}</style></head><body>
<h1>{data.org_name}</h1>
<div class="subtitle">Monthly compliance report &middot; {data.period_start:%b %d} – {data.period_end:%b %d, %Y}</div>

<h2>At a glance</h2>
<div class="grid">{tile_grid}</div>

<h2>Activity</h2>
<div class="kv"><span class="k">AI actions audited</span><span class="v">{data.audit_log_count:,}</span></div>
<div class="kv"><span class="k">Actions blocked</span><span class="v">{data.blocked_count:,}</span></div>
<div class="kv"><span class="k">Alerts acknowledged</span><span class="v">{data.alerts_acknowledged:,} / {data.alerts_total:,}</span></div>
<div class="kv"><span class="k">Shadow-AI observations</span><span class="v">{data.shadow_observations_total:,}</span></div>

<h2>Tools registry</h2>
<div class="kv"><span class="k">Total registered</span><span class="v">{data.tools_total}</span></div>
<div class="kv"><span class="k">Currently active</span><span class="v">{data.tools_active}</span></div>
<div class="kv"><span class="k">Under review</span><span class="v">{data.tools_under_review}</span></div>
<div class="kv"><span class="k">High-risk</span><span class="v">{data.tools_high_risk}</span></div>

<h2>Compliance posture</h2>
<div class="kv"><span class="k">HIPAA BAA</span><span class="v">{baa}</span></div>
<div class="kv"><span class="k">Plan</span><span class="v">{data.org_tier.replace('_', ' ').title()}</span></div>

<div class="foot">
This report contains aggregated counts only. No patient data is included.
Generated by Sentinel AI &middot; {datetime.utcnow():%Y-%m-%d %H:%M UTC}
</div>
</body></html>"""


def _render_pdf_bytes(html: str) -> bytes | None:
    """Try WeasyPrint; return None if unavailable so caller falls back to HTML."""
    try:
        from weasyprint import HTML  # type: ignore
    except Exception:  # pragma: no cover — optional dependency
        return None
    try:
        return HTML(string=html).write_pdf()
    except Exception as exc:  # pragma: no cover — surface in caller
        logger.exception("WeasyPrint render failed: %s", exc)
        return None


# ── Public entry points ─────────────────────────────────────────────────

def generate_report_for_org(
    db: Session,
    org: Organization,
    period_start: datetime,
    period_end: datetime,
) -> ClinicReportArtifact:
    """Generate (and persist a pointer to) a clinic compliance report."""
    if not is_clinic_tier(org.tier):
        raise ValueError(f"Org {org.id} is not on a clinic tier ({org.tier!r})")

    data = _collect(db, org, period_start, period_end)
    html = _render_html(data)

    target = _artifact_path(org.id, period_end)
    target.parent.mkdir(parents=True, exist_ok=True)

    pdf_bytes = _render_pdf_bytes(html)
    if pdf_bytes is None:
        # Fallback — write HTML alongside, surface as the artifact.
        target = target.with_suffix(".html")
        target.write_text(html, encoding="utf-8")
        size = target.stat().st_size
    else:
        target.write_bytes(pdf_bytes)
        size = target.stat().st_size

    storage_uri = f"file://{target.as_posix()}"

    artifact = ClinicReportArtifact(
        id=str(uuid.uuid4()),
        org_id=org.id,
        period_start=period_start,
        period_end=period_end,
        storage_uri=storage_uri,
        size_bytes=size,
        generated_at=datetime.utcnow(),
        status="ready",
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    return artifact


def _previous_calendar_month(now: datetime | None = None) -> tuple[datetime, datetime]:
    now = now or datetime.utcnow()
    first_of_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    period_end = first_of_this_month
    period_start = (period_end - timedelta(days=1)).replace(day=1)
    return period_start, period_end


def make_monthly_report_job():
    """Returns a callable for ``services.scheduler`` to invoke periodically.

    Generates one artifact per clinic org per call.  Idempotent: skips orgs
    that already have a 'ready' artifact for the previous month.
    """
    def _job() -> None:
        period_start, period_end = _previous_calendar_month()
        db = SessionLocal()
        try:
            clinics = db.query(Organization).filter(
                Organization.tier.in_(
                    ("clinic_basic", "clinic_standard", "clinic_multi_site")
                ),
                Organization.is_active == True,  # noqa: E712
            ).all()
            for org in clinics:
                existing = (
                    db.query(ClinicReportArtifact)
                    .filter(
                        ClinicReportArtifact.org_id == org.id,
                        ClinicReportArtifact.period_end == period_end,
                        ClinicReportArtifact.status == "ready",
                    )
                    .first()
                )
                if existing:
                    continue
                try:
                    generate_report_for_org(db, org, period_start, period_end)
                except Exception as exc:  # pragma: no cover — log + persist failure
                    logger.exception("Failed to generate clinic report for %s: %s", org.id, exc)
                    db.add(
                        ClinicReportArtifact(
                            id=str(uuid.uuid4()),
                            org_id=org.id,
                            period_start=period_start,
                            period_end=period_end,
                            storage_uri="",
                            generated_at=datetime.utcnow(),
                            status="failed",
                            error_message=str(exc)[:500],
                        )
                    )
                    db.commit()
        finally:
            db.close()

    return _job


def is_enabled() -> bool:
    return os.environ.get("CLINIC_REPORT_AUTO_GENERATE", "true").lower() == "true"


def interval_seconds() -> float:
    # Default daily — the job is idempotent so cheap to run more often than
    # needed.  Override with CLINIC_REPORT_INTERVAL_SECONDS for tests.
    return float(os.environ.get("CLINIC_REPORT_INTERVAL_SECONDS", 86400))
