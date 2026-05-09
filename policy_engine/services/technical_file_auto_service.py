"""Technical file auto-population from upstream artifacts.

Tier 2 Sprint 4 — given a `TechnicalFile` and a `model_card_id`, populate the
file's sections from the model card, MLflow metrics (already in
ModelCard.performance_metrics), bias audit results, adverse events, and PMS
reports. Sections are marked `auto_generated=True` so reviewers know what
to verify.

This is a service module that the existing `/v1/regulatory/technical-files`
endpoint can opt into via a query flag, and that the scheduler can run on a
weekly cadence to re-sync stale sections.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from policy_engine.models.bias_audit import BiasAuditModel, BiasAuditResultModel
from policy_engine.models.model_card import ModelCard
from policy_engine.models.post_market import (
    AdverseEvent,
    AdverseEventSeverityDB,
    PMSReport,
)
from policy_engine.models.technical_file import (
    RegulatoryTypeDB,
    TechnicalFile,
    TechnicalFileSection,
)

logger = logging.getLogger(__name__)


SECTION_DEVICE_DESCRIPTION = "device_description"
SECTION_INTENDED_USE = "intended_use"
SECTION_PERFORMANCE_DATA = "performance_data"
SECTION_RISK_MANAGEMENT = "risk_management"
SECTION_CLINICAL_EVALUATION = "clinical_evaluation"
SECTION_PREDICATE_COMPARISON = "predicate_comparison"
SECTION_PMS_PLAN = "clinical_post_market_plan"
SECTION_CLINICAL_EVIDENCE = "clinical_evidence"


# ---------------------------------------------------------------------------
# Per-regulation section list
# ---------------------------------------------------------------------------

_FDA_510K_SECTIONS = [
    SECTION_DEVICE_DESCRIPTION,
    SECTION_INTENDED_USE,
    SECTION_PERFORMANCE_DATA,
    SECTION_RISK_MANAGEMENT,
    SECTION_CLINICAL_EVALUATION,
    SECTION_PREDICATE_COMPARISON,
]

_EU_MDR_SECTIONS = _FDA_510K_SECTIONS + [
    SECTION_PMS_PLAN,
    SECTION_CLINICAL_EVIDENCE,
]


def _sections_for_type(reg_type: RegulatoryTypeDB) -> List[str]:
    if reg_type == RegulatoryTypeDB.FDA_510K:
        return list(_FDA_510K_SECTIONS)
    if reg_type == RegulatoryTypeDB.EU_MDR:
        return list(_EU_MDR_SECTIONS)
    if reg_type == RegulatoryTypeDB.BOTH:
        # Union, preserving order
        seen, merged = set(), []
        for s in _FDA_510K_SECTIONS + _EU_MDR_SECTIONS:
            if s not in seen:
                seen.add(s)
                merged.append(s)
        return merged
    return list(_FDA_510K_SECTIONS)


# ---------------------------------------------------------------------------
# Per-section content builders
# ---------------------------------------------------------------------------

def _section_device_description(card: ModelCard) -> str:
    parts = [
        f"## Device Description",
        f"**Product**: {card.name}",
        f"**Version**: {card.version}",
        f"**Lifecycle**: {card.lifecycle_stage}",
        f"**FDA Status**: {card.fda_status or '_(not assigned)_'}",
        f"**CHAI Version**: {card.chai_version}",
        "",
        f"**Training data source**: {card.training_data_source or '_(unspecified)_'}",
        f"**Model artifact URI**: {card.model_artifact_uri or '_(not pinned)_'}",
        f"**Training dataset SHA-256**: {card.training_dataset_sha256 or '_(not pinned)_'}",
        f"**Evaluation dataset SHA-256**: {card.evaluation_dataset_sha256 or '_(not pinned)_'}",
        f"**Framework version**: {card.framework_version or '_(unspecified)_'}",
    ]
    return "\n".join(parts)


def _section_intended_use(card: ModelCard) -> str:
    return "\n".join([
        "## Intended Use",
        card.intended_use or "_(intended_use not yet documented)_",
        "",
        "### Indications for use",
        card.clinical_indications or "_(indications not yet documented)_",
        "",
        "### Out-of-scope / Contraindications",
        card.contraindications or "_(contraindications not yet documented — REQUIRES REVIEW)_",
    ])


def _section_performance_data(card: ModelCard) -> str:
    perf = card.performance_metrics or {}
    if not perf:
        return (
            "## Performance Data\n"
            "_No performance metrics available. Run an evaluation pipeline and "
            "populate `performance_metrics` on the linked model card._"
        )
    lines = ["## Performance Data", ""]
    for key, value in perf.items():
        lines.append(f"- **{key}**: {value}")

    ext_val = card.external_validation or {}
    if ext_val:
        lines.append("")
        lines.append("### External validation")
        for key, value in ext_val.items():
            lines.append(f"- **{key}**: {value}")
    return "\n".join(lines)


def _section_risk_management(
    card: ModelCard,
    *,
    open_events: int,
    critical_events: int,
    bias_failures: int,
) -> str:
    lines = [
        "## Risk Management",
        "Risk management is performed continuously via Sentinel governance.",
        "",
        f"**Open adverse events**: {open_events}",
        f"**Critical/high severity events (last 12 months)**: {critical_events}",
        f"**Failing bias-audit subgroups (most recent audit)**: {bias_failures}",
        "",
        "### Predetermined Change Control Plan (FDA 2023 PCCP guidance)",
    ]
    pccp = card.pccp or {}
    if pccp:
        for key, value in pccp.items():
            lines.append(f"- **{key}**: {value}")
    else:
        lines.append("_No PCCP authored — required for adaptive AI under FDA SaMD._")
    return "\n".join(lines)


def _section_clinical_evaluation(
    card: ModelCard,
    *,
    bias_audits: List[BiasAuditModel],
) -> str:
    lines = [
        "## Clinical Evaluation",
        f"This evaluation summarises the clinical assessment of {card.name} v{card.version}.",
        "",
    ]
    if not bias_audits:
        lines.append("_No bias audits on file. A subgroup fairness audit is required._")
        return "\n".join(lines)

    for audit in bias_audits[:5]:
        lines.append(
            f"### Audit `{audit.audit_name}` "
            f"(status={audit.status}, completed={audit.completed_at})"
        )
        if audit.dataset_description:
            lines.append(f"_Dataset:_ {audit.dataset_description}")
        lines.append("")
    return "\n".join(lines)


def _section_predicate_comparison(card: ModelCard) -> str:
    return (
        "## Predicate Comparison (FDA 510(k))\n"
        f"Identify legally marketed predicate device for {card.name}, "
        "compare intended use, technological characteristics, and "
        "performance. Mark substantial equivalence claims here.\n\n"
        "_This section requires regulatory analyst input — auto-population "
        "cannot replace clinical-equivalence reasoning._"
    )


def _section_pms_plan(
    card: ModelCard, recent_pms: List[PMSReport]
) -> str:
    lines = [
        "## Post-Market Surveillance Plan (EU MDR)",
        "Surveillance is performed continuously via the Sentinel platform.",
        "",
    ]
    monitoring = card.monitoring_plan or {}
    if monitoring:
        for k, v in monitoring.items():
            lines.append(f"- **{k}**: {v}")
        lines.append("")
    if recent_pms:
        lines.append("### Recent PMS / PSUR reports")
        for r in recent_pms[:5]:
            lines.append(
                f"- {r.report_type.value} "
                f"({r.period_start.date()}..{r.period_end.date()}) — "
                f"status={r.status.value}"
            )
    else:
        lines.append("_No PMS reports on file yet. Quarterly + annual auto-generation enabled._")
    return "\n".join(lines)


def _section_clinical_evidence(
    card: ModelCard,
    *,
    open_events: int,
    critical_events: int,
) -> str:
    lines = [
        "## Clinical Evidence",
        f"Performance is monitored on production data. To date "
        f"{open_events} open adverse events and {critical_events} "
        "critical/high-severity events have been logged.",
        "",
    ]
    perf = card.performance_metrics or {}
    if perf:
        lines.append("### Latest validated performance metrics")
        for k, v in perf.items():
            lines.append(f"- **{k}**: {v}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@dataclass
class PopulateOutcome:
    file_id: str
    sections_created: int = 0
    sections_updated: int = 0
    sections_skipped: int = 0
    errors: List[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []


def _adverse_event_counts(
    db: Session, model_id: str
) -> Tuple[int, int]:
    """Return (open_count, critical_or_high_in_last_year)."""
    cutoff = datetime.utcnow() - timedelta(days=365)
    events = (
        db.query(AdverseEvent)
        .filter(AdverseEvent.model_id == model_id)
        .all()
    )
    open_count = sum(
        1 for e in events
        if (e.status.value if hasattr(e.status, "value") else str(e.status))
        in ("open", "investigating")
    )
    critical = sum(
        1 for e in events
        if e.reported_at >= cutoff and e.severity in (
            AdverseEventSeverityDB.HIGH, AdverseEventSeverityDB.CRITICAL,
        )
    )
    return open_count, critical


def _bias_audit_failure_count(db: Session, model_id: str) -> Tuple[int, List[BiasAuditModel]]:
    """Return (failing_subgroup_count, recent_complete_audits)."""
    audits = (
        db.query(BiasAuditModel)
        .filter(
            BiasAuditModel.model_card_id == model_id,
            BiasAuditModel.status == "complete",
        )
        .order_by(BiasAuditModel.completed_at.desc())
        .limit(10)
        .all()
    )
    if not audits:
        return 0, []
    most_recent_id = audits[0].id
    failing = (
        db.query(BiasAuditResultModel)
        .filter(
            BiasAuditResultModel.audit_id == most_recent_id,
            BiasAuditResultModel.passes_threshold.is_(False),
        )
        .count()
    )
    return failing, audits


def populate_from_model_card(
    db: Session,
    *,
    technical_file_id: str,
    model_card_id: str,
    overwrite: bool = False,
) -> PopulateOutcome:
    """Populate (or refresh) sections of a TechnicalFile from a ModelCard +
    associated bias audits, adverse events, and PMS reports.

    Args:
        overwrite: If True, replace content of existing auto-generated sections.
            If False, only fill missing sections (preserves human edits).
    """
    outcome = PopulateOutcome(file_id=technical_file_id)

    tf = (
        db.query(TechnicalFile)
        .filter(TechnicalFile.id == technical_file_id)
        .first()
    )
    if tf is None:
        outcome.errors.append("technical_file_not_found")
        return outcome

    card = (
        db.query(ModelCard)
        .filter(ModelCard.id == model_card_id)
        .first()
    )
    if card is None:
        outcome.errors.append("model_card_not_found")
        return outcome

    open_events, critical_events = _adverse_event_counts(db, card.id)
    failing_subgroups, audits = _bias_audit_failure_count(db, card.id)
    recent_pms = (
        db.query(PMSReport)
        .filter(PMSReport.organization_id == card.organization_id)
        .order_by(PMSReport.period_end.desc())
        .limit(10)
        .all()
    )

    section_builders = {
        SECTION_DEVICE_DESCRIPTION: lambda: _section_device_description(card),
        SECTION_INTENDED_USE: lambda: _section_intended_use(card),
        SECTION_PERFORMANCE_DATA: lambda: _section_performance_data(card),
        SECTION_RISK_MANAGEMENT: lambda: _section_risk_management(
            card,
            open_events=open_events,
            critical_events=critical_events,
            bias_failures=failing_subgroups,
        ),
        SECTION_CLINICAL_EVALUATION: lambda: _section_clinical_evaluation(
            card, bias_audits=audits,
        ),
        SECTION_PREDICATE_COMPARISON: lambda: _section_predicate_comparison(card),
        SECTION_PMS_PLAN: lambda: _section_pms_plan(card, recent_pms),
        SECTION_CLINICAL_EVIDENCE: lambda: _section_clinical_evidence(
            card,
            open_events=open_events,
            critical_events=critical_events,
        ),
    }

    section_types = _sections_for_type(tf.regulatory_type)
    existing = {
        s.section_type: s
        for s in (
            db.query(TechnicalFileSection)
            .filter(TechnicalFileSection.file_id == tf.id)
            .all()
        )
    }
    now = datetime.utcnow()

    for index, section_type in enumerate(section_types):
        try:
            content = section_builders[section_type]()
            existing_section = existing.get(section_type)

            if existing_section is None:
                db.add(TechnicalFileSection(
                    id=str(uuid.uuid4()),
                    file_id=tf.id,
                    section_type=section_type,
                    content=content,
                    order_index=index,
                    auto_generated=True,
                    created_at=now,
                    updated_at=now,
                ))
                outcome.sections_created += 1
            elif existing_section.auto_generated and overwrite:
                existing_section.content = content
                existing_section.order_index = index
                existing_section.updated_at = now
                outcome.sections_updated += 1
            elif not existing_section.auto_generated:
                outcome.sections_skipped += 1  # human-authored, leave alone
            else:
                outcome.sections_skipped += 1
        except Exception as exc:
            outcome.errors.append(f"section={section_type} error={exc}")
            logger.error("populate section %s failed: %s", section_type, exc, exc_info=True)

    try:
        db.commit()
    except Exception as exc:
        outcome.errors.append(f"commit_failed: {exc}")
        try:
            db.rollback()
        except Exception:
            pass

    logger.info(
        "Tech file populated: file_id=%s created=%d updated=%d skipped=%d errors=%d",
        tf.id, outcome.sections_created, outcome.sections_updated,
        outcome.sections_skipped, len(outcome.errors),
    )
    return outcome
