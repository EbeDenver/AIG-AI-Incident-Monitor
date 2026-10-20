"""Raw import persistence and deduplication review queue relational models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ai_incident_monitor.db.base import Base

if TYPE_CHECKING:
    from ai_incident_monitor.db.models.incident import IncidentModel


class RawImportRecordModel(Base):
    """Raw record preservation retaining original row payloads and content hashes (DEC-P3-002)."""

    __tablename__ = "raw_import_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    source_format: Mapped[str] = mapped_column(String(10), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    staged_file_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="INGESTED")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    incident_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("incidents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    dedup_candidates: Mapped[list[DedupCandidateModel]] = relationship(
        "DedupCandidateModel",
        back_populates="raw_import",
        cascade="all, delete-orphan",
    )


class DedupCandidateModel(Base):
    """Potential near-duplicate candidate queued for human review (DEC-P3-003)."""

    __tablename__ = "dedup_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raw_import_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("raw_import_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    existing_incident_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tier: Mapped[int] = mapped_column(Integer, nullable=False)
    similarity_score: Mapped[float] = mapped_column(Float, nullable=False)
    match_rationale: Mapped[str] = mapped_column(Text, nullable=False)

    review_decision: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    raw_import: Mapped[RawImportRecordModel] = relationship(
        "RawImportRecordModel",
        back_populates="dedup_candidates",
    )
