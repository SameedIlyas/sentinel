"""Add healthcare data layer tables

Revision ID: 008
Revises: 007
Create Date: 2024-02-15 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect as sa_inspect
    from alembic import op as _op

    bind = _op.get_bind()
    existing = sa_inspect(bind).get_table_names()

    if "fhir_resource_cache" not in existing:
        op.create_table(
            "fhir_resource_cache",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("resource_type", sa.String(), nullable=False),
            sa.Column("fhir_id", sa.String(), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("org_id", sa.String(), nullable=True),
            sa.Column("cached_at", sa.DateTime(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_fhir_resource_cache_resource_type",
            "fhir_resource_cache",
            ["resource_type"],
        )
        op.create_index(
            "ix_fhir_resource_cache_fhir_id", "fhir_resource_cache", ["fhir_id"]
        )

    if "dicom_metadata" not in existing:
        op.create_table(
            "dicom_metadata",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("study_uid", sa.String(), nullable=True),
            sa.Column("series_uid", sa.String(), nullable=True),
            sa.Column("modality", sa.String(), nullable=True),
            sa.Column("safe_metadata", sa.JSON(), nullable=False),
            sa.Column("org_id", sa.String(), nullable=True),
            sa.Column("extracted_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_dicom_metadata_study_uid", "dicom_metadata", ["study_uid"]
        )

    if "phi_redaction_log" not in existing:
        op.create_table(
            "phi_redaction_log",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("org_id", sa.String(), nullable=True),
            sa.Column("content_hash", sa.String(), nullable=False),
            sa.Column("phi_types_found", sa.JSON(), nullable=False),
            sa.Column("strategy_used", sa.String(), nullable=False),
            sa.Column("finding_count", sa.Integer(), nullable=False),
            sa.Column("processed_at", sa.DateTime(), nullable=False),
            sa.Column("user_id", sa.String(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_phi_redaction_log_content_hash",
            "phi_redaction_log",
            ["content_hash"],
        )

    if "data_classifications" not in existing:
        op.create_table(
            "data_classifications",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("content_hash", sa.String(), nullable=False),
            sa.Column("classification_level", sa.String(), nullable=False),
            sa.Column("confidence", sa.String(), nullable=True),
            sa.Column("org_id", sa.String(), nullable=True),
            sa.Column("classified_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_data_classifications_content_hash",
            "data_classifications",
            ["content_hash"],
        )


def downgrade() -> None:
    op.drop_index(
        "ix_data_classifications_content_hash", table_name="data_classifications"
    )
    op.drop_table("data_classifications")
    op.drop_index(
        "ix_phi_redaction_log_content_hash", table_name="phi_redaction_log"
    )
    op.drop_table("phi_redaction_log")
    op.drop_index("ix_dicom_metadata_study_uid", table_name="dicom_metadata")
    op.drop_table("dicom_metadata")
    op.drop_index(
        "ix_fhir_resource_cache_fhir_id", table_name="fhir_resource_cache"
    )
    op.drop_index(
        "ix_fhir_resource_cache_resource_type", table_name="fhir_resource_cache"
    )
    op.drop_table("fhir_resource_cache")
