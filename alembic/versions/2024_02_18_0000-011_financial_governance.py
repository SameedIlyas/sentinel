"""Financial Governance tables — Phase 5

Revision ID: 011
Revises: 010
Create Date: 2024-02-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '011'
down_revision = '010'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = inspector.get_table_names()

    if 'prior_auth_records' not in existing:
        op.create_table('prior_auth_records',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('patient_id_hash', sa.String(), nullable=False),
            sa.Column('claim_id', sa.String(), nullable=False),
            sa.Column('service_type', sa.String(), nullable=True),
            sa.Column('request_date', sa.String(), nullable=True),
            sa.Column('decision_date', sa.String(), nullable=True),
            sa.Column('ai_recommendation', sa.String(), nullable=False),
            sa.Column('ai_confidence', sa.Float(), nullable=False, server_default='0.0'),
            sa.Column('human_reviewer_id', sa.String(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('human_review_timestamp', sa.DateTime(), nullable=True),
            sa.Column('final_decision', sa.String(), nullable=False),
            sa.Column('denial_reason_code', sa.String(), nullable=True),
            sa.Column('ai_rationale', sa.String(), nullable=True),
            sa.Column('override_reason', sa.String(), nullable=True),
            sa.Column('prev_record_hash', sa.String(), nullable=False, server_default=''),
            sa.Column('record_hash', sa.String(), nullable=False),
            sa.Column('organization_id', sa.String(), sa.ForeignKey('organizations.id', ondelete='SET NULL'), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )

    if 'prior_auth_chain_status' not in existing:
        op.create_table('prior_auth_chain_status',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('organization_id', sa.String(), sa.ForeignKey('organizations.id', ondelete='SET NULL'), nullable=True),
            sa.Column('last_verified_at', sa.DateTime(), nullable=False),
            sa.Column('total_records', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('chain_valid', sa.Boolean(), nullable=False, server_default='1'),
            sa.Column('broken_at_record_id', sa.String(), nullable=True),
            sa.Column('verification_duration_ms', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )

    if 'revenue_cycle_audits' not in existing:
        op.create_table('revenue_cycle_audits',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('claim_id', sa.String(), nullable=False, unique=True),
            sa.Column('claim_date', sa.String(), nullable=True),
            sa.Column('provider_id', sa.String(), nullable=True),
            sa.Column('payer_id', sa.String(), nullable=True),
            sa.Column('primary_diagnosis_code', sa.String(), nullable=True),
            sa.Column('procedure_codes', sa.JSON(), nullable=False),
            sa.Column('modifiers', sa.JSON(), nullable=False),
            sa.Column('billed_amount', sa.Float(), nullable=False, server_default='0.0'),
            sa.Column('expected_amount_range', sa.JSON(), nullable=False),
            sa.Column('risk_score', sa.Float(), nullable=False, server_default='0.0'),
            sa.Column('findings', sa.JSON(), nullable=False),
            sa.Column('status', sa.String(), nullable=False, server_default='clean'),
            sa.Column('reviewed_by', sa.String(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('reviewed_at', sa.DateTime(), nullable=True),
            sa.Column('organization_id', sa.String(), sa.ForeignKey('organizations.id', ondelete='SET NULL'), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )

    if 'revenue_cycle_findings' not in existing:
        op.create_table('revenue_cycle_findings',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('audit_id', sa.String(), sa.ForeignKey('revenue_cycle_audits.id', ondelete='CASCADE'), nullable=False),
            sa.Column('finding_type', sa.String(), nullable=False),
            sa.Column('severity', sa.String(), nullable=False),
            sa.Column('description', sa.String(), nullable=False),
            sa.Column('affected_codes', sa.JSON(), nullable=False),
            sa.Column('estimated_overbilling', sa.Float(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )

    if 'coding_benchmarks' not in existing:
        op.create_table('coding_benchmarks',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('procedure_code', sa.String(), nullable=False),
            sa.Column('specialty', sa.String(), nullable=True),
            sa.Column('p25_amount', sa.Float(), nullable=False),
            sa.Column('p50_amount', sa.Float(), nullable=False),
            sa.Column('p75_amount', sa.Float(), nullable=False),
            sa.Column('p90_amount', sa.Float(), nullable=False),
            sa.Column('national_frequency_per_1000', sa.Float(), nullable=True),
            sa.Column('last_updated', sa.DateTime(), nullable=False),
            sa.Column('source', sa.String(), nullable=False),
            sa.Column('organization_id', sa.String(), sa.ForeignKey('organizations.id', ondelete='SET NULL'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )


def downgrade():
    for t in ['coding_benchmarks', 'revenue_cycle_findings', 'revenue_cycle_audits',
              'prior_auth_chain_status', 'prior_auth_records']:
        op.drop_table(t)
