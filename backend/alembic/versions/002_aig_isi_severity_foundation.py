"""aig_isi_severity_foundation

Revision ID: 002
Revises: 001
Create Date: 2026-10-20 20:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'severity_assessments',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('incident_id', sa.String(length=64), nullable=False),
        sa.Column('methodology_version', sa.String(length=20), server_default='AIG-ISI-1.0.0', nullable=False),
        sa.Column('actual_raw_score', sa.Float(), nullable=True),
        sa.Column('actual_normalized_score', sa.Float(), nullable=True),
        sa.Column('actual_lower_bound', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('actual_upper_bound', sa.Float(), server_default='100.0', nullable=False),
        sa.Column('actual_completeness_pct', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('actual_tier', sa.String(length=30), server_default='UNSCORED', nullable=False),
        sa.Column('actual_confidence', sa.String(length=20), server_default='INSUFFICIENT', nullable=False),
        sa.Column('potential_raw_score', sa.Float(), nullable=True),
        sa.Column('potential_normalized_score', sa.Float(), nullable=True),
        sa.Column('potential_lower_bound', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('potential_upper_bound', sa.Float(), server_default='100.0', nullable=False),
        sa.Column('potential_completeness_pct', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('potential_tier', sa.String(length=30), server_default='UNSCORED', nullable=False),
        sa.Column('potential_confidence', sa.String(length=20), server_default='INSUFFICIENT', nullable=False),
        sa.Column('dimension_scores', sa.JSON(), nullable=False),
        sa.Column('review_state', sa.String(length=30), server_default='DRAFT', nullable=False),
        sa.Column('review_gates_triggered', sa.JSON(), nullable=False),
        sa.Column('is_pending_review', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('has_disputed_facts', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('overrides', sa.JSON(), nullable=False),
        sa.Column('supersedes_assessment_id', sa.String(length=64), nullable=True),
        sa.Column('superseded_by_id', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], name=op.f('fk_severity_assessments_incident_id_incidents'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_severity_assessments'))
    )
    with op.batch_alter_table('severity_assessments', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_severity_assessments_incident_id'), ['incident_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_severity_assessments_review_state'), ['review_state'], unique=False)
        batch_op.create_index(batch_op.f('ix_severity_assessments_is_pending_review'), ['is_pending_review'], unique=False)
        batch_op.create_index(batch_op.f('ix_severity_assessments_supersedes_assessment_id'), ['supersedes_assessment_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_severity_assessments_superseded_by_id'), ['superseded_by_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('severity_assessments', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_severity_assessments_superseded_by_id'))
        batch_op.drop_index(batch_op.f('ix_severity_assessments_supersedes_assessment_id'))
        batch_op.drop_index(batch_op.f('ix_severity_assessments_is_pending_review'))
        batch_op.drop_index(batch_op.f('ix_severity_assessments_review_state'))
        batch_op.drop_index(batch_op.f('ix_severity_assessments_incident_id'))

    op.drop_table('severity_assessments')
