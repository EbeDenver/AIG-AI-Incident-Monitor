"""governance_framework_mappings

Revision ID: 003
Revises: 002
Create Date: 2026-10-21 00:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Framework Reference Sets
    op.create_table(
        'framework_reference_sets',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('framework_code', sa.String(length=30), nullable=False),
        sa.Column('framework_name', sa.String(length=255), nullable=False),
        sa.Column('version', sa.String(length=30), nullable=False),
        sa.Column('source_url', sa.Text(), nullable=False),
        sa.Column('publisher', sa.String(length=100), nullable=False),
        sa.Column('retrieved_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('verified_by', sa.String(length=64), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('license_notes', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=30), server_default='ACTIVE', nullable=False),
        sa.Column('supersedes_reference_set_id', sa.String(length=64), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_framework_reference_sets')),
        sa.UniqueConstraint('framework_code', 'version', name=op.f('uq_framework_reference_sets_framework_code_version'))
    )
    with op.batch_alter_table('framework_reference_sets', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_framework_reference_sets_framework_code'), ['framework_code'], unique=False)
        batch_op.create_index(batch_op.f('ix_framework_reference_sets_supersedes_reference_set_id'), ['supersedes_reference_set_id'], unique=False)

    # 2. Framework Controls
    op.create_table(
        'framework_controls',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('reference_set_id', sa.String(length=64), nullable=False),
        sa.Column('external_identifier', sa.String(length=64), nullable=False),
        sa.Column('parent_identifier', sa.String(length=64), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('control_level', sa.String(length=30), nullable=False),
        sa.Column('framework_function', sa.String(length=64), nullable=True),
        sa.Column('category', sa.String(length=64), nullable=True),
        sa.Column('subcategory', sa.String(length=64), nullable=True),
        sa.Column('article_number', sa.String(length=30), nullable=True),
        sa.Column('effective_date', sa.Date(), nullable=True),
        sa.Column('applicability_notes', sa.Text(), nullable=True),
        sa.Column('source_locator', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=30), server_default='ACTIVE', nullable=False),
        sa.Column('metadata_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['reference_set_id'], ['framework_reference_sets.id'], name=op.f('fk_framework_controls_reference_set_id_framework_reference_sets'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_framework_controls')),
        sa.UniqueConstraint('reference_set_id', 'external_identifier', name=op.f('uq_framework_controls_reference_set_id_external_identifier'))
    )
    with op.batch_alter_table('framework_controls', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_framework_controls_reference_set_id'), ['reference_set_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_framework_controls_external_identifier'), ['external_identifier'], unique=False)
        batch_op.create_index(batch_op.f('ix_framework_controls_parent_identifier'), ['parent_identifier'], unique=False)

    # 3. Incident Framework Mappings
    op.create_table(
        'incident_framework_mappings',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('incident_id', sa.String(length=64), nullable=False),
        sa.Column('framework_code', sa.String(length=30), nullable=False),
        sa.Column('reference_set_id', sa.String(length=64), nullable=False),
        sa.Column('framework_control_id', sa.String(length=64), nullable=True),
        sa.Column('mapping_level', sa.String(length=30), nullable=False),
        sa.Column('applicability', sa.String(length=40), nullable=False),
        sa.Column('confidence', sa.String(length=20), server_default='INSUFFICIENT', nullable=False),
        sa.Column('mapping_status', sa.String(length=30), server_default='DRAFT', nullable=False),
        sa.Column('rationale', sa.Text(), nullable=False),
        sa.Column('known_facts', sa.JSON(), nullable=False),
        sa.Column('unknowns', sa.JSON(), nullable=False),
        sa.Column('disputed_facts', sa.JSON(), nullable=False),
        sa.Column('evidence_ids', sa.JSON(), nullable=False),
        sa.Column('recommended_control_or_follow_up', sa.Text(), nullable=True),
        sa.Column('generated_by', sa.String(length=64), nullable=False),
        sa.Column('reviewed_by', sa.String(length=64), nullable=True),
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('supersedes_mapping_id', sa.String(length=64), nullable=True),
        sa.Column('superseded_by_id', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['framework_control_id'], ['framework_controls.id'], name=op.f('fk_incident_framework_mappings_framework_control_id_framework_controls'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], name=op.f('fk_incident_framework_mappings_incident_id_incidents'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reference_set_id'], ['framework_reference_sets.id'], name=op.f('fk_incident_framework_mappings_reference_set_id_framework_reference_sets'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_incident_framework_mappings'))
    )
    with op.batch_alter_table('incident_framework_mappings', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_incident_framework_mappings_incident_id'), ['incident_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_incident_framework_mappings_framework_code'), ['framework_code'], unique=False)
        batch_op.create_index(batch_op.f('ix_incident_framework_mappings_reference_set_id'), ['reference_set_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_incident_framework_mappings_framework_control_id'), ['framework_control_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_incident_framework_mappings_mapping_status'), ['mapping_status'], unique=False)
        batch_op.create_index(batch_op.f('ix_incident_framework_mappings_supersedes_mapping_id'), ['supersedes_mapping_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_incident_framework_mappings_superseded_by_id'), ['superseded_by_id'], unique=False)

    # 4. EU Legal Relevance Screens
    op.create_table(
        'eu_legal_relevance_screens',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('incident_id', sa.String(length=64), nullable=False),
        sa.Column('reference_set_id', sa.String(length=64), nullable=False),
        sa.Column('territorial_nexus', sa.String(length=40), server_default='INSUFFICIENT_INFORMATION', nullable=False),
        sa.Column('ai_system_relevance', sa.String(length=40), server_default='INSUFFICIENT_INFORMATION', nullable=False),
        sa.Column('actor_roles', sa.JSON(), nullable=False),
        sa.Column('risk_class', sa.String(length=40), server_default='INSUFFICIENT_INFORMATION', nullable=False),
        sa.Column('serious_incident_relevance', sa.String(length=40), server_default='INSUFFICIENT_INFORMATION', nullable=False),
        sa.Column('potentially_relevant_articles', sa.JSON(), nullable=False),
        sa.Column('operational_obligations', sa.JSON(), nullable=False),
        sa.Column('applicability_date_assessment', sa.Text(), nullable=False),
        sa.Column('missing_facts', sa.JSON(), nullable=False),
        sa.Column('confidence', sa.String(length=20), server_default='INSUFFICIENT', nullable=False),
        sa.Column('status', sa.String(length=30), server_default='DRAFT', nullable=False),
        sa.Column('disclaimer_text', sa.Text(), nullable=False),
        sa.Column('generated_by', sa.String(length=64), nullable=False),
        sa.Column('reviewed_by', sa.String(length=64), nullable=True),
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('supersedes_screen_id', sa.String(length=64), nullable=True),
        sa.Column('superseded_by_id', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], name=op.f('fk_eu_legal_relevance_screens_incident_id_incidents'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reference_set_id'], ['framework_reference_sets.id'], name=op.f('fk_eu_legal_relevance_screens_reference_set_id_framework_reference_sets'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_eu_legal_relevance_screens'))
    )
    with op.batch_alter_table('eu_legal_relevance_screens', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_eu_legal_relevance_screens_incident_id'), ['incident_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_eu_legal_relevance_screens_reference_set_id'), ['reference_set_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_eu_legal_relevance_screens_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_eu_legal_relevance_screens_supersedes_screen_id'), ['supersedes_screen_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_eu_legal_relevance_screens_superseded_by_id'), ['superseded_by_id'], unique=False)

    # 5. Mapping Evidence Links (Junction)
    op.create_table(
        'mapping_evidence_links',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('incident_framework_mapping_id', sa.String(length=64), nullable=True),
        sa.Column('eu_legal_relevance_screen_id', sa.String(length=64), nullable=True),
        sa.Column('evidence_id', sa.String(length=64), nullable=False),
        sa.Column('claim_type', sa.String(length=50), nullable=False),
        sa.Column('relevance_note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.CheckConstraint(
            '(incident_framework_mapping_id IS NOT NULL AND eu_legal_relevance_screen_id IS NULL) OR '
            '(incident_framework_mapping_id IS NULL AND eu_legal_relevance_screen_id IS NOT NULL)',
            name=op.f('ck_mapping_evidence_links_ck_mapping_link_xor_parent')
        ),
        sa.ForeignKeyConstraint(['eu_legal_relevance_screen_id'], ['eu_legal_relevance_screens.id'], name=op.f('fk_mapping_evidence_links_eu_legal_relevance_screen_id_eu_legal_relevance_screens'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['evidence_id'], ['evidence_records.id'], name=op.f('fk_mapping_evidence_links_evidence_id_evidence_records'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['incident_framework_mapping_id'], ['incident_framework_mappings.id'], name=op.f('fk_mapping_evidence_links_incident_framework_mapping_id_incident_framework_mappings'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_mapping_evidence_links'))
    )
    with op.batch_alter_table('mapping_evidence_links', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_mapping_evidence_links_incident_framework_mapping_id'), ['incident_framework_mapping_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_mapping_evidence_links_eu_legal_relevance_screen_id'), ['eu_legal_relevance_screen_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_mapping_evidence_links_evidence_id'), ['evidence_id'], unique=False)

    # 6. Governance Audit Logs
    op.create_table(
        'governance_audit_logs',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('entity_type', sa.String(length=64), nullable=False),
        sa.Column('entity_id', sa.String(length=64), nullable=False),
        sa.Column('transition_type', sa.String(length=50), nullable=False),
        sa.Column('actor_id', sa.String(length=64), nullable=False),
        sa.Column('is_human', sa.Boolean(), nullable=False),
        sa.Column('actor_role', sa.String(length=64), nullable=True),
        sa.Column('timestamp_utc', sa.DateTime(timezone=True), nullable=False),
        sa.Column('before_state_digest', sa.String(length=64), nullable=True),
        sa.Column('after_state_digest', sa.String(length=64), nullable=False),
        sa.Column('event_hash', sa.String(length=64), nullable=False),
        sa.Column('previous_event_hash', sa.String(length=64), nullable=True),
        sa.Column('details_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_governance_audit_logs')),
        sa.UniqueConstraint('event_hash', name=op.f('uq_governance_audit_logs_event_hash'))
    )
    with op.batch_alter_table('governance_audit_logs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_governance_audit_logs_entity_type'), ['entity_type'], unique=False)
        batch_op.create_index(batch_op.f('ix_governance_audit_logs_entity_id'), ['entity_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_governance_audit_logs_transition_type'), ['transition_type'], unique=False)
        batch_op.create_index(batch_op.f('ix_governance_audit_logs_event_hash'), ['event_hash'], unique=True)
        batch_op.create_index(batch_op.f('ix_governance_audit_logs_previous_event_hash'), ['previous_event_hash'], unique=False)


def downgrade() -> None:
    # Drop only objects created in migration 003, in reverse dependency order
    with op.batch_alter_table('governance_audit_logs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_governance_audit_logs_previous_event_hash'))
        batch_op.drop_index(batch_op.f('ix_governance_audit_logs_event_hash'))
        batch_op.drop_index(batch_op.f('ix_governance_audit_logs_transition_type'))
        batch_op.drop_index(batch_op.f('ix_governance_audit_logs_entity_id'))
        batch_op.drop_index(batch_op.f('ix_governance_audit_logs_entity_type'))
    op.drop_table('governance_audit_logs')

    with op.batch_alter_table('mapping_evidence_links', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_mapping_evidence_links_evidence_id'))
        batch_op.drop_index(batch_op.f('ix_mapping_evidence_links_eu_legal_relevance_screen_id'))
        batch_op.drop_index(batch_op.f('ix_mapping_evidence_links_incident_framework_mapping_id'))
    op.drop_table('mapping_evidence_links')

    with op.batch_alter_table('eu_legal_relevance_screens', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_eu_legal_relevance_screens_superseded_by_id'))
        batch_op.drop_index(batch_op.f('ix_eu_legal_relevance_screens_supersedes_screen_id'))
        batch_op.drop_index(batch_op.f('ix_eu_legal_relevance_screens_status'))
        batch_op.drop_index(batch_op.f('ix_eu_legal_relevance_screens_reference_set_id'))
        batch_op.drop_index(batch_op.f('ix_eu_legal_relevance_screens_incident_id'))
    op.drop_table('eu_legal_relevance_screens')

    with op.batch_alter_table('incident_framework_mappings', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_incident_framework_mappings_superseded_by_id'))
        batch_op.drop_index(batch_op.f('ix_incident_framework_mappings_supersedes_mapping_id'))
        batch_op.drop_index(batch_op.f('ix_incident_framework_mappings_mapping_status'))
        batch_op.drop_index(batch_op.f('ix_incident_framework_mappings_framework_control_id'))
        batch_op.drop_index(batch_op.f('ix_incident_framework_mappings_reference_set_id'))
        batch_op.drop_index(batch_op.f('ix_incident_framework_mappings_framework_code'))
        batch_op.drop_index(batch_op.f('ix_incident_framework_mappings_incident_id'))
    op.drop_table('incident_framework_mappings')

    with op.batch_alter_table('framework_controls', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_framework_controls_parent_identifier'))
        batch_op.drop_index(batch_op.f('ix_framework_controls_external_identifier'))
        batch_op.drop_index(batch_op.f('ix_framework_controls_reference_set_id'))
    op.drop_table('framework_controls')

    with op.batch_alter_table('framework_reference_sets', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_framework_reference_sets_supersedes_reference_set_id'))
        batch_op.drop_index(batch_op.f('ix_framework_reference_sets_framework_code'))
    op.drop_table('framework_reference_sets')
