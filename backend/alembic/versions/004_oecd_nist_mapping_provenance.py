"""oecd_nist_mapping_provenance

Revision ID: 004
Revises: 003
Create Date: 2026-10-21 18:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('incident_framework_mappings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('rule_id', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('rule_version', sa.String(length=30), nullable=True))
        batch_op.create_index(batch_op.f('ix_incident_framework_mappings_rule_id'), ['rule_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('incident_framework_mappings', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_incident_framework_mappings_rule_id'))
        batch_op.drop_column('rule_version')
        batch_op.drop_column('rule_id')
