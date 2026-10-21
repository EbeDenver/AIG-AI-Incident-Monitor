"""Controlled vocabularies and enumerations for the AIG-ISI scoring engine.

Follows AIG-ISI Methodology Specification Version 1.0.0.
"""

from enum import Enum


class ISIDimension(str, Enum):
    """The eight approved dimensions of the AI Guardians Incident Severity Index."""

    HUMAN_IMPACT = "human_impact"
    FINANCIAL_PROPERTY = "financial_property"
    TRUST_REPUTATION = "trust_reputation"
    PRIVACY_CONFIDENTIALITY = "privacy_confidentiality"
    RIGHTS_FAIRNESS = "rights_fairness"
    OPERATIONAL_CRITICAL_SERVICE = "operational_critical_service"
    SCALE_REACH = "scale_reach"
    SOCIETAL_ENVIRONMENTAL = "societal_environmental"


class SeverityTier(str, Enum):
    """Standardized severity tiers (0-100 scale) plus special status tiers."""

    MINIMAL = "MINIMAL"           # 0.0 - 19.999
    MODERATE = "MODERATE"         # 20.0 - 39.999
    SIGNIFICANT = "SIGNIFICANT"   # 40.0 - 59.999
    SEVERE = "SEVERE"             # 60.0 - 79.999
    CRITICAL = "CRITICAL"         # 80.0 - 100.0

    # Special / Status Tiers
    UNSCORED = "UNSCORED"         # Completeness 0% or insufficient data
    DISPUTED = "DISPUTED"         # Primary facts or scores contested
    SUPERSEDED = "SUPERSEDED"     # Replaced by newer versioned record


class ConfidenceLevel(str, Enum):
    """Evidentiary confidence level. Orthogonal to severity score."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INSUFFICIENT = "INSUFFICIENT"


class HumanReviewState(str, Enum):
    """Lifecycle state of an assessment in the human-in-the-loop workflow."""

    DRAFT = "DRAFT"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class ImpactType(str, Enum):
    """Impact evaluation context: demonstrated actual versus counterfactual potential."""

    ACTUAL = "ACTUAL"
    POTENTIAL = "POTENTIAL"


class ReviewGateId(str, Enum):
    """Identifiers for the 10 mandatory human-review workflow gates."""

    TIER_4_OR_5 = "TIER_4_OR_5"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    LOW_COMPLETENESS = "LOW_COMPLETENESS"
    ACTUAL_VS_POTENTIAL_DIVERGENCE = "ACTUAL_VS_POTENTIAL_DIVERGENCE"
    OVERRIDE_PRESENT = "OVERRIDE_PRESENT"
    SERIOUS_INJURY_OR_DEATH = "SERIOUS_INJURY_OR_DEATH"
    CRITICAL_INFRASTRUCTURE = "CRITICAL_INFRASTRUCTURE"
    SERIOUS_PRIVACY_IMPACT = "SERIOUS_PRIVACY_IMPACT"
    SERIOUS_RIGHTS_IMPACT = "SERIOUS_RIGHTS_IMPACT"
    MATERIALLY_DISPUTED_FACTS = "MATERIALLY_DISPUTED_FACTS"
