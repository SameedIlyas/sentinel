"""Backfill ``organization_id`` on multi-tenant tables.

CRIT-010 prerequisite — migration 020 refuses to set NOT NULL on tables
that still contain NULL-tenancy rows. This script:

1. Surveys every target table for orphans (NULL ``organization_id`` / ``org_id``).
2. Where possible, infers the owning org from a related table
   (e.g. ``audit_logs.organization_id`` may be derivable from
   ``agents.organization_id`` via ``agent_id``).
3. Falls back to a single sentinel "unknown" Organization that lets the
   migration succeed without losing the historical record. Operators
   should hand-curate the sentinel rows after the fact.

The script is **idempotent** — running it twice is a no-op once all
orphans are attached.

Usage::

    python scripts/backfill_organization_id.py            # apply
    python scripts/backfill_organization_id.py --dry-run  # report only

Environment:
    DATABASE_URL must point at the target database.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import uuid
from typing import Iterable

# Ensure project root on path when run as a script
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sqlalchemy import text
from sqlalchemy.orm import Session

from policy_engine.database import SessionLocal
from policy_engine.models.organization import Organization


logger = logging.getLogger("backfill_organization_id")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


# Same target list as migration 020. (table, column) — kept here so the
# script and the migration can drift independently if needed.
TARGETS: tuple[tuple[str, str], ...] = (
    ("audit_logs", "organization_id"),
    ("alerts", "organization_id"),
    ("prior_auth_records", "organization_id"),
    ("hitl_reviews", "organization_id"),
    ("shadow_ai_detections", "organization_id"),
    ("scribe_audits", "organization_id"),
    ("model_cards", "organization_id"),
    ("bias_audits", "organization_id"),
    ("revenue_cycle_audits", "organization_id"),
    ("risk_scores", "organization_id"),
    ("clinic_ai_tools", "org_id"),
    ("clinic_ai_observations", "org_id"),
    ("clinic_report_artifacts", "org_id"),
)


SENTINEL_SLUG = "_orphan_pre_crit010"


def _ensure_sentinel_org(db: Session) -> str:
    """Return the id of the orphan-recovery sentinel org, creating it if needed."""
    org = db.query(Organization).filter(Organization.slug == SENTINEL_SLUG).first()
    if org is not None:
        return org.id
    org = Organization(
        id=str(uuid.uuid4()),
        name="Orphan pre-CRIT-010 (recovery)",
        slug=SENTINEL_SLUG,
        tier="enterprise",
    )
    db.add(org)
    db.commit()
    logger.info(
        "Created sentinel organization %s for orphan recovery (slug=%s).",
        org.id,
        SENTINEL_SLUG,
    )
    return org.id


def _count_orphans(db: Session, table: str, column: str) -> int:
    try:
        result = db.execute(
            text(f'SELECT COUNT(*) FROM {table} WHERE "{column}" IS NULL')
        )
        return int(result.scalar() or 0)
    except Exception as e:
        logger.warning("Skipping survey of %s.%s: %s", table, column, e)
        return 0


def _try_infer_audit_log_orgs(db: Session) -> int:
    """For audit_logs with NULL organization_id, copy from agents.organization_id
    where agent_id matches and the agent's org_id is known."""
    result = db.execute(
        text(
            """
            UPDATE audit_logs
               SET organization_id = (
                   SELECT agents.organization_id
                     FROM agents
                    WHERE agents.id = audit_logs.agent_id
                      AND agents.organization_id IS NOT NULL
               )
             WHERE audit_logs.organization_id IS NULL
               AND EXISTS (
                   SELECT 1 FROM agents
                    WHERE agents.id = audit_logs.agent_id
                      AND agents.organization_id IS NOT NULL
               )
            """
        )
    )
    return int(result.rowcount or 0)


def _backfill_sentinel(db: Session, table: str, column: str, sentinel_id: str) -> int:
    result = db.execute(
        text(
            f'UPDATE {table} SET "{column}" = :org WHERE "{column}" IS NULL'
        ),
        {"org": sentinel_id},
    )
    return int(result.rowcount or 0)


def _survey(db: Session) -> dict[tuple[str, str], int]:
    return {
        (t, c): _count_orphans(db, t, c) for t, c in TARGETS
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Survey only — do not modify any rows.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    db = SessionLocal()
    try:
        survey_before = _survey(db)
        total_before = sum(survey_before.values())
        logger.info("Orphan survey (before): %d total NULL-tenancy rows.", total_before)
        for (t, c), n in sorted(survey_before.items()):
            if n:
                logger.info("  %s.%s: %d NULL", t, c, n)

        if total_before == 0:
            logger.info("Nothing to do.")
            return 0

        if args.dry_run:
            logger.info("Dry-run requested — exiting without modification.")
            return 0

        # Phase 1 — infer audit_logs from agents.
        try:
            inferred = _try_infer_audit_log_orgs(db)
            db.commit()
            logger.info("Inferred audit_logs.organization_id for %d rows.", inferred)
        except Exception as e:
            db.rollback()
            logger.warning("Inference pass failed: %s", e)

        # Phase 2 — sentinel fallback.
        sentinel_id = _ensure_sentinel_org(db)
        for table, column in TARGETS:
            remaining = _count_orphans(db, table, column)
            if remaining == 0:
                continue
            applied = _backfill_sentinel(db, table, column, sentinel_id)
            db.commit()
            logger.info(
                "Backfilled %d orphan rows in %s.%s → sentinel %s",
                applied,
                table,
                column,
                sentinel_id,
            )

        survey_after = _survey(db)
        total_after = sum(survey_after.values())
        logger.info("Orphan survey (after): %d total NULL-tenancy rows.", total_after)
        if total_after:
            for (t, c), n in sorted(survey_after.items()):
                if n:
                    logger.warning("  %s.%s: %d NULL remain", t, c, n)
            return 1
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
