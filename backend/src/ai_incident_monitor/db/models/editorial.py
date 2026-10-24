"""Editorial dossier relational models enforcing human review primacy, immutability, and evidence linkage."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ai_incident_monitor.db.base import Base
from ai_incident_monitor.db.models.common import TimestampMixin

if TYPE_CHECKING:
    from ai_incident_monitor.db.models.governance import EULegalRelevanceScreenModel
    from ai_incident_monitor.db.models.incident import IncidentModel


class EditorialDossierModel(Base, TimestampMixin):
    """Relational model for an editorial dossier aggregating incidents and research."""

    __tablename__ = "editorial_dossiers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(40), nullable=False, default="CUSTOM")
    coverage_period_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    coverage_period_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="DRAFT", index=True)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    disclaimer_version: Mapped[str] = mapped_column(
        String(30), nullable=False, default="editorial-v1"
    )
    disclaimer_text: Mapped[str] = mapped_column(Text, nullable=False)
    methodology_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Structured aggregates
    summary_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    # Attribution and Human-in-the-Loop review
    generated_by: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Immutability and supersession tracking
    supersedes_dossier_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("editorial_dossiers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    superseded_by_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("editorial_dossiers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    entries: Mapped[list[EditorialDossierEntryModel]] = relationship(
        "EditorialDossierEntryModel",
        back_populates="dossier",
        cascade="all, delete-orphan",
        order_by="EditorialDossierEntryModel.entry_order",
    )
    reviews: Mapped[list[EditorialDossierReviewModel]] = relationship(
        "EditorialDossierReviewModel",
        back_populates="dossier",
        cascade="all, delete-orphan",
        order_by="EditorialDossierReviewModel.reviewed_at",
    )


class EditorialDossierEntryModel(Base):
    """Relational model for a single incident entry within an editorial dossier."""

    __tablename__ = "editorial_dossier_entries"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dossier_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("editorial_dossiers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    incident_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("incidents.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    entry_order: Mapped[int] = mapped_column(Integer, nullable=False)
    entry_type: Mapped[str] = mapped_column(String(40), nullable=False, default="PRIMARY")
    source_evidence_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    source_version_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # Optional EU screen linkage
    eu_screen_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("eu_legal_relevance_screens.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    eu_screen_status: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)

    # Canonical structured entry content
    content_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    dossier: Mapped[EditorialDossierModel] = relationship(
        "EditorialDossierModel",
        back_populates="entries",
    )
    incident: Mapped[IncidentModel] = relationship("IncidentModel")
    eu_screen: Mapped[Optional[EULegalRelevanceScreenModel]] = relationship(
        "EULegalRelevanceScreenModel"
    )


class EditorialDossierReviewModel(Base):
    """Relational model for human review decisions and attestations on editorial dossiers."""

    __tablename__ = "editorial_dossier_reviews"

    __table_args__ = (
        CheckConstraint(
            "is_human = true OR is_human = 1",
            name="ck_editorial_reviews_is_human",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dossier_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("editorial_dossiers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dossier_version: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    reviewer_id: Mapped[str] = mapped_column(String(64), nullable=False)
    reviewer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reviewer_role: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_human: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    statement_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    attestation_statement: Mapped[str] = mapped_column(Text, nullable=False)

    action: Mapped[str] = mapped_column(String(40), nullable=False)
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attestation_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    dossier: Mapped[EditorialDossierModel] = relationship(
        "EditorialDossierModel",
        back_populates="reviews",
    )
