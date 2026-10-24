"""editorial_dossiers_and_review

Revision ID: 006
Revises: 005
Create Date: 2026-10-23 20:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '006'
down_revision: Union[str, None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create editorial_dossiers table
    op.create_table(
        'editorial_dossiers',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('version', sa.Integer(), server_default='1', nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('scope_type', sa.String(length=40), server_default='CUSTOM', nullable=False),
        sa.Column('coverage_period_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('coverage_period_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=40), server_default='DRAFT', nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=True),
        sa.Column('disclaimer_version', sa.String(length=30), server_default='editorial-v1', nullable=False),
        sa.Column('disclaimer_text', sa.Text(), nullable=False),
        sa.Column('methodology_notes', sa.Text(), nullable=True),
        sa.Column('summary_json', sa.JSON(), server_default='{}', nullable=False),
        sa.Column('metadata_json', sa.JSON(), server_default='{}', nullable=False),
        sa.Column('generated_by', sa.String(length=64), server_default='system', nullable=False),
        sa.Column('reviewed_by', sa.String(length=64), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('supersedes_dossier_id', sa.String(length=64), nullable=True),
        sa.Column('superseded_by_id', sa.String(length=64), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(
            ['superseded_by_id'],
            ['editorial_dossiers.id'],
            name=op.f('fk_editorial_dossiers_superseded_by_id_editorial_dossiers'),
            ondelete='SET NULL',
        ),
        sa.ForeignKeyConstraint(
            ['supersedes_dossier_id'],
            ['editorial_dossiers.id'],
            name=op.f('fk_editorial_dossiers_supersedes_dossier_id_editorial_dossiers'),
            ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_editorial_dossiers')),
    )
    with op.batch_alter_table('editorial_dossiers', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_editorial_dossiers_status'),
            ['status'],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f('ix_editorial_dossiers_content_hash'),
            ['content_hash'],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f('ix_editorial_dossiers_supersedes_dossier_id'),
            ['supersedes_dossier_id'],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f('ix_editorial_dossiers_superseded_by_id'),
            ['superseded_by_id'],
            unique=False,
        )

    # 2. Create editorial_dossier_entries table
    op.create_table(
        'editorial_dossier_entries',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('dossier_id', sa.String(length=64), nullable=False),
        sa.Column('incident_id', sa.String(length=64), nullable=False),
        sa.Column('entry_order', sa.Integer(), nullable=False),
        sa.Column('entry_type', sa.String(length=40), server_default='PRIMARY', nullable=False),
        sa.Column('source_evidence_ids', sa.JSON(), server_default='[]', nullable=False),
        sa.Column('source_version_hash', sa.String(length=64), nullable=False),
        sa.Column('eu_screen_id', sa.String(length=64), nullable=True),
        sa.Column('eu_screen_status', sa.String(length=40), nullable=True),
        sa.Column('content_json', sa.JSON(), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(
            ['dossier_id'],
            ['editorial_dossiers.id'],
            name=op.f('fk_editorial_dossier_entries_dossier_id_editorial_dossiers'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['incident_id'],
            ['incidents.id'],
            name=op.f('fk_editorial_dossier_entries_incident_id_incidents'),
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['eu_screen_id'],
            ['eu_legal_relevance_screens.id'],
            name=op.f('fk_editorial_dossier_entries_eu_screen_id_eu_legal_relevance_screens'),
            ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_editorial_dossier_entries')),
    )
    with op.batch_alter_table('editorial_dossier_entries', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_editorial_dossier_entries_dossier_id'),
            ['dossier_id'],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f('ix_editorial_dossier_entries_incident_id'),
            ['incident_id'],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f('ix_editorial_dossier_entries_eu_screen_id'),
            ['eu_screen_id'],
            unique=False,
        )

    # 3. Create editorial_dossier_reviews table
    op.create_table(
        'editorial_dossier_reviews',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('dossier_id', sa.String(length=64), nullable=False),
        sa.Column('dossier_version', sa.Integer(), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('reviewer_id', sa.String(length=64), nullable=False),
        sa.Column('reviewer_name', sa.String(length=255), nullable=True),
        sa.Column('reviewer_role', sa.String(length=64), nullable=True),
        sa.Column('is_human', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column('statement_confirmed', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('attestation_statement', sa.Text(), nullable=False),
        sa.Column('action', sa.String(length=40), nullable=False),
        sa.Column('rationale', sa.Text(), nullable=True),
        sa.Column('attestation_json', sa.JSON(), server_default='{}', nullable=False),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.CheckConstraint(
            'is_human = true OR is_human = 1',
            name=op.f('ck_editorial_dossier_reviews_is_human'),
        ),
        sa.ForeignKeyConstraint(
            ['dossier_id'],
            ['editorial_dossiers.id'],
            name=op.f('fk_editorial_dossier_reviews_dossier_id_editorial_dossiers'),
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_editorial_dossier_reviews')),
    )
    with op.batch_alter_table('editorial_dossier_reviews', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_editorial_dossier_reviews_dossier_id'),
            ['dossier_id'],
            unique=False,
        )


def downgrade() -> None:
    # 1. Drop editorial_dossier_reviews
    with op.batch_alter_table('editorial_dossier_reviews', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_editorial_dossier_reviews_dossier_id'))
    op.drop_table('editorial_dossier_reviews')

    # 2. Drop editorial_dossier_entries
    with op.batch_alter_table('editorial_dossier_entries', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_editorial_dossier_entries_eu_screen_id'))
        batch_op.drop_index(batch_op.f('ix_editorial_dossier_entries_incident_id'))
        batch_op.drop_index(batch_op.f('ix_editorial_dossier_entries_dossier_id'))
    op.drop_table('editorial_dossier_entries')

    # 3. Drop editorial_dossiers
    with op.batch_alter_table('editorial_dossiers', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_editorial_dossiers_superseded_by_id'))
        batch_op.drop_index(batch_op.f('ix_editorial_dossiers_supersedes_dossier_id'))
        batch_op.drop_index(batch_op.f('ix_editorial_dossiers_content_hash'))
        batch_op.drop_index(batch_op.f('ix_editorial_dossiers_status'))
    op.drop_table('editorial_dossiers')
