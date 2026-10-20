"""Uncertainty, disputed facts, and evidence gap relational models."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    JSON,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ai_incident_monitor.db.base import Base
from ai_incident_monitor.db.models.common import TimestampMixin

if TYPE_CHECKING:
    from ai_incident_monitor.db.models.incident import IncidentModel


class UncertaintyRecordModel(Base, TimestampMixin):
    """Relational model capturing known facts, unknown variables, and evidence gaps."""

    __tablename__ = "uncertainty_records"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    incident_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    known_facts: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    unknown_facts: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    missing_evidence: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    conflicting_evidence: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    information_expected_later: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reason_unresolved: Mapped[str] = mapped_column(String(50), nullable=False)
    resolution_criteria: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    demonstration_notice: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0.0")

    # Relationships
    incident: Mapped[IncidentModel] = relationship(
        "IncidentModel",
        back_populates="uncertainties",
    )
    disputed_facts: Mapped[list[DisputedFactModel]] = relationship(
        "DisputedFactModel",
        back_populates="uncertainty",
        cascade="all, delete-orphan",
    )


class DisputedFactModel(Base):
    """Relational model for specific assertions contested by one or more parties."""

    __tablename__ = "disputed_facts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uncertainty_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("uncertainty_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assertion: Mapped[str] = mapped_column(Text, nullable=False)
    contesting_party: Mapped[str] = mapped_column(String(255), nullable=False)
    supporting_evidence_ids: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    contradicting_evidence_ids: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    demonstration_notice: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    uncertainty: Mapped[UncertaintyRecordModel] = relationship(
        "UncertaintyRecordModel",
        back_populates="disputed_facts",
    )
