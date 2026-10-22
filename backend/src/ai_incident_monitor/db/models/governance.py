"""Relational ORM models for governance framework reference sets, controls, mappings, and audit trails."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ai_incident_monitor.db.base import Base
from ai_incident_monitor.db.models.common import TimestampMixin

if TYPE_CHECKING:
    from ai_incident_monitor.db.models.evidence import EvidenceRecordModel
    from ai_incident_monitor.db.models.incident import IncidentModel


class FrameworkReferenceSetModel(Base, TimestampMixin):
    """Relational model for an official versioned governance reference set."""

    __tablename__ = "framework_reference_sets"
    __table_args__ = (
        UniqueConstraint(
            "framework_code", "version", name="uq_framework_refset_code_version"
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    framework_code: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    framework_name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(30), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    publisher: Mapped[str] = mapped_column(String(100), nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    verified_by: Mapped[str] = mapped_column(String(64), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    license_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ACTIVE")
    supersedes_reference_set_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, index=True
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    # Relationships
    controls: Mapped[list[FrameworkControlModel]] = relationship(
        "FrameworkControlModel",
        back_populates="reference_set",
        cascade="all, delete-orphan",
    )
    mappings: Mapped[list[IncidentFrameworkMappingModel]] = relationship(
        "IncidentFrameworkMappingModel",
        back_populates="reference_set",
    )
    eu_screens: Mapped[list[EULegalRelevanceScreenModel]] = relationship(
        "EULegalRelevanceScreenModel",
        back_populates="reference_set",
    )


class FrameworkControlModel(Base, TimestampMixin):
    """Relational model for a framework principle, function, category, or article node."""

    __tablename__ = "framework_controls"
    __table_args__ = (
        UniqueConstraint(
            "reference_set_id", "external_identifier", name="uq_control_refset_ext_id"
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    reference_set_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("framework_reference_sets.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    external_identifier: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    parent_identifier: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    control_level: Mapped[str] = mapped_column(String(30), nullable=False)
    framework_function: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    subcategory: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    article_number: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    effective_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    applicability_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_locator: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ACTIVE")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    # Relationships
    reference_set: Mapped[FrameworkReferenceSetModel] = relationship(
        "FrameworkReferenceSetModel",
        back_populates="controls",
    )
    mappings: Mapped[list[IncidentFrameworkMappingModel]] = relationship(
        "IncidentFrameworkMappingModel",
        back_populates="framework_control",
    )


class IncidentFrameworkMappingModel(Base, TimestampMixin):
    """Relational model mapping an incident to a framework control based on evidence."""

    __tablename__ = "incident_framework_mappings"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    incident_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    framework_code: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    reference_set_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("framework_reference_sets.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    framework_control_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("framework_controls.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    mapping_level: Mapped[str] = mapped_column(String(30), nullable=False)
    applicability: Mapped[str] = mapped_column(String(40), nullable=False)
    confidence: Mapped[str] = mapped_column(String(20), nullable=False, default="INSUFFICIENT")
    mapping_status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT", index=True)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    known_facts: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    unknowns: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    disputed_facts: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    evidence_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    recommended_control_or_follow_up: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Provenance and HITL review tracking
    rule_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    rule_version: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    generated_by: Mapped[str] = mapped_column(String(64), nullable=False)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Immutability and supersession chain
    supersedes_mapping_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    superseded_by_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    # Relationships
    incident: Mapped[IncidentModel] = relationship(
        "IncidentModel",
        back_populates="framework_mappings",
    )
    reference_set: Mapped[FrameworkReferenceSetModel] = relationship(
        "FrameworkReferenceSetModel",
        back_populates="mappings",
    )
    framework_control: Mapped[Optional[FrameworkControlModel]] = relationship(
        "FrameworkControlModel",
        back_populates="mappings",
    )
    evidence_links: Mapped[list[MappingEvidenceLinkModel]] = relationship(
        "MappingEvidenceLinkModel",
        back_populates="incident_mapping",
        cascade="all, delete-orphan",
    )


class EULegalRelevanceScreenModel(Base, TimestampMixin):
    """Relational model for informational regulatory screening under Regulation (EU) 2024/1689."""

    __tablename__ = "eu_legal_relevance_screens"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    incident_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reference_set_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("framework_reference_sets.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    screen_version: Mapped[str] = mapped_column(String(30), nullable=False, default="1.0.0")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT", index=True)
    relevance_level: Mapped[str] = mapped_column(
        String(40), nullable=False, default="INSUFFICIENT_INFORMATION", index=True
    )
    nexus_assessment: Mapped[str] = mapped_column(
        String(50), nullable=False, default="INSUFFICIENT_NEXUS_INFORMATION"
    )
    territorial_nexus: Mapped[str] = mapped_column(
        String(40), nullable=False, default="INSUFFICIENT_INFORMATION"
    )
    ai_system_context: Mapped[str] = mapped_column(
        String(40), nullable=False, default="INSUFFICIENT_INFORMATION"
    )
    ai_system_relevance: Mapped[str] = mapped_column(
        String(40), nullable=False, default="INSUFFICIENT_INFORMATION"
    )
    actor_roles: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    actor_role_confidence: Mapped[str] = mapped_column(String(40), nullable=False, default="UNKNOWN")
    risk_class: Mapped[str] = mapped_column(
        String(40), nullable=False, default="INSUFFICIENT_INFORMATION"
    )
    serious_incident_relevance: Mapped[str] = mapped_column(
        String(40), nullable=False, default="INSUFFICIENT_INFORMATION"
    )
    conceptual_risk_areas: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    potentially_relevant_articles: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    potentially_relevant_reference_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    operational_obligations: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    operational_relevance_areas: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    applicability_date_assessment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    timing_assessment: Mapped[str] = mapped_column(String(50), nullable=False, default="NOT_ASSESSED")
    known_facts: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    unknowns: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    disputed_facts: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    missing_facts: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    follow_up_questions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    confidence: Mapped[str] = mapped_column(String(20), nullable=False, default="INSUFFICIENT")
    disclaimer_version: Mapped[str] = mapped_column(String(30), nullable=False, default="2024-1689-v2")
    disclaimer_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Provenance and HITL review tracking
    generated_by: Mapped[str] = mapped_column(String(64), nullable=False)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Immutability and supersession chain
    supersedes_screen_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    superseded_by_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    # Relationships
    incident: Mapped[IncidentModel] = relationship(
        "IncidentModel",
        back_populates="eu_legal_screens",
    )
    reference_set: Mapped[FrameworkReferenceSetModel] = relationship(
        "FrameworkReferenceSetModel",
        back_populates="eu_screens",
    )
    evidence_links: Mapped[list[MappingEvidenceLinkModel]] = relationship(
        "MappingEvidenceLinkModel",
        back_populates="eu_screen",
        cascade="all, delete-orphan",
    )
    rule_traces: Mapped[list[EUScreenRuleTraceModel]] = relationship(
        "EUScreenRuleTraceModel",
        back_populates="screen",
        cascade="all, delete-orphan",
    )

    @property
    def screen_status(self) -> str:
        """Alias for status property to align with domain model conventions."""
        return self.status

    @screen_status.setter
    def screen_status(self, value: str) -> None:
        self.status = value


class EUScreenRuleTraceModel(Base):
    """Relational model recording fine-grained rule evaluation provenance for an EU informational screen."""

    __tablename__ = "eu_screen_rule_traces"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    eu_legal_relevance_screen_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("eu_legal_relevance_screens.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rule_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    rule_version: Mapped[str] = mapped_column(String(30), nullable=False)
    reference_set_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("framework_reference_sets.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    matched_condition_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    screen: Mapped[EULegalRelevanceScreenModel] = relationship(
        "EULegalRelevanceScreenModel",
        back_populates="rule_traces",
    )
    reference_set: Mapped[FrameworkReferenceSetModel] = relationship(
        "FrameworkReferenceSetModel",
    )


class MappingEvidenceLinkModel(Base):
    """Junction model connecting an evidence record to a framework mapping or EU legal screen."""

    __tablename__ = "mapping_evidence_links"
    __table_args__ = (
        CheckConstraint(
            "(incident_framework_mapping_id IS NOT NULL AND eu_legal_relevance_screen_id IS NULL) OR "
            "(incident_framework_mapping_id IS NULL AND eu_legal_relevance_screen_id IS NOT NULL)",
            name="ck_mapping_link_xor_parent",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    incident_framework_mapping_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("incident_framework_mappings.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    eu_legal_relevance_screen_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("eu_legal_relevance_screens.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    evidence_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("evidence_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    claim_type: Mapped[str] = mapped_column(String(50), nullable=False)
    relevance_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    incident_mapping: Mapped[Optional[IncidentFrameworkMappingModel]] = relationship(
        "IncidentFrameworkMappingModel",
        back_populates="evidence_links",
    )
    eu_screen: Mapped[Optional[EULegalRelevanceScreenModel]] = relationship(
        "EULegalRelevanceScreenModel",
        back_populates="evidence_links",
    )
    evidence: Mapped[EvidenceRecordModel] = relationship(
        "EvidenceRecordModel",
        back_populates="governance_links",
    )


class GovernanceAuditLogModel(Base):
    """Append-only, cryptographically chained audit log for governance transitions and reviews."""

    __tablename__ = "governance_audit_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    transition_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    is_human: Mapped[bool] = mapped_column(Boolean, nullable=False)
    actor_role: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    timestamp_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    before_state_digest: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    after_state_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    previous_event_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    details_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
