"""Calibration benchmark tests verifying mathematical repeatability against canonical archetypes.

Directly tests the cases specified in docs/AIG_ISI_CALIBRATION.md:
- Case 1: Trivial Output Glitch (Tier 1 Minimal)
- Case 2: Regional E-Commerce Outage (Tier 2 Moderate)
- Case 3: Algorithmic Tenant Screening Disparate Impact (Tier 3 Significant)
- Case 4: Deepfake Bank Wire Fraud (Tier 4 Severe)
- Case 5: Autonomous Clinical Triage Failure (Tier 5 Critical)
- Case 6: Unconfirmed Single-Source Whistleblower Report (Incomplete / Low Confidence)
"""

from __future__ import annotations

import pytest

from ai_incident_monitor.scoring.engine import (
    calculate_aig_isi_assessment,
    calculate_impact_assessment,
)
from ai_incident_monitor.scoring.enums import (
    ConfidenceLevel,
    ImpactType,
    ISIDimension,
    ReviewGateId,
    SeverityTier,
)
from ai_incident_monitor.scoring.models import DimensionScoreInput


class TestCalibrationBenchmarks:
    """Mathematical validation of the 6 canonical calibration profiles."""

    def test_case_01_trivial_output_glitch_minimal(self) -> None:
        """Case 1: Glitch with instant failover, score 2.0 (Tier 1 Minimal)."""
        inputs = {
            ISIDimension.HUMAN_IMPACT: DimensionScoreInput(score=0, rationale="No injury"),
            ISIDimension.FINANCIAL_PROPERTY: DimensionScoreInput(score=0, rationale="Zero loss"),
            ISIDimension.TRUST_REPUTATION: DimensionScoreInput(score=0, rationale="No fallout"),
            ISIDimension.PRIVACY_CONFIDENTIALITY: DimensionScoreInput(score=0, rationale="Zero data leak"),
            ISIDimension.RIGHTS_FAIRNESS: DimensionScoreInput(score=0, rationale="No bias"),
            ISIDimension.OPERATIONAL_CRITICAL_SERVICE: DimensionScoreInput(score=1, rationale="Glitch with redundant failover"),
            ISIDimension.SCALE_REACH: DimensionScoreInput(score=0, rationale="Internal test harness"),
            ISIDimension.SOCIETAL_ENVIRONMENTAL: DimensionScoreInput(score=0, rationale="No societal harm"),
        }
        res = calculate_impact_assessment(ImpactType.ACTUAL, inputs)
        assert res.lower_bound == 2.0
        assert res.upper_bound == 2.0
        assert res.completeness_pct == 100.0
        assert res.provisional_normalized_score == 2.0
        assert res.final_score == 2.0
        assert res.tier == SeverityTier.MINIMAL

    def test_case_02_regional_ecommerce_outage_moderate(self) -> None:
        """Case 2: E-commerce crash, $45k loss, score 18.0 (Tier 1/2 borderline)."""
        inputs = {
            ISIDimension.HUMAN_IMPACT: DimensionScoreInput(score=0, rationale="No physical harm"),
            ISIDimension.FINANCIAL_PROPERTY: DimensionScoreInput(score=2, rationale="$45,000 lost revenue"),
            ISIDimension.TRUST_REPUTATION: DimensionScoreInput(score=2, rationale="Merchant complaints, regional press"),
            ISIDimension.PRIVACY_CONFIDENTIALITY: DimensionScoreInput(score=0, rationale="No breach"),
            ISIDimension.RIGHTS_FAIRNESS: DimensionScoreInput(score=0, rationale="No bias"),
            ISIDimension.OPERATIONAL_CRITICAL_SERVICE: DimensionScoreInput(score=2, rationale="Outage < 1 hour"),
            ISIDimension.SCALE_REACH: DimensionScoreInput(score=2, rationale="Regional customers"),
            ISIDimension.SOCIETAL_ENVIRONMENTAL: DimensionScoreInput(score=0, rationale="No societal harm"),
        }
        res = calculate_impact_assessment(ImpactType.ACTUAL, inputs)
        # 2*(15/5) + 2*(15/5) + 2*(10/5) + 2*(5/5) = 6 + 6 + 4 + 2 = 18.0
        assert res.lower_bound == 18.0
        assert res.upper_bound == 18.0
        assert res.provisional_normalized_score == 18.0
        assert res.tier == SeverityTier.MINIMAL

    def test_case_03_algorithmic_tenant_screening_significant(self) -> None:
        """Case 3: Automated eviction flags against 12k applicants, score 39.0."""
        inputs = {
            ISIDimension.HUMAN_IMPACT: DimensionScoreInput(score=2, rationale="Moderate psychological distress"),  # 2 * 5 = 10
            ISIDimension.FINANCIAL_PROPERTY: DimensionScoreInput(score=2, rationale="Application fees and temporary lodging"),  # 2 * 3 = 6
            ISIDimension.TRUST_REPUTATION: DimensionScoreInput(score=3, rationale="National press, civil rights inquiry"),  # 3 * 3 = 9
            ISIDimension.PRIVACY_CONFIDENTIALITY: DimensionScoreInput(score=1, rationale="Inadvertent exposure of applicant status"),  # 1 * 3 = 3
            ISIDimension.RIGHTS_FAIRNESS: DimensionScoreInput(score=3, rationale="Systemic denial of housing access"),  # 3 * 2 = 6
            ISIDimension.OPERATIONAL_CRITICAL_SERVICE: DimensionScoreInput(score=0, rationale="No critical infrastructure outage"),  # 0
            ISIDimension.SCALE_REACH: DimensionScoreInput(score=3, rationale="Multi-state, 12,000 individuals"),  # 3 * 1 = 3
            ISIDimension.SOCIETAL_ENVIRONMENTAL: DimensionScoreInput(score=2, rationale="National discourse on algorithmic bias"),  # 2 * 1 = 2
        }
        res = calculate_impact_assessment(ImpactType.ACTUAL, inputs)
        # 10 + 6 + 9 + 3 + 6 + 0 + 3 + 2 = 39.0
        assert res.lower_bound == 39.0
        assert res.provisional_normalized_score == 39.0
        assert res.tier == SeverityTier.MODERATE

    def test_case_04_deepfake_wire_fraud_severe(self) -> None:
        """Case 4: Voice clone $25M heist, score 50.0 (Significant tier with severe financial)."""
        inputs = {
            ISIDimension.HUMAN_IMPACT: DimensionScoreInput(score=1, rationale="Emotional distress of staff"),  # 1 * 5 = 5
            ISIDimension.FINANCIAL_PROPERTY: DimensionScoreInput(score=5, rationale="$25M stolen via shell accounts"),  # 5 * 3 = 15
            ISIDimension.TRUST_REPUTATION: DimensionScoreInput(score=4, rationale="Executive crisis, stock plunge"),  # 4 * 3 = 12
            ISIDimension.PRIVACY_CONFIDENTIALITY: DimensionScoreInput(score=3, rationale="Internal executive communications exfiltrated"),  # 3 * 3 = 9
            ISIDimension.RIGHTS_FAIRNESS: DimensionScoreInput(score=0, rationale="No civil rights violation"),  # 0
            ISIDimension.OPERATIONAL_CRITICAL_SERVICE: DimensionScoreInput(score=2, rationale="Freeze on financial operations"),  # 2 * 2 = 4
            ISIDimension.SCALE_REACH: DimensionScoreInput(score=3, rationale="International supplier network"),  # 3 * 1 = 3
            ISIDimension.SOCIETAL_ENVIRONMENTAL: DimensionScoreInput(score=2, rationale="Erosion of voice authentication trust"),  # 2 * 1 = 2
        }
        res = calculate_impact_assessment(ImpactType.ACTUAL, inputs)
        # 5 + 15 + 12 + 9 + 0 + 4 + 3 + 2 = 50.0
        assert res.lower_bound == 50.0
        assert res.provisional_normalized_score == 50.0
        assert res.tier == SeverityTier.SIGNIFICANT

    def test_case_05_autonomous_clinical_triage_critical(self) -> None:
        """Case 5: Hospital agent routing bug, fatalities, score 80.0 (Tier 5 Critical)."""
        inputs = {
            ISIDimension.HUMAN_IMPACT: DimensionScoreInput(score=5, rationale="4 fatalities, 11 permanent injuries"),  # 5 * 5 = 25
            ISIDimension.FINANCIAL_PROPERTY: DimensionScoreInput(score=3, rationale="Hospital remediation > $500k"),  # 3 * 3 = 9
            ISIDimension.TRUST_REPUTATION: DimensionScoreInput(score=5, rationale="Total collapse of hospital trust"),  # 5 * 3 = 15
            ISIDimension.PRIVACY_CONFIDENTIALITY: DimensionScoreInput(score=2, rationale="Accidental disclosure of triage tickets"),  # 2 * 3 = 6
            ISIDimension.RIGHTS_FAIRNESS: DimensionScoreInput(score=4, rationale="Systemic denial of emergency healthcare"),  # 4 * 2 = 8
            ISIDimension.OPERATIONAL_CRITICAL_SERVICE: DimensionScoreInput(score=5, rationale="Prolonged emergency network collapse"),  # 5 * 2 = 10
            ISIDimension.SCALE_REACH: DimensionScoreInput(score=3, rationale="Multi-hospital regional network"),  # 3 * 1 = 3
            ISIDimension.SOCIETAL_ENVIRONMENTAL: DimensionScoreInput(score=4, rationale="Severe public panic in healthcare automation"),  # 4 * 1 = 4
        }
        actual = calculate_impact_assessment(ImpactType.ACTUAL, inputs)
        # 25 + 9 + 15 + 6 + 8 + 10 + 3 + 4 = 80.0
        assert actual.lower_bound == 80.0
        assert actual.provisional_normalized_score == 80.0
        assert actual.tier == SeverityTier.CRITICAL

        # Also verify review gates triggered in full assessment
        result = calculate_aig_isi_assessment("inc-case-05", inputs, inputs)
        assert result.is_pending_review is True
        gate_ids = [g.gate_id for g in result.review_gates]
        assert ReviewGateId.TIER_4_OR_5 in gate_ids
        assert ReviewGateId.SERIOUS_INJURY_OR_DEATH in gate_ids
        assert ReviewGateId.CRITICAL_INFRASTRUCTURE in gate_ids
        assert ReviewGateId.SERIOUS_RIGHTS_IMPACT in gate_ids

    def test_case_06_unconfirmed_whistleblower_report(self) -> None:
        """Case 6: Incomplete whistleblower report, completeness 55%, bounds [28.0, 73.0]."""
        inputs = {
            ISIDimension.HUMAN_IMPACT: DimensionScoreInput(score=3, rationale="Allegation of military injury"),  # 3 * 5 = 15
            ISIDimension.FINANCIAL_PROPERTY: DimensionScoreInput(score=None, rationale="Unknown"),
            ISIDimension.TRUST_REPUTATION: DimensionScoreInput(score=2, rationale="Internal discontent"),  # 2 * 3 = 6
            ISIDimension.PRIVACY_CONFIDENTIALITY: DimensionScoreInput(score=None, rationale="Unknown"),
            ISIDimension.RIGHTS_FAIRNESS: DimensionScoreInput(score=None, rationale="Unknown"),
            ISIDimension.OPERATIONAL_CRITICAL_SERVICE: DimensionScoreInput(score=3, rationale="Significant operational disruption"),  # 3 * 2 = 6
            ISIDimension.SCALE_REACH: DimensionScoreInput(score=1, rationale="Single test site"),  # 1 * 1 = 1
            ISIDimension.SOCIETAL_ENVIRONMENTAL: DimensionScoreInput(score=None, rationale="Unknown"),
        }
        res = calculate_impact_assessment(ImpactType.ACTUAL, inputs)
        # Evaluated: 25 + 15 + 10 + 5 = 55. Unknown: 15 + 15 + 10 + 5 = 45.
        assert res.evaluated_weight == 55
        assert res.unknown_weight == 45
        assert res.completeness_pct == 55.0
        # Lower bound: 15 + 6 + 6 + 1 = 28.0
        assert res.lower_bound == 28.0
        # Upper bound: 28.0 + 45.0 = 73.0
        assert res.upper_bound == 73.0
        # Normalized score: (28.0 / 55.0) * 100 = 50.91
        assert res.provisional_normalized_score == 50.91
        assert res.tier == SeverityTier.SIGNIFICANT
