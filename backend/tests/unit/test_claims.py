"""Tests for ClaimRecord enforcing constitutional validation rules."""

from decimal import Decimal
from pydantic import ValidationError
import pytest

from ai_incident_monitor.domain.causality import CausalAssessment
from ai_incident_monitor.domain.claims import ClaimRecord
from ai_incident_monitor.domain.money import MonetaryAmount
from ai_incident_monitor.domain.vocabularies import (
    AssessmentLifecycleStatus,
    CausalAttributionStatus,
    ClaimMateriality,
    ClaimType,
    ConfidenceLevel,
    EpistemicStatus,
    MonetaryAmountStatus,
    ReviewStatus,
)


def test_valid_confirmed_fact_with_evidence():
    c = ClaimRecord(
        id="CLM-test-01",
        incident_id="INC-test-01",
        claim_text="The automated trading algorithm stalled during volatility spike.",
        claim_type=ClaimType.FACTUAL_EVENT,
        epistemic_status=EpistemicStatus.CONFIRMED_FACT,
        supporting_evidence_ids=["EVD-evidence-01"],
        confidence=ConfidenceLevel.VERY_HIGH,
        materiality=ClaimMateriality.CORE_IMPACT,
    )
    assert c.epistemic_status == EpistemicStatus.CONFIRMED_FACT


def test_confirmed_fact_without_evidence_rejected():
    # Constitutional Rule 4: Confirmed fact requires evidence
    with pytest.raises(ValidationError, match="must have at least one supporting evidence ID"):
        ClaimRecord(
            id="CLM-test-02",
            incident_id="INC-test-01",
            claim_text="Unverified claim marked as fact without proof.",
            claim_type=ClaimType.FACTUAL_EVENT,
            epistemic_status=EpistemicStatus.CONFIRMED_FACT,
            supporting_evidence_ids=[],  # Empty evidence
            confidence=ConfidenceLevel.HIGH,
            materiality=ClaimMateriality.CORE_IMPACT,
        )


def test_material_numeric_claim_without_evidence_rejected():
    # Constitutional Rule 5: Material numeric claim requires evidence
    with pytest.raises(ValidationError, match="requires at least one supporting evidence ID"):
        ClaimRecord(
            id="CLM-test-03",
            incident_id="INC-test-01",
            claim_text="The breach resulted in 5,000,000 USD in damages.",
            claim_type=ClaimType.NUMERIC_METRIC,
            epistemic_status=EpistemicStatus.TECHNICAL_ANALYSIS,
            supporting_evidence_ids=[],  # Empty evidence
            confidence=ConfidenceLevel.HIGH,
            materiality=ClaimMateriality.CORE_IMPACT,
            is_numeric_claim=True,
            numeric_amount=None,
        )


def test_material_numeric_claim_without_amount_record_rejected():
    # Constitutional Rule 5: Material numeric claim requires numeric_amount
    with pytest.raises(ValidationError, match="requires an attached MonetaryAmount record"):
        ClaimRecord(
            id="CLM-test-04",
            incident_id="INC-test-01",
            claim_text="The breach resulted in 5,000,000 USD in damages.",
            claim_type=ClaimType.NUMERIC_METRIC,
            epistemic_status=EpistemicStatus.CONFIRMED_FACT,
            supporting_evidence_ids=["EVD-123"],
            confidence=ConfidenceLevel.HIGH,
            materiality=ClaimMateriality.CORE_IMPACT,
            is_numeric_claim=True,
            numeric_amount=None,
        )


def test_causal_claim_without_causal_assessment_rejected():
    # Constitutional Rule 6: Causal claim requires CausalAssessment
    with pytest.raises(ValidationError, match="requires an attached CausalAssessment record"):
        ClaimRecord(
            id="CLM-test-05",
            incident_id="INC-test-01",
            claim_text="The model hallucination caused the incorrect medical prescription.",
            claim_type=ClaimType.CAUSAL_ASSERTION,
            epistemic_status=EpistemicStatus.TECHNICAL_ANALYSIS,
            supporting_evidence_ids=["EVD-123"],
            confidence=ConfidenceLevel.HIGH,
            materiality=ClaimMateriality.CORE_IMPACT,
            is_causal_claim=True,
            causal_assessment=None,  # Missing assessment
        )


def test_legal_claim_confirmed_without_human_approval_rejected():
    # Constitutional Rule 7: Legal claim cannot be confirmed by LLM alone
    with pytest.raises(ValidationError, match="cannot be marked CONFIRMED_FACT without explicit human review"):
        ClaimRecord(
            id="CLM-test-06",
            incident_id="INC-test-01",
            claim_text="The company violated Article 5 of the EU AI Act.",
            claim_type=ClaimType.LEGAL_COMPLIANCE,
            epistemic_status=EpistemicStatus.CONFIRMED_FACT,
            supporting_evidence_ids=["EVD-123"],
            confidence=ConfidenceLevel.HIGH,
            materiality=ClaimMateriality.CORE_IMPACT,
            is_legal_claim=True,
            review_status=ReviewStatus.DRAFT_UNREVIEWED,  # Not human approved
            human_review_id=None,
        )


def test_legal_claim_confirmed_with_human_approval_valid():
    c = ClaimRecord(
        id="CLM-test-07",
        incident_id="INC-test-01",
        claim_text="The court entered judgment finding statutory non-compliance.",
        claim_type=ClaimType.LEGAL_COMPLIANCE,
        epistemic_status=EpistemicStatus.CONFIRMED_FACT,
        supporting_evidence_ids=["EVD-123"],
        confidence=ConfidenceLevel.VERY_HIGH,
        materiality=ClaimMateriality.CORE_IMPACT,
        is_legal_claim=True,
        review_status=ReviewStatus.HUMAN_APPROVED,
        human_review_id="REV-auditor-01",
    )
    assert c.review_status == ReviewStatus.HUMAN_APPROVED


def test_superseded_claim_without_replacement_rejected():
    # Constitutional Rule 9: Superseded record must reference replacement
    with pytest.raises(ValidationError, match="must declare a valid 'superseded_by' reference"):
        ClaimRecord(
            id="CLM-test-08",
            incident_id="INC-test-01",
            claim_text="Superseded claim with no successor reference.",
            claim_type=ClaimType.FACTUAL_EVENT,
            epistemic_status=EpistemicStatus.UNVERIFIED_ALLEGATION,
            supporting_evidence_ids=["EVD-123"],
            confidence=ConfidenceLevel.LOW,
            materiality=ClaimMateriality.SECONDARY_CONTRIBUTOR,
            lifecycle_status=AssessmentLifecycleStatus.SUPERSEDED,
            superseded_by=None,
        )


def test_corrected_claim_without_previous_reference_rejected():
    # Constitutional Rule 10: Corrected record must reference previous version
    with pytest.raises(ValidationError, match="must declare a valid 'supersedes' reference"):
        ClaimRecord(
            id="CLM-test-09",
            incident_id="INC-test-01",
            claim_text="Corrected claim with no prior version reference.",
            claim_type=ClaimType.FACTUAL_EVENT,
            epistemic_status=EpistemicStatus.CONFIRMED_FACT,
            supporting_evidence_ids=["EVD-123"],
            confidence=ConfidenceLevel.HIGH,
            materiality=ClaimMateriality.SECONDARY_CONTRIBUTOR,
            lifecycle_status=AssessmentLifecycleStatus.CORRECTED,
            supersedes=None,
        )
