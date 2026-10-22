"""Deterministic governance mapping rules for NIST AI Risk Management Framework (RMF 1.0).

Enforces strict functional hierarchy:
- FUNCTION level: broad governance or lifecycle gaps
- CATEGORY level: exact evidence-supported category
- SUBCATEGORY level: exact verified identifier, strict parent validation, and high-specificity evidence
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from ai_incident_monitor.governance.enums import (
    ControlLevel,
    FrameworkCode,
    NISTApplicability,
)
from ai_incident_monitor.governance.models import (
    IncidentFactContext,
    MappingRuleMetadata,
)


class BaseNISTRule(ABC):
    """Abstract base class for NIST AI RMF mapping rules."""

    @property
    @abstractmethod
    def metadata(self) -> MappingRuleMetadata:
        """Rule metadata and specification."""
        ...

    @abstractmethod
    def evaluate(
        self, context: IncidentFactContext
    ) -> Optional[tuple[NISTApplicability, str, list[str], list[str], list[str], Optional[str]]]:
        """Evaluate rule against incident context.

        Returns:
            None if rule does not match, or tuple of:
            (applicability, rationale, known_facts, unknowns, disputed_facts, recommended_control)
        """
        ...


# ------------------------------------------------------------------------------
# NIST Function Rules
# ------------------------------------------------------------------------------

class NISTGovernFunctionRule(BaseNISTRule):
    """Broad organizational governance, policy, or risk tolerance gap mapping to NIST-GOVERN."""

    RULE_ID = "RULE-NIST-GOVERN-01"
    RULE_VERSION = "1.0.0"

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.NIST_AI_RMF,
            target_identifier="NIST-GOVERN",
            target_level=ControlLevel.FUNCTION,
            title="NIST AI RMF — GOVERN Function",
            description=(
                "Maps organizational policy absences, risk tolerance ambiguity, unclear governance "
                "structures, or third-party oversight gaps to NIST GOVERN function."
            ),
            prerequisite_fact_keys=[
                "organizational_policy_gap",
                "risk_tolerance_undefined",
                "leadership_oversight_lapse",
                "third_party_governance_gap",
            ],
            applicability=NISTApplicability.OBSERVED_CONTROL_GAP.value,
        )

    def evaluate(
        self, context: IncidentFactContext
    ) -> Optional[tuple[NISTApplicability, str, list[str], list[str], list[str], Optional[str]]]:
        prereq_tags = {
            "organizational_policy_gap",
            "risk_tolerance_undefined",
            "leadership_oversight_lapse",
            "third_party_governance_gap",
            "unclear_ownership",
            "missing_governance_structure",
        }
        matched_tags = prereq_tags.intersection(context.fact_tags)
        if not matched_tags:
            return None

        known_facts = [
            f"Observed governance framework signals: {', '.join(sorted(matched_tags))}"
        ]
        if context.known_facts:
            known_facts.extend(context.known_facts[:3])

        applicability = NISTApplicability.OBSERVED_CONTROL_GAP
        if "potential_lesson" in context.fact_tags:
            applicability = NISTApplicability.POTENTIAL_RISK_MANAGEMENT_LESSON

        rationale = (
            "Evidence indicates deficiencies in high-level risk management culture, organizational policies, "
            "or governance structures. NIST AI RMF GOVERN function cultivates and implements a culture of "
            "risk management across organizational lifecycle stages."
        )

        recommended_control = (
            "Establish formal organizational AI governance committee and ratify lifecycle risk policies."
        )

        return (
            applicability,
            rationale,
            known_facts,
            list(context.unknowns),
            list(context.disputed_facts),
            recommended_control,
        )


class NISTMapFunctionRule(BaseNISTRule):
    """Context framing, deployment environment, or intended use boundary gap mapping to NIST-MAP."""

    RULE_ID = "RULE-NIST-MAP-01"
    RULE_VERSION = "1.0.0"

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.NIST_AI_RMF,
            target_identifier="NIST-MAP",
            target_level=ControlLevel.FUNCTION,
            title="NIST AI RMF — MAP Function",
            description=(
                "Maps failures to establish operational context, characterize affected populations, "
                "or anticipate foreseeable misuse to NIST MAP function."
            ),
            prerequisite_fact_keys=[
                "missing_context_analysis",
                "unanticipated_deployment_environment",
                "foreseeable_misuse_unmapped",
                "affected_population_unidentified",
            ],
            applicability=NISTApplicability.OBSERVED_CONTROL_GAP.value,
        )

    def evaluate(
        self, context: IncidentFactContext
    ) -> Optional[tuple[NISTApplicability, str, list[str], list[str], list[str], Optional[str]]]:
        prereq_tags = {
            "missing_context_analysis",
            "unanticipated_deployment_environment",
            "foreseeable_misuse_unmapped",
            "affected_population_unidentified",
            "unanticipated_use_case",
        }
        matched_tags = prereq_tags.intersection(context.fact_tags)
        if not matched_tags:
            return None

        known_facts = [
            f"Observed MAP framework factors: {', '.join(sorted(matched_tags))}"
        ]
        if context.known_facts:
            known_facts.extend(context.known_facts[:3])

        applicability = NISTApplicability.OBSERVED_CONTROL_GAP
        if "potential_lesson" in context.fact_tags:
            applicability = NISTApplicability.POTENTIAL_RISK_MANAGEMENT_LESSON

        rationale = (
            "Evidence shows the AI system operated outside expected context or impacted populations that "
            "were not characterized prior to deployment. NIST AI RMF MAP function establishes context, "
            "categorizes capabilities, and maps potential risks to affected communities."
        )

        recommended_control = (
            "Complete contextual risk assessment mapping intended operational boundaries and foreseeable misuses."
        )

        return (
            applicability,
            rationale,
            known_facts,
            list(context.unknowns),
            list(context.disputed_facts),
            recommended_control,
        )


class NISTMeasureFunctionRule(BaseNISTRule):
    """Testing, validation, metric evaluation, or monitoring deficiency mapping to NIST-MEASURE."""

    RULE_ID = "RULE-NIST-MEASURE-01"
    RULE_VERSION = "1.0.0"

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.NIST_AI_RMF,
            target_identifier="NIST-MEASURE",
            target_level=ControlLevel.FUNCTION,
            title="NIST AI RMF — MEASURE Function",
            description=(
                "Maps absent testing, evaluation, verification, validation (TEVV), bias measurement, "
                "or tracking gaps to NIST MEASURE function."
            ),
            prerequisite_fact_keys=[
                "insufficient_testing",
                "absent_tevv_process",
                "unmeasured_system_performance",
                "monitoring_gap",
            ],
            applicability=NISTApplicability.OBSERVED_CONTROL_GAP.value,
        )

    def evaluate(
        self, context: IncidentFactContext
    ) -> Optional[tuple[NISTApplicability, str, list[str], list[str], list[str], Optional[str]]]:
        prereq_tags = {
            "insufficient_testing",
            "absent_tevv_process",
            "unmeasured_system_performance",
            "monitoring_gap",
            "bias_not_measured",
            "security_testing_omitted",
        }
        matched_tags = prereq_tags.intersection(context.fact_tags)
        if not matched_tags:
            return None

        known_facts = [
            f"Observed MEASURE framework factors: {', '.join(sorted(matched_tags))}"
        ]
        if context.known_facts:
            known_facts.extend(context.known_facts[:3])

        applicability = NISTApplicability.OBSERVED_CONTROL_GAP
        if "potential_lesson" in context.fact_tags:
            applicability = NISTApplicability.POTENTIAL_RISK_MANAGEMENT_LESSON

        rationale = (
            "Evidence indicates testing, evaluation, or tracking procedures were absent or failed to detect "
            "adverse behavior before or during deployment. NIST AI RMF MEASURE function analyzes, assesses, "
            "evaluates, and monitors AI system risks and trustworthiness characteristics using rigorous TEVV processes."
        )

        recommended_control = (
            "Implement standardized TEVV protocols with continuous post-deployment metric tracking."
        )

        return (
            applicability,
            rationale,
            known_facts,
            list(context.unknowns),
            list(context.disputed_facts),
            recommended_control,
        )


class NISTManageFunctionRule(BaseNISTRule):
    """Failure to prioritize, mitigate, correct, or recover from risks mapping to NIST-MANAGE."""

    RULE_ID = "RULE-NIST-MANAGE-01"
    RULE_VERSION = "1.0.0"

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.NIST_AI_RMF,
            target_identifier="NIST-MANAGE",
            target_level=ControlLevel.FUNCTION,
            title="NIST AI RMF — MANAGE Function",
            description=(
                "Maps unmitigated known risks, delayed response, absent rollback, or incident response "
                "failures to NIST MANAGE function."
            ),
            prerequisite_fact_keys=[
                "unmitigated_known_risk",
                "absent_incident_response",
                "lack_of_rollback_mechanism",
                "failed_risk_treatment",
            ],
            applicability=NISTApplicability.OBSERVED_CONTROL_GAP.value,
        )

    def evaluate(
        self, context: IncidentFactContext
    ) -> Optional[tuple[NISTApplicability, str, list[str], list[str], list[str], Optional[str]]]:
        prereq_tags = {
            "unmitigated_known_risk",
            "absent_incident_response",
            "lack_of_rollback_mechanism",
            "failed_risk_treatment",
            "unaddressed_safety_alert",
        }
        matched_tags = prereq_tags.intersection(context.fact_tags)
        if not matched_tags:
            return None

        known_facts = [
            f"Observed MANAGE framework factors: {', '.join(sorted(matched_tags))}"
        ]
        if context.known_facts:
            known_facts.extend(context.known_facts[:3])

        applicability = NISTApplicability.OBSERVED_CONTROL_GAP
        if "potential_lesson" in context.fact_tags:
            applicability = NISTApplicability.POTENTIAL_RISK_MANAGEMENT_LESSON

        rationale = (
            "Evidence documents that identified risks were not treated, mitigated, or managed effectively "
            "prior to or during the event. NIST AI RMF MANAGE function prioritizes, treats, mitigates, "
            "and monitors identified AI risks to minimize adverse consequences."
        )

        recommended_control = (
            "Deploy verified mitigation playbooks, incident response escalation, and rapid rollback mechanisms."
        )

        return (
            applicability,
            rationale,
            known_facts,
            list(context.unknowns),
            list(context.disputed_facts),
            recommended_control,
        )


# ------------------------------------------------------------------------------
# NIST Category Rules
# ------------------------------------------------------------------------------

class NISTGovern1CategoryRule(BaseNISTRule):
    """Policies, processes, procedures, and practices category (GOVERN 1)."""

    RULE_ID = "RULE-NIST-GOVERN-1-01"
    RULE_VERSION = "1.0.0"

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.NIST_AI_RMF,
            target_identifier="NIST-GOVERN-1",
            target_level=ControlLevel.CATEGORY,
            title="NIST AI RMF — Category GOVERN 1 (Policies, processes, procedures, and practices)",
            description="Maps lifecycle policy, procedural documentation, and organizational practice gaps to GOVERN 1.",
            prerequisite_fact_keys=["lifecycle_policy_omitted", "procedural_gap"],
            applicability=NISTApplicability.OBSERVED_CONTROL_GAP.value,
            parent_function_identifier="NIST-GOVERN",
        )

    def evaluate(
        self, context: IncidentFactContext
    ) -> Optional[tuple[NISTApplicability, str, list[str], list[str], list[str], Optional[str]]]:
        if "lifecycle_policy_omitted" not in context.fact_tags and "procedural_gap" not in context.fact_tags:
            return None

        known_facts = ["Documented policy omission or procedural deficiency identified in incident record."]
        if context.known_facts:
            known_facts.extend(context.known_facts[:2])

        rationale = (
            "Evidence demonstrates absence or non-implementation of lifecycle policies and operational "
            "procedures. NIST AI RMF GOVERN 1 requires policies, processes, procedures, and practices across "
            "the AI lifecycle to be established, transparent, and implemented."
        )
        return (
            NISTApplicability.OBSERVED_CONTROL_GAP,
            rationale,
            known_facts,
            list(context.unknowns),
            list(context.disputed_facts),
            "Formalize and publish operational AI policies across design, evaluation, and deployment phases.",
        )


class NISTGovern2CategoryRule(BaseNISTRule):
    """Accountability structures and roles category (GOVERN 2)."""

    RULE_ID = "RULE-NIST-GOVERN-2-01"
    RULE_VERSION = "1.0.0"

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.NIST_AI_RMF,
            target_identifier="NIST-GOVERN-2",
            target_level=ControlLevel.CATEGORY,
            title="NIST AI RMF — Category GOVERN 2 (Accountability and roles)",
            description="Maps lack of defined roles, personnel oversight responsibilities, and accountability to GOVERN 2.",
            prerequisite_fact_keys=["unclear_roles", "unassigned_accountability"],
            applicability=NISTApplicability.OBSERVED_CONTROL_GAP.value,
            parent_function_identifier="NIST-GOVERN",
        )

    def evaluate(
        self, context: IncidentFactContext
    ) -> Optional[tuple[NISTApplicability, str, list[str], list[str], list[str], Optional[str]]]:
        if "unclear_roles" not in context.fact_tags and "unassigned_accountability" not in context.fact_tags:
            return None

        known_facts = ["Personnel roles or risk accountability responsibilities were unassigned or ambiguous."]
        if context.known_facts:
            known_facts.extend(context.known_facts[:2])

        rationale = (
            "Evidence shows ambiguity in decision authority and operational ownership. NIST AI RMF "
            "GOVERN 2 directs that accountability structures be in place so that roles and responsibilities are clear."
        )
        return (
            NISTApplicability.OBSERVED_CONTROL_GAP,
            rationale,
            known_facts,
            list(context.unknowns),
            list(context.disputed_facts),
            "Assign named role responsibility for AI system performance and risk oversight.",
        )


class NISTMap1CategoryRule(BaseNISTRule):
    """Context of the AI system category (MAP 1)."""

    RULE_ID = "RULE-NIST-MAP-1-01"
    RULE_VERSION = "1.0.0"

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.NIST_AI_RMF,
            target_identifier="NIST-MAP-1",
            target_level=ControlLevel.CATEGORY,
            title="NIST AI RMF — Category MAP 1 (Context of the AI system)",
            description="Maps unmapped operational context, deployment environment, and system framing gaps to MAP 1.",
            prerequisite_fact_keys=["context_not_established", "unmapped_environment"],
            applicability=NISTApplicability.OBSERVED_CONTROL_GAP.value,
            parent_function_identifier="NIST-MAP",
        )

    def evaluate(
        self, context: IncidentFactContext
    ) -> Optional[tuple[NISTApplicability, str, list[str], list[str], list[str], Optional[str]]]:
        if "context_not_established" not in context.fact_tags and "unmapped_environment" not in context.fact_tags:
            return None

        known_facts = ["Operational deployment environment and domain context were not formally established."]
        if context.known_facts:
            known_facts.extend(context.known_facts[:2])

        rationale = (
            "Evidence indicates the operational context and intended setting were not characterized before use. "
            "NIST AI RMF MAP 1 establishes that context of the AI system must be understood."
        )
        return (
            NISTApplicability.OBSERVED_CONTROL_GAP,
            rationale,
            known_facts,
            list(context.unknowns),
            list(context.disputed_facts),
            "Document intended domain setting, operational conditions, and business context.",
        )


class NISTMeasure2CategoryRule(BaseNISTRule):
    """Trustworthiness characteristics category (MEASURE 2)."""

    RULE_ID = "RULE-NIST-MEASURE-2-01"
    RULE_VERSION = "1.0.0"

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.NIST_AI_RMF,
            target_identifier="NIST-MEASURE-2",
            target_level=ControlLevel.CATEGORY,
            title="NIST AI RMF — Category MEASURE 2 (Trustworthiness characteristics)",
            description="Maps failure to measure or evaluate specific trustworthiness characteristics to MEASURE 2.",
            prerequisite_fact_keys=["trustworthiness_metrics_unmeasured", "bias_metrics_untracked"],
            applicability=NISTApplicability.OBSERVED_CONTROL_GAP.value,
            parent_function_identifier="NIST-MEASURE",
        )

    def evaluate(
        self, context: IncidentFactContext
    ) -> Optional[tuple[NISTApplicability, str, list[str], list[str], list[str], Optional[str]]]:
        if (
            "trustworthiness_metrics_unmeasured" not in context.fact_tags
            and "bias_metrics_untracked" not in context.fact_tags
        ):
            return None

        known_facts = ["Trustworthiness characteristics (accuracy, fairness, or robustness) were unmeasured."]
        if context.known_facts:
            known_facts.extend(context.known_facts[:2])

        rationale = (
            "Evidence shows trustworthiness characteristics were not quantitatively evaluated. NIST AI RMF "
            "MEASURE 2 provides that trustworthiness characteristics are identified, measured, and tracked."
        )
        return (
            NISTApplicability.OBSERVED_CONTROL_GAP,
            rationale,
            known_facts,
            list(context.unknowns),
            list(context.disputed_facts),
            "Benchmark AI system against quantitative accuracy, bias, and robustness thresholds.",
        )


class NISTManage1CategoryRule(BaseNISTRule):
    """AI risks are prioritized, treated, and managed category (MANAGE 1)."""

    RULE_ID = "RULE-NIST-MANAGE-1-01"
    RULE_VERSION = "1.0.0"

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.NIST_AI_RMF,
            target_identifier="NIST-MANAGE-1",
            target_level=ControlLevel.CATEGORY,
            title="NIST AI RMF — Category MANAGE 1 (Risk treatment and management)",
            description="Maps unprioritized or unmitigated identified risks to MANAGE 1.",
            prerequisite_fact_keys=["risks_untreated", "risk_mitigation_unperformed"],
            applicability=NISTApplicability.OBSERVED_CONTROL_GAP.value,
            parent_function_identifier="NIST-MANAGE",
        )

    def evaluate(
        self, context: IncidentFactContext
    ) -> Optional[tuple[NISTApplicability, str, list[str], list[str], list[str], Optional[str]]]:
        if "risks_untreated" not in context.fact_tags and "risk_mitigation_unperformed" not in context.fact_tags:
            return None

        known_facts = ["Mapped risks were not prioritized, treated, or mitigated."]
        if context.known_facts:
            known_facts.extend(context.known_facts[:2])

        rationale = (
            "Evidence shows identified risks were not treated or mitigated before causing adverse outcomes. "
            "NIST AI RMF MANAGE 1 requires that AI risks are prioritized, treated, and managed."
        )
        return (
            NISTApplicability.OBSERVED_CONTROL_GAP,
            rationale,
            known_facts,
            list(context.unknowns),
            list(context.disputed_facts),
            "Develop prioritized risk treatment plans and allocate mitigation resources.",
        )


# ------------------------------------------------------------------------------
# NIST Subcategory Rules (High-Specificity Evidence Required)
# ------------------------------------------------------------------------------

class NISTGovern11SubcategoryRule(BaseNISTRule):
    """Specific legal, regulatory, or policy requirements alignment subcategory (GOVERN 1.1)."""

    RULE_ID = "RULE-NIST-GOVERN-1.1-01"
    RULE_VERSION = "1.0.0"

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.NIST_AI_RMF,
            target_identifier="NIST-GOVERN-1.1",
            target_level=ControlLevel.SUBCATEGORY,
            title="NIST AI RMF — Subcategory GOVERN 1.1",
            description=(
                "Maps specific gaps in understanding applicable legal, regulatory, or policy requirements "
                "to GOVERN 1.1 (requires high-specificity evidence)."
            ),
            prerequisite_fact_keys=["specific_regulatory_requirements_untracked"],
            applicability=NISTApplicability.OBSERVED_CONTROL_GAP.value,
            parent_category_identifier="NIST-GOVERN-1",
            parent_function_identifier="NIST-GOVERN",
        )

    def evaluate(
        self, context: IncidentFactContext
    ) -> Optional[tuple[NISTApplicability, str, list[str], list[str], list[str], Optional[str]]]:
        # High specificity requirement: requires specific_regulatory_requirements_untracked tag
        if "specific_regulatory_requirements_untracked" not in context.fact_tags:
            return None

        known_facts = ["Specific applicable regulatory or policy requirements were unmapped to AI lifecycle."]
        if context.known_facts:
            known_facts.extend(context.known_facts[:2])

        rationale = (
            "Granular evidence demonstrates that organizational leadership failed to identify applicable "
            "governance and regulatory expectations relevant to this AI system. NIST AI RMF GOVERN 1.1 specifies "
            "that legal and regulatory requirements involving AI are understood and managed."
        )
        return (
            NISTApplicability.OBSERVED_CONTROL_GAP,
            rationale,
            known_facts,
            list(context.unknowns),
            list(context.disputed_facts),
            "Establish inventory of applicable regulatory expectations mapped to system components.",
        )


class NISTMap11SubcategoryRule(BaseNISTRule):
    """Intended purpose, operational environment context subcategory (MAP 1.1)."""

    RULE_ID = "RULE-NIST-MAP-1.1-01"
    RULE_VERSION = "1.0.0"

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.NIST_AI_RMF,
            target_identifier="NIST-MAP-1.1",
            target_level=ControlLevel.SUBCATEGORY,
            title="NIST AI RMF — Subcategory MAP 1.1",
            description=(
                "Maps specific gaps in documented intended purpose, business value, and deployment boundaries "
                "to MAP 1.1 (requires high-specificity evidence)."
            ),
            prerequisite_fact_keys=["intended_purpose_undocumented"],
            applicability=NISTApplicability.OBSERVED_CONTROL_GAP.value,
            parent_category_identifier="NIST-MAP-1",
            parent_function_identifier="NIST-MAP",
        )

    def evaluate(
        self, context: IncidentFactContext
    ) -> Optional[tuple[NISTApplicability, str, list[str], list[str], list[str], Optional[str]]]:
        if "intended_purpose_undocumented" not in context.fact_tags:
            return None

        known_facts = ["Intended purpose and operational deployment boundaries were undocumented."]
        if context.known_facts:
            known_facts.extend(context.known_facts[:2])

        rationale = (
            "Granular evidence shows the system was deployed without formal documentation of intended purpose "
            "or operational setting boundaries. NIST AI RMF MAP 1.1 specifies that intended purpose and "
            "operational environment are documented."
        )
        return (
            NISTApplicability.OBSERVED_CONTROL_GAP,
            rationale,
            known_facts,
            list(context.unknowns),
            list(context.disputed_facts),
            "Formally document intended operational parameters, boundaries, and authorized deployment contexts.",
        )


class NISTMeasure21SubcategoryRule(BaseNISTRule):
    """Specific measurement of trustworthiness characteristics subcategory (MEASURE 2.1)."""

    RULE_ID = "RULE-NIST-MEASURE-2.1-01"
    RULE_VERSION = "1.0.0"

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.NIST_AI_RMF,
            target_identifier="NIST-MEASURE-2.1",
            target_level=ControlLevel.SUBCATEGORY,
            title="NIST AI RMF — Subcategory MEASURE 2.1",
            description=(
                "Maps specific testing failures where formal quantitative metrics for trustworthiness were not evaluated "
                "against baselines to MEASURE 2.1 (requires high-specificity evidence)."
            ),
            prerequisite_fact_keys=["quantitative_baseline_testing_omitted"],
            applicability=NISTApplicability.OBSERVED_CONTROL_GAP.value,
            parent_category_identifier="NIST-MEASURE-2",
            parent_function_identifier="NIST-MEASURE",
        )

    def evaluate(
        self, context: IncidentFactContext
    ) -> Optional[tuple[NISTApplicability, str, list[str], list[str], list[str], Optional[str]]]:
        if "quantitative_baseline_testing_omitted" not in context.fact_tags:
            return None

        known_facts = ["Quantitative baseline evaluation for model trustworthiness characteristics was omitted."]
        if context.known_facts:
            known_facts.extend(context.known_facts[:2])

        rationale = (
            "Granular evidence demonstrates that system performance characteristics were never evaluated against "
            "established quantitative baselines prior to release. NIST AI RMF MEASURE 2.1 establishes that "
            "test metrics are identified and evaluated against baseline expectations."
        )
        return (
            NISTApplicability.OBSERVED_CONTROL_GAP,
            rationale,
            known_facts,
            list(context.unknowns),
            list(context.disputed_facts),
            "Execute formal baseline evaluations and define explicit metric thresholds before production rollout.",
        )


class NISTManage11SubcategoryRule(BaseNISTRule):
    """Determination to treat, transfer, tolerate, or terminate AI risks subcategory (MANAGE 1.1)."""

    RULE_ID = "RULE-NIST-MANAGE-1.1-01"
    RULE_VERSION = "1.0.0"

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.NIST_AI_RMF,
            target_identifier="NIST-MANAGE-1.1",
            target_level=ControlLevel.SUBCATEGORY,
            title="NIST AI RMF — Subcategory MANAGE 1.1",
            description=(
                "Maps specific failures to enact risk treatment determinations (treat, transfer, tolerate, terminate) "
                "to MANAGE 1.1 (requires high-specificity evidence)."
            ),
            prerequisite_fact_keys=["risk_treatment_decision_unmade"],
            applicability=NISTApplicability.OBSERVED_CONTROL_GAP.value,
            parent_category_identifier="NIST-MANAGE-1",
            parent_function_identifier="NIST-MANAGE",
        )

    def evaluate(
        self, context: IncidentFactContext
    ) -> Optional[tuple[NISTApplicability, str, list[str], list[str], list[str], Optional[str]]]:
        if "risk_treatment_decision_unmade" not in context.fact_tags:
            return None

        known_facts = ["Formal risk treatment determination (treat, transfer, tolerate, terminate) was not made."]
        if context.known_facts:
            known_facts.extend(context.known_facts[:2])

        rationale = (
            "Granular evidence indicates known system hazards were left in an unaddressed state without an "
            "actionable risk treatment decision. NIST AI RMF MANAGE 1.1 directs that determinations to treat, "
            "transfer, tolerate, or terminate AI risks are enacted."
        )
        return (
            NISTApplicability.OBSERVED_CONTROL_GAP,
            rationale,
            known_facts,
            list(context.unknowns),
            list(context.disputed_facts),
            "Document explicit risk treatment determinations with named ownership for each identified hazard.",
        )


ALL_NIST_RULES: tuple[BaseNISTRule, ...] = (
    # Functions
    NISTGovernFunctionRule(),
    NISTMapFunctionRule(),
    NISTMeasureFunctionRule(),
    NISTManageFunctionRule(),
    # Categories
    NISTGovern1CategoryRule(),
    NISTGovern2CategoryRule(),
    NISTMap1CategoryRule(),
    NISTMeasure2CategoryRule(),
    NISTManage1CategoryRule(),
    # Subcategories
    NISTGovern11SubcategoryRule(),
    NISTMap11SubcategoryRule(),
    NISTMeasure21SubcategoryRule(),
    NISTManage11SubcategoryRule(),
)
