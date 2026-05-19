"""Enforce ``organization_id NOT NULL`` on multi-tenant tables.

CRIT-010 — historically every multi-tenant table accepted
``organization_id IS NULL``, which produced two distinct hazards:

1. A bug that forgot to set ``organization_id`` on insert silently
   produced a tenant-less row that no scope filter would ever exclude.
2. The ``ON DELETE SET NULL`` cascade on the FK meant deleting an
   organisation row could quietly orphan every child — losing the
   tenancy boundary entirely.

This migration **surveys** each target table first and refuses to run
if any row has ``organization_id IS NULL``. Operators must run
``scripts/backfill_organization_id.py`` (creates an "unknown" sentinel
org, attaches orphans) and re-run.

Per-table FK switch from ``ON DELETE SET NULL`` → ``ON DELETE
RESTRICT`` is intentionally **out of scope** here. PR #10 already
landed the alerts.audit_log_id real-FK fix; the remaining
``organization_id`` FK semantics change is deferred to a Pass-2
migration where it can be paired with PostgreSQL row-level security
(see REVIEW.md ARCH-FOLLOWUP).

Revision ID: 020
Revises: 019
"""
from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect


revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


logger = logging.getLogger("alembic.020")


# (table_name, column_name) pairs.
# Most tables use ``organization_id`` — the clinic tables added in
# migration 008-018 use ``org_id``. Both are included so the contract
# holds across the full multi-tenant surface.
_TARGETS: tuple[tuple[str, str], ...] = (
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


def _survey_nulls(bind, table: str, column: str) -> int:
    """Return the count of rows where ``column`` is NULL.

    Returns 0 if the table or column doesn't exist on this DB.
    """
    inspector = sa_inspect(bind)
    if table not in set(inspector.get_table_names()):
        return 0
    cols = {c["name"] for c in inspector.get_columns(table)}
    if column not in cols:
        return 0
    result = bind.execute(
        sa.text(f'SELECT COUNT(*) FROM {table} WHERE "{column}" IS NULL')
    )
    return int(result.scalar() or 0)


def upgrade() -> None:
    bind = op.get_bind()

    # ── Step 1: survey ──────────────────────────────────────────────
    orphans: dict[tuple[str, str], int] = {}
    for table, column in _TARGETS:
        count = _survey_nulls(bind, table, column)
        if count:
            orphans[(table, column)] = count

    if orphans:
        msg_lines = [
            "CRIT-010 backfill required — refusing to set NOT NULL on tables",
            "with orphan rows. Run scripts/backfill_organization_id.py and re-run.",
            "",
            "Tables with NULL tenancy:",
        ]
        for (t, c), n in sorted(orphans.items()):
            msg_lines.append(f"  {t}.{c}: {n} NULL row(s)")
        raise RuntimeError("\n".join(msg_lines))

    # ── Step 2: ALTER each column to NOT NULL ───────────────────────
    inspector = sa_inspect(bind)
    existing_tables = set(inspector.get_table_names())
    for table, column in _TARGETS:
        if table not in existing_tables:
            logger.info("020: table %s absent — skipping", table)
            continue
        cols = {c["name"]: c for c in inspector.get_columns(table)}
        if column not in cols:
            logger.info("020: column %s.%s absent — skipping", table, column)
            continue
        if cols[column].get("nullable") is False:
            logger.info(
                "020: column %s.%s already NOT NULL — skipping", table, column
            )
            continue
        with op.batch_alter_table(table) as batch:
            batch.alter_column(column, existing_type=sa.String(), nullable=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    existing_tables = set(inspector.get_table_names())
    for table, column in _TARGETS:
        if table not in existing_tables:
            continue
        cols = {c["name"]: c for c in inspector.get_columns(table)}
        if column not in cols:
            continue
        if cols[column].get("nullable") is True:
            continue
        with op.batch_alter_table(table) as batch:
            batch.alter_column(column, existing_type=sa.String(), nullable=True)
