"""Causal assessment and AI involvement relational models."""

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
    from ai_incident_monitor.db.models.claim import ClaimRecordModel
    from ai_incident_monitor.db.models.incident import IncidentModel


class CausalAssessmentModel(Base, TimestampMixin):
    """Relational model evaluating causal link between AI behavior and observed impact."""

    __tablename__ = "causal_assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    claim_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("claim_records.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    attribution_status: Mapped[str] = mapped_column(String(50), nullable=False)
    mechanism_description: Mapped[str] = mapped_column(Text, nullable=False)
    target_outcome: Mapped[str] = mapped_column(Text, nullable=False)
    counterfactual_rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    supporting_evidence_ids: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    demonstration_notice: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0.0")

    # Relationships
    claim: Mapped[ClaimRecordModel] = relationship(
        "ClaimRecordModel",
        back_populates="causal_assessment",
    )


class AIInvolvementAssessmentModel(Base, TimestampMixin):
    """Relational model evaluating specific role and components of AI in an incident."""

    __tablename__ = "ai_involvement_assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    involvement_status: Mapped[str] = mapped_column(String(50), nullable=False)
    component_implicated: Mapped[str] = mapped_column(String(50), nullable=False)
    technical_rationale: Mapped[str] = mapped_column(Text, nullable=False)
    supporting_evidence_ids: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    demonstration_notice: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0.0")

    # Relationships
    incident: Mapped[IncidentModel] = relationship(
        "IncidentModel",
        back_populates="ai_involvements",
    )
