"""Incident relational model persisting core incident dossiers."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ai_incident_monitor.db.base import Base
from ai_incident_monitor.db.models.common import TimestampMixin

if TYPE_CHECKING:
    from ai_incident_monitor.db.models.causality import AIInvolvementAssessmentModel
    from ai_incident_monitor.db.models.claim import ClaimRecordModel
    from ai_incident_monitor.db.models.severity import SeverityAssessmentModel
    from ai_incident_monitor.db.models.uncertainty import UncertaintyRecordModel


class IncidentModel(Base, TimestampMixin):
    """Relational model for an AI incident dossier."""

    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="UNDER_INVESTIGATION")

    # Date with precision modeling (Unknown is not coerced to zero / arbitrary dates)
    incident_date_precision: Mapped[str] = mapped_column(
        String(20), nullable=False, default="UNKNOWN"
    )
    incident_exact_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    incident_start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    incident_end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    incident_date_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    incident_date_month: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    incident_date_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    demonstration_notice: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0.0")

    # Relationships
    claims: Mapped[list[ClaimRecordModel]] = relationship(
        "ClaimRecordModel",
        back_populates="incident",
        cascade="all, delete-orphan",
    )
    ai_involvements: Mapped[list[AIInvolvementAssessmentModel]] = relationship(
        "AIInvolvementAssessmentModel",
        back_populates="incident",
        cascade="all, delete-orphan",
    )
    uncertainties: Mapped[list[UncertaintyRecordModel]] = relationship(
        "UncertaintyRecordModel",
        back_populates="incident",
        cascade="all, delete-orphan",
    )
    severity_assessments: Mapped[list[SeverityAssessmentModel]] = relationship(
        "SeverityAssessmentModel",
        back_populates="incident",
        cascade="all, delete-orphan",
    )
