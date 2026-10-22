"""eu_ai_act_informational_screen

Revision ID: 005
Revises: 004
Create Date: 2026-10-22 12:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add informational screening and epistemic columns to eu_legal_relevance_screens
    with op.batch_alter_table('eu_legal_relevance_screens', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('screen_version', sa.String(length=30), server_default='1.0.0', nullable=False)
        )
        batch_op.add_column(
            sa.Column(
                'relevance_level',
                sa.String(length=40),
                server_default='INSUFFICIENT_INFORMATION',
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                'nexus_assessment',
                sa.String(length=50),
                server_default='INSUFFICIENT_NEXUS_INFORMATION',
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                'ai_system_context',
                sa.String(length=40),
                server_default='INSUFFICIENT_INFORMATION',
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                'actor_role_confidence',
                sa.String(length=40),
                server_default='UNKNOWN',
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column('conceptual_risk_areas', sa.JSON(), server_default='[]', nullable=False)
        )
        batch_op.add_column(
            sa.Column('potentially_relevant_reference_ids', sa.JSON(), server_default='[]', nullable=False)
        )
        batch_op.add_column(
            sa.Column('operational_relevance_areas', sa.JSON(), server_default='[]', nullable=False)
        )
        batch_op.add_column(
            sa.Column(
                'timing_assessment',
                sa.String(length=50),
                server_default='NOT_ASSESSED',
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column('known_facts', sa.JSON(), server_default='[]', nullable=False)
        )
        batch_op.add_column(
            sa.Column('unknowns', sa.JSON(), server_default='[]', nullable=False)
        )
        batch_op.add_column(
            sa.Column('disputed_facts', sa.JSON(), server_default='[]', nullable=False)
        )
        batch_op.add_column(
            sa.Column('follow_up_questions', sa.JSON(), server_default='[]', nullable=False)
        )
        batch_op.add_column(
            sa.Column('rationale', sa.Text(), server_default='', nullable=False)
        )
        batch_op.add_column(
            sa.Column('disclaimer_version', sa.String(length=30), server_default='2024-1689-v2', nullable=False)
        )
        batch_op.add_column(
            sa.Column('metadata_json', sa.JSON(), server_default='{}', nullable=False)
        )
        batch_op.create_index(
            batch_op.f('ix_eu_legal_relevance_screens_relevance_level'),
            ['relevance_level'],
            unique=False,
        )

    # 2. Create eu_screen_rule_traces junction table
    op.create_table(
        'eu_screen_rule_traces',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('eu_legal_relevance_screen_id', sa.String(length=64), nullable=False),
        sa.Column('rule_id', sa.String(length=64), nullable=False),
        sa.Column('rule_version', sa.String(length=30), nullable=False),
        sa.Column('reference_set_id', sa.String(length=64), nullable=False),
        sa.Column('matched_condition_ids', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(
            ['eu_legal_relevance_screen_id'],
            ['eu_legal_relevance_screens.id'],
            name=op.f('fk_eu_screen_rule_traces_eu_legal_relevance_screen_id_eu_legal_relevance_screens'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['reference_set_id'],
            ['framework_reference_sets.id'],
            name=op.f('fk_eu_screen_rule_traces_reference_set_id_framework_reference_sets'),
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_eu_screen_rule_traces')),
    )
    with op.batch_alter_table('eu_screen_rule_traces', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_eu_screen_rule_traces_eu_legal_relevance_screen_id'),
            ['eu_legal_relevance_screen_id'],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f('ix_eu_screen_rule_traces_rule_id'),
            ['rule_id'],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f('ix_eu_screen_rule_traces_reference_set_id'),
            ['reference_set_id'],
            unique=False,
        )


def downgrade() -> None:
    # 1. Drop eu_screen_rule_traces table
    with op.batch_alter_table('eu_screen_rule_traces', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_eu_screen_rule_traces_reference_set_id'))
        batch_op.drop_index(batch_op.f('ix_eu_screen_rule_traces_rule_id'))
        batch_op.drop_index(batch_op.f('ix_eu_screen_rule_traces_eu_legal_relevance_screen_id'))
    op.drop_table('eu_screen_rule_traces')

    # 2. Drop added columns from eu_legal_relevance_screens
    with op.batch_alter_table('eu_legal_relevance_screens', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_eu_legal_relevance_screens_relevance_level'))
        batch_op.drop_column('metadata_json')
        batch_op.drop_column('disclaimer_version')
        batch_op.drop_column('rationale')
        batch_op.drop_column('follow_up_questions')
        batch_op.drop_column('disputed_facts')
        batch_op.drop_column('unknowns')
        batch_op.drop_column('known_facts')
        batch_op.drop_column('timing_assessment')
        batch_op.drop_column('operational_relevance_areas')
        batch_op.drop_column('potentially_relevant_reference_ids')
        batch_op.drop_column('conceptual_risk_areas')
        batch_op.drop_column('actor_role_confidence')
        batch_op.drop_column('ai_system_context')
        batch_op.drop_column('nexus_assessment')
        batch_op.drop_column('relevance_level')
        batch_op.drop_column('screen_version')
