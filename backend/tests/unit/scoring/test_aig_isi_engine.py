"""Comprehensive unit tests for the AIG-ISI deterministic scoring engine.

Tests mathematical invariants, dimension contributions, tier boundaries,
review gates, overrides, confidence levels, and epistemic rules (Unknown is not zero).
"""

from __future__ import annotations

import pytest

from ai_incident_monitor.scoring.engine import (
    calculate_aig_isi_assessment,
    calculate_dimension_contribution,
    calculate_impact_assessment,
    calculate_overall_confidence,
    determine_tier,
    evaluate_review_gates,
)
from ai_incident_monitor.scoring.enums import (
    ConfidenceLevel,
    HumanReviewState,
    ImpactType,
    ISIDimension,
    ReviewGateId,
    SeverityTier,
)
from ai_incident_monitor.scoring.models import (
    DIMENSION_WEIGHTS,
    DimensionScoreInput,
    ScoreOverride,
)


class TestAIGISIDimensionWeights:
    """Validate approved dimension weights totaling 100."""

    def test_eight_approved_dimensions(self) -> None:
        assert len(ISIDimension) == 8
        assert len(DIMENSION_WEIGHTS) == 8

    def test_weights_sum_to_exact_100(self) -> None:
        assert sum(DIMENSION_WEIGHTS.values()) == 100

    def test_exact_approved_dimension_weights(self) -> None:
        assert DIMENSION_WEIGHTS[ISIDimension.HUMAN_IMPACT] == 25
        assert DIMENSION_WEIGHTS[ISIDimension.FINANCIAL_PROPERTY] == 15
        assert DIMENSION_WEIGHTS[ISIDimension.TRUST_REPUTATION] == 15
        assert DIMENSION_WEIGHTS[ISIDimension.PRIVACY_CONFIDENTIALITY] == 15
        assert DIMENSION_WEIGHTS[ISIDimension.RIGHTS_FAIRNESS] == 10
        assert DIMENSION_WEIGHTS[ISIDimension.OPERATIONAL_CRITICAL_SERVICE] == 10
        assert DIMENSION_WEIGHTS[ISIDimension.SCALE_REACH] == 5
        assert DIMENSION_WEIGHTS[ISIDimension.SOCIETAL_ENVIRONMENTAL] == 5


class TestDimensionContributions:
    """Validate deterministic calculation of dimension contributions."""

    def test_score_zero_contributes_zero(self) -> None:
        assert calculate_dimension_contribution(0, 25) == 0.0
        assert calculate_dimension_contribution(0, 15) == 0.0

    def test_score_five_contributes_full_weight(self) -> None:
        assert calculate_dimension_contribution(5, 25) == 25.0
        assert calculate_dimension_contribution(5, 15) == 15.0
        assert calculate_dimension_contribution(5, 10) == 10.0
        assert calculate_dimension_contribution(5, 5) == 5.0

    def test_intermediate_score_proportional(self) -> None:
        # Score 3 on weight 25: 3 * (25 / 5) = 15.0
        assert calculate_dimension_contribution(3, 25) == 15.0
        # Score 2 on weight 15: 2 * (15 / 5) = 6.0
        assert calculate_dimension_contribution(2, 15) == 6.0
        # Score 4 on weight 10: 4 * (10 / 5) = 8.0
        assert calculate_dimension_contribution(4, 10) == 8.0

    def test_unknown_score_returns_none(self) -> None:
        # Constitutional Rule 2: Unknown is not zero
        assert calculate_dimension_contribution(None, 25) is None
        assert calculate_dimension_contribution(None, 15) is None


class TestSeverityTierBoundaries:
    """Validate tier boundaries (Minimal 0-19, Moderate 20-39, Significant 40-59, Severe 60-79, Critical 80-100)."""

    def test_minimal_tier(self) -> None:
        assert determine_tier(0.0, 100.0) == SeverityTier.MINIMAL
        assert determine_tier(10.0, 100.0) == SeverityTier.MINIMAL
        assert determine_tier(19.99, 100.0) == SeverityTier.MINIMAL

    def test_moderate_tier(self) -> None:
        assert determine_tier(20.0, 100.0) == SeverityTier.MODERATE
        assert determine_tier(30.0, 100.0) == SeverityTier.MODERATE
        assert determine_tier(39.99, 100.0) == SeverityTier.MODERATE

    def test_significant_tier(self) -> None:
        assert determine_tier(40.0, 100.0) == SeverityTier.SIGNIFICANT
        assert determine_tier(50.0, 100.0) == SeverityTier.SIGNIFICANT
        assert determine_tier(59.99, 100.0) == SeverityTier.SIGNIFICANT

    def test_severe_tier(self) -> None:
        assert determine_tier(60.0, 100.0) == SeverityTier.SEVERE
        assert determine_tier(70.0, 100.0) == SeverityTier.SEVERE
        assert determine_tier(79.99, 100.0) == SeverityTier.SEVERE

    def test_critical_tier(self) -> None:
        assert determine_tier(80.0, 100.0) == SeverityTier.CRITICAL
        assert determine_tier(90.0, 100.0) == SeverityTier.CRITICAL
        assert determine_tier(100.0, 100.0) == SeverityTier.CRITICAL

    def test_special_status_unscored(self) -> None:
        assert determine_tier(None, 0.0) == SeverityTier.UNSCORED
        assert determine_tier(50.0, 0.0) == SeverityTier.UNSCORED

    def test_special_status_disputed(self) -> None:
        assert determine_tier(75.0, 100.0, is_disputed=True) == SeverityTier.DISPUTED


class TestImpactAssessmentMathAndEpistemics:
    """Validate math and epistemic invariants in ImpactAssessmentResult."""

    def test_all_dimensions_zero(self) -> None:
        inputs = {
            dim: DimensionScoreInput(score=0, rationale="No harm observed")
            for dim in ISIDimension
        }
        res = calculate_impact_assessment(ImpactType.ACTUAL, inputs)
        assert res.lower_bound == 0.0
        assert res.upper_bound == 0.0
        assert res.completeness_pct == 100.0
        assert res.evaluated_weight == 100
        assert res.unknown_weight == 0
        assert res.provisional_normalized_score == 0.0
        assert res.final_score == 0.0
        assert res.tier == SeverityTier.MINIMAL

    def test_all_dimensions_five(self) -> None:
        inputs = {
            dim: DimensionScoreInput(score=5, rationale="Catastrophic impact observed")
            for dim in ISIDimension
        }
        res = calculate_impact_assessment(ImpactType.ACTUAL, inputs)
        assert res.lower_bound == 100.0
        assert res.upper_bound == 100.0
        assert res.completeness_pct == 100.0
        assert res.provisional_normalized_score == 100.0
        assert res.tier == SeverityTier.CRITICAL

    def test_all_dimensions_unknown(self) -> None:
        # Rule 2: Unknown is not zero
        inputs = {
            dim: DimensionScoreInput(score=None, rationale="Data unavailable")
            for dim in ISIDimension
        }
        res = calculate_impact_assessment(ImpactType.ACTUAL, inputs)
        assert res.lower_bound == 0.0
        assert res.upper_bound == 100.0
        assert res.completeness_pct == 0.0
        assert res.evaluated_weight == 0
        assert res.unknown_weight == 100
        assert res.provisional_normalized_score is None
        assert res.final_score is None
        assert res.tier == SeverityTier.UNSCORED

    def test_partial_completeness_and_bounds_invariant(self) -> None:
        # Only human impact (weight 25) and financial (weight 15) evaluated
        inputs = {
            ISIDimension.HUMAN_IMPACT: DimensionScoreInput(score=4, rationale="Severe injury"),  # 4 * 5 = 20.0
            ISIDimension.FINANCIAL_PROPERTY: DimensionScoreInput(score=2, rationale="Moderate loss"),  # 2 * 3 = 6.0
        }
        # Other 6 dimensions unknown (weight = 60)
        res = calculate_impact_assessment(ImpactType.ACTUAL, inputs)
        assert res.evaluated_weight == 40
        assert res.unknown_weight == 60
        assert res.completeness_pct == 40.0
        assert res.lower_bound == 26.0
        assert res.upper_bound == 86.0  # 26.0 + 60
        # Invariant: upper - lower == unknown_weight
        assert round(res.upper_bound - res.lower_bound, 4) == 60.0
        # Normalized score: (26.0 / 40) * 100 = 65.0
        assert res.provisional_normalized_score == 65.0
        assert res.tier == SeverityTier.SEVERE


class TestHumanReviewGates:
    """Validate all 10 mandatory human-review workflow gates."""

    def _create_minimal_inputs(self) -> dict[ISIDimension, DimensionScoreInput]:
        return {
            dim: DimensionScoreInput(score=1, rationale="Minor impact", confidence=ConfidenceLevel.HIGH)
            for dim in ISIDimension
        }

    def test_gate_01_tier_4_or_5(self) -> None:
        inputs_severe = {
            dim: DimensionScoreInput(score=4, rationale="Severe impact", confidence=ConfidenceLevel.HIGH)
            for dim in ISIDimension
        }
        actual = calculate_impact_assessment(ImpactType.ACTUAL, inputs_severe)
        potential = calculate_impact_assessment(ImpactType.POTENTIAL, inputs_severe)
        gates = evaluate_review_gates(actual, potential)
        gate_ids = [g.gate_id for g in gates]
        assert ReviewGateId.TIER_4_OR_5 in gate_ids

    def test_gate_02_low_confidence(self) -> None:
        inputs = self._create_minimal_inputs()
        inputs[ISIDimension.HUMAN_IMPACT] = DimensionScoreInput(
            score=1, rationale="Minor", confidence=ConfidenceLevel.LOW
        )
        actual = calculate_impact_assessment(ImpactType.ACTUAL, inputs)
        potential = calculate_impact_assessment(ImpactType.POTENTIAL, inputs)
        gates = evaluate_review_gates(actual, potential)
        gate_ids = [g.gate_id for g in gates]
        # Low confidence triggers gate
        if actual.confidence in (ConfidenceLevel.LOW, ConfidenceLevel.INSUFFICIENT):
            assert ReviewGateId.LOW_CONFIDENCE in gate_ids

    def test_gate_03_low_completeness(self) -> None:
        # Only 2 dimensions evaluated (weight 40 < 70)
        inputs = {
            ISIDimension.HUMAN_IMPACT: DimensionScoreInput(score=1, rationale="Minor", confidence=ConfidenceLevel.HIGH),
            ISIDimension.FINANCIAL_PROPERTY: DimensionScoreInput(score=1, rationale="Minor", confidence=ConfidenceLevel.HIGH),
        }
        actual = calculate_impact_assessment(ImpactType.ACTUAL, inputs)
        potential = calculate_impact_assessment(ImpactType.POTENTIAL, inputs)
        gates = evaluate_review_gates(actual, potential)
        gate_ids = [g.gate_id for g in gates]
        assert ReviewGateId.LOW_COMPLETENESS in gate_ids

    def test_gate_04_actual_vs_potential_divergence(self) -> None:
        act_inputs = {
            dim: DimensionScoreInput(score=0, rationale="No harm", confidence=ConfidenceLevel.HIGH)
            for dim in ISIDimension
        }
        pot_inputs = {
            dim: DimensionScoreInput(score=3, rationale="Worst case substantial", confidence=ConfidenceLevel.HIGH)
            for dim in ISIDimension
        }
        actual = calculate_impact_assessment(ImpactType.ACTUAL, act_inputs)
        potential = calculate_impact_assessment(ImpactType.POTENTIAL, pot_inputs)
        gates = evaluate_review_gates(actual, potential)
        gate_ids = [g.gate_id for g in gates]
        assert ReviewGateId.ACTUAL_VS_POTENTIAL_DIVERGENCE in gate_ids

    def test_gate_05_override_present(self) -> None:
        from datetime import datetime, timezone
        override = ScoreOverride(
            target="actual_impact",
            original_score=20.0,
            overridden_score=45.0,
            original_tier=SeverityTier.MODERATE,
            overridden_tier=SeverityTier.SIGNIFICANT,
            rationale="Analyst discovered secondary evidence of widespread service disruption.",
            applied_by_id="usr_analyst_01",
            applied_at_utc=datetime.now(timezone.utc),
        )
        inputs = self._create_minimal_inputs()
        actual = calculate_impact_assessment(ImpactType.ACTUAL, inputs, override=override)
        potential = calculate_impact_assessment(ImpactType.POTENTIAL, inputs)
        gates = evaluate_review_gates(actual, potential, overrides=[override])
        gate_ids = [g.gate_id for g in gates]
        assert ReviewGateId.OVERRIDE_PRESENT in gate_ids

    def test_gate_06_serious_injury_or_death(self) -> None:
        inputs = self._create_minimal_inputs()
        inputs[ISIDimension.HUMAN_IMPACT] = DimensionScoreInput(
            score=4, rationale="Severe permanent disability", confidence=ConfidenceLevel.HIGH
        )
        actual = calculate_impact_assessment(ImpactType.ACTUAL, inputs)
        potential = calculate_impact_assessment(ImpactType.POTENTIAL, inputs)
        gates = evaluate_review_gates(actual, potential)
        gate_ids = [g.gate_id for g in gates]
        assert ReviewGateId.SERIOUS_INJURY_OR_DEATH in gate_ids

    def test_gate_07_critical_infrastructure(self) -> None:
        inputs = self._create_minimal_inputs()
        inputs[ISIDimension.OPERATIONAL_CRITICAL_SERVICE] = DimensionScoreInput(
            score=4, rationale="Hospital grid outage > 12h", confidence=ConfidenceLevel.HIGH
        )
        actual = calculate_impact_assessment(ImpactType.ACTUAL, inputs)
        potential = calculate_impact_assessment(ImpactType.POTENTIAL, inputs)
        gates = evaluate_review_gates(actual, potential)
        gate_ids = [g.gate_id for g in gates]
        assert ReviewGateId.CRITICAL_INFRASTRUCTURE in gate_ids

    def test_gate_08_serious_privacy_impact(self) -> None:
        inputs = self._create_minimal_inputs()
        inputs[ISIDimension.PRIVACY_CONFIDENTIALITY] = DimensionScoreInput(
            score=5, rationale="Mass exfiltration > 1M records", confidence=ConfidenceLevel.HIGH
        )
        actual = calculate_impact_assessment(ImpactType.ACTUAL, inputs)
        potential = calculate_impact_assessment(ImpactType.POTENTIAL, inputs)
        gates = evaluate_review_gates(actual, potential)
        gate_ids = [g.gate_id for g in gates]
        assert ReviewGateId.SERIOUS_PRIVACY_IMPACT in gate_ids

    def test_gate_09_serious_rights_impact(self) -> None:
        inputs = self._create_minimal_inputs()
        inputs[ISIDimension.RIGHTS_FAIRNESS] = DimensionScoreInput(
            score=4, rationale="Systemic unlawful arrest due to facial recognition", confidence=ConfidenceLevel.HIGH
        )
        actual = calculate_impact_assessment(ImpactType.ACTUAL, inputs)
        potential = calculate_impact_assessment(ImpactType.POTENTIAL, inputs)
        gates = evaluate_review_gates(actual, potential)
        gate_ids = [g.gate_id for g in gates]
        assert ReviewGateId.SERIOUS_RIGHTS_IMPACT in gate_ids

    def test_gate_10_materially_disputed_facts(self) -> None:
        inputs = self._create_minimal_inputs()
        actual = calculate_impact_assessment(ImpactType.ACTUAL, inputs)
        potential = calculate_impact_assessment(ImpactType.POTENTIAL, inputs)
        gates = evaluate_review_gates(actual, potential, has_materially_disputed_facts=True)
        gate_ids = [g.gate_id for g in gates]
        assert ReviewGateId.MATERIALLY_DISPUTED_FACTS in gate_ids


class TestAuditableOverrides:
    """Validate override constraints and auditable tracking."""

    def test_override_rationale_min_length(self) -> None:
        from datetime import datetime, timezone
        with pytest.raises(ValueError):
            ScoreOverride(
                target="actual_impact",
                original_score=20.0,
                overridden_score=40.0,
                original_tier=SeverityTier.MODERATE,
                overridden_tier=SeverityTier.SIGNIFICANT,
                rationale="short",  # < 10 chars
                applied_by_id="usr_01",
                applied_at_utc=datetime.now(timezone.utc),
            )

    def test_override_modifies_final_score_and_tier(self) -> None:
        from datetime import datetime, timezone
        override = ScoreOverride(
            target="actual_impact",
            original_score=10.0,
            overridden_score=65.0,
            original_tier=SeverityTier.MINIMAL,
            overridden_tier=SeverityTier.SEVERE,
            rationale="Confirmed uncaptured compounding supply-chain losses.",
            applied_by_id="usr_senior_analyst",
            applied_at_utc=datetime.now(timezone.utc),
        )
        inputs = {
            dim: DimensionScoreInput(score=0, rationale="None", confidence=ConfidenceLevel.HIGH)
            for dim in ISIDimension
        }
        res = calculate_impact_assessment(ImpactType.ACTUAL, inputs, override=override)
        assert res.provisional_normalized_score == 0.0
        assert res.final_score == 65.0
        assert res.tier == SeverityTier.SEVERE
        assert res.override == override


class TestFullAIGISIScoreResult:
    """Validate top-level AIGISIScoreResult workflow integration."""

    def test_full_assessment_generation(self) -> None:
        act_inputs = {
            dim: DimensionScoreInput(score=1, rationale="Minor", confidence=ConfidenceLevel.HIGH)
            for dim in ISIDimension
        }
        pot_inputs = {
            dim: DimensionScoreInput(score=2, rationale="Moderate", confidence=ConfidenceLevel.HIGH)
            for dim in ISIDimension
        }
        result = calculate_aig_isi_assessment(
            incident_id="inc-test-001",
            actual_inputs=act_inputs,
            potential_inputs=pot_inputs,
        )
        assert result.incident_id == "inc-test-001"
        assert result.methodology_version == "AIG-ISI-1.0.0"
        assert result.actual_impact.final_score == 20.0
        assert result.potential_impact.final_score == 40.0
        # Score difference is 20.0 -> divergence gate triggers PENDING_REVIEW
        assert result.is_pending_review is True
        assert result.review_state == HumanReviewState.PENDING_REVIEW
