"""Review gatekeeper rules evaluating candidate mappings for mandatory human review routing.

Enforces Constitutional Rules 12 & 13:
- Automated algorithms cannot self-approve.
- Elevated scrutiny for sensitive domains, disputed evidence, low confidence, and granular controls.
"""

from __future__ import annotations

from typing import Any

from ai_incident_monitor.governance.enums import (
    ControlLevel,
    GovernanceConfidence,
    MappingStatus,
    SensitiveDomain,
)
from ai_incident_monitor.governance.models import ReviewGateEvaluation


class ReviewGateId:
    """Identifiers for governance review gates."""

    GATE_LOW_CONFIDENCE = "GOV_GATE_LOW_CONFIDENCE"
    GATE_DISPUTED_EVIDENCE = "GOV_GATE_DISPUTED_EVIDENCE"
    GATE_SPECIFIC_GRANULARITY = "GOV_GATE_SPECIFIC_GRANULARITY"
    GATE_SENSITIVE_DOMAIN = "GOV_GATE_SENSITIVE_DOMAIN"
    GATE_REVIEWER_EDIT = "GOV_GATE_REVIEWER_EDIT"
    GATE_INSUFFICIENT_EVIDENCE = "GOV_GATE_INSUFFICIENT_EVIDENCE"


def evaluate_review_gates(
    target_level: ControlLevel,
    confidence: GovernanceConfidence,
    has_disputed_facts: bool,
    sensitive_domains: list[SensitiveDomain],
    is_insufficient_evidence: bool = False,
    is_reviewer_edit: bool = False,
) -> ReviewGateEvaluation:
    """Evaluate whether a candidate mapping requires mandatory human review routing.

    Returns:
        ReviewGateEvaluation with status, triggered gates, and justification.
    """
    triggers: list[str] = []

    if is_insufficient_evidence or confidence == GovernanceConfidence.INSUFFICIENT:
        triggers.append(ReviewGateId.GATE_INSUFFICIENT_EVIDENCE)

    if confidence in {GovernanceConfidence.LOW, GovernanceConfidence.INSUFFICIENT}:
        triggers.append(ReviewGateId.GATE_LOW_CONFIDENCE)

    if has_disputed_facts:
        triggers.append(ReviewGateId.GATE_DISPUTED_EVIDENCE)

    # Category or subcategory level mappings require elevated scrutiny
    if target_level in {ControlLevel.CATEGORY, ControlLevel.SUBCATEGORY}:
        triggers.append(ReviewGateId.GATE_SPECIFIC_GRANULARITY)

    # Sensitive domain implications
    if sensitive_domains:
        triggers.append(ReviewGateId.GATE_SENSITIVE_DOMAIN)

    if is_reviewer_edit:
        triggers.append(ReviewGateId.GATE_REVIEWER_EDIT)

    if is_insufficient_evidence:
        return ReviewGateEvaluation(
            status=MappingStatus.INSUFFICIENT_EVIDENCE,
            gate_triggers=triggers,
            requires_human_review=True,
            reason="Insufficient evidence to substantiate positive governance relevance.",
        )

    if triggers:
        return ReviewGateEvaluation(
            status=MappingStatus.PENDING_REVIEW,
            gate_triggers=triggers,
            requires_human_review=True,
            reason=f"Mandatory human review gate triggered: {', '.join(triggers)}.",
        )

    return ReviewGateEvaluation(
        status=MappingStatus.CANDIDATE,
        gate_triggers=[],
        requires_human_review=False,
        reason="Candidate mapping satisfies baseline automated criteria; ready for review queue.",
    )
