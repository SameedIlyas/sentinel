"""Add alert_configs table

Revision ID: 004
Revises: 003
Create Date: 2024-02-11 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect as sa_inspect
    from alembic import op as _op
    bind = _op.get_bind()
    if 'alert_configs' in sa_inspect(bind).get_table_names():
        return  # Table already exists (created via create_all before migrations)
    op.create_table(
        'alert_configs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('policy_type', sa.String(), nullable=True),
        sa.Column('alert_type', sa.String(), nullable=False),
        sa.Column('severity', sa.String(), nullable=False),
        sa.Column('conditions', sa.JSON(), nullable=True),
        sa.Column('slack_webhook_url', sa.String(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_alert_configs_id', 'alert_configs', ['id'])
    op.create_index('ix_alert_configs_policy_type', 'alert_configs', ['policy_type'])
    op.create_index('ix_alert_configs_alert_type', 'alert_configs', ['alert_type'])


def downgrade() -> None:
    op.drop_index('ix_alert_configs_alert_type', table_name='alert_configs')
    op.drop_index('ix_alert_configs_policy_type', table_name='alert_configs')
    op.drop_index('ix_alert_configs_id', table_name='alert_configs')
    op.drop_table('alert_configs')
