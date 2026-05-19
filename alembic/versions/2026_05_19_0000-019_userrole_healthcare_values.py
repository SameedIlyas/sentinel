"""Add healthcare values to userrole Postgres enum.

CRIT-009: When the application code expanded UserRole to 8 healthcare
values (migration 006 was a no-op), the Postgres ``userrole`` enum was
never updated. Any INSERT/UPDATE that writes one of the new values
(``cmio``, ``data_scientist``, ``compliance_officer``, ``clinical_user``,
``system_admin``) fails with ``invalid input value for enum`` on Postgres.

SQLite stores enums as text and accepts any value, so the existing test
suite never caught the gap.

This migration is **Postgres-only**. SQLite is skipped because there is
no enum type to alter.

Note: ``ALTER TYPE ... ADD VALUE`` is non-transactional in Postgres and
must run outside the alembic transaction. We use
``op.get_context().autocommit_block()`` to escape the implicit
transaction.

Revision ID: 019
Revises: 018
"""
from alembic import op


revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


# Values that must exist in the userrole enum after this migration.
_HEALTHCARE_ROLES = (
    "system_admin",
    "cmio",
    "data_scientist",
    "compliance_officer",
    "clinical_user",
)


def upgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    if dialect_name != "postgresql":
        # SQLite stores enums as plain text — nothing to alter.
        return

    # ALTER TYPE ... ADD VALUE cannot run inside a transaction.
    with op.get_context().autocommit_block():
        for value in _HEALTHCARE_ROLES:
            op.execute(
                f"ALTER TYPE userrole ADD VALUE IF NOT EXISTS '{value}'"
            )


def downgrade() -> None:
    # Postgres does not support removing enum values without recreating
    # the type and rewriting every column that references it. Leave the
    # added values in place on downgrade — they are harmless if unused.
    pass
