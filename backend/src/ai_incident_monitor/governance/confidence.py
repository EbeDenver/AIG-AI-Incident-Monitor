"""Deterministic confidence calculation engine for governance framework mappings.

Evaluates evidence quantity, directness, corroboration, specificity, material unknowns,
disputed facts, and structural granularity independently from AIG-ISI severity scores.
"""

from __future__ import annotations

from typing import Any

from ai_incident_monitor.governance.enums import (
    ControlLevel,
    GovernanceConfidence,
)
from ai_incident_monitor.governance.models import ConfidenceFactorBreakdown


def calculate_mapping_confidence(
    evidence_records: list[dict[str, Any]],
    target_level: ControlLevel,
    has_unknowns: bool = False,
    has_disputed_facts: bool = False,
) -> ConfidenceFactorBreakdown:
    """Calculate deterministic evidentiary confidence for a framework mapping.

    Args:
        evidence_records: List of evidence record dicts associated with this mapping.
        target_level: Granularity level of the target control (PRINCIPLE, FUNCTION, CATEGORY, SUBCATEGORY).
        has_unknowns: Whether material unknowns are flagged in context.
        has_disputed_facts: Whether disputed or conflicting facts are flagged in context.

    Returns:
        ConfidenceFactorBreakdown containing normalized score, level, and rationale.
    """
    if not evidence_records:
        return ConfidenceFactorBreakdown(
            score=0.0,
            level=GovernanceConfidence.INSUFFICIENT,
            evidence_count=0,
            directness_score=0.0,
            corroboration_score=0.0,
            specificity_score=0.0,
            unknowns_penalty=0.0,
            disputed_penalty=0.0,
            granularity_penalty=0.0,
            rationale="Zero linked evidence items. Governance mappings require at least one verified evidence link.",
        )

    # 1. Base score from evidence count (max 40 points)
    count = len(evidence_records)
    if count == 1:
        count_score = 25.0
    elif count == 2:
        count_score = 33.0
    else:
        count_score = 40.0

    # 2. Directness score (max 25 points)
    # Primary direct evidence gives max points, hearsay penalizes
    directness_points = 0.0
    for ev in evidence_records:
        directness = str(ev.get("directness", "SECONDARY_DERIVED")).upper()
        if "PRIMARY_DIRECT" in directness:
            directness_points += 25.0
        elif "PRIMARY_OBSERVATIONAL" in directness:
            directness_points += 20.0
        elif "SECONDARY_DERIVED" in directness:
            directness_points += 15.0
        else:  # HEARSAY_OR_ANECDOTAL
            directness_points += 5.0
    avg_directness = min(25.0, directness_points / count)

    # 3. Corroboration score (max 20 points)
    corroboration_points = 0.0
    any_contested = False
    any_refuted = False
    for ev in evidence_records:
        corr = str(ev.get("corroboration_status", "SINGLE_SOURCE_UNCONTESTED")).upper()
        if "FULLY_CORROBORATED" in corr:
            corroboration_points += 20.0
        elif "PARTIALLY_CORROBORATED" in corr:
            corroboration_points += 15.0
        elif "SINGLE_SOURCE" in corr:
            corroboration_points += 10.0
        elif "CONTESTED" in corr or "DISPUTED" in corr:
            any_contested = True
            corroboration_points += 5.0
        elif "REFUTED" in corr:
            any_refuted = True
            corroboration_points += 0.0
    avg_corroboration = min(20.0, corroboration_points / count)

    # 4. Specificity score (max 15 points)
    specificity_points = 0.0
    all_vague = True
    for ev in evidence_records:
        spec = str(ev.get("specificity", "MODERATELY_SPECIFIC")).upper()
        if "HIGHLY_SPECIFIC" in spec:
            specificity_points += 15.0
            all_vague = False
        elif "MODERATELY_SPECIFIC" in spec:
            specificity_points += 10.0
            all_vague = False
        else:
            specificity_points += 3.0
    avg_specificity = min(15.0, specificity_points / count)

    # Base raw score sum (0 to 100)
    raw_score = count_score + avg_directness + avg_corroboration + avg_specificity

    # Penalties
    unknowns_penalty = 15.0 if has_unknowns else 0.0
    disputed_penalty = 25.0 if (has_disputed_facts or any_contested) else 0.0

    # Granularity penalty: deeper controls (subcategory) demand higher standard
    granularity_penalty = 0.0
    if target_level == ControlLevel.SUBCATEGORY:
        if all_vague:
            granularity_penalty = 30.0
        elif avg_specificity < 12.0:
            granularity_penalty = 15.0
    elif target_level == ControlLevel.CATEGORY and all_vague:
        granularity_penalty = 15.0

    total_penalty = unknowns_penalty + disputed_penalty + granularity_penalty
    final_score = max(0.0, round(raw_score - total_penalty, 2))

    # Determine confidence level
    if any_refuted:
        level = GovernanceConfidence.INSUFFICIENT
        rationale_notes = "Evidence is refuted; confidence evaluated as INSUFFICIENT."
    elif has_disputed_facts or any_contested:
        # Cap confidence at MEDIUM if disputed
        if final_score >= 50.0:
            level = GovernanceConfidence.MEDIUM
            rationale_notes = "Disputed facts or contested corroboration cap confidence at MEDIUM."
        else:
            level = GovernanceConfidence.LOW
            rationale_notes = "Disputed evidence and lower base metrics result in LOW confidence."
    elif target_level == ControlLevel.SUBCATEGORY and (all_vague or avg_specificity < 10.0):
        level = GovernanceConfidence.LOW
        rationale_notes = "Subcategory mapping with low-specificity evidence restricted to LOW confidence."
    elif final_score >= 75.0:
        level = GovernanceConfidence.HIGH
        rationale_notes = "High-quality, corroborated evidence backing specific rule conditions."
    elif final_score >= 50.0:
        level = GovernanceConfidence.MEDIUM
        rationale_notes = "Moderate evidence backing with minor uncertainty or single-source verification."
    elif final_score >= 25.0:
        level = GovernanceConfidence.LOW
        rationale_notes = "Low evidentiary density or material unknowns present."
    else:
        level = GovernanceConfidence.INSUFFICIENT
        rationale_notes = "Evidentiary metrics fall below minimum confidence thresholds."

    full_rationale = (
        f"Score: {final_score:.1f}/100.0 [{level.value}]. Evidence count: {count}, "
        f"Directness: {avg_directness:.1f}, Corroboration: {avg_corroboration:.1f}, "
        f"Specificity: {avg_specificity:.1f}. {rationale_notes}"
    )

    return ConfidenceFactorBreakdown(
        score=final_score,
        level=level,
        evidence_count=count,
        directness_score=round(avg_directness, 2),
        corroboration_score=round(avg_corroboration, 2),
        specificity_score=round(avg_specificity, 2),
        unknowns_penalty=unknowns_penalty,
        disputed_penalty=disputed_penalty,
        granularity_penalty=granularity_penalty,
        rationale=full_rationale,
    )
