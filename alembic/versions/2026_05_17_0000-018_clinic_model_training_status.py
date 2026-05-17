"""Clinic AI Tools — Model Training Status + Practice Opt-Out State.

PRD.v2.md §6.8.2.a. HEALTH-5 split: vendor capability (model_training_status)
distinguished from practice configuration (practice_opt_out_state) with
provenance fields for the verified state.

Revision ID: 018
Revises: 017
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    if "clinic_ai_tools" not in set(inspector.get_table_names()):
        return
    existing = {c["name"] for c in inspector.get_columns("clinic_ai_tools")}

    with op.batch_alter_table("clinic_ai_tools") as batch_op:
        if "model_training_status" not in existing:
            batch_op.add_column(sa.Column(
                "model_training_status", sa.String(),
                nullable=False, server_default="unknown"))
        if "practice_opt_out_state" not in existing:
            batch_op.add_column(sa.Column(
                "practice_opt_out_state", sa.String(),
                nullable=False, server_default="not_applicable"))
        if "opt_out_verified_at" not in existing:
            batch_op.add_column(sa.Column(
                "opt_out_verified_at", sa.DateTime(), nullable=True))
        if "opt_out_verified_by_user_id" not in existing:
            batch_op.add_column(sa.Column(
                "opt_out_verified_by_user_id", sa.String(),
                sa.ForeignKey("users.id", ondelete="SET NULL",
                              name="fk_clinic_ai_tools_opt_out_verified_by"),
                nullable=True))
        if "model_training_status_evidence" not in existing:
            batch_op.add_column(sa.Column(
                "model_training_status_evidence", sa.String(length=2000),
                nullable=True))

    op.execute(
        "UPDATE clinic_ai_tools SET model_training_status='unknown' "
        "WHERE model_training_status IS NULL"
    )
    op.execute(
        "UPDATE clinic_ai_tools SET practice_opt_out_state='not_applicable' "
        "WHERE practice_opt_out_state IS NULL"
    )

    # Drop server_default so application code owns the value going forward
    # (matches migration 016 idiom — see alembic/versions/2024_02_23_0000-016_clinic_tier.py:51).
    with op.batch_alter_table("clinic_ai_tools") as batch_op:
        batch_op.alter_column("model_training_status", server_default=None)
        batch_op.alter_column("practice_opt_out_state", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    if "clinic_ai_tools" not in set(inspector.get_table_names()):
        return
    existing = {c["name"] for c in inspector.get_columns("clinic_ai_tools")}
    with op.batch_alter_table("clinic_ai_tools") as batch_op:
        for col in (
            "model_training_status_evidence",
            "opt_out_verified_by_user_id",
            "opt_out_verified_at",
            "practice_opt_out_state",
            "model_training_status",
        ):
            if col in existing:
                batch_op.drop_column(col)
