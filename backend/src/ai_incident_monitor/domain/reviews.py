"""Human review records and reviewer credentials.

Constitutional Rules 14, 15, 18:
- LLM output shall not approve itself.
- High-severity ratings and public dossiers require authenticated human sign-off.
- Machine recommendations must remain structurally distinct from human approval.
"""

from typing import Optional

from pydantic import Field, field_validator

from ai_incident_monitor.domain.common import BaseEntity, SchemaVersioned
from ai_incident_monitor.domain.identifiers import ReviewId
from ai_incident_monitor.domain.vocabularies import ReviewDecision, ReviewStatus


class ReviewerIdentity(SchemaVersioned):
    """Authenticated human reviewer credentials enforcing human primacy."""

    reviewer_id: str = Field(min_length=2, description="Unique identifier of human editor")
    full_name: str = Field(min_length=2, description="Full name of human reviewer")
    email: str = Field(description="Corporate/institutional email of reviewer")
    role: str = Field(description="Editorial or safety review role")
    is_human: bool = Field(default=True, description="Strict human-reviewer flag")

    @field_validator("is_human")
    @classmethod
    def validate_human_primacy(cls, v: bool) -> bool:
        if not v:
            raise ValueError(
                "ReviewerIdentity requires is_human=True. Constitutional Rule 14 strictly forbids "
                "automated agents or LLMs from serving as reviewers or approving work."
            )
        return v


class HumanReviewRecord(SchemaVersioned):
    """Tamper-evident human sign-off record required before publication."""

    id: ReviewId
    reviewer: ReviewerIdentity
    review_status: ReviewStatus
    review_decision: ReviewDecision
    rationale: str = Field(
        min_length=10, description="Detailed substantive justification for review decision"
    )
    requested_changes: list[str] = Field(default_factory=list)
    approval_restrictions: list[str] = Field(default_factory=list)
    reviewed_at: str = Field(description="ISO 8601 UTC timestamp of human review sign-off")
    supersedes_review_id: Optional[ReviewId] = None

    @field_validator("review_status")
    @classmethod
    def validate_human_status(cls, v: ReviewStatus) -> ReviewStatus:
        if v not in (
            ReviewStatus.HUMAN_APPROVED,
            ReviewStatus.HUMAN_REJECTED,
            ReviewStatus.REVISION_REQUESTED,
        ):
            raise ValueError(
                f"HumanReviewRecord review_status must be a human decision (HUMAN_APPROVED, "
                f"HUMAN_REJECTED, REVISION_REQUESTED), got '{v}'."
            )
        return v
