"""Human review relational model enforcing human primacy."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ai_incident_monitor.db.base import Base
from ai_incident_monitor.db.models.common import TimestampMixin

if TYPE_CHECKING:
    from ai_incident_monitor.db.models.claim import ClaimRecordModel


class HumanReviewRecordModel(Base, TimestampMixin):
    """Relational model for authenticated human sign-off enforcing Rule 14."""

    __tablename__ = "human_review_records"

    __table_args__ = (
        CheckConstraint(
            "is_human = true OR is_human = 1",
            name="ck_human_review_records_is_human",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    reviewer_id: Mapped[str] = mapped_column(String(64), nullable=False)
    reviewer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    reviewer_email: Mapped[str] = mapped_column(String(255), nullable=False)
    reviewer_role: Mapped[str] = mapped_column(String(100), nullable=False)
    is_human: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    review_status: Mapped[str] = mapped_column(String(50), nullable=False)
    review_decision: Mapped[str] = mapped_column(String(50), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    requested_changes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    approval_restrictions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    supersedes_review_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("human_review_records.id", ondelete="SET NULL"),
        nullable=True,
    )

    demonstration_notice: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0.0")

    # Relationships
    claims: Mapped[list[ClaimRecordModel]] = relationship(
        "ClaimRecordModel",
        back_populates="human_review",
    )
