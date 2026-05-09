"""Add organization_id columns to multi-tenant tables

The User, Agent, Policy, and AuditLog SQLAlchemy models declare
`organization_id` columns referencing organizations.id, but no prior
migration created those columns. This migration adds the missing
nullable, indexed columns to all four tables.

Revision ID: 014
Revises: 013
Create Date: 2024-02-21 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect


revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


# Tables that need a nullable organization_id FK to organizations.id,
# with a matching index. The model declares the FK; migration only adds
# the physical column + index (SQLite cannot add a real FK to an existing
# table; the FK constraint is enforced at the model layer).
TABLES_NEEDING_ORG_ID = ("users", "agents", "policies", "audit_logs")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)

    for table in TABLES_NEEDING_ORG_ID:
        if table not in inspector.get_table_names():
            continue
        columns = {col["name"] for col in inspector.get_columns(table)}
        if "organization_id" in columns:
            continue

        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(
                sa.Column("organization_id", sa.String(), nullable=True)
            )

        index_name = f"ix_{table}_organization_id"
        existing_indexes = {idx["name"] for idx in inspector.get_indexes(table)}
        if index_name not in existing_indexes:
            op.create_index(
                index_name, table, ["organization_id"], unique=False
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)

    for table in reversed(TABLES_NEEDING_ORG_ID):
        if table not in inspector.get_table_names():
            continue
        index_name = f"ix_{table}_organization_id"
        existing_indexes = {idx["name"] for idx in inspector.get_indexes(table)}
        if index_name in existing_indexes:
            op.drop_index(index_name, table_name=table)

        columns = {col["name"] for col in inspector.get_columns(table)}
        if "organization_id" in columns:
            with op.batch_alter_table(table) as batch_op:
                batch_op.drop_column("organization_id")
