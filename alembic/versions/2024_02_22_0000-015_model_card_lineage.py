"""Add artifact lineage + external validation + monitoring + PCCP columns to model_cards

Phase: Model Card best-in-class upgrade.

Adds:
    model_artifact_uri        — pinned model artifact URI (mlflow:// or s3://)
    training_dataset_sha256   — hash of training data manifest
    evaluation_dataset_sha256 — hash of eval data manifest
    git_commit_sha            — git SHA of training code
    framework_version         — runtime + framework version string
    external_validation       — JSON {sites,dates,n,auc} for CHAI section 5
    monitoring_plan           — JSON {drift_baseline_id,cadence,owner} for CHAI section 9
    pccp                      — JSON Predetermined Change Control Plan (FDA 2023 guidance)

Revision ID: 015
Revises: 014
Create Date: 2024-02-22 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


_NEW_STRING_COLS = (
    "model_artifact_uri",
    "training_dataset_sha256",
    "evaluation_dataset_sha256",
    "git_commit_sha",
    "framework_version",
)
_NEW_JSON_COLS = (
    "external_validation",
    "monitoring_plan",
    "pccp",
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    if "model_cards" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("model_cards")}

    with op.batch_alter_table("model_cards") as batch_op:
        for col_name in _NEW_STRING_COLS:
            if col_name not in existing:
                batch_op.add_column(sa.Column(col_name, sa.String(), nullable=True))
        for col_name in _NEW_JSON_COLS:
            if col_name not in existing:
                # JSON columns must have a default; existing rows will get '{}'
                batch_op.add_column(
                    sa.Column(
                        col_name,
                        sa.JSON(),
                        nullable=False,
                        server_default=sa.text("'{}'"),
                    )
                )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    if "model_cards" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("model_cards")}

    with op.batch_alter_table("model_cards") as batch_op:
        for col_name in (*_NEW_JSON_COLS, *_NEW_STRING_COLS):
            if col_name in existing:
                batch_op.drop_column(col_name)
