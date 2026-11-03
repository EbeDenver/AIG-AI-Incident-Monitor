"""Relational ORM model for EU AI Act Compliance Assessments.

Governing Charter: Regulation (EU) 2024/1689,
AI-incident-AU-Act-Compliance-assessor.pdf, Phase 8C Direction.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ai_incident_monitor.db.base import Base
from ai_incident_monitor.db.models.common import TimestampMixin

if TYPE_CHECKING:
    from ai_incident_monitor.db.models.incident import IncidentModel


class EUAIActComplianceAssessmentModel(Base, TimestampMixin):
    """Relational model storing structured EU AI Act compliance intelligence."""

    __tablename__ = "incident_eu_compliance_assessments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    incident_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="COMPLETED", index=True
    )

    jurisdiction_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="UNDETERMINED"
    )
    system_classification: Mapped[str] = mapped_column(
        String(50), nullable=False, default="UNKNOWN"
    )
    annex_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    enforcement_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="ACTIVE_LAW"
    )
    is_serious_incident: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # Full serialized EUAIActComplianceAssessment payload
    payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    model_provider: Mapped[str] = mapped_column(
        String(50), nullable=False, default="deterministic"
    )
    model_name: Mapped[str] = mapped_column(
        String(100), nullable=False, default="eu-act-assessor-v1"
    )

    # Relationship to incident
    incident: Mapped[IncidentModel] = relationship(
        "IncidentModel",
        back_populates="eu_compliance_assessment",
    )
