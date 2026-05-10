"""Clinic tier — add tier column + clinic-only tables.

Phase: Clinic SaaS persona ($199 / $349 / $699 per month).

Adds:
    organizations.tier            — string flag, default "enterprise" so every
                                    existing tenant keeps its current behavior.
    clinic_ai_tools               — manually registered AI tools (lightweight
                                    model_card alternative for clinics).
    clinic_ai_observations        — Shadow AI Lite detections from the
                                    browser-extension + DNS-only detector.
    billing_events                — Stripe webhook audit trail.  Schema is a
                                    strict subset of BILLING_IMPLEMENTATION.md
                                    §3.2 — when the full billing system lands,
                                    no migration needed; only the handler grows.
    clinic_report_artifacts       — pointer to generated monthly PDF reports.

Revision ID: 016
Revises: 015
Create Date: 2024-02-23 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)

    # ── 1. Organization.tier ────────────────────────────────────────────
    if "organizations" in inspector.get_table_names():
        existing = {col["name"] for col in inspector.get_columns("organizations")}
        if "tier" not in existing:
            with op.batch_alter_table("organizations") as batch_op:
                batch_op.add_column(
                    sa.Column(
                        "tier",
                        sa.String(),
                        nullable=False,
                        server_default=sa.text("'enterprise'"),
                    )
                )
            # Drop the server_default after backfill so application code owns
            # the value — avoids surprise default churn on later inserts.
            with op.batch_alter_table("organizations") as batch_op:
                batch_op.alter_column("tier", server_default=None)
            op.create_index(
                "ix_organizations_tier", "organizations", ["tier"], unique=False
            )

    # ── 2. clinic_ai_tools ──────────────────────────────────────────────
    if "clinic_ai_tools" not in inspector.get_table_names():
        op.create_table(
            "clinic_ai_tools",
            sa.Column("id", sa.String(), primary_key=True, nullable=False),
            sa.Column(
                "org_id",
                sa.String(),
                sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("vendor", sa.String(), nullable=True),
            sa.Column("category", sa.String(), nullable=False, server_default="other"),
            sa.Column("purpose", sa.String(), nullable=True),
            sa.Column(
                "handles_phi",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column("risk_level", sa.String(), nullable=False, server_default="low"),
            sa.Column("status", sa.String(), nullable=False, server_default="active"),
            sa.Column(
                "owner_user_id",
                sa.String(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("notes", sa.String(), nullable=True),
            sa.Column(
                "source", sa.String(), nullable=False, server_default="manual"
            ),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )

    # ── 3. clinic_ai_observations ───────────────────────────────────────
    if "clinic_ai_observations" not in inspector.get_table_names():
        op.create_table(
            "clinic_ai_observations",
            sa.Column("id", sa.String(), primary_key=True, nullable=False),
            sa.Column(
                "org_id",
                sa.String(),
                sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("host", sa.String(), nullable=False),
            sa.Column("tool_fingerprint", sa.String(), nullable=True),
            sa.Column("page_url_hash", sa.String(), nullable=True),
            sa.Column("severity", sa.String(), nullable=False, server_default="low"),
            sa.Column("observed_at", sa.DateTime(), nullable=False, index=True),
            sa.Column("user_agent", sa.String(), nullable=True),
            sa.Column("extension_version", sa.String(), nullable=True),
            sa.Column(
                "acknowledged",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),
            ),
        )
        op.create_index(
            "ix_clinic_obs_org_observed",
            "clinic_ai_observations",
            ["org_id", "observed_at"],
        )

    # ── 4. billing_events ───────────────────────────────────────────────
    if "billing_events" not in inspector.get_table_names():
        op.create_table(
            "billing_events",
            sa.Column("id", sa.String(), primary_key=True, nullable=False),
            sa.Column(
                "org_id",
                sa.String(),
                sa.ForeignKey("organizations.id", ondelete="SET NULL"),
                nullable=True,
                index=True,
            ),
            sa.Column(
                "stripe_event_id",
                sa.String(),
                unique=True,
                nullable=False,
                index=True,
            ),
            sa.Column("event_type", sa.String(), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("processed_at", sa.DateTime(), nullable=False),
            sa.Column(
                "status", sa.String(), nullable=False, server_default="processed"
            ),
            sa.Column("error_message", sa.String(), nullable=True),
        )

    # ── 5. clinic_report_artifacts ──────────────────────────────────────
    if "clinic_report_artifacts" not in inspector.get_table_names():
        op.create_table(
            "clinic_report_artifacts",
            sa.Column("id", sa.String(), primary_key=True, nullable=False),
            sa.Column(
                "org_id",
                sa.String(),
                sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("period_start", sa.DateTime(), nullable=False),
            sa.Column("period_end", sa.DateTime(), nullable=False),
            sa.Column("storage_uri", sa.String(), nullable=False),
            sa.Column("size_bytes", sa.Integer(), nullable=True),
            sa.Column("generated_at", sa.DateTime(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="ready"),
            sa.Column("error_message", sa.String(), nullable=True),
        )
        op.create_index(
            "ix_clinic_report_org_period",
            "clinic_report_artifacts",
            ["org_id", "period_end"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    tables = set(inspector.get_table_names())

    for table_name, indexes in (
        ("clinic_report_artifacts", ("ix_clinic_report_org_period",)),
        ("billing_events", ()),
        ("clinic_ai_observations", ("ix_clinic_obs_org_observed",)),
        ("clinic_ai_tools", ()),
    ):
        if table_name in tables:
            for idx in indexes:
                try:
                    op.drop_index(idx, table_name=table_name)
                except Exception:
                    pass
            op.drop_table(table_name)

    if "organizations" in tables:
        existing = {col["name"] for col in inspector.get_columns("organizations")}
        if "tier" in existing:
            try:
                op.drop_index("ix_organizations_tier", table_name="organizations")
            except Exception:
                pass
            with op.batch_alter_table("organizations") as batch_op:
                batch_op.drop_column("tier")
