"""Causal attribution and AI involvement assessments.

Constitutional Rules 1, 4, 6:
- Causal claims require explicit attribution status and supporting evidence.
- AI involvement must be rigorously distinguished from causal contribution.
"""

from typing import Optional

from pydantic import Field, model_validator

from ai_incident_monitor.domain.common import (
    BaseEntity,
    SchemaVersioned,
    UngroundedClaimError,
)
from ai_incident_monitor.domain.identifiers import EvidenceId
from ai_incident_monitor.domain.vocabularies import (
    AIComponentType,
    AIInvolvementStatus,
    CausalAttributionStatus,
)


class CausalAssessment(SchemaVersioned):
    """Rigorous evaluation of the causal link between system behavior and observed impact."""

    attribution_status: CausalAttributionStatus
    mechanism_description: str = Field(
        min_length=5, description="Technical description of the proposed causal mechanism"
    )
    target_outcome: str = Field(
        min_length=3, description="Specific real-world harm or failure outcome evaluated"
    )
    supporting_evidence_ids: list[EvidenceId] = Field(default_factory=list)
    counterfactual_rationale: Optional[str] = Field(
        default=None, description="Reasoning on whether outcome would have occurred absent the AI failure"
    )

    @model_validator(mode="after")
    def validate_causal_evidence(self) -> "CausalAssessment":
        # Rule 6: Confirmed or probable causes require evidence
        if self.attribution_status in (
            CausalAttributionStatus.CONFIRMED_CAUSE,
            CausalAttributionStatus.PROBABLE_CONTRIBUTOR,
        ):
            if not self.supporting_evidence_ids:
                raise UngroundedClaimError(
                    f"Causal assessment with status '{self.attribution_status}' requires at least "
                    "one supporting evidence ID."
                )
        return self


class AIInvolvementAssessment(SchemaVersioned):
    """Evaluation of the specific role and components of AI systems in an incident."""

    involvement_status: AIInvolvementStatus
    component_implicated: AIComponentType
    supporting_evidence_ids: list[EvidenceId] = Field(default_factory=list)
    technical_rationale: str = Field(
        min_length=5, description="Evidentiary justification for the involvement classification"
    )

    @model_validator(mode="after")
    def validate_involvement_evidence(self) -> "AIInvolvementAssessment":
        if self.involvement_status in (
            AIInvolvementStatus.CONFIRMED_CAUSAL_CONTRIBUTION,
            AIInvolvementStatus.PROBABLE_CAUSAL_CONTRIBUTION,
        ):
            if not self.supporting_evidence_ids:
                raise UngroundedClaimError(
                    f"AI involvement assessment with status '{self.involvement_status}' requires at least "
                    "one supporting evidence ID."
                )
        return self
