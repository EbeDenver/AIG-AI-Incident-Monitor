"""Deterministic calculation engine for the AI Guardians Incident Severity Index (AIG-ISI).

Follows AIG-ISI Methodology Specification Version 1.0.0.
All calculations are pure, deterministic, and free of external network or model calls.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
import uuid

from ai_incident_monitor.scoring.enums import (
    ConfidenceLevel,
    HumanReviewState,
    ImpactType,
    ISIDimension,
    ReviewGateId,
    SeverityTier,
)
from ai_incident_monitor.scoring.models import (
    DIMENSION_NAMES,
    DIMENSION_WEIGHTS,
    AIGISIScoreResult,
    DimensionScoreInput,
    DimensionScoreResult,
    ImpactAssessmentResult,
    ReviewGateTrigger,
    ScoreOverride,
)


def calculate_dimension_contribution(score: Optional[int], weight: int) -> Optional[float]:
    """Calculate the weighted contribution of a single dimension score (0-5).

    Contribution = score * (weight / 5.0).
    If score is None (UNKNOWN), returns None.
    """
    if score is None:
        return None
    return round(score * (weight / 5.0), 4)


def determine_tier(
    score: Optional[float],
    completeness_pct: float,
    is_disputed: bool = False,
) -> SeverityTier:
    """Determine the severity tier based on score (0-100) and completeness.

    Tiers:
    - Minimal: 0.0 - 19.999
    - Moderate: 20.0 - 39.999
    - Significant: 40.0 - 59.999
    - Severe: 60.0 - 79.999
    - Critical: 80.0 - 100.0
    - Unscored: completeness 0% or score is None
    - Disputed: disputed facts
    """
    if is_disputed:
        return SeverityTier.DISPUTED

    if completeness_pct == 0.0 or score is None:
        return SeverityTier.UNSCORED

    if score < 20.0:
        return SeverityTier.MINIMAL
    elif score < 40.0:
        return SeverityTier.MODERATE
    elif score < 60.0:
        return SeverityTier.SIGNIFICANT
    elif score < 80.0:
        return SeverityTier.SEVERE
    else:
        return SeverityTier.CRITICAL


def calculate_overall_confidence(
    dimension_scores: dict[ISIDimension, DimensionScoreResult]
) -> ConfidenceLevel:
    """Calculate the weighted evidentiary confidence across evaluated dimensions."""
    evaluated = [d for d in dimension_scores.values() if not d.is_unknown]
    if not evaluated:
        return ConfidenceLevel.INSUFFICIENT

    # Map confidence to numeric rank
    confidence_rank = {
        ConfidenceLevel.INSUFFICIENT: 0,
        ConfidenceLevel.LOW: 1,
        ConfidenceLevel.MEDIUM: 2,
        ConfidenceLevel.HIGH: 3,
    }

    total_weight = sum(d.weight for d in evaluated)
    weighted_sum = sum(confidence_rank[d.confidence] * d.weight for d in evaluated)
    avg_score = weighted_sum / total_weight

    # Human impact dimension with weight 25 has strict floor enforcement
    human_dim = dimension_scores.get(ISIDimension.HUMAN_IMPACT)
    if human_dim and not human_dim.is_unknown and human_dim.score is not None and human_dim.score >= 4:
        # If critical human harm is reported with LOW/INSUFFICIENT confidence, cap overall confidence
        if human_dim.confidence in (ConfidenceLevel.LOW, ConfidenceLevel.INSUFFICIENT):
            return human_dim.confidence

    if avg_score >= 2.5:
        return ConfidenceLevel.HIGH
    elif avg_score >= 1.5:
        return ConfidenceLevel.MEDIUM
    elif avg_score >= 0.5:
        return ConfidenceLevel.LOW
    else:
        return ConfidenceLevel.INSUFFICIENT


def calculate_impact_assessment(
    impact_type: ImpactType,
    dimension_inputs: dict[ISIDimension, DimensionScoreInput],
    override: Optional[ScoreOverride] = None,
) -> ImpactAssessmentResult:
    """Calculate a complete impact assessment (Actual or Potential).

    All 8 dimensions are evaluated. Missing dimensions default to UNKNOWN.
    """
    evaluated_scores: dict[ISIDimension, DimensionScoreResult] = {}
    lower_bound_sum = 0.0
    evaluated_weight = 0
    unknown_weight = 0

    for dim in ISIDimension:
        weight = DIMENSION_WEIGHTS[dim]
        dim_name = DIMENSION_NAMES[dim]
        inp = dimension_inputs.get(dim)

        if inp is None or inp.score is None:
            is_unknown = True
            score = None
            contribution = None
            unknown_weight += weight
            rationale = inp.rationale if inp else "Dimension not assessed (UNKNOWN)."
            evidence_ids = inp.evidence_ids if inp else []
            confidence = inp.confidence if inp else ConfidenceLevel.INSUFFICIENT
            is_disputed = inp.is_disputed if inp else False
        else:
            is_unknown = False
            score = inp.score
            contribution = calculate_dimension_contribution(score, weight)
            assert contribution is not None
            lower_bound_sum += contribution
            evaluated_weight += weight
            rationale = inp.rationale
            evidence_ids = inp.evidence_ids
            confidence = inp.confidence
            is_disputed = inp.is_disputed

        evaluated_scores[dim] = DimensionScoreResult(
            dimension=dim,
            dimension_name=dim_name,
            score=score,
            weight=weight,
            weighted_contribution=contribution,
            rationale=rationale,
            evidence_ids=evidence_ids,
            confidence=confidence,
            is_unknown=is_unknown,
            is_disputed=is_disputed,
        )

    lower_bound = round(lower_bound_sum, 4)
    upper_bound = round(lower_bound + unknown_weight, 4)
    completeness_pct = round((evaluated_weight / 100.0) * 100.0, 2)

    if evaluated_weight > 0:
        provisional_normalized_score = round((lower_bound / evaluated_weight) * 100.0, 2)
    else:
        provisional_normalized_score = None

    has_disputed = any(d.is_disputed for d in evaluated_scores.values())

    if override is not None:
        final_score = override.overridden_score
        tier = override.overridden_tier
    else:
        final_score = provisional_normalized_score
        tier = determine_tier(final_score, completeness_pct, is_disputed=has_disputed)

    overall_confidence = calculate_overall_confidence(evaluated_scores)

    return ImpactAssessmentResult(
        impact_type=impact_type,
        dimension_scores=evaluated_scores,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
        score_range=(lower_bound, upper_bound),
        completeness_pct=completeness_pct,
        evaluated_weight=evaluated_weight,
        unknown_weight=unknown_weight,
        provisional_normalized_score=provisional_normalized_score,
        final_score=final_score,
        tier=tier,
        confidence=overall_confidence,
        override=override,
    )


def evaluate_review_gates(
    actual: ImpactAssessmentResult,
    potential: ImpactAssessmentResult,
    has_materially_disputed_facts: bool = False,
    overrides: Optional[list[ScoreOverride]] = None,
) -> list[ReviewGateTrigger]:
    """Evaluate all 10 mandatory human-review workflow gates."""
    triggers: list[ReviewGateTrigger] = []
    overrides = overrides or []

    # Gate 1: Tier 4 or 5
    severe_or_critical = (SeverityTier.SEVERE, SeverityTier.CRITICAL)
    if actual.tier in severe_or_critical or potential.tier in severe_or_critical:
        triggers.append(
            ReviewGateTrigger(
                gate_id=ReviewGateId.TIER_4_OR_5,
                description="Actual or potential severity is Tier 4 (Severe) or Tier 5 (Critical).",
            )
        )

    # Gate 2: Low or Insufficient Confidence
    low_conf = (ConfidenceLevel.LOW, ConfidenceLevel.INSUFFICIENT)
    if actual.confidence in low_conf or potential.confidence in low_conf:
        triggers.append(
            ReviewGateTrigger(
                gate_id=ReviewGateId.LOW_CONFIDENCE,
                description=f"Confidence is low or insufficient (Actual: {actual.confidence.value}, Potential: {potential.confidence.value}).",
            )
        )

    # Gate 3: Low Completeness (< 70%)
    if actual.completeness_pct < 70.0 or potential.completeness_pct < 70.0:
        triggers.append(
            ReviewGateTrigger(
                gate_id=ReviewGateId.LOW_COMPLETENESS,
                description=f"Completeness is below 70% threshold (Actual: {actual.completeness_pct}%, Potential: {potential.completeness_pct}%).",
            )
        )

    # Gate 4: Actual vs Potential Divergence
    if actual.final_score is not None and potential.final_score is not None:
        score_diff = abs(actual.final_score - potential.final_score)
        valid_tiers = (
            SeverityTier.MINIMAL,
            SeverityTier.MODERATE,
            SeverityTier.SIGNIFICANT,
            SeverityTier.SEVERE,
            SeverityTier.CRITICAL,
        )
        tier_diff = (actual.tier != potential.tier) and (actual.tier in valid_tiers and potential.tier in valid_tiers)
        if score_diff >= 20.0 or tier_diff:
            triggers.append(
                ReviewGateTrigger(
                    gate_id=ReviewGateId.ACTUAL_VS_POTENTIAL_DIVERGENCE,
                    description=f"Major divergence between actual ({actual.final_score}, {actual.tier.value}) and potential ({potential.final_score}, {potential.tier.value}) impact.",
                )
            )

    # Gate 5: Override Present
    if len(overrides) > 0 or actual.override is not None or potential.override is not None:
        triggers.append(
            ReviewGateTrigger(
                gate_id=ReviewGateId.OVERRIDE_PRESENT,
                description="Manual score or tier override is present, requiring human review and authorization.",
            )
        )

    # Gate 6: Serious Injury or Death (Human Impact >= 4)
    act_human = actual.dimension_scores[ISIDimension.HUMAN_IMPACT].score
    pot_human = potential.dimension_scores[ISIDimension.HUMAN_IMPACT].score
    if (act_human is not None and act_human >= 4) or (pot_human is not None and pot_human >= 4):
        triggers.append(
            ReviewGateTrigger(
                gate_id=ReviewGateId.SERIOUS_INJURY_OR_DEATH,
                description="Human Impact and Dignity score is 4 or 5 (severe injury, permanent disability, or fatality).",
            )
        )

    # Gate 7: Critical Infrastructure (Operational Impact >= 4)
    act_ops = actual.dimension_scores[ISIDimension.OPERATIONAL_CRITICAL_SERVICE].score
    pot_ops = potential.dimension_scores[ISIDimension.OPERATIONAL_CRITICAL_SERVICE].score
    if (act_ops is not None and act_ops >= 4) or (pot_ops is not None and pot_ops >= 4):
        triggers.append(
            ReviewGateTrigger(
                gate_id=ReviewGateId.CRITICAL_INFRASTRUCTURE,
                description="Operational and Critical-Service Impact score is 4 or 5 (vital infrastructure or emergency outage).",
            )
        )

    # Gate 8: Serious Privacy Impact (Privacy Impact >= 4)
    act_priv = actual.dimension_scores[ISIDimension.PRIVACY_CONFIDENTIALITY].score
    pot_priv = potential.dimension_scores[ISIDimension.PRIVACY_CONFIDENTIALITY].score
    if (act_priv is not None and act_priv >= 4) or (pot_priv is not None and pot_priv >= 4):
        triggers.append(
            ReviewGateTrigger(
                gate_id=ReviewGateId.SERIOUS_PRIVACY_IMPACT,
                description="Privacy and Confidentiality Impact score is 4 or 5 (mass breach of sensitive personal records or trade secrets).",
            )
        )

    # Gate 9: Serious Rights Impact (Rights Impact >= 4)
    act_rights = actual.dimension_scores[ISIDimension.RIGHTS_FAIRNESS].score
    pot_rights = potential.dimension_scores[ISIDimension.RIGHTS_FAIRNESS].score
    if (act_rights is not None and act_rights >= 4) or (pot_rights is not None and pot_rights >= 4):
        triggers.append(
            ReviewGateTrigger(
                gate_id=ReviewGateId.SERIOUS_RIGHTS_IMPACT,
                description="Rights, Fairness, and Access Impact score is 4 or 5 (systemic civil rights violation or unlawful detention).",
            )
        )

    # Gate 10: Materially Disputed Facts
    act_disputed = any(d.is_disputed for d in actual.dimension_scores.values())
    pot_disputed = any(d.is_disputed for d in potential.dimension_scores.values())
    if has_materially_disputed_facts or act_disputed or pot_disputed:
        triggers.append(
            ReviewGateTrigger(
                gate_id=ReviewGateId.MATERIALLY_DISPUTED_FACTS,
                description="Incident contains contested facts, disputed claims, or contested causal attribution.",
            )
        )

    return triggers


def calculate_aig_isi_assessment(
    incident_id: str,
    actual_inputs: dict[ISIDimension, DimensionScoreInput],
    potential_inputs: dict[ISIDimension, DimensionScoreInput],
    overrides: Optional[list[ScoreOverride]] = None,
    has_materially_disputed_facts: bool = False,
    initial_review_state: HumanReviewState = HumanReviewState.DRAFT,
    assessment_id: Optional[str] = None,
) -> AIGISIScoreResult:
    """Calculate the complete, authoritative AIG-ISI severity assessment for an incident.

    Generates both Actual and Potential assessments, evaluates all 10 review gates,
    and returns a tamper-evident, immutable score result.
    """
    overrides = overrides or []
    assessment_id = assessment_id or f"isi-{uuid.uuid4().hex[:12]}"

    actual_override = next((o for o in overrides if o.target in ("actual_impact", "actual")), None)
    potential_override = next((o for o in overrides if o.target in ("potential_impact", "potential")), None)

    actual_assessment = calculate_impact_assessment(
        impact_type=ImpactType.ACTUAL,
        dimension_inputs=actual_inputs,
        override=actual_override,
    )

    potential_assessment = calculate_impact_assessment(
        impact_type=ImpactType.POTENTIAL,
        dimension_inputs=potential_inputs,
        override=potential_override,
    )

    review_gates = evaluate_review_gates(
        actual=actual_assessment,
        potential=potential_assessment,
        has_materially_disputed_facts=has_materially_disputed_facts,
        overrides=overrides,
    )

    is_pending_review = len(review_gates) > 0

    if initial_review_state == HumanReviewState.APPROVED:
        final_review_state = HumanReviewState.APPROVED
    elif initial_review_state == HumanReviewState.REJECTED:
        final_review_state = HumanReviewState.REJECTED
    elif initial_review_state == HumanReviewState.SUPERSEDED:
        final_review_state = HumanReviewState.SUPERSEDED
    elif is_pending_review:
        final_review_state = HumanReviewState.PENDING_REVIEW
    else:
        final_review_state = initial_review_state

    has_disputed = (
        has_materially_disputed_facts
        or any(d.is_disputed for d in actual_assessment.dimension_scores.values())
        or any(d.is_disputed for d in potential_assessment.dimension_scores.values())
    )

    return AIGISIScoreResult(
        incident_id=incident_id,
        assessment_id=assessment_id,
        methodology_version="AIG-ISI-1.0.0",
        actual_impact=actual_assessment,
        potential_impact=potential_assessment,
        review_state=final_review_state,
        review_gates=review_gates,
        is_pending_review=is_pending_review,
        has_disputed_facts=has_disputed,
        overrides=overrides,
        created_at_utc=datetime.now(timezone.utc),
    )
