"""Severity assessment relational model persisting AIG-ISI evaluations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import Boolean, Float, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ai_incident_monitor.db.base import Base
from ai_incident_monitor.db.models.common import TimestampMixin

if TYPE_CHECKING:
    from ai_incident_monitor.db.models.incident import IncidentModel


class SeverityAssessmentModel(Base, TimestampMixin):
    """Relational model for versioned, immutable AIG-ISI severity assessments."""

    __tablename__ = "severity_assessments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    incident_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    methodology_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="AIG-ISI-1.0.0",
    )

    # Actual Impact fields
    actual_raw_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    actual_normalized_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    actual_lower_bound: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    actual_upper_bound: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    actual_completeness_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    actual_tier: Mapped[str] = mapped_column(String(30), nullable=False, default="UNSCORED")
    actual_confidence: Mapped[str] = mapped_column(String(20), nullable=False, default="INSUFFICIENT")

    # Potential Impact fields
    potential_raw_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    potential_normalized_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    potential_lower_bound: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    potential_upper_bound: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    potential_completeness_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    potential_tier: Mapped[str] = mapped_column(String(30), nullable=False, default="UNSCORED")
    potential_confidence: Mapped[str] = mapped_column(String(20), nullable=False, default="INSUFFICIENT")

    # Detailed dimensions payload (JSON)
    dimension_scores: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    # Review workflow fields
    review_state: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT", index=True)
    review_gates_triggered: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    is_pending_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    has_disputed_facts: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Overrides (JSON array)
    overrides: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)

    # Versioning & immutability chain
    supersedes_assessment_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )
    superseded_by_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )

    # Relationships
    incident: Mapped[IncidentModel] = relationship(
        "IncidentModel",
        back_populates="severity_assessments",
    )
