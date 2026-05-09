"""Shadow AI batch ingestion + provider adapters.

Tier 3 — turns the Shadow AI Discovery page from "manually inserted demo
rows" to "live detections from your network gateway". This module accepts
batched flow records (vendor-agnostic) and creates ShadowAIDetectionModel
rows with provider classification, confidence scoring, dedup, and allowlist
filtering.

Three vendor adapters are included:

  - Cloudflare Logpush JSON-lines (gateway audit_logs)
  - Zscaler / Netskope SIEM-style flat JSON
  - AWS VPC Flow Logs version-2 fields

All adapters normalise to the canonical `FlowRecord` shape so the ingestion
pipeline is a single code path.
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from policy_engine.domain.admin.shadow_ai import (
    assess_phi_risk,
    detect_ai_provider,
    is_allowlisted,
    score_confidence,
)
from policy_engine.models.shadow_ai import (
    ShadowAIAllowlist,
    ShadowAIDetectionModel,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Canonical record + outcome
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FlowRecord:
    """Normalised network/API flow record from any source."""
    destination_host: str
    destination_port: int = 443
    source_ip: Optional[str] = None
    bytes_transferred: int = 0
    method: Optional[str] = None
    user_agent: Optional[str] = None
    department: Optional[str] = None
    timestamp: Optional[datetime] = None
    raw: Optional[Dict[str, Any]] = None


@dataclass
class IngestOutcome:
    received: int = 0
    classified_as_ai: int = 0
    detections_created: int = 0
    detections_deduped: int = 0
    allowlisted: int = 0
    errors: List[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []


# ---------------------------------------------------------------------------
# Vendor adapters — each returns Iterable[FlowRecord]
# ---------------------------------------------------------------------------

def parse_cloudflare_logpush(payload: Any) -> List[FlowRecord]:
    """Cloudflare Logpush ships either a list of records or newline-delimited JSON.

    Schema: https://developers.cloudflare.com/logs/reference/log-fields/
    Relevant fields: ClientIP, ClientRequestHost, ClientRequestMethod,
    ClientRequestUserAgent, EdgeResponseBytes, EdgeStartTimestamp,
    DestinationPort.
    """
    raw_records: List[Dict[str, Any]] = []
    if isinstance(payload, str):
        for line in payload.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                raw_records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    elif isinstance(payload, list):
        raw_records = [r for r in payload if isinstance(r, dict)]
    elif isinstance(payload, dict):
        # Some logpush configs wrap in {"events": [...]} or {"records": [...]}
        for key in ("events", "records", "data"):
            if isinstance(payload.get(key), list):
                raw_records = payload[key]
                break

    out: List[FlowRecord] = []
    for r in raw_records:
        host = (
            r.get("ClientRequestHost")
            or r.get("DestinationHost")
            or r.get("RequestHost")
            or ""
        )
        if not host:
            continue
        timestamp = None
        ts = (
            r.get("EdgeStartTimestamp")
            or r.get("Datetime")
            or r.get("@timestamp")
        )
        if isinstance(ts, str):
            try:
                timestamp = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                pass
        try:
            port = int(r.get("DestinationPort") or 443)
        except (TypeError, ValueError):
            port = 443
        try:
            bytes_n = int(r.get("EdgeResponseBytes") or r.get("BytesTransferred") or 0)
        except (TypeError, ValueError):
            bytes_n = 0
        out.append(FlowRecord(
            destination_host=str(host),
            destination_port=port,
            source_ip=r.get("ClientIP") or r.get("SourceIP"),
            bytes_transferred=bytes_n,
            method=r.get("ClientRequestMethod") or r.get("HTTPMethod"),
            user_agent=r.get("ClientRequestUserAgent") or r.get("UserAgent"),
            department=r.get("Department") or r.get("ClientASN"),
            timestamp=timestamp,
            raw=r,
        ))
    return out


def parse_zscaler_siem(payload: Any) -> List[FlowRecord]:
    """Zscaler SIEM flat-JSON format (one object per record)."""
    raw_records: List[Dict[str, Any]] = []
    if isinstance(payload, list):
        raw_records = [r for r in payload if isinstance(r, dict)]
    elif isinstance(payload, dict):
        for key in ("records", "events", "logs"):
            if isinstance(payload.get(key), list):
                raw_records = payload[key]
                break

    out: List[FlowRecord] = []
    for r in raw_records:
        host = r.get("host") or r.get("url_host") or r.get("dst_host")
        if not host:
            continue
        try:
            port = int(r.get("dst_port") or r.get("destination_port") or 443)
        except (TypeError, ValueError):
            port = 443
        try:
            bytes_n = int(r.get("bytes_out") or r.get("bytes") or 0)
        except (TypeError, ValueError):
            bytes_n = 0
        out.append(FlowRecord(
            destination_host=str(host),
            destination_port=port,
            source_ip=r.get("user_ip") or r.get("src_ip"),
            bytes_transferred=bytes_n,
            method=r.get("method"),
            user_agent=r.get("user_agent") or r.get("ua"),
            department=r.get("department") or r.get("user_dept"),
            raw=r,
        ))
    return out


def parse_aws_vpc_flow_logs(payload: Any) -> List[FlowRecord]:
    """AWS VPC Flow Logs (version 2) — space-delimited or JSON-lines."""
    out: List[FlowRecord] = []
    lines: List[str] = []
    if isinstance(payload, str):
        lines = payload.splitlines()
    elif isinstance(payload, list):
        for item in payload:
            if isinstance(item, str):
                lines.append(item)
            elif isinstance(item, dict):
                # AWS sometimes pre-parses to dict
                host = item.get("dstaddr") or item.get("destination_host")
                if host:
                    out.append(FlowRecord(
                        destination_host=str(host),
                        destination_port=int(item.get("dstport") or 443),
                        source_ip=item.get("srcaddr"),
                        bytes_transferred=int(item.get("bytes") or 0),
                        raw=item,
                    ))

    # version 2: version account-id interface-id srcaddr dstaddr srcport dstport protocol packets bytes start end action log-status
    for line in lines:
        parts = line.strip().split()
        if len(parts) < 10:
            continue
        try:
            srcaddr = parts[3]
            dstaddr = parts[4]
            dstport = int(parts[6])
            bytes_n = int(parts[9])
        except (IndexError, ValueError):
            continue
        out.append(FlowRecord(
            destination_host=dstaddr,
            destination_port=dstport,
            source_ip=srcaddr,
            bytes_transferred=bytes_n,
            raw={"line": line},
        ))
    return out


# ---------------------------------------------------------------------------
# Core ingestion
# ---------------------------------------------------------------------------

def _allowlist_patterns(db: Session, organization_id: Optional[str]) -> List[str]:
    """Return the active allowlist patterns for an organization (None = global)."""
    now = datetime.utcnow()
    rows = (
        db.query(ShadowAIAllowlist)
        .filter(
            (ShadowAIAllowlist.organization_id == organization_id)
            | (ShadowAIAllowlist.organization_id.is_(None))
        )
        .all()
    )
    out: List[str] = []
    for r in rows:
        if r.expires_at is not None and r.expires_at < now:
            continue
        out.append(r.host_pattern)
    return out


def _existing_recent_detection(
    db: Session,
    *,
    destination_host: str,
    source_ip: Optional[str],
    organization_id: Optional[str],
    window_minutes: int = 30,
) -> Optional[ShadowAIDetectionModel]:
    cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)
    return (
        db.query(ShadowAIDetectionModel)
        .filter(
            ShadowAIDetectionModel.destination_host == destination_host,
            ShadowAIDetectionModel.source_ip == source_ip,
            ShadowAIDetectionModel.organization_id == organization_id,
            ShadowAIDetectionModel.created_at >= cutoff,
        )
        .order_by(ShadowAIDetectionModel.created_at.desc())
        .first()
    )


def ingest_flow_records(
    db: Session,
    records: Iterable[FlowRecord],
    *,
    organization_id: Optional[str] = None,
    dedup_window_minutes: int = 30,
) -> IngestOutcome:
    """Classify and persist a batch of normalised flow records.

    Behaviour:
      - Hosts not in the AI provider list are dropped (not "shadow AI").
      - Hosts in the org's allowlist are dropped.
      - Repeats (same host + source_ip) within `dedup_window_minutes` are
        merged: existing detection's confidence_score is bumped, no new row.
    """
    outcome = IngestOutcome()
    allowlist = _allowlist_patterns(db, organization_id)

    for record in records:
        outcome.received += 1
        try:
            provider = detect_ai_provider(record.destination_host)
            if provider is None:
                continue  # not an AI host — silently drop
            outcome.classified_as_ai += 1

            if is_allowlisted(record.destination_host, allowlist):
                outcome.allowlisted += 1
                continue

            existing = _existing_recent_detection(
                db,
                destination_host=record.destination_host,
                source_ip=record.source_ip,
                organization_id=organization_id,
                window_minutes=dedup_window_minutes,
            )

            confidence = score_confidence(
                bytes_transferred=record.bytes_transferred,
                method=record.method or "GET",
                user_agent=record.user_agent,
                repeated_in_window=(
                    1 if existing is None else 5  # boost repeats
                ),
                department=record.department or "",
            )
            phi_risk = assess_phi_risk(
                record.destination_host,
                record.destination_port,
                record.department or "",
            )

            if existing is not None:
                # Bump existing detection's confidence + phi_risk
                if confidence > existing.confidence_score:
                    existing.confidence_score = confidence
                if (phi_risk == "high"
                        or (phi_risk == "medium" and existing.phi_risk_level == "low")):
                    existing.phi_risk_level = phi_risk
                outcome.detections_deduped += 1
                continue

            now = record.timestamp or datetime.utcnow()
            db.add(ShadowAIDetectionModel(
                id=str(uuid.uuid4()),
                detected_at=now,
                source_ip=record.source_ip,
                destination_host=record.destination_host,
                destination_port=record.destination_port,
                ai_provider=provider,
                confidence_score=confidence,
                department=record.department,
                phi_risk_level=phi_risk,
                status="detected",
                notes=(
                    f"Auto-ingested: bytes={record.bytes_transferred} "
                    f"method={record.method or '?'} "
                    f"ua={(record.user_agent or '')[:80]}"
                ),
                organization_id=organization_id,
                created_at=now,
            ))
            outcome.detections_created += 1
        except Exception as exc:
            outcome.errors.append(f"record={record.destination_host}: {exc}")
            logger.error("shadow_ai ingest record failed: %s", exc, exc_info=True)

    try:
        db.commit()
    except Exception as exc:
        outcome.errors.append(f"commit_failed: {exc}")
        try:
            db.rollback()
        except Exception:
            pass

    logger.info(
        "shadow_ai ingest: received=%d ai=%d created=%d deduped=%d allowlisted=%d errors=%d",
        outcome.received, outcome.classified_as_ai, outcome.detections_created,
        outcome.detections_deduped, outcome.allowlisted, len(outcome.errors),
    )
    return outcome


VENDOR_PARSERS = {
    "cloudflare": parse_cloudflare_logpush,
    "zscaler": parse_zscaler_siem,
    "netskope": parse_zscaler_siem,  # very similar shape
    "aws_vpc": parse_aws_vpc_flow_logs,
}


def ingest_vendor_payload(
    db: Session,
    *,
    vendor: str,
    payload: Any,
    organization_id: Optional[str] = None,
) -> IngestOutcome:
    """Parse a vendor-specific payload then run the canonical ingest pipeline."""
    parser = VENDOR_PARSERS.get(vendor.lower())
    if parser is None:
        outcome = IngestOutcome()
        outcome.errors.append(f"unsupported_vendor:{vendor}")
        return outcome
    records = parser(payload)
    return ingest_flow_records(
        db, records, organization_id=organization_id,
    )
