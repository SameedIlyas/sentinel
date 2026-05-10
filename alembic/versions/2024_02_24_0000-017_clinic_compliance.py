"""Clinic compliance — close cross-tenant alert leak + hashed extension tokens.

Adds:
    alerts.organization_id        — FK to organizations(id), backfilled from
                                    audit_logs.organization_id where the
                                    alert references an audit log row.
                                    Closes the cross-tenant alert leak (HIPAA
                                    §164.312(a)(1) access control).
    clinic_extension_tokens       — replaces plaintext-in-settings token
                                    storage with a SHA-256 hashed,
                                    indexed lookup table (GDPR Art. 32).

Revision ID: 017
Revises: 016
Create Date: 2024-02-24 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    tables = set(inspector.get_table_names())

    # ── 1. alerts.organization_id ───────────────────────────────────────
    if "alerts" in tables:
        existing = {col["name"] for col in inspector.get_columns("alerts")}
        if "organization_id" not in existing:
            with op.batch_alter_table("alerts") as batch_op:
                batch_op.add_column(
                    sa.Column(
                        "organization_id",
                        sa.String(),
                        sa.ForeignKey(
                            "organizations.id",
                            ondelete="SET NULL",
                            name="fk_alerts_organization_id",
                        ),
                        nullable=True,
                    )
                )
            op.create_index(
                "ix_alerts_organization_id",
                "alerts",
                ["organization_id"],
            )
            # Backfill from the linked audit log where present.  Use raw SQL
            # because a SQLAlchemy correlated update on SQLite is awkward.
            try:
                op.execute(
                    """
                    UPDATE alerts
                       SET organization_id = (
                         SELECT audit_logs.organization_id
                           FROM audit_logs
                          WHERE audit_logs.id = alerts.audit_log_id
                       )
                     WHERE alerts.audit_log_id IS NOT NULL
                       AND alerts.organization_id IS NULL
                    """
                )
            except Exception:
                # Best-effort backfill — production envs may have inconsistent
                # legacy data and we'd rather not fail the migration here.
                pass

    # ── 2. clinic_extension_tokens ──────────────────────────────────────
    if "clinic_extension_tokens" not in tables:
        op.create_table(
            "clinic_extension_tokens",
            sa.Column("id", sa.String(), primary_key=True, nullable=False),
            sa.Column(
                "org_id",
                sa.String(),
                sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                nullable=False,
                unique=True,
                index=True,
            ),
            sa.Column("token_hash", sa.String(), nullable=False),
            sa.Column("issued_at", sa.DateTime(), nullable=False),
            sa.Column("issued_by_user_id", sa.String(), nullable=True),
            sa.Column("last_used_at", sa.DateTime(), nullable=True),
            sa.Column("revoked_at", sa.DateTime(), nullable=True),
        )
        op.create_index(
            "ix_clinic_extension_tokens_hash",
            "clinic_extension_tokens",
            ["token_hash"],
            unique=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    tables = set(inspector.get_table_names())

    if "clinic_extension_tokens" in tables:
        try:
            op.drop_index(
                "ix_clinic_extension_tokens_hash",
                table_name="clinic_extension_tokens",
            )
        except Exception:
            pass
        op.drop_table("clinic_extension_tokens")

    if "alerts" in tables:
        existing = {col["name"] for col in inspector.get_columns("alerts")}
        if "organization_id" in existing:
            try:
                op.drop_index("ix_alerts_organization_id", table_name="alerts")
            except Exception:
                pass
            with op.batch_alter_table("alerts") as batch_op:
                batch_op.drop_column("organization_id")
