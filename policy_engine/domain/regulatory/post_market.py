"""Post-Market Surveillance domain — adverse events, PSUR generation."""
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


class AdverseEventSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AdverseEventStatus(str, Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    REPORTED_TO_FDA = "reported_to_fda"


class PMSReportType(str, Enum):
    PSUR = "psur"        # Periodic Safety Update Report
    MDR = "mdr"          # Medical Device Report (FDA)
    INCIDENT = "incident"
    QUARTERLY = "quarterly"


class PMSReportStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    SUBMITTED = "submitted"


@dataclass
class AdverseEventEntity:
    id: str
    model_id: str
    event_type: str
    severity: AdverseEventSeverity
    description: str
    status: AdverseEventStatus = AdverseEventStatus.OPEN
    patient_impact: Optional[str] = None
    reported_by: Optional[str] = None
    agent_id: Optional[str] = None
    organization_id: Optional[str] = None

    def is_reportable_to_fda(self) -> bool:
        """True when severity is HIGH or CRITICAL — requires FDA MDR filing."""
        return self.severity in (AdverseEventSeverity.HIGH, AdverseEventSeverity.CRITICAL)

    def can_resolve(self) -> bool:
        """Can only be resolved if currently OPEN or INVESTIGATING."""
        return self.status in (AdverseEventStatus.OPEN, AdverseEventStatus.INVESTIGATING)


def classify_severity(
    patient_harm: bool,
    system_failure: bool,
    regulatory_violation: bool,
    data_breach: bool,
) -> AdverseEventSeverity:
    """
    Classify adverse event severity from four boolean flags.

    Rules (in priority order):
    - CRITICAL: patient harm OR (regulatory violation AND system failure)
    - HIGH: system failure alone OR regulatory violation alone
    - MEDIUM: data breach (no other major flag)
    - LOW: none of the above
    """
    if patient_harm or (regulatory_violation and system_failure):
        return AdverseEventSeverity.CRITICAL
    if system_failure or regulatory_violation:
        return AdverseEventSeverity.HIGH
    if data_breach:
        return AdverseEventSeverity.MEDIUM
    return AdverseEventSeverity.LOW


def aggregate_pms_metrics(adverse_events: List[Dict]) -> Dict:
    """
    Compute PMS aggregate metrics from a list of adverse event dicts.

    Each dict must have keys: severity, status.
    Returns a summary dict suitable for storing as PMSMetric rows.
    """
    total = len(adverse_events)
    by_severity: Dict[str, int] = {
        "low": 0, "medium": 0, "high": 0, "critical": 0
    }
    by_status: Dict[str, int] = {
        "open": 0, "investigating": 0, "resolved": 0, "reported_to_fda": 0
    }

    for ev in adverse_events:
        sev = ev.get("severity", "low")
        if sev in by_severity:
            by_severity[sev] += 1

        status = ev.get("status", "open")
        if status in by_status:
            by_status[status] += 1

    open_count = by_status["open"] + by_status["investigating"]
    critical_rate = by_severity["critical"] / total if total else 0.0
    resolution_rate = by_status["resolved"] / total if total else 0.0

    return {
        "total_events": total,
        "by_severity": by_severity,
        "by_status": by_status,
        "open_count": open_count,
        "critical_rate": round(critical_rate, 4),
        "resolution_rate": round(resolution_rate, 4),
    }


def generate_psur_summary(metrics: Dict, period_days: int) -> str:
    """
    Generate a PSUR plain-text summary from aggregated metrics.

    The summary is designed to be human-readable and suitable for
    regulatory submission supporting documentation.
    """
    total = metrics.get("total_events", 0)
    critical_rate = metrics.get("critical_rate", 0.0)
    resolution_rate = metrics.get("resolution_rate", 0.0)
    open_count = metrics.get("open_count", 0)

    if critical_rate >= 0.20:
        risk_level = "CRITICAL"
    elif critical_rate >= 0.10:
        risk_level = "HIGH"
    elif critical_rate >= 0.05:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    return (
        f"PSUR Summary ({period_days}-day period): "
        f"Total adverse events: {total}. "
        f"Critical rate: {critical_rate:.1%}. "
        f"Resolution rate: {resolution_rate:.1%}. "
        f"Open/investigating: {open_count}. "
        f"Overall risk level: {risk_level}."
    )
