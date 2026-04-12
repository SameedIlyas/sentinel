"""MedTech & Regulatory Automation tables — Phase 6

Revision ID: 012
Revises: 011
Create Date: 2024-02-19

New tables:
  - technical_files
  - technical_file_sections
  - technical_file_versions
  - adverse_events
  - pms_reports
  - pms_metrics
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '012'
down_revision = '011'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = inspector.get_table_names()

    if 'technical_files' not in existing:
        op.create_table(
            'technical_files',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('organization_id', sa.String(), nullable=True),
            sa.Column('title', sa.String(), nullable=False),
            sa.Column(
                'regulatory_type',
                sa.Enum('fda_510k', 'eu_mdr', 'both', name='regulatorytypedb'),
                nullable=False,
            ),
            sa.Column('product_name', sa.String(), nullable=False),
            sa.Column('device_version', sa.String(), nullable=False),
            sa.Column(
                'lifecycle_stage',
                sa.Enum(
                    'draft', 'submitted', 'under_review', 'approved', 'retired',
                    name='technicalfilelifecycledb',
                ),
                nullable=False,
                server_default='draft',
            ),
            sa.Column('created_by', sa.String(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ['organization_id'], ['organizations.id'], ondelete='SET NULL'
            ),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(
            'ix_technical_files_id', 'technical_files', ['id'], unique=False
        )
        op.create_index(
            'ix_technical_files_organization_id',
            'technical_files', ['organization_id'], unique=False,
        )

    if 'technical_file_sections' not in existing:
        op.create_table(
            'technical_file_sections',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('file_id', sa.String(), nullable=False),
            sa.Column('section_type', sa.String(), nullable=False),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('order_index', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('auto_generated', sa.Boolean(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ['file_id'], ['technical_files.id'], ondelete='CASCADE'
            ),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(
            'ix_technical_file_sections_id',
            'technical_file_sections', ['id'], unique=False,
        )
        op.create_index(
            'ix_technical_file_sections_file_id',
            'technical_file_sections', ['file_id'], unique=False,
        )

    if 'technical_file_versions' not in existing:
        op.create_table(
            'technical_file_versions',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('file_id', sa.String(), nullable=False),
            sa.Column('version_number', sa.Integer(), nullable=False),
            sa.Column('snapshot_json', sa.JSON(), nullable=False),
            sa.Column('created_by', sa.String(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ['file_id'], ['technical_files.id'], ondelete='CASCADE'
            ),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(
            'ix_technical_file_versions_id',
            'technical_file_versions', ['id'], unique=False,
        )
        op.create_index(
            'ix_technical_file_versions_file_id',
            'technical_file_versions', ['file_id'], unique=False,
        )

    if 'adverse_events' not in existing:
        op.create_table(
            'adverse_events',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('organization_id', sa.String(), nullable=True),
            sa.Column('model_id', sa.String(), nullable=False),
            sa.Column('agent_id', sa.String(), nullable=True),
            sa.Column('event_type', sa.String(), nullable=False),
            sa.Column(
                'severity',
                sa.Enum('low', 'medium', 'high', 'critical', name='adverseeventseveritydb'),
                nullable=False,
            ),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('patient_impact', sa.Text(), nullable=True),
            sa.Column('reported_by', sa.String(), nullable=True),
            sa.Column(
                'status',
                sa.Enum(
                    'open', 'investigating', 'resolved', 'reported_to_fda',
                    name='adverseeventstatusdb',
                ),
                nullable=False,
                server_default='open',
            ),
            sa.Column('resolved_at', sa.DateTime(), nullable=True),
            sa.Column('reported_at', sa.DateTime(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ['organization_id'], ['organizations.id'], ondelete='SET NULL'
            ),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_adverse_events_id', 'adverse_events', ['id'], unique=False)
        op.create_index(
            'ix_adverse_events_organization_id',
            'adverse_events', ['organization_id'], unique=False,
        )
        op.create_index(
            'ix_adverse_events_model_id', 'adverse_events', ['model_id'], unique=False
        )
        op.create_index(
            'ix_adverse_events_severity', 'adverse_events', ['severity'], unique=False
        )
        op.create_index(
            'ix_adverse_events_status', 'adverse_events', ['status'], unique=False
        )

    if 'pms_reports' not in existing:
        op.create_table(
            'pms_reports',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('organization_id', sa.String(), nullable=True),
            sa.Column(
                'report_type',
                sa.Enum('psur', 'mdr', 'incident', 'quarterly', name='pmsreporttypedb'),
                nullable=False,
            ),
            sa.Column(
                'status',
                sa.Enum('draft', 'published', 'submitted', name='pmsreportstatusdb'),
                nullable=False,
                server_default='draft',
            ),
            sa.Column('period_start', sa.DateTime(), nullable=False),
            sa.Column('period_end', sa.DateTime(), nullable=False),
            sa.Column('summary', sa.Text(), nullable=True),
            sa.Column('generated_at', sa.DateTime(), nullable=True),
            sa.Column('created_by', sa.String(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ['organization_id'], ['organizations.id'], ondelete='SET NULL'
            ),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_pms_reports_id', 'pms_reports', ['id'], unique=False)
        op.create_index(
            'ix_pms_reports_organization_id',
            'pms_reports', ['organization_id'], unique=False,
        )

    if 'pms_metrics' not in existing:
        op.create_table(
            'pms_metrics',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('report_id', sa.String(), nullable=False),
            sa.Column('metric_name', sa.String(), nullable=False),
            sa.Column('metric_value', sa.Float(), nullable=False),
            sa.Column('metric_unit', sa.String(), nullable=True),
            sa.Column('computed_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ['report_id'], ['pms_reports.id'], ondelete='CASCADE'
            ),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_pms_metrics_id', 'pms_metrics', ['id'], unique=False)
        op.create_index(
            'ix_pms_metrics_report_id', 'pms_metrics', ['report_id'], unique=False
        )


def downgrade():
    op.drop_table('pms_metrics')
    op.drop_table('pms_reports')
    op.drop_table('adverse_events')
    op.drop_table('technical_file_versions')
    op.drop_table('technical_file_sections')
    op.drop_table('technical_files')
