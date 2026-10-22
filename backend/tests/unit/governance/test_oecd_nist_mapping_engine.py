"""Unit tests verifying the deterministic OECD and NIST AI RMF governance mapping engine.

Covers:
- Reference integrity & anti-fabrication enforcement
- Evidence linkage & provenance
- Granularity & specificity gates (NIST subcategory requirements)
- Independent multi-factor confidence scoring & penalties
- Review state machine routing (sensitive domains, disputed facts, low confidence)
- OECD Principles 1.1-1.5 coverage & determinism
- NIST AI RMF Functions, Categories, Subcategories & multi-function independence
- Strict separation from AIG-ISI severity and exclusion of legal conclusion language
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any
import pytest

from ai_incident_monitor.domain.common import ConstitutionalViolationError
from ai_incident_monitor.governance.confidence import calculate_mapping_confidence
from ai_incident_monitor.governance.engine import GovernanceMappingEngine
from ai_incident_monitor.governance.enums import (
    ControlLevel,
    FrameworkCode,
    FrameworkStatus,
    GovernanceConfidence,
    MappingStatus,
    NISTApplicability,
    OECDApplicability,
    SensitiveDomain,
)
from ai_incident_monitor.governance.models import (
    ConfidenceFactorBreakdown,
    FrameworkControlSchema,
    FrameworkReferenceSetSchema,
    IncidentFactContext,
    MappingCandidate,
    MappingRuleMetadata,
    ReviewGateEvaluation,
    validate_no_legal_language,
)
from ai_incident_monitor.governance.reference_loader import load_reference_set
from ai_incident_monitor.governance.review_gates import ReviewGateId, evaluate_review_gates
from ai_incident_monitor.governance.rules.nist_rules import (
    ALL_NIST_RULES,
    BaseNISTRule,
    NISTGovern11SubcategoryRule,
    NISTGovernFunctionRule,
    NISTManageFunctionRule,
    NISTMapFunctionRule,
    NISTMeasure21SubcategoryRule,
    NISTMeasureFunctionRule,
)
from ai_incident_monitor.governance.rules.oecd_rules import (
    ALL_OECD_RULES,
    BaseOECDRule,
    OECDAccountabilityRule,
    OECDFairnessPrivacyRule,
    OECDInclusiveGrowthRule,
    OECDRobustnessSecuritySafetyRule,
    OECDTransparencyExplainabilityRule,
)


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


@pytest.fixture
def oecd_ref_set(repo_root: Path) -> FrameworkReferenceSetSchema:
    return load_reference_set(repo_root / "frameworks" / "oecd" / "oecd-principles-2024.yaml")


@pytest.fixture
def nist_ref_set(repo_root: Path) -> FrameworkReferenceSetSchema:
    return load_reference_set(repo_root / "frameworks" / "nist" / "nist-ai-rmf-1.0.yaml")


@pytest.fixture
def engine(
    oecd_ref_set: FrameworkReferenceSetSchema,
    nist_ref_set: FrameworkReferenceSetSchema,
) -> GovernanceMappingEngine:
    return GovernanceMappingEngine(
        reference_sets={
            FrameworkCode.OECD_AI_PRINCIPLES: oecd_ref_set,
            FrameworkCode.NIST_AI_RMF: nist_ref_set,
        }
    )


@pytest.fixture
def base_context() -> IncidentFactContext:
    return IncidentFactContext(
        incident_id="INC-2026-TEST-001",
        title="Automated Test Incident",
        summary="A test incident summary for deterministic governance mapping.",
        evidence_records=[
            {
                "id": "EV-001",
                "directness": "PRIMARY_DIRECT",
                "corroboration_status": "FULLY_CORROBORATED",
                "specificity": "HIGHLY_SPECIFIC",
                "content": "Detailed audit log documenting model bias and control gap.",
            },
            {
                "id": "EV-002",
                "directness": "PRIMARY_DIRECT",
                "corroboration_status": "PARTIALLY_CORROBORATED",
                "specificity": "MODERATELY_SPECIFIC",
                "content": "Technical report on algorithmic impact.",
            },
        ],
        known_facts=["Algorithmic output showed demographic disparity across user cohorts."],
        unknowns=["Whether third-party training data was audited prior to deployment."],
        disputed_facts=[],
        sensitive_domains=[],
        fact_tags=["differential_impact", "bias_or_discrimination"],
        system_context={"aig_isi_score": 42.5},
    )


class TestReferenceIntegrityAndAntiFabrication:
    """Verifies that the engine rejects non-existent, malformed, or fabricated framework IDs."""

    def test_engine_rejects_unknown_oecd_target_identifier_in_rule(
        self,
        engine: GovernanceMappingEngine,
        base_context: IncidentFactContext,
    ) -> None:
        class FabricatedOECDRule(BaseOECDRule):
            @property
            def metadata(self) -> MappingRuleMetadata:
                return MappingRuleMetadata(
                    rule_id="RULE-FAKE-01",
                    rule_version="1.0.0",
                    framework_code=FrameworkCode.OECD_AI_PRINCIPLES,
                    target_identifier="OECD-P9.9-FABRICATED",
                    target_level=ControlLevel.PRINCIPLE,
                    title="Fabricated OECD Rule",
                    description="Fabricated description",
                    applicability=OECDApplicability.DIRECTLY_IMPLICATED.value,
                )

            def evaluate(self, context: IncidentFactContext) -> Any:
                return (
                    OECDApplicability.DIRECTLY_IMPLICATED,
                    "Rationale",
                    ["Known fact"],
                    [],
                    [],
                    None,
                )

        engine_with_fake = GovernanceMappingEngine(
            reference_sets=engine.reference_sets,
            oecd_rules=(FabricatedOECDRule(),),
        )

        with pytest.raises(ConstitutionalViolationError, match="Safety Rule 2: Target OECD identifier"):
            engine_with_fake.map_incident(base_context)

    def test_engine_rejects_unknown_nist_target_identifier_in_rule(
        self,
        engine: GovernanceMappingEngine,
        base_context: IncidentFactContext,
    ) -> None:
        class FabricatedNISTRule(BaseNISTRule):
            @property
            def metadata(self) -> MappingRuleMetadata:
                return MappingRuleMetadata(
                    rule_id="RULE-FAKE-NIST",
                    rule_version="1.0.0",
                    framework_code=FrameworkCode.NIST_AI_RMF,
                    target_identifier="NIST-FLYAWAY-1.0",
                    target_level=ControlLevel.FUNCTION,
                    title="Fabricated NIST Function",
                    description="Fabricated NIST function description",
                    applicability=NISTApplicability.OBSERVED_CONTROL_GAP.value,
                )

            def evaluate(self, context: IncidentFactContext) -> Any:
                return (
                    NISTApplicability.OBSERVED_CONTROL_GAP,
                    "Rationale",
                    ["Known fact"],
                    [],
                    [],
                    None,
                )

        engine_with_fake = GovernanceMappingEngine(
            reference_sets=engine.reference_sets,
            nist_rules=(FabricatedNISTRule(),),
        )

        with pytest.raises(ConstitutionalViolationError, match="Safety Rule 2: Target NIST identifier"):
            engine_with_fake.map_incident(base_context)

    def test_mapping_candidate_schema_validates_nist_hierarchy(self) -> None:
        """Pydantic model validator rejects subcategory without parent category/function."""
        with pytest.raises(ValueError, match="must store parent_category_identifier"):
            MappingCandidate(
                incident_id="INC-001",
                framework_code=FrameworkCode.NIST_AI_RMF,
                reference_set_id="ref_001",
                reference_set_version="1.0.0",
                target_identifier="NIST-GOVERN-1.1",
                mapping_level=ControlLevel.SUBCATEGORY,
                applicability="OBSERVED_CONTROL_GAP",
                confidence=GovernanceConfidence.HIGH,
                rule_id="RULE-01",
                rule_version="1.0.0",
                rationale="Valid observational rationale.",
                evidence_ids=["EV-001"],
                parent_category_identifier=None,  # Missing!
                parent_function_identifier="NIST-GOVERN",
            )

        with pytest.raises(ValueError, match="must store parent_function_identifier"):
            MappingCandidate(
                incident_id="INC-001",
                framework_code=FrameworkCode.NIST_AI_RMF,
                reference_set_id="ref_001",
                reference_set_version="1.0.0",
                target_identifier="NIST-GOVERN-1",
                mapping_level=ControlLevel.CATEGORY,
                applicability="OBSERVED_CONTROL_GAP",
                confidence=GovernanceConfidence.HIGH,
                rule_id="RULE-01",
                rule_version="1.0.0",
                rationale="Valid observational rationale.",
                evidence_ids=["EV-001"],
                parent_function_identifier=None,  # Missing!
            )


class TestEvidenceLinkageAndProvenance:
    """Verifies that mappings require evidence, strictly link evidence IDs, and preserve facts."""

    def test_empty_evidence_yields_no_mappings(
        self,
        engine: GovernanceMappingEngine,
        base_context: IncidentFactContext,
    ) -> None:
        ctx = base_context.model_copy(update={"evidence_records": []})
        candidates = engine.map_incident(ctx)
        assert candidates == []

    def test_missing_or_blank_evidence_ids_yields_no_mappings(
        self,
        engine: GovernanceMappingEngine,
        base_context: IncidentFactContext,
    ) -> None:
        ctx = base_context.model_copy(
            update={"evidence_records": [{"content": "No ID here"}, {"id": ""}]}
        )
        candidates = engine.map_incident(ctx)
        assert candidates == []

    def test_candidate_contains_only_incident_evidence_ids(
        self,
        engine: GovernanceMappingEngine,
        base_context: IncidentFactContext,
    ) -> None:
        candidates = engine.map_incident(base_context)
        assert len(candidates) > 0
        expected_ids = {"EV-001", "EV-002"}
        for c in candidates:
            assert set(c.evidence_ids) == expected_ids
            assert c.rule_id.startswith("RULE-")
            assert c.rule_version == "1.0.0"

    def test_candidate_preserves_explicit_unknowns_and_disputed_facts(
        self,
        engine: GovernanceMappingEngine,
        base_context: IncidentFactContext,
    ) -> None:
        ctx = base_context.model_copy(
            update={
                "unknowns": ["Unknown vendor architecture.", "Unknown training dataset date."],
                "disputed_facts": ["Whether data was encrypted at rest."],
            }
        )
        candidates = engine.map_incident(ctx)
        assert len(candidates) > 0
        for c in candidates:
            assert "Unknown vendor architecture." in c.unknowns
            assert "Whether data was encrypted at rest." in c.disputed_facts


class TestSpecificityAndGranularityGate:
    """Verifies that NIST subcategories require HIGHLY_SPECIFIC evidence records."""

    def test_nist_subcategory_generated_when_highly_specific_evidence_present(
        self,
        engine: GovernanceMappingEngine,
        base_context: IncidentFactContext,
    ) -> None:
        ctx = base_context.model_copy(
            update={
                "fact_tags": ["specific_regulatory_requirements_untracked"],
                "evidence_records": [
                    {
                        "id": "EV-SPEC-01",
                        "directness": "PRIMARY_DIRECT",
                        "corroboration_status": "FULLY_CORROBORATED",
                        "specificity": "HIGHLY_SPECIFIC",
                        "content": "Specific governance audit finding no risk ownership assigned.",
                    }
                ],
            }
        )
        candidates = engine.map_incident(ctx)
        subcat_cands = [c for c in candidates if c.mapping_level == ControlLevel.SUBCATEGORY]
        assert len(subcat_cands) >= 1
        govern_1_1 = next(c for c in subcat_cands if c.target_identifier == "NIST-GOVERN-1.1")
        assert govern_1_1.parent_category_identifier == "NIST-GOVERN-1"
        assert govern_1_1.parent_function_identifier == "NIST-GOVERN"

    def test_nist_subcategory_suppressed_when_only_general_evidence_present(
        self,
        engine: GovernanceMappingEngine,
        base_context: IncidentFactContext,
    ) -> None:
        ctx = base_context.model_copy(
            update={
                "fact_tags": [
                    "organizational_policy_gap",
                    "lifecycle_policy_omitted",
                    "specific_regulatory_requirements_untracked",
                ],
                "evidence_records": [
                    {
                        "id": "EV-GEN-01",
                        "directness": "PRIMARY_DIRECT",
                        "corroboration_status": "SINGLE_SOURCE_UNCONTESTED",
                        "specificity": "GENERAL_SYSTEM_DESCRIPTION",  # NOT HIGHLY_SPECIFIC
                        "content": "Broad description mentioning lack of governance.",
                    }
                ],
            }
        )
        candidates = engine.map_incident(ctx)
        subcat_cands = [c for c in candidates if c.mapping_level == ControlLevel.SUBCATEGORY]
        assert len(subcat_cands) == 0

        # Category and Function candidates are still emitted
        func_or_cat = [
            c for c in candidates if c.mapping_level in {ControlLevel.FUNCTION, ControlLevel.CATEGORY}
        ]
        assert len(func_or_cat) > 0


class TestConfidenceCalculationAndReviewGates:
    """Verifies confidence calculations, penalties, and review gate routing."""

    def test_confidence_calculation_factors_and_penalties(self) -> None:
        evidence = [
            {
                "directness": "PRIMARY_DIRECT",
                "corroboration_status": "FULLY_CORROBORATED",
                "specificity": "HIGHLY_SPECIFIC",
            }
        ]
        high_res = calculate_mapping_confidence(
            evidence, ControlLevel.FUNCTION, has_unknowns=False, has_disputed_facts=False
        )
        assert high_res.level == GovernanceConfidence.HIGH
        assert high_res.score == 85.0

        # Unknowns penalty (-15)
        with_unknowns = calculate_mapping_confidence(
            evidence, ControlLevel.FUNCTION, has_unknowns=True, has_disputed_facts=False
        )
        assert with_unknowns.unknowns_penalty == 15.0
        assert with_unknowns.score == high_res.score - 15.0

        # Disputed penalty (-25)
        with_disputed = calculate_mapping_confidence(
            evidence, ControlLevel.FUNCTION, has_unknowns=False, has_disputed_facts=True
        )
        assert with_disputed.disputed_penalty == 25.0
        assert with_disputed.score == high_res.score - 25.0

        # Subcategory granularity penalty (when specificity is moderate)
        mod_evidence = [
            {
                "directness": "PRIMARY_DIRECT",
                "corroboration_status": "FULLY_CORROBORATED",
                "specificity": "MODERATELY_SPECIFIC",
            }
        ]
        subcat_mod = calculate_mapping_confidence(
            mod_evidence, ControlLevel.SUBCATEGORY, has_unknowns=False, has_disputed_facts=False
        )
        assert subcat_mod.granularity_penalty == 15.0

    def test_review_gate_routes_subcategory_to_pending_review(self) -> None:
        eval_res = evaluate_review_gates(
            target_level=ControlLevel.SUBCATEGORY,
            confidence=GovernanceConfidence.HIGH,
            has_disputed_facts=False,
            sensitive_domains=[],
            is_insufficient_evidence=False,
        )
        assert eval_res.status == MappingStatus.PENDING_REVIEW
        assert ReviewGateId.GATE_SPECIFIC_GRANULARITY in eval_res.gate_triggers

    def test_review_gate_routes_disputed_facts_to_pending_review(self) -> None:
        eval_res = evaluate_review_gates(
            target_level=ControlLevel.PRINCIPLE,
            confidence=GovernanceConfidence.HIGH,
            has_disputed_facts=True,
            sensitive_domains=[],
            is_insufficient_evidence=False,
        )
        assert eval_res.status == MappingStatus.PENDING_REVIEW
        assert ReviewGateId.GATE_DISPUTED_EVIDENCE in eval_res.gate_triggers

    def test_review_gate_routes_sensitive_domains_to_pending_review(self) -> None:
        eval_res = evaluate_review_gates(
            target_level=ControlLevel.PRINCIPLE,
            confidence=GovernanceConfidence.HIGH,
            has_disputed_facts=False,
            sensitive_domains=[SensitiveDomain.HEALTH_SAFETY],
            is_insufficient_evidence=False,
        )
        assert eval_res.status == MappingStatus.PENDING_REVIEW
        assert ReviewGateId.GATE_SENSITIVE_DOMAIN in eval_res.gate_triggers

    def test_review_gate_routes_insufficient_evidence_status(self) -> None:
        eval_res = evaluate_review_gates(
            target_level=ControlLevel.PRINCIPLE,
            confidence=GovernanceConfidence.INSUFFICIENT,
            has_disputed_facts=False,
            sensitive_domains=[],
            is_insufficient_evidence=True,
        )
        assert eval_res.status == MappingStatus.INSUFFICIENT_EVIDENCE


class TestOECDPrinciplesCoverageAndDeterminism:
    """Verifies complete coverage of OECD Principles 1.1 through 1.5 and strict determinism."""

    def test_oecd_principle_1_1_inclusive_growth(
        self,
        engine: GovernanceMappingEngine,
        base_context: IncidentFactContext,
    ) -> None:
        ctx = base_context.model_copy(
            update={"fact_tags": ["societal_externalities", "direct_societal_harm"]}
        )
        candidates = engine.map_incident(ctx)
        c = next((cand for cand in candidates if cand.target_identifier == "OECD-P1.1"), None)
        assert c is not None
        assert c.applicability == OECDApplicability.DIRECTLY_IMPLICATED.value

    def test_oecd_principle_1_2_human_rights_and_fairness(
        self,
        engine: GovernanceMappingEngine,
        base_context: IncidentFactContext,
    ) -> None:
        ctx = base_context.model_copy(update={"fact_tags": ["bias_or_discrimination"]})
        candidates = engine.map_incident(ctx)
        c = next((cand for cand in candidates if cand.target_identifier == "OECD-P1.2"), None)
        assert c is not None
        assert c.target_identifier == "OECD-P1.2"
        assert c.applicability == OECDApplicability.DIRECTLY_IMPLICATED.value

    def test_oecd_principle_1_3_transparency_and_explainability(
        self,
        engine: GovernanceMappingEngine,
        base_context: IncidentFactContext,
    ) -> None:
        ctx = base_context.model_copy(update={"fact_tags": ["unexplainable_output"]})
        candidates = engine.map_incident(ctx)
        c = next((cand for cand in candidates if cand.target_identifier == "OECD-P1.3"), None)
        assert c is not None
        assert c.applicability == OECDApplicability.DIRECTLY_IMPLICATED.value

    def test_oecd_principle_1_4_robustness_security_safety(
        self,
        engine: GovernanceMappingEngine,
        base_context: IncidentFactContext,
    ) -> None:
        ctx = base_context.model_copy(update={"fact_tags": ["safety_hazard"]})
        candidates = engine.map_incident(ctx)
        c = next((cand for cand in candidates if cand.target_identifier == "OECD-P1.4"), None)
        assert c is not None
        assert c.applicability == OECDApplicability.DIRECTLY_IMPLICATED.value

    def test_oecd_principle_1_5_accountability(
        self,
        engine: GovernanceMappingEngine,
        base_context: IncidentFactContext,
    ) -> None:
        ctx = base_context.model_copy(update={"fact_tags": ["absent_oversight"]})
        candidates = engine.map_incident(ctx)
        c = next((cand for cand in candidates if cand.target_identifier == "OECD-P1.5"), None)
        assert c is not None
        assert c.applicability == OECDApplicability.DIRECTLY_IMPLICATED.value

    def test_engine_determinism_repeated_execution(
        self,
        engine: GovernanceMappingEngine,
        base_context: IncidentFactContext,
    ) -> None:
        """Calling map_incident repeatedly produces byte-for-byte identical candidates."""
        runs = [engine.map_incident(base_context) for _ in range(10)]
        first_run = [c.model_dump(exclude={"generated_at"}) for c in runs[0]]
        for run in runs[1:]:
            current_run = [c.model_dump(exclude={"generated_at"}) for c in run]
            assert current_run == first_run


class TestNISTFunctionsCategoriesSubcategories:
    """Verifies coverage of NIST functions, categories, subcategories, and multi-function independence."""

    def test_nist_functions_govern_map_measure_manage(
        self,
        engine: GovernanceMappingEngine,
        base_context: IncidentFactContext,
    ) -> None:
        ctx = base_context.model_copy(
            update={
                "fact_tags": [
                    "organizational_policy_gap",
                    "missing_context_analysis",
                    "insufficient_testing",
                    "unmitigated_known_risk",
                ]
            }
        )
        candidates = engine.map_incident(ctx)
        func_targets = {c.target_identifier for c in candidates if c.mapping_level == ControlLevel.FUNCTION}
        assert {"NIST-GOVERN", "NIST-MAP", "NIST-MEASURE", "NIST-MANAGE"}.issubset(func_targets)

    def test_nist_multi_function_independence(
        self,
        engine: GovernanceMappingEngine,
        base_context: IncidentFactContext,
    ) -> None:
        """Engine maps GOVERN and MEASURE without forcing MAP or MANAGE."""
        ctx = base_context.model_copy(
            update={"fact_tags": ["organizational_policy_gap", "insufficient_testing"]}
        )
        candidates = engine.map_incident(ctx)
        func_targets = {c.target_identifier for c in candidates if c.mapping_level == ControlLevel.FUNCTION}
        assert "NIST-GOVERN" in func_targets
        assert "NIST-MEASURE" in func_targets
        assert "NIST-MAP" not in func_targets
        assert "NIST-MANAGE" not in func_targets

    def test_nist_categories_and_subcategories_with_parents(
        self,
        engine: GovernanceMappingEngine,
        base_context: IncidentFactContext,
    ) -> None:
        ctx = base_context.model_copy(
            update={
                "fact_tags": [
                    "intended_purpose_undocumented",
                    "risk_treatment_decision_unmade",
                ],
                "evidence_records": [
                    {
                        "id": "EV-001",
                        "directness": "PRIMARY_DIRECT",
                        "corroboration_status": "FULLY_CORROBORATED",
                        "specificity": "HIGHLY_SPECIFIC",
                        "content": "Specific granular documentation of missing controls.",
                    }
                ],
            }
        )
        candidates = engine.map_incident(ctx)
        subcats = {c.target_identifier: c for c in candidates if c.mapping_level == ControlLevel.SUBCATEGORY}
        assert "NIST-MAP-1.1" in subcats
        assert subcats["NIST-MAP-1.1"].parent_category_identifier == "NIST-MAP-1"
        assert subcats["NIST-MAP-1.1"].parent_function_identifier == "NIST-MAP"

        assert "NIST-MANAGE-1.1" in subcats
        assert subcats["NIST-MANAGE-1.1"].parent_category_identifier == "NIST-MANAGE-1"
        assert subcats["NIST-MANAGE-1.1"].parent_function_identifier == "NIST-MANAGE"


class TestSeparationOfConcernsAndNonLegalRules:
    """Verifies isolation from AIG-ISI severity and strict exclusion of legal conclusion language."""

    def test_aig_isi_severity_score_does_not_affect_mapping(
        self,
        engine: GovernanceMappingEngine,
        base_context: IncidentFactContext,
    ) -> None:
        ctx_low = base_context.model_copy(update={"system_context": {"aig_isi_score": 5.0}})
        ctx_high = base_context.model_copy(update={"system_context": {"aig_isi_score": 95.0}})

        cands_low = [c.model_dump(exclude={"generated_at"}) for c in engine.map_incident(ctx_low)]
        cands_high = [c.model_dump(exclude={"generated_at"}) for c in engine.map_incident(ctx_high)]
        assert cands_low == cands_high

    def test_prohibited_legal_terms_rejected_by_validator(self) -> None:
        prohibited_samples = [
            "This constitutes an obvious violation of the principle.",
            "There were multiple breaches observed.",
            "The system was operating in an illegal mode.",
            "This behavior is clearly unlawful under law.",
            "The vendor is fully compliant with standards.",
            "The deployment is noncompliant with rules.",
            "The operator breached their statutory duty.",
        ]
        for sample in prohibited_samples:
            with pytest.raises(ValueError, match="Prohibited legal determination language detected"):
                validate_no_legal_language(sample, field_name="test_text")

    def test_mapping_candidate_rejects_legal_terms_in_rationale_and_facts(self) -> None:
        with pytest.raises(ValueError, match="Prohibited legal determination language detected in rationale"):
            MappingCandidate(
                incident_id="INC-001",
                framework_code=FrameworkCode.OECD_AI_PRINCIPLES,
                reference_set_id="ref_001",
                reference_set_version="2024.1",
                target_identifier="OECD-P1.2",
                mapping_level=ControlLevel.PRINCIPLE,
                applicability="DIRECTLY_IMPLICATED",
                confidence=GovernanceConfidence.HIGH,
                rule_id="RULE-01",
                rule_version="1.0.0",
                rationale="The organization committed a serious violation of privacy rules.",
                evidence_ids=["EV-001"],
            )

        with pytest.raises(ValueError, match="Prohibited legal determination language detected in fact_item"):
            MappingCandidate(
                incident_id="INC-001",
                framework_code=FrameworkCode.OECD_AI_PRINCIPLES,
                reference_set_id="ref_001",
                reference_set_version="2024.1",
                target_identifier="OECD-P1.2",
                mapping_level=ControlLevel.PRINCIPLE,
                applicability="DIRECTLY_IMPLICATED",
                confidence=GovernanceConfidence.HIGH,
                rule_id="RULE-01",
                rule_version="1.0.0",
                rationale="Valid observational statement.",
                evidence_ids=["EV-001"],
                known_facts=["The company committed an illegal deployment."],
            )
