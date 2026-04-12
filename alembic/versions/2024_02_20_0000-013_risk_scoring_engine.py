"""Risk Scoring Engine tables — Phase 7

Revision ID: 013
Revises: 012
Create Date: 2024-02-20

New tables:
  - risk_scores
  - risk_score_history
  - risk_configurations
  - risk_regulatory_mapping
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '013'
down_revision = '012'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = inspector.get_table_names()

    if 'risk_scores' not in existing:
        op.create_table(
            'risk_scores',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('organization_id', sa.String(), nullable=True),
            sa.Column('model_id', sa.String(), nullable=False),
            sa.Column('agent_id', sa.String(), nullable=True),
            sa.Column('severity_score', sa.Float(), nullable=False),
            sa.Column('exposure_score', sa.Float(), nullable=False),
            sa.Column('regulatory_penalty', sa.Float(), nullable=False),
            sa.Column('total_risk', sa.Float(), nullable=False),
            sa.Column('risk_level', sa.String(), nullable=False),
            sa.Column('severity_factors', sa.JSON(), nullable=False),
            sa.Column('exposure_factors', sa.JSON(), nullable=False),
            sa.Column('regulatory_flags', sa.JSON(), nullable=False),
            sa.Column('org_multiplier', sa.Float(), nullable=False, server_default='1.0'),
            sa.Column('computed_at', sa.DateTime(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ['organization_id'], ['organizations.id'], ondelete='SET NULL'
            ),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_risk_scores_id', 'risk_scores', ['id'], unique=False)
        op.create_index(
            'ix_risk_scores_organization_id', 'risk_scores', ['organization_id'], unique=False
        )
        op.create_index('ix_risk_scores_model_id', 'risk_scores', ['model_id'], unique=False)
        op.create_index('ix_risk_scores_agent_id', 'risk_scores', ['agent_id'], unique=False)
        op.create_index('ix_risk_scores_total_risk', 'risk_scores', ['total_risk'], unique=False)

    if 'risk_score_history' not in existing:
        op.create_table(
            'risk_score_history',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('organization_id', sa.String(), nullable=True),
            sa.Column('model_id', sa.String(), nullable=False),
            sa.Column('total_risk', sa.Float(), nullable=False),
            sa.Column('risk_level', sa.String(), nullable=False),
            sa.Column('delta', sa.Float(), nullable=True),
            sa.Column('trend', sa.String(), nullable=False, server_default='stable'),
            sa.Column('computed_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(
            'ix_risk_score_history_id', 'risk_score_history', ['id'], unique=False
        )
        op.create_index(
            'ix_risk_score_history_organization_id',
            'risk_score_history', ['organization_id'], unique=False,
        )
        op.create_index(
            'ix_risk_score_history_model_id',
            'risk_score_history', ['model_id'], unique=False,
        )

    if 'risk_configurations' not in existing:
        op.create_table(
            'risk_configurations',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('organization_id', sa.String(), nullable=False),
            sa.Column('regulatory_multiplier', sa.Float(), nullable=False, server_default='1.0'),
            sa.Column('critical_threshold', sa.Float(), nullable=False, server_default='75.0'),
            sa.Column('high_threshold', sa.Float(), nullable=False, server_default='50.0'),
            sa.Column('medium_threshold', sa.Float(), nullable=False, server_default='25.0'),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ['organization_id'], ['organizations.id'], ondelete='CASCADE'
            ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('organization_id', name='uq_risk_config_org'),
        )
        op.create_index(
            'ix_risk_configurations_id', 'risk_configurations', ['id'], unique=False
        )
        op.create_index(
            'ix_risk_configurations_organization_id',
            'risk_configurations', ['organization_id'], unique=False,
        )

    if 'risk_regulatory_mapping' not in existing:
        op.create_table(
            'risk_regulatory_mapping',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('organization_id', sa.String(), nullable=True),
            sa.Column('model_id', sa.String(), nullable=False),
            sa.Column('regulation', sa.String(), nullable=False),
            sa.Column('applicable', sa.Boolean(), nullable=False, server_default='1'),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(
            'ix_risk_regulatory_mapping_id',
            'risk_regulatory_mapping', ['id'], unique=False,
        )
        op.create_index(
            'ix_risk_regulatory_mapping_organization_id',
            'risk_regulatory_mapping', ['organization_id'], unique=False,
        )
        op.create_index(
            'ix_risk_regulatory_mapping_model_id',
            'risk_regulatory_mapping', ['model_id'], unique=False,
        )


def downgrade():
    op.drop_table('risk_regulatory_mapping')
    op.drop_table('risk_configurations')
    op.drop_table('risk_score_history')
    op.drop_table('risk_scores')
