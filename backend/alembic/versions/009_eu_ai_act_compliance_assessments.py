"""eu_ai_act_compliance_assessments

Revision ID: 009
Revises: 008
Create Date: 2026-11-03 03:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '009'
down_revision: Union[str, None] = '008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'incident_eu_compliance_assessments',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('incident_id', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='COMPLETED'),
        sa.Column('jurisdiction_status', sa.String(length=30), nullable=False, server_default='UNDETERMINED'),
        sa.Column('system_classification', sa.String(length=50), nullable=False, server_default='UNKNOWN'),
        sa.Column('annex_reference', sa.String(length=100), nullable=True),
        sa.Column('enforcement_status', sa.String(length=30), nullable=False, server_default='ACTIVE_LAW'),
        sa.Column('is_serious_incident', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('payload_json', sa.Text(), nullable=True),
        sa.Column('model_provider', sa.String(length=50), nullable=False, server_default='deterministic'),
        sa.Column('model_name', sa.String(length=100), nullable=False, server_default='eu-act-assessor-v1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('incident_id', name='uq_incident_eu_compliance_incident_id'),
    )
    op.create_index(
        'ix_incident_eu_compliance_assessments_incident_id',
        'incident_eu_compliance_assessments',
        ['incident_id'],
        unique=True,
    )
    op.create_index(
        'ix_incident_eu_compliance_assessments_status',
        'incident_eu_compliance_assessments',
        ['status'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        'ix_incident_eu_compliance_assessments_status',
        table_name='incident_eu_compliance_assessments',
    )
    op.drop_index(
        'ix_incident_eu_compliance_assessments_incident_id',
        table_name='incident_eu_compliance_assessments',
    )
    op.drop_table('incident_eu_compliance_assessments')
