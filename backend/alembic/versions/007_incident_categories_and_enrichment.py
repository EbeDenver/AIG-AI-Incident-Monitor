"""incident_categories_and_enrichment

Revision ID: 007
Revises: 006
Create Date: 2026-11-02 20:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '007'
down_revision: Union[str, None] = '006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add primary_category and category_tags to incidents table
    with op.batch_alter_table('incidents', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'primary_category',
                sa.String(length=50),
                server_default='UNCATEGORIZED',
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                'category_tags',
                sa.Text(),
                nullable=True,
            )
        )
        batch_op.create_index('ix_incidents_primary_category', ['primary_category'], unique=False)

    # 2. Create incident_enrichments table
    op.create_table(
        'incident_enrichments',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('incident_id', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=30), server_default='PENDING', nullable=False),
        sa.Column('prompt_version', sa.String(length=30), server_default='1.0.0', nullable=False),
        sa.Column('model_provider', sa.String(length=50), server_default='mock', nullable=False),
        sa.Column('model_name', sa.String(length=100), server_default='mock-intelligence-v1', nullable=False),
        sa.Column('prompt_digest', sa.String(length=64), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('cache_key', sa.String(length=64), nullable=False),
        sa.Column('evidence_sufficiency', sa.String(length=30), server_default='LIMITED_EVIDENCE', nullable=False),
        sa.Column('executive_summary', sa.Text(), nullable=False),
        sa.Column('event_chronology', sa.Text(), server_default='[]', nullable=False),
        sa.Column('ai_system_role', sa.Text(), nullable=False),
        sa.Column('affected_stakeholders', sa.Text(), server_default='[]', nullable=False),
        sa.Column('documented_consequences', sa.Text(), server_default='[]', nullable=False),
        sa.Column('unknowns_and_disputes', sa.Text(), server_default='[]', nullable=False),
        sa.Column('evidence_limitations', sa.Text(), server_default='', nullable=False),
        sa.Column('applicable_profiles', sa.Text(), server_default='[]', nullable=False),
        sa.Column('early_warning_indicators', sa.Text(), server_default='[]', nullable=False),
        sa.Column('preventive_controls', sa.Text(), server_default='[]', nullable=False),
        sa.Column('detection_mechanisms', sa.Text(), server_default='[]', nullable=False),
        sa.Column('incident_response_actions', sa.Text(), server_default='[]', nullable=False),
        sa.Column('responsible_functions', sa.Text(), server_default='[]', nullable=False),
        sa.Column('validation_methods', sa.Text(), server_default='[]', nullable=False),
        sa.Column('token_count_input', sa.Integer(), server_default='0', nullable=False),
        sa.Column('token_count_output', sa.Integer(), server_default='0', nullable=False),
        sa.Column('estimated_cost_usd', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('latency_seconds', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('schema_version', sa.String(length=20), server_default='1.0.0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('incident_id'),
    )
    op.create_index('ix_incident_enrichments_status', 'incident_enrichments', ['status'], unique=False)
    op.create_index('ix_incident_enrichments_cache_key', 'incident_enrichments', ['cache_key'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_incident_enrichments_cache_key', table_name='incident_enrichments')
    op.drop_index('ix_incident_enrichments_status', table_name='incident_enrichments')
    op.drop_table('incident_enrichments')

    with op.batch_alter_table('incidents', schema=None) as batch_op:
        batch_op.drop_index('ix_incidents_primary_category')
        batch_op.drop_column('category_tags')
        batch_op.drop_column('primary_category')
