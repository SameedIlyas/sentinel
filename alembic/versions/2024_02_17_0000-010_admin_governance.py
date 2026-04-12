"""Admin Governance tables — Phase 4

Revision ID: 010
Revises: 009
Create Date: 2024-02-17 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '010'
down_revision = '009'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = inspector.get_table_names()

    if 'shadow_ai_detections' not in existing:
        op.create_table('shadow_ai_detections',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('detected_at', sa.DateTime(), nullable=False),
            sa.Column('source_ip', sa.String(), nullable=True),
            sa.Column('destination_host', sa.String(), nullable=False),
            sa.Column('destination_port', sa.Integer(), nullable=False, server_default='443'),
            sa.Column('ai_provider', sa.String(), nullable=True),
            sa.Column('confidence_score', sa.Float(), nullable=False, server_default='1.0'),
            sa.Column('staff_id', sa.String(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('department', sa.String(), nullable=True),
            sa.Column('phi_risk_level', sa.String(), nullable=False, server_default='none'),
            sa.Column('status', sa.String(), nullable=False, server_default='detected'),
            sa.Column('notes', sa.String(), nullable=True),
            sa.Column('organization_id', sa.String(), sa.ForeignKey('organizations.id', ondelete='SET NULL'), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )

    if 'shadow_ai_allowlist' not in existing:
        op.create_table('shadow_ai_allowlist',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('host_pattern', sa.String(), nullable=False),
            sa.Column('reason', sa.String(), nullable=True),
            sa.Column('approved_by', sa.String(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('approved_at', sa.DateTime(), nullable=False),
            sa.Column('expires_at', sa.DateTime(), nullable=True),
            sa.Column('organization_id', sa.String(), sa.ForeignKey('organizations.id', ondelete='SET NULL'), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )

    if 'scribe_audits' not in existing:
        op.create_table('scribe_audits',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('session_id', sa.String(), nullable=False, unique=True),
            sa.Column('patient_context_hash', sa.String(), nullable=True),
            sa.Column('ai_model_used', sa.String(), nullable=True),
            sa.Column('generated_note_hash', sa.String(), nullable=True),
            sa.Column('audit_score', sa.Float(), nullable=False, server_default='0.0'),
            sa.Column('hallucination_detected', sa.Boolean(), nullable=False, server_default='0'),
            sa.Column('completeness_score', sa.Float(), nullable=False, server_default='0.0'),
            sa.Column('attribution_score', sa.Float(), nullable=False, server_default='100.0'),
            sa.Column('status', sa.String(), nullable=False, server_default='pending'),
            sa.Column('organization_id', sa.String(), sa.ForeignKey('organizations.id', ondelete='SET NULL'), nullable=True),
            sa.Column('audited_by', sa.String(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if 'scribe_audit_findings' not in existing:
        op.create_table('scribe_audit_findings',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('audit_id', sa.String(), sa.ForeignKey('scribe_audits.id', ondelete='CASCADE'), nullable=False),
            sa.Column('finding_type', sa.String(), nullable=False),
            sa.Column('severity', sa.String(), nullable=False),
            sa.Column('description', sa.String(), nullable=False),
            sa.Column('suggested_correction', sa.String(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )

    if 'transparency_records' not in existing:
        op.create_table('transparency_records',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('model_name', sa.String(), nullable=False),
            sa.Column('model_version', sa.String(), nullable=False),
            sa.Column('algorithm_description', sa.String(), nullable=True),
            sa.Column('plain_language_summary', sa.String(), nullable=False),
            sa.Column('evidence_base', sa.String(), nullable=True),
            sa.Column('intended_population', sa.String(), nullable=False),
            sa.Column('known_limitations', sa.String(), nullable=False),
            sa.Column('performance_summary', sa.JSON(), nullable=False),
            sa.Column('bias_considerations', sa.String(), nullable=True),
            sa.Column('regulatory_status', sa.String(), nullable=True),
            sa.Column('published_at', sa.DateTime(), nullable=True),
            sa.Column('version_number', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('organization_id', sa.String(), sa.ForeignKey('organizations.id', ondelete='SET NULL'), nullable=True),
            sa.Column('created_by', sa.String(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )

    if 'transparency_versions' not in existing:
        op.create_table('transparency_versions',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('record_id', sa.String(), sa.ForeignKey('transparency_records.id', ondelete='CASCADE'), nullable=False),
            sa.Column('version_number', sa.Integer(), nullable=False),
            sa.Column('content_snapshot', sa.JSON(), nullable=False),
            sa.Column('change_summary', sa.String(), nullable=True),
            sa.Column('published_by', sa.String(), nullable=True),
            sa.Column('published_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )

    if 'transparency_acknowledgments' not in existing:
        op.create_table('transparency_acknowledgments',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('record_id', sa.String(), sa.ForeignKey('transparency_records.id', ondelete='CASCADE'), nullable=False),
            sa.Column('acknowledged_by', sa.String(), nullable=True),
            sa.Column('acknowledged_at', sa.DateTime(), nullable=False),
            sa.Column('role_at_time', sa.String(), nullable=True),
            sa.Column('ip_address_hash', sa.String(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )


def downgrade():
    for t in ['transparency_acknowledgments', 'transparency_versions', 'transparency_records',
              'scribe_audit_findings', 'scribe_audits',
              'shadow_ai_allowlist', 'shadow_ai_detections']:
        op.drop_table(t)
