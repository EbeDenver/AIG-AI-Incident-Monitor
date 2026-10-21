"""Domain models and data contracts for the AIG-ISI scoring engine.

Follows AIG-ISI Methodology Specification Version 1.0.0.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ai_incident_monitor.scoring.enums import (
    ConfidenceLevel,
    HumanReviewState,
    ImpactType,
    ISIDimension,
    ReviewGateId,
    SeverityTier,
)

# Approved weights summing exactly to 100
DIMENSION_WEIGHTS: dict[ISIDimension, int] = {
    ISIDimension.HUMAN_IMPACT: 25,
    ISIDimension.FINANCIAL_PROPERTY: 15,
    ISIDimension.TRUST_REPUTATION: 15,
    ISIDimension.PRIVACY_CONFIDENTIALITY: 15,
    ISIDimension.RIGHTS_FAIRNESS: 10,
    ISIDimension.OPERATIONAL_CRITICAL_SERVICE: 10,
    ISIDimension.SCALE_REACH: 5,
    ISIDimension.SOCIETAL_ENVIRONMENTAL: 5,
}

DIMENSION_NAMES: dict[ISIDimension, str] = {
    ISIDimension.HUMAN_IMPACT: "Human Impact and Dignity",
    ISIDimension.FINANCIAL_PROPERTY: "Financial and Property Impact",
    ISIDimension.TRUST_REPUTATION: "Trust and Reputational Impact",
    ISIDimension.PRIVACY_CONFIDENTIALITY: "Privacy and Confidentiality Impact",
    ISIDimension.RIGHTS_FAIRNESS: "Rights, Fairness, and Access Impact",
    ISIDimension.OPERATIONAL_CRITICAL_SERVICE: "Operational and Critical-Service Impact",
    ISIDimension.SCALE_REACH: "Scale, Reach, and Propagation",
    ISIDimension.SOCIETAL_ENVIRONMENTAL: "Societal and Environmental Impact",
}

assert sum(DIMENSION_WEIGHTS.values()) == 100, "Dimension weights must sum to exactly 100"


class DimensionScoreInput(BaseModel):
    """Input payload for scoring a single AIG-ISI dimension."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    score: Optional[int] = Field(
        default=None,
        ge=0,
        le=5,
        description="Ordinal score 0 to 5, or None for UNKNOWN",
    )
    rationale: str = Field(
        min_length=1,
        description="Human-readable evidentiary justification for the score or reason for UNKNOWN",
    )
    evidence_ids: list[str] = Field(
        default_factory=list,
        description="IDs of evidence anchors substantiating this dimension",
    )
    confidence: ConfidenceLevel = Field(
        default=ConfidenceLevel.MEDIUM,
        description="Confidence in evidence backing this specific dimension",
    )
    is_disputed: bool = Field(
        default=False,
        description="True if facts or score for this dimension are actively contested",
    )


class DimensionScoreResult(BaseModel):
    """Evaluated result for a single AIG-ISI dimension."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dimension: ISIDimension
    dimension_name: str
    score: Optional[int]
    weight: int
    weighted_contribution: Optional[float] = Field(
        description="Calculated contribution score * (weight / 5.0), or None if unknown"
    )
    rationale: str
    evidence_ids: list[str]
    confidence: ConfidenceLevel
    is_unknown: bool
    is_disputed: bool


class ScoreOverride(BaseModel):
    """Explicit, auditable record of an analyst or reviewer score override."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    target: str = Field(
        description="Target of override, e.g. 'actual_impact', 'potential_impact', or dimension ID"
    )
    original_score: Optional[float] = Field(
        description="Calculated score before override"
    )
    overridden_score: float = Field(
        ge=0.0,
        le=100.0,
        description="Manually overridden score (0.0 to 100.0)",
    )
    original_tier: SeverityTier
    overridden_tier: SeverityTier
    rationale: str = Field(
        min_length=10,
        description="Mandatory substantive explanation for why the calculation was overridden",
    )
    applied_by_id: str = Field(
        min_length=2,
        description="Identifier of the authenticated human reviewer applying the override",
    )
    applied_at_utc: datetime = Field(
        description="UTC timestamp when the override was applied"
    )

    @field_validator("rationale")
    @classmethod
    def validate_rationale_length(cls, v: str) -> str:
        if len(v.strip()) < 10:
            raise ValueError("Override rationale must be at least 10 non-whitespace characters.")
        return v


class ImpactAssessmentResult(BaseModel):
    """Complete evaluation for one impact perspective (Actual or Potential)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    impact_type: ImpactType
    dimension_scores: dict[ISIDimension, DimensionScoreResult]
    lower_bound: float = Field(
        description="Lower evidence bound (treating unknown dimensions as 0)"
    )
    upper_bound: float = Field(
        description="Upper uncertainty bound (treating unknown dimensions as worst-case 5)"
    )
    score_range: tuple[float, float] = Field(
        description="(lower_bound, upper_bound)"
    )
    completeness_pct: float = Field(
        description="Percentage of framework weight evaluated (0.0 to 100.0)"
    )
    evaluated_weight: int = Field(
        description="Sum of weights for evaluated dimensions (0 to 100)"
    )
    unknown_weight: int = Field(
        description="Sum of weights for unknown dimensions (0 to 100)"
    )
    provisional_normalized_score: Optional[float] = Field(
        description="Normalized score over evaluated dimensions (0.0 to 100.0), or None if unscored"
    )
    final_score: Optional[float] = Field(
        description="Final score after any override, or provisional_normalized_score"
    )
    tier: SeverityTier = Field(
        description="Severity tier determined by final score or special status"
    )
    confidence: ConfidenceLevel = Field(
        description="Overall confidence level for this impact assessment"
    )
    override: Optional[ScoreOverride] = Field(
        default=None,
        description="Details of any manual override applied to this impact assessment",
    )


class ReviewGateTrigger(BaseModel):
    """Record of an activated human-review workflow gate."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    gate_id: ReviewGateId
    description: str
    triggered: bool = True


class AIGISIScoreResult(BaseModel):
    """Authoritative, tamper-evident composite severity assessment for an incident."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    incident_id: str
    assessment_id: str
    methodology_version: str = Field(default="AIG-ISI-1.0.0")
    actual_impact: ImpactAssessmentResult
    potential_impact: ImpactAssessmentResult
    review_state: HumanReviewState
    review_gates: list[ReviewGateTrigger]
    is_pending_review: bool
    has_disputed_facts: bool
    overrides: list[ScoreOverride] = Field(default_factory=list)
    created_at_utc: datetime
    superseded_by_id: Optional[str] = None
