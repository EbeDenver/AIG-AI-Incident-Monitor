"""intelligence_dossier_contract

Revision ID: 008
Revises: 007
Create Date: 2026-11-03 01:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '008'
down_revision: Union[str, None] = '007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('incident_enrichments', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'assessment_status',
                sa.String(length=30),
                server_default='COMPLETE',
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                'payload_json',
                sa.Text(),
                nullable=True,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table('incident_enrichments', schema=None) as batch_op:
        batch_op.drop_column('payload_json')
        batch_op.drop_column('assessment_status')
