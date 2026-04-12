"""Clinical Governance tables — Phase 3

Revision ID: 009
Revises: 008
Create Date: 2024-02-16 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = inspector.get_table_names()

    if 'model_cards' not in existing:
        op.create_table('model_cards',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('version', sa.String(), nullable=False, server_default='1.0'),
            sa.Column('lifecycle_stage', sa.String(), nullable=False, server_default='draft'),
            sa.Column('intended_use', sa.String(), nullable=True),
            sa.Column('clinical_indications', sa.String(), nullable=True),
            sa.Column('contraindications', sa.String(), nullable=True),
            sa.Column('training_data_source', sa.String(), nullable=True),
            sa.Column('performance_metrics', sa.JSON(), nullable=False),
            sa.Column('bias_summary', sa.JSON(), nullable=False),
            sa.Column('fda_status', sa.String(), nullable=True),
            sa.Column('chai_version', sa.String(), nullable=False, server_default='1.0'),
            sa.Column('organization_id', sa.String(), sa.ForeignKey('organizations.id', ondelete='SET NULL'), nullable=True),
            sa.Column('created_by', sa.String(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )

    if 'model_card_versions' not in existing:
        op.create_table('model_card_versions',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('model_card_id', sa.String(), sa.ForeignKey('model_cards.id', ondelete='CASCADE'), nullable=False),
            sa.Column('version_number', sa.String(), nullable=False),
            sa.Column('content', sa.JSON(), nullable=False),
            sa.Column('published_by', sa.String(), nullable=True),
            sa.Column('published_at', sa.DateTime(), nullable=True),
            sa.Column('changelog', sa.String(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if 'model_card_metrics' not in existing:
        op.create_table('model_card_metrics',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('model_card_id', sa.String(), sa.ForeignKey('model_cards.id', ondelete='CASCADE'), nullable=False),
            sa.Column('metric_name', sa.String(), nullable=False),
            sa.Column('metric_value', sa.Float(), nullable=False),
            sa.Column('metric_type', sa.String(), nullable=True),
            sa.Column('subgroup', sa.String(), nullable=True),
            sa.Column('evaluation_date', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if 'model_card_reviews' not in existing:
        op.create_table('model_card_reviews',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('model_card_id', sa.String(), sa.ForeignKey('model_cards.id', ondelete='CASCADE'), nullable=False),
            sa.Column('reviewer_id', sa.String(), nullable=False),
            sa.Column('reviewer_role', sa.String(), nullable=False),
            sa.Column('decision', sa.String(), nullable=False),
            sa.Column('comments', sa.String(), nullable=True),
            sa.Column('reviewed_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )

    if 'bias_audits' not in existing:
        op.create_table('bias_audits',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('model_card_id', sa.String(), sa.ForeignKey('model_cards.id', ondelete='SET NULL'), nullable=True),
            sa.Column('audit_name', sa.String(), nullable=False),
            sa.Column('status', sa.String(), nullable=False, server_default='pending'),
            sa.Column('dataset_description', sa.String(), nullable=True),
            sa.Column('organization_id', sa.String(), sa.ForeignKey('organizations.id', ondelete='SET NULL'), nullable=True),
            sa.Column('created_by', sa.String(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if 'bias_audit_subgroups' not in existing:
        op.create_table('bias_audit_subgroups',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('audit_id', sa.String(), sa.ForeignKey('bias_audits.id', ondelete='CASCADE'), nullable=False),
            sa.Column('subgroup_name', sa.String(), nullable=False),
            sa.Column('subgroup_type', sa.String(), nullable=False),
            sa.Column('sample_size', sa.Integer(), nullable=False, server_default='0'),
            sa.PrimaryKeyConstraint('id'),
        )

    if 'bias_audit_results' not in existing:
        op.create_table('bias_audit_results',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('audit_id', sa.String(), sa.ForeignKey('bias_audits.id', ondelete='CASCADE'), nullable=False),
            sa.Column('subgroup_id', sa.String(), sa.ForeignKey('bias_audit_subgroups.id', ondelete='CASCADE'), nullable=True),
            sa.Column('metric_name', sa.String(), nullable=False),
            sa.Column('metric_value', sa.Float(), nullable=False),
            sa.Column('reference_value', sa.Float(), nullable=False),
            sa.Column('disparity_ratio', sa.Float(), nullable=False),
            sa.Column('passes_threshold', sa.Boolean(), nullable=False, server_default='1'),
            sa.Column('threshold_used', sa.Float(), nullable=False, server_default='0.8'),
            sa.PrimaryKeyConstraint('id'),
        )

    if 'drift_baselines' not in existing:
        op.create_table('drift_baselines',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('model_id', sa.String(), nullable=False),
            sa.Column('baseline_name', sa.String(), nullable=False),
            sa.Column('feature_distributions', sa.JSON(), nullable=False),
            sa.Column('performance_baseline', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('organization_id', sa.String(), sa.ForeignKey('organizations.id', ondelete='SET NULL'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if 'drift_measurements' not in existing:
        op.create_table('drift_measurements',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('baseline_id', sa.String(), sa.ForeignKey('drift_baselines.id', ondelete='CASCADE'), nullable=False),
            sa.Column('measurement_time', sa.DateTime(), nullable=False),
            sa.Column('feature_distributions', sa.JSON(), nullable=False),
            sa.Column('psi_scores', sa.JSON(), nullable=False),
            sa.Column('ks_scores', sa.JSON(), nullable=False),
            sa.Column('performance_current', sa.JSON(), nullable=False),
            sa.Column('drift_detected', sa.Boolean(), nullable=False, server_default='0'),
            sa.Column('drift_magnitude', sa.Float(), nullable=False, server_default='0.0'),
            sa.PrimaryKeyConstraint('id'),
        )

    if 'drift_alerts' not in existing:
        op.create_table('drift_alerts',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('measurement_id', sa.String(), sa.ForeignKey('drift_measurements.id', ondelete='CASCADE'), nullable=False),
            sa.Column('alert_type', sa.String(), nullable=False),
            sa.Column('severity', sa.String(), nullable=False, server_default='low'),
            sa.Column('message', sa.String(), nullable=False),
            sa.Column('acknowledged', sa.Boolean(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )

    if 'hitl_reviews' not in existing:
        op.create_table('hitl_reviews',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('title', sa.String(), nullable=False),
            sa.Column('description', sa.String(), nullable=True),
            sa.Column('ai_decision', sa.JSON(), nullable=False),
            sa.Column('risk_score', sa.Float(), nullable=False, server_default='0.0'),
            sa.Column('status', sa.String(), nullable=False, server_default='pending'),
            sa.Column('priority', sa.String(), nullable=False, server_default='medium'),
            sa.Column('assigned_to', sa.String(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('sla_deadline', sa.DateTime(), nullable=True),
            sa.Column('organization_id', sa.String(), sa.ForeignKey('organizations.id', ondelete='SET NULL'), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )

    if 'hitl_assignments' not in existing:
        op.create_table('hitl_assignments',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('review_id', sa.String(), sa.ForeignKey('hitl_reviews.id', ondelete='CASCADE'), nullable=False),
            sa.Column('assigned_to', sa.String(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('assigned_by', sa.String(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('assigned_at', sa.DateTime(), nullable=False),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if 'hitl_audit_trail' not in existing:
        op.create_table('hitl_audit_trail',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('review_id', sa.String(), sa.ForeignKey('hitl_reviews.id', ondelete='CASCADE'), nullable=False),
            sa.Column('actor_id', sa.String(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('action', sa.String(), nullable=False),
            sa.Column('old_status', sa.String(), nullable=True),
            sa.Column('new_status', sa.String(), nullable=True),
            sa.Column('comments', sa.String(), nullable=True),
            sa.Column('timestamp', sa.DateTime(), nullable=False),
            sa.Column('entry_hash', sa.String(), nullable=False, server_default=''),
            sa.PrimaryKeyConstraint('id'),
        )


def downgrade():
    for t in [
        'hitl_audit_trail', 'hitl_assignments', 'hitl_reviews',
        'drift_alerts', 'drift_measurements', 'drift_baselines',
        'bias_audit_results', 'bias_audit_subgroups', 'bias_audits',
        'model_card_reviews', 'model_card_metrics', 'model_card_versions', 'model_cards',
    ]:
        op.drop_table(t)
