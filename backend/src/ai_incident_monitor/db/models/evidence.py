"""Evidence records, verbatim quotation spans, and claim-evidence junction models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
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
    from ai_incident_monitor.db.models.claim import ClaimRecordModel
    from ai_incident_monitor.db.models.source import SourceReferenceModel


class EvidenceRecordModel(Base, TimestampMixin):
    """Relational model for an extracted evidence record."""

    __tablename__ = "evidence_records"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("source_references.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    short_summary: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(50), nullable=False)
    directness: Mapped[str] = mapped_column(String(50), nullable=False)
    specificity: Mapped[str] = mapped_column(String(50), nullable=False)
    corroboration_status: Mapped[str] = mapped_column(String(50), nullable=False)
    access_limitations: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    review_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="DRAFT_UNREVIEWED"
    )

    # Ingestion provenance
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    ingestion_batch_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    demonstration_notice: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0.0")

    # Relationships
    source: Mapped[SourceReferenceModel] = relationship(
        "SourceReferenceModel",
        back_populates="evidence_records",
    )
    quote_spans: Mapped[list[QuoteSpanModel]] = relationship(
        "QuoteSpanModel",
        back_populates="evidence",
        cascade="all, delete-orphan",
    )
    claim_links: Mapped[list[ClaimEvidenceLinkModel]] = relationship(
        "ClaimEvidenceLinkModel",
        back_populates="evidence",
        cascade="all, delete-orphan",
    )


class QuoteSpanModel(Base):
    """Verbatim quote span anchored to character offsets in the raw payload."""

    __tablename__ = "quote_spans"

    __table_args__ = (
        CheckConstraint(
            "end_char_offset > start_char_offset",
            name="ck_quote_spans_offset_order",
        ),
        CheckConstraint(
            "start_char_offset >= 0",
            name="ck_quote_spans_offset_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evidence_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("evidence_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    quote_text: Mapped[str] = mapped_column(Text, nullable=False)
    start_char_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    end_char_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    demonstration_notice: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    evidence: Mapped[EvidenceRecordModel] = relationship(
        "EvidenceRecordModel",
        back_populates="quote_spans",
    )


class ClaimEvidenceLinkModel(Base):
    """Junction table connecting claims to supporting or contradicting evidence."""

    __tablename__ = "claim_evidence_links"

    claim_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("claim_records.id", ondelete="CASCADE"),
        primary_key=True,
    )
    evidence_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("evidence_records.id", ondelete="CASCADE"),
        primary_key=True,
    )
    link_type: Mapped[str] = mapped_column(
        String(20),
        primary_key=True,
        default="SUPPORTING",
    )

    # Relationships
    claim: Mapped[ClaimRecordModel] = relationship(
        "ClaimRecordModel",
        back_populates="evidence_links",
    )
    evidence: Mapped[EvidenceRecordModel] = relationship(
        "EvidenceRecordModel",
        back_populates="claim_links",
    )
