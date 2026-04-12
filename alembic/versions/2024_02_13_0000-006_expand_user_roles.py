"""Expand UserRole enum to 8 healthcare roles

Revision ID: 006
Revises: 005
Create Date: 2024-02-13 00:00:00.000000

Note: SQLite does not support ALTER COLUMN for enum types.
The new roles are enforced at the application layer.
This migration is a no-op but tracked by Alembic.
"""
from alembic import op
import sqlalchemy as sa

revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite does not support altering enum columns.
    # Role expansion is handled at the application layer (UserRole enum in user.py).
    # This migration acts as a tracked no-op for version history.
    pass


def downgrade() -> None:
    pass
