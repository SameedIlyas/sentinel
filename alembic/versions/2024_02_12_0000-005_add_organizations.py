"""Add organizations and organization_members tables

Revision ID: 005
Revises: 004
Create Date: 2024-02-12 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect as sa_inspect
    from alembic import op as _op
    bind = _op.get_bind()
    existing = sa_inspect(bind).get_table_names()

    if 'organizations' not in existing:
        op.create_table(
            'organizations',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('slug', sa.String(), nullable=False),
            sa.Column('org_type', sa.String(), nullable=False),
            sa.Column('settings', sa.JSON(), nullable=True),
            sa.Column('hipaa_baa_signed', sa.Boolean(), nullable=False, server_default='0'),
            sa.Column('hipaa_baa_date', sa.DateTime(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_organizations_id', 'organizations', ['id'])
        op.create_index('ix_organizations_slug', 'organizations', ['slug'], unique=True)

    if 'organization_members' not in existing:
        op.create_table(
            'organization_members',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('org_id', sa.String(), nullable=False),
            sa.Column('user_id', sa.String(), nullable=False),
            sa.Column('role', sa.String(), nullable=False),
            sa.Column('invited_at', sa.DateTime(), nullable=False),
            sa.Column('joined_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('org_id', 'user_id', name='uq_org_member'),
        )
        op.create_index('ix_organization_members_id', 'organization_members', ['id'])
        op.create_index('ix_organization_members_org_id', 'organization_members', ['org_id'])
        op.create_index('ix_organization_members_user_id', 'organization_members', ['user_id'])


def downgrade() -> None:
    # Drop indexes explicitly so a re-run after a partial rollback (e.g. an
    # earlier drop_table held by an FK from another table) does not leave
    # orphaned indexes that block a subsequent upgrade. if_exists=True keeps
    # this idempotent on SQLite as well as PostgreSQL.
    op.drop_index('ix_organization_members_user_id', table_name='organization_members', if_exists=True)
    op.drop_index('ix_organization_members_org_id', table_name='organization_members', if_exists=True)
    op.drop_index('ix_organization_members_id', table_name='organization_members', if_exists=True)
    op.drop_index('ix_organizations_slug', table_name='organizations', if_exists=True)
    op.drop_index('ix_organizations_id', table_name='organizations', if_exists=True)
    op.drop_table('organization_members')
    op.drop_table('organizations')
