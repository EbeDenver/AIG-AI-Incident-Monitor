"""Claim relational model enforcing epistemic status and monetary rules."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ai_incident_monitor.db.base import Base
from ai_incident_monitor.db.models.common import TimestampMixin

if TYPE_CHECKING:
    from ai_incident_monitor.db.models.causality import CausalAssessmentModel
    from ai_incident_monitor.db.models.evidence import ClaimEvidenceLinkModel
    from ai_incident_monitor.db.models.incident import IncidentModel
    from ai_incident_monitor.db.models.review import HumanReviewRecordModel


class ClaimRecordModel(Base, TimestampMixin):
    """Relational model for an assertion within an incident dossier."""

    __tablename__ = "claim_records"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    incident_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    claim_type: Mapped[str] = mapped_column(String(50), nullable=False)
    epistemic_status: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[str] = mapped_column(String(50), nullable=False)
    materiality: Mapped[str] = mapped_column(String(50), nullable=False)

    is_causal_claim: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_numeric_claim: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_legal_claim: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_framework_interpretation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    review_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="DRAFT_UNREVIEWED"
    )
    human_review_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("human_review_records.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    lifecycle_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="INITIAL_ASSESSMENT"
    )
    superseded_by: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("claim_records.id", ondelete="SET NULL"),
        nullable=True,
    )
    supersedes: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("claim_records.id", ondelete="SET NULL"),
        nullable=True,
    )
    supersession_reason: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Monetary representation (Constitutional Rule 2: Unknown is not zero)
    monetary_amount_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    monetary_exact_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    monetary_min_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    monetary_max_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    monetary_currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)

    demonstration_notice: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0.0")

    # Relationships
    incident: Mapped[IncidentModel] = relationship(
        "IncidentModel",
        back_populates="claims",
    )
    evidence_links: Mapped[list[ClaimEvidenceLinkModel]] = relationship(
        "ClaimEvidenceLinkModel",
        back_populates="claim",
        cascade="all, delete-orphan",
    )
    causal_assessment: Mapped[Optional[CausalAssessmentModel]] = relationship(
        "CausalAssessmentModel",
        back_populates="claim",
        uselist=False,
        cascade="all, delete-orphan",
    )
    human_review: Mapped[Optional[HumanReviewRecordModel]] = relationship(
        "HumanReviewRecordModel",
        back_populates="claims",
    )
