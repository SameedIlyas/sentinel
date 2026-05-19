"""Add audit-log legal-hold + convert alerts.audit_log_id to a real FK.

CRIT-008 — the retention sweep deleted any row older than ``RETENTION_DAYS``
unconditionally. There was no way to flag a row as "under legal hold"
(litigation, regulatory request, internal investigation) and exempt it
from purge. There was also no FK on ``alerts.audit_log_id``: it was a
plain ``String`` column, so purging an audit row left a dangling
pointer in ``alerts``.

This migration:

1. Adds ``audit_logs.legal_hold BOOLEAN NOT NULL DEFAULT FALSE``.
2. Adds a covering index on ``(organization_id, timestamp)`` (defensive —
   the retention sweep scans this combination, large multi-tenant
   deployments need the index to avoid full-table scans).
3. Adds a partial-index on ``legal_hold=TRUE`` so legal-hold rows can be
   counted / listed without scanning the whole table.
4. Converts ``alerts.audit_log_id`` to a real foreign key with
   ``ON DELETE SET NULL`` so the cascade does not produce dangling
   references when the audit row is finally purged.

Revision ID: 021
Revises: 020
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect


revision = "021"
# 020 (org_id NOT NULL) hasn't landed yet but is queued — order here is
# legal-hold first, then NOT NULL, so the NOT NULL migration can switch
# FKs to ON DELETE RESTRICT *after* the dangling-FK risk on alerts is
# resolved.
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    dialect = bind.dialect.name

    if "audit_logs" not in set(inspector.get_table_names()):
        return

    # ── 1. legal_hold column ────────────────────────────────────────────
    audit_cols = {c["name"] for c in inspector.get_columns("audit_logs")}
    if "legal_hold" not in audit_cols:
        with op.batch_alter_table("audit_logs") as batch:
            batch.add_column(
                sa.Column(
                    "legal_hold",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text("0" if dialect == "sqlite" else "false"),
                )
            )

    # ── 2/3. indexes — only create when absent ──────────────────────────
    audit_index_names = {ix["name"] for ix in inspector.get_indexes("audit_logs")}
    if "ix_audit_logs_org_id_timestamp" not in audit_index_names:
        op.create_index(
            "ix_audit_logs_org_id_timestamp",
            "audit_logs",
            ["organization_id", "timestamp"],
        )
    # Partial index — supported on Postgres + SQLite ≥3.8 but not MySQL.
    # We use a regular index on legal_hold to keep cross-DB portability;
    # the small footprint outweighs the marginal benefit of partial.
    if "ix_audit_logs_legal_hold" not in audit_index_names:
        op.create_index(
            "ix_audit_logs_legal_hold",
            "audit_logs",
            ["legal_hold"],
        )

    # ── 4. alerts.audit_log_id -> real FK ───────────────────────────────
    if "alerts" in set(inspector.get_table_names()):
        # Some rows may reference now-purged audit logs; null them so the
        # FK constraint can succeed.
        op.execute(
            """
            UPDATE alerts
               SET audit_log_id = NULL
             WHERE audit_log_id IS NOT NULL
               AND NOT EXISTS (
                   SELECT 1 FROM audit_logs WHERE audit_logs.id = alerts.audit_log_id
               )
            """
        )

        # Add the FK in a batch op so SQLite can rebuild the table.
        existing_fks = {
            fk.get("name")
            for fk in inspector.get_foreign_keys("alerts")
            if fk.get("name")
        }
        if "fk_alerts_audit_log_id" not in existing_fks:
            with op.batch_alter_table("alerts") as batch:
                batch.create_foreign_key(
                    "fk_alerts_audit_log_id",
                    "audit_logs",
                    ["audit_log_id"],
                    ["id"],
                    ondelete="SET NULL",
                )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)

    if "alerts" in set(inspector.get_table_names()):
        fk_names = {
            fk.get("name")
            for fk in inspector.get_foreign_keys("alerts")
            if fk.get("name")
        }
        if "fk_alerts_audit_log_id" in fk_names:
            with op.batch_alter_table("alerts") as batch:
                batch.drop_constraint(
                    "fk_alerts_audit_log_id", type_="foreignkey"
                )

    if "audit_logs" in set(inspector.get_table_names()):
        index_names = {ix["name"] for ix in inspector.get_indexes("audit_logs")}
        if "ix_audit_logs_legal_hold" in index_names:
            op.drop_index("ix_audit_logs_legal_hold", table_name="audit_logs")
        if "ix_audit_logs_org_id_timestamp" in index_names:
            op.drop_index(
                "ix_audit_logs_org_id_timestamp", table_name="audit_logs"
            )
        col_names = {c["name"] for c in inspector.get_columns("audit_logs")}
        if "legal_hold" in col_names:
            with op.batch_alter_table("audit_logs") as batch:
                batch.drop_column("legal_hold")
