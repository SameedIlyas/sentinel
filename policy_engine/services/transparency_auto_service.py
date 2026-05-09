"""Transparency auto-generation on model card publish.

Tier 2 Sprint 1 — when a model card is published, auto-generate a draft
TransparencyRecord populated from the card's fields. The plain-language
summary is rewritten via an LLM if an API key is present, otherwise a
deterministic template is used so the demo flow works without external
dependencies.

The draft is created with `published_at=None` (not yet public) so a
compliance officer can review and click publish when ready.
"""
from __future__ import annotations

import logging
import os
import re
import textwrap
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from policy_engine.models.model_card import ModelCard
from policy_engine.models.transparency import (
    TransparencyRecordModel,
    TransparencyVersion,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Plain-language summarisation
# ---------------------------------------------------------------------------

_PLAIN_LANGUAGE_PROMPT = """You are a clinical-AI plain-language writer.
Rewrite the following technical clinical AI model description for a patient
audience at an 8th-grade reading level. Output 4-6 sentences in plain
English. Avoid jargon, acronyms, or numeric metrics — instead say what the
tool does, who it's for, when it should NOT be used, and why a clinician
oversight matters.

Technical description:
- Intended use: {intended_use}
- Indications: {indications}
- Contraindications: {contraindications}
- Population: {population}

Plain-language summary:"""


def _claude_summary(prompt: str) -> Optional[str]:
    """Call Anthropic Claude to generate the summary. Returns None on any failure."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        # Lazy-import so the policy engine doesn't hard-depend on anthropic
        from anthropic import Anthropic  # type: ignore

        client = Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"),
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        # SDK returns a list of content blocks; concat their .text attrs
        parts = []
        for block in getattr(msg, "content", []):
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        text = "".join(parts).strip()
        return text or None
    except Exception as exc:
        logger.warning("Claude summary failed, falling back to template: %s", exc)
        return None


def _template_summary(card: ModelCard) -> str:
    """Deterministic plain-language summary used when no LLM is available."""
    name = card.name or "This clinical AI model"
    intended_use = (card.intended_use or "support clinical decision-making").strip()
    indications = (card.clinical_indications or "").strip()
    contra = (card.contraindications or "").strip()

    # Strip bullets/markdown to reduce noise in the public summary
    def _clean(text: str) -> str:
        text = re.sub(r"^[\s\-\*•]+", "", text, flags=re.MULTILINE)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    intended_use = _clean(intended_use)
    indications = _clean(indications) or "appropriate clinical situations chosen by your care team"
    contra = _clean(contra) or "situations that fall outside the validated population"

    summary = (
        f"{name} is a clinical decision-support tool used by your care team. "
        f"It is designed to {intended_use}. "
        f"Clinicians use it for {indications}. "
        f"This tool is not used for {contra}. "
        "A doctor or other licensed clinician always reviews the model's "
        "suggestion before any care decision is made — the tool is an aid, "
        "not a replacement for human judgement. "
        "If you have questions about how this tool was used in your care, "
        "ask your care team or your facility's patient advocate."
    )
    return textwrap.dedent(summary).strip()


def generate_plain_language_summary(card: ModelCard) -> str:
    """Generate a plain-language summary from a model card.

    Tries Claude first (when ANTHROPIC_API_KEY is configured); otherwise
    returns a deterministic template. Always returns ≥ 50 chars (the
    transparency-record minimum).
    """
    prompt = _PLAIN_LANGUAGE_PROMPT.format(
        intended_use=card.intended_use or "(not specified)",
        indications=card.clinical_indications or "(not specified)",
        contraindications=card.contraindications or "(not specified)",
        population=card.organization_id or "(not specified)",
    )
    summary = _claude_summary(prompt)
    if summary and len(summary) >= 50:
        return summary
    return _template_summary(card)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TransparencyAutoResult:
    record_id: Optional[str]
    created: bool
    bumped_existing_version: bool = False
    skipped_reason: Optional[str] = None


def _build_performance_summary(card: ModelCard) -> Dict[str, Any]:
    """Project the card's performance_metrics into the public-facing shape."""
    perf = card.performance_metrics or {}
    # Strip sensitive internal keys (random hashes, paths) — keep public metrics
    public_keys = {
        "auc", "auroc", "accuracy", "sensitivity", "specificity",
        "ppv", "npv", "f1", "calibration", "n_external", "validation_sites",
    }
    return {k: v for k, v in perf.items() if k in public_keys}


def _draft_record_from_card(
    card: ModelCard,
    *,
    created_by: str,
) -> TransparencyRecordModel:
    """Build a draft TransparencyRecordModel from a ModelCard."""
    plain_language = generate_plain_language_summary(card)
    bias = card.bias_summary or {}
    bias_notes_parts = []
    if "max_disparity_ratio" in bias:
        bias_notes_parts.append(
            f"Maximum disparity ratio across measured subgroups: "
            f"{bias['max_disparity_ratio']}"
        )
    if "subgroups" in bias:
        bias_notes_parts.append(
            "Subgroup-level performance was evaluated; see the model card for details."
        )
    bias_considerations = (
        " ".join(bias_notes_parts)
        or "This model has been reviewed for fairness across demographic subgroups."
    )

    now = datetime.utcnow()
    return TransparencyRecordModel(
        id=str(uuid.uuid4()),
        model_name=card.name,
        model_version=card.version,
        algorithm_description=card.training_data_source,
        plain_language_summary=plain_language,
        evidence_base=card.training_data_source,
        intended_population=(
            card.clinical_indications or "Clinical population specified by deploying facility"
        ),
        known_limitations=(
            card.contraindications
            or "See the model card for limitations and out-of-scope situations."
        ),
        performance_summary=_build_performance_summary(card),
        bias_considerations=bias_considerations,
        regulatory_status=card.fda_status,
        published_at=None,  # Draft — compliance officer must review
        version_number=1,
        organization_id=card.organization_id,
        created_by=created_by,
        created_at=now,
        updated_at=now,
    )


def auto_create_or_bump_transparency(
    db: Session,
    card: ModelCard,
    *,
    created_by: str,
) -> TransparencyAutoResult:
    """Create or bump the transparency record for a published model card.

    Behaviour:
      - If no record exists for (model_name, model_version): create a fresh
        draft (published_at=None).
      - If a record exists for that exact name+version: leave it alone but
        return its id so callers can link.
      - If a record exists for the name but at a different version: clone
        forward, bump version_number, and capture the snapshot under
        TransparencyVersion.

    Failures never raise — they just return a result with skipped_reason set,
    so the publish flow stays unblocked.
    """
    try:
        # Exact match — already drafted, no-op
        existing_exact = (
            db.query(TransparencyRecordModel)
            .filter(
                TransparencyRecordModel.model_name == card.name,
                TransparencyRecordModel.model_version == card.version,
            )
            .first()
        )
        if existing_exact is not None:
            return TransparencyAutoResult(
                record_id=existing_exact.id,
                created=False,
                skipped_reason="record_already_exists",
            )

        # Name match at a different version → bump
        existing_prior = (
            db.query(TransparencyRecordModel)
            .filter(TransparencyRecordModel.model_name == card.name)
            .order_by(TransparencyRecordModel.version_number.desc())
            .first()
        )

        record = _draft_record_from_card(card, created_by=created_by)

        if existing_prior is not None:
            # Bump version on the existing chain rather than fork
            existing_prior.model_version = card.version
            existing_prior.version_number = existing_prior.version_number + 1
            existing_prior.algorithm_description = record.algorithm_description
            existing_prior.plain_language_summary = record.plain_language_summary
            existing_prior.evidence_base = record.evidence_base
            existing_prior.intended_population = record.intended_population
            existing_prior.known_limitations = record.known_limitations
            existing_prior.performance_summary = record.performance_summary
            existing_prior.bias_considerations = record.bias_considerations
            existing_prior.regulatory_status = record.regulatory_status
            existing_prior.published_at = None
            existing_prior.updated_at = datetime.utcnow()

            db.add(TransparencyVersion(
                id=str(uuid.uuid4()),
                record_id=existing_prior.id,
                version_number=existing_prior.version_number,
                content_snapshot={
                    "model_name": existing_prior.model_name,
                    "model_version": existing_prior.model_version,
                    "plain_language_summary": existing_prior.plain_language_summary,
                    "intended_population": existing_prior.intended_population,
                    "known_limitations": existing_prior.known_limitations,
                    "performance_summary": existing_prior.performance_summary or {},
                    "bias_considerations": existing_prior.bias_considerations,
                    "regulatory_status": existing_prior.regulatory_status,
                    "auto_generated_from_model_card": card.id,
                },
                change_summary=(
                    f"Auto-generated draft on model card publish "
                    f"(card_id={card.id}, version={card.version})"
                ),
                published_by=created_by,
                published_at=datetime.utcnow(),
            ))

            db.commit()
            logger.info(
                "Transparency record bumped on model card publish: "
                "record_id=%s name=%s new_version=%s",
                existing_prior.id, existing_prior.model_name, existing_prior.model_version,
            )
            return TransparencyAutoResult(
                record_id=existing_prior.id,
                created=False,
                bumped_existing_version=True,
            )

        # Fresh record
        db.add(record)
        db.flush()
        # Seed an initial version snapshot
        db.add(TransparencyVersion(
            id=str(uuid.uuid4()),
            record_id=record.id,
            version_number=1,
            content_snapshot={
                "model_name": record.model_name,
                "model_version": record.model_version,
                "plain_language_summary": record.plain_language_summary,
                "intended_population": record.intended_population,
                "known_limitations": record.known_limitations,
                "performance_summary": record.performance_summary or {},
                "bias_considerations": record.bias_considerations,
                "regulatory_status": record.regulatory_status,
                "auto_generated_from_model_card": card.id,
            },
            change_summary=(
                f"Auto-drafted from model card publish "
                f"(card_id={card.id}, version={card.version})"
            ),
            published_by=created_by,
            published_at=datetime.utcnow(),
        ))
        db.commit()

        logger.info(
            "Transparency record auto-drafted: record_id=%s model=%s version=%s",
            record.id, record.model_name, record.model_version,
        )
        return TransparencyAutoResult(record_id=record.id, created=True)

    except Exception as exc:
        logger.error("Transparency auto-create failed: %s", exc, exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass
        return TransparencyAutoResult(
            record_id=None,
            created=False,
            skipped_reason=f"error:{exc}",
        )
