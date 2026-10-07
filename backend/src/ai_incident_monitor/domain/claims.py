"""Claim records enforcing core constitutional invariants and epistemic validation.

Constitutional Rules 1, 3, 4, 5, 6, 7, 8, 9, 10:
- Confirmed facts require evidence.
- Material numeric claims require evidence and numeric models.
- Causal claims require CausalAssessment.
- Legal claims cannot be confirmed without human sign-off.
- Superseded records require replacement references.
"""

from typing import Optional

from pydantic import Field, model_validator

from ai_incident_monitor.domain.causality import CausalAssessment
from ai_incident_monitor.domain.common import (
    BaseEntity,
    SchemaVersioned,
    UngroundedClaimError,
    UnverifiedLegalConclusionError,
)
from ai_incident_monitor.domain.identifiers import (
    ClaimId,
    EvidenceId,
    IncidentId,
    ReviewId,
)
from ai_incident_monitor.domain.money import MonetaryAmount
from ai_incident_monitor.domain.vocabularies import (
    AssessmentLifecycleStatus,
    ClaimMateriality,
    ClaimType,
    ConfidenceLevel,
    EpistemicStatus,
    ReviewStatus,
    SupersessionReason,
)


class ClaimRecord(SchemaVersioned):
    """Core assertion model with deterministic constitutional validation."""

    id: ClaimId
    incident_id: IncidentId
    claim_text: str = Field(min_length=5, description="Full text statement of the claim")
    claim_type: ClaimType
    epistemic_status: EpistemicStatus
    supporting_evidence_ids: list[EvidenceId] = Field(default_factory=list)
    contradicting_evidence_ids: list[EvidenceId] = Field(default_factory=list)
    confidence: ConfidenceLevel
    materiality: ClaimMateriality
    is_causal_claim: bool = False
    is_numeric_claim: bool = False
    is_legal_claim: bool = False
    is_framework_interpretation: bool = False
    causal_assessment: Optional[CausalAssessment] = None
    numeric_amount: Optional[MonetaryAmount] = None
    review_status: ReviewStatus = ReviewStatus.DRAFT_UNREVIEWED
    human_review_id: Optional[ReviewId] = None
    lifecycle_status: AssessmentLifecycleStatus = AssessmentLifecycleStatus.INITIAL_ASSESSMENT
    superseded_by: Optional[ClaimId] = None
    supersedes: Optional[ClaimId] = None
    supersession_reason: Optional[SupersessionReason] = None

    @model_validator(mode="after")
    def validate_claim_constitutional_invariants(self) -> "ClaimRecord":
        # Rule 4: Confirmed factual claims require supporting evidence
        if self.epistemic_status == EpistemicStatus.CONFIRMED_FACT:
            if not self.supporting_evidence_ids:
                raise UngroundedClaimError(
                    f"Claim '{self.id}' with status CONFIRMED_FACT must have at least one supporting "
                    "evidence ID."
                )

        # Rule 5: Material numeric claims require supporting evidence and numeric_amount
        if self.is_numeric_claim and self.materiality in (
            ClaimMateriality.CORE_IMPACT,
            ClaimMateriality.SECONDARY_CONTRIBUTOR,
        ):
            if not self.supporting_evidence_ids:
                raise UngroundedClaimError(
                    f"Material numeric claim '{self.id}' requires at least one supporting evidence ID."
                )
            if self.numeric_amount is None:
                raise UngroundedClaimError(
                    f"Material numeric claim '{self.id}' requires an attached MonetaryAmount record."
                )

        # Rule 6: Causal claim requires attached CausalAssessment
        if self.is_causal_claim:
            if self.causal_assessment is None:
                raise UngroundedClaimError(
                    f"Causal claim '{self.id}' requires an attached CausalAssessment record."
                )

        # Rule 7: Legal conclusion cannot be confirmed by LLM alone
        if self.is_legal_claim and self.epistemic_status == EpistemicStatus.CONFIRMED_FACT:
            if self.review_status != ReviewStatus.HUMAN_APPROVED or self.human_review_id is None:
                raise UnverifiedLegalConclusionError(
                    f"Legal claim '{self.id}' cannot be marked CONFIRMED_FACT without explicit "
                    "human review approval (HUMAN_APPROVED) and an attached human_review_id."
                )

        # Rule 9: Superseded record must reference replacement
        if self.lifecycle_status == AssessmentLifecycleStatus.SUPERSEDED:
            if self.superseded_by is None:
                raise ValueError(
                    f"Superseded claim '{self.id}' must declare a valid 'superseded_by' reference."
                )

        # Rule 10: Corrected record must preserve previous version
        if self.lifecycle_status == AssessmentLifecycleStatus.CORRECTED:
            if self.supersedes is None:
                raise ValueError(
                    f"Corrected claim '{self.id}' must declare a valid 'supersedes' reference."
                )

        return self
