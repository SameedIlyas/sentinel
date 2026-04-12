"""Add domain_events table

Revision ID: 007
Revises: 006
Create Date: 2024-02-14 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect as sa_inspect
    from alembic import op as _op
    bind = _op.get_bind()
    if 'domain_events' in sa_inspect(bind).get_table_names():
        return  # Already exists

    op.create_table(
        'domain_events',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('org_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_domain_events_id', 'domain_events', ['id'])
    op.create_index('ix_domain_events_event_type', 'domain_events', ['event_type'])
    op.create_index('ix_domain_events_org_id', 'domain_events', ['org_id'])


def downgrade() -> None:
    op.drop_index('ix_domain_events_org_id', table_name='domain_events')
    op.drop_index('ix_domain_events_event_type', table_name='domain_events')
    op.drop_index('ix_domain_events_id', table_name='domain_events')
    op.drop_table('domain_events')
