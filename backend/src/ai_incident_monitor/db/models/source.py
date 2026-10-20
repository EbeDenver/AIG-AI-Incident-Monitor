"""Source reference relational model tracking external sources and cryptographic digests."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ai_incident_monitor.db.base import Base
from ai_incident_monitor.db.models.common import TimestampMixin

if TYPE_CHECKING:
    from ai_incident_monitor.db.models.evidence import EvidenceRecordModel


class SourceReferenceModel(Base, TimestampMixin):
    """Relational model for an external source reference."""

    __tablename__ = "source_references"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    publisher: Mapped[str] = mapped_column(String(255), nullable=False)
    author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)

    publication_date_precision: Mapped[str] = mapped_column(
        String(20), nullable=False, default="UNKNOWN"
    )
    publication_exact_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    publication_date_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    publication_date_month: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    publication_date_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    retrieval_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    access_status: Mapped[str] = mapped_column(String(50), nullable=False)
    authority: Mapped[str] = mapped_column(String(50), nullable=False)
    reliability: Mapped[str] = mapped_column(String(50), nullable=False)
    independence: Mapped[str] = mapped_column(String(50), nullable=False)
    syndication_origin: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")

    # Cryptographic integrity digest (Constitutional Rule 4, 16)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    # Copyright and fair-use flags (ADR-003, Rule 16)
    is_copyright_restricted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fair_use_quotation_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    full_text_git_excluded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    retention_policy_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    demonstration_notice: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0.0")

    # Relationships
    evidence_records: Mapped[list[EvidenceRecordModel]] = relationship(
        "EvidenceRecordModel",
        back_populates="source",
        cascade="all, delete-orphan",
    )
