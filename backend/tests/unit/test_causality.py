"""Tests for CausalAssessment and AIInvolvementAssessment."""

from pydantic import ValidationError
import pytest

from ai_incident_monitor.domain.causality import AIInvolvementAssessment, CausalAssessment
from ai_incident_monitor.domain.vocabularies import (
    AIComponentType,
    AIInvolvementStatus,
    CausalAttributionStatus,
)


def test_valid_causal_assessment():
    ca = CausalAssessment(
        attribution_status=CausalAttributionStatus.CONFIRMED_CAUSE,
        mechanism_description="Stochastic output fluctuation in vision model delayed emergency brake.",
        target_outcome="Autonomous ground collision with stationary obstacle.",
        supporting_evidence_ids=["EVD-evidence-01"],
    )
    assert ca.attribution_status == CausalAttributionStatus.CONFIRMED_CAUSE


def test_confirmed_cause_without_evidence_rejected():
    with pytest.raises(ValidationError, match="requires at least one supporting evidence ID"):
        CausalAssessment(
            attribution_status=CausalAttributionStatus.CONFIRMED_CAUSE,
            mechanism_description="Alleged causal mechanism without proof.",
            target_outcome="Failure outcome.",
            supporting_evidence_ids=[],
        )


def test_valid_ai_involvement_assessment():
    ai = AIInvolvementAssessment(
        involvement_status=AIInvolvementStatus.CONFIRMED_CAUSAL_CONTRIBUTION,
        component_implicated=AIComponentType.MODEL_WEIGHTS_OR_INFERENCE,
        supporting_evidence_ids=["EVD-evidence-01"],
        technical_rationale="Log files establish that vision model hallucinated an empty path.",
    )
    assert ai.involvement_status == AIInvolvementStatus.CONFIRMED_CAUSAL_CONTRIBUTION


def test_confirmed_ai_involvement_without_evidence_rejected():
    with pytest.raises(ValidationError, match="requires at least one supporting evidence ID"):
        AIInvolvementAssessment(
            involvement_status=AIInvolvementStatus.CONFIRMED_CAUSAL_CONTRIBUTION,
            component_implicated=AIComponentType.TRAINING_DATA_OR_FINE_TUNING,
            supporting_evidence_ids=[],
            technical_rationale="Unsubstantiated claim of training data defect.",
        )
