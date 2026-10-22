"""Deterministic governance mapping rules for OECD AI Principles (2024 update).

Provides inspectable, versioned rule objects mapping incident evidence to OECD principles
without free-text heuristics, LLMs, or stochastic processing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from ai_incident_monitor.governance.enums import (
    ControlLevel,
    FrameworkCode,
    OECDApplicability,
)
from ai_incident_monitor.governance.models import (
    IncidentFactContext,
    MappingRuleMetadata,
)


class BaseOECDRule(ABC):
    """Abstract base class for OECD AI Principles mapping rules."""

    @property
    @abstractmethod
    def metadata(self) -> MappingRuleMetadata:
        """Rule metadata and specification."""
        ...

    @abstractmethod
    def evaluate(
        self, context: IncidentFactContext
    ) -> Optional[tuple[OECDApplicability, str, list[str], list[str], list[str], Optional[str]]]:
        """Evaluate rule against incident context.

        Returns:
            None if rule does not match, or tuple of:
            (applicability, rationale, known_facts, unknowns, disputed_facts, recommended_control)
        """
        ...


class OECDFairnessPrivacyRule(BaseOECDRule):
    """Rule mapping evidence of bias, discrimination, or privacy compromise to OECD Principle 1.2."""

    RULE_ID = "RULE-OECD-1.2-01"
    RULE_VERSION = "1.0.0"

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.OECD_AI_PRINCIPLES,
            target_identifier="OECD-P1.2",
            target_level=ControlLevel.PRINCIPLE,
            title="OECD Principle 1.2 — Human rights and democratic values, fairness, privacy",
            description=(
                "Maps observed differential treatment, algorithmic bias, protected-attribute disparities, "
                "or unauthorized data exposure to OECD Principle 1.2."
            ),
            prerequisite_fact_keys=[
                "differential_impact",
                "bias_or_discrimination",
                "privacy_compromise",
                "rights_deprivation",
            ],
            applicability=OECDApplicability.DIRECTLY_IMPLICATED.value,
        )

    def evaluate(
        self, context: IncidentFactContext
    ) -> Optional[tuple[OECDApplicability, str, list[str], list[str], list[str], Optional[str]]]:
        prereq_tags = {
            "differential_impact",
            "bias_or_discrimination",
            "privacy_compromise",
            "rights_deprivation",
            "unauthorized_surveillance",
            "demographic_disparity",
        }
        matched_tags = prereq_tags.intersection(context.fact_tags)
        if not matched_tags and not any(
            sd.value in {"DISCRIMINATION", "PRIVACY", "FUNDAMENTAL_RIGHTS"}
            for sd in context.sensitive_domains
        ):
            return None

        # Build known facts from matching evidence/context
        known_facts = [
            f"Observed factual signals for human rights, fairness, or privacy: {', '.join(sorted(matched_tags))}"
        ]
        if context.known_facts:
            known_facts.extend(context.known_facts[:3])

        rationale = (
            "Empirical evidence demonstrates impact on demographic groups, personal privacy, "
            "or fundamental fairness. OECD Principle 1.2 explicitly directs AI actors to respect "
            "human rights, fairness, privacy, and non-discrimination throughout the system lifecycle."
        )

        recommended_control = (
            "Conduct structured impact assessment on affected populations and implement fairness "
            "and privacy safeguards."
        )

        return (
            OECDApplicability.DIRECTLY_IMPLICATED,
            rationale,
            known_facts,
            list(context.unknowns),
            list(context.disputed_facts),
            recommended_control,
        )


class OECDTransparencyExplainabilityRule(BaseOECDRule):
    """Rule mapping opaque models, absent notice, or unexplainable outputs to OECD Principle 1.3."""

    RULE_ID = "RULE-OECD-1.3-01"
    RULE_VERSION = "1.0.0"

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.OECD_AI_PRINCIPLES,
            target_identifier="OECD-P1.3",
            target_level=ControlLevel.PRINCIPLE,
            title="OECD Principle 1.3 — Transparency and explainability",
            description=(
                "Maps absent user disclosure, black-box decision outcomes, untraceable training provenance, "
                "or lack of explainability to OECD Principle 1.3."
            ),
            prerequisite_fact_keys=[
                "absent_disclosure",
                "opaque_decision_making",
                "unexplainable_output",
                "missing_traceability",
            ],
            applicability=OECDApplicability.DIRECTLY_IMPLICATED.value,
        )

    def evaluate(
        self, context: IncidentFactContext
    ) -> Optional[tuple[OECDApplicability, str, list[str], list[str], list[str], Optional[str]]]:
        prereq_tags = {
            "absent_disclosure",
            "opaque_decision_making",
            "unexplainable_output",
            "missing_traceability",
            "lack_of_contestability",
        }
        matched_tags = prereq_tags.intersection(context.fact_tags)
        if not matched_tags:
            return None

        known_facts = [
            f"Identified transparency or explainability factors: {', '.join(sorted(matched_tags))}"
        ]
        if context.known_facts:
            known_facts.extend(context.known_facts[:3])

        applicability = OECDApplicability.DIRECTLY_IMPLICATED
        if "broader_lesson" in context.fact_tags:
            applicability = OECDApplicability.BROADER_GOVERNANCE_LESSON

        rationale = (
            "Evidence indicates affected parties were not provided meaningful disclosure, explainable "
            "rationales, or contestability mechanisms regarding automated system outputs. OECD Principle "
            "1.3 provides that stakeholders should understand interactions, outcomes, and have contestability."
        )

        recommended_control = (
            "Deploy plain-language decision explainability tools and clear user disclosure notices."
        )

        return (
            applicability,
            rationale,
            known_facts,
            list(context.unknowns),
            list(context.disputed_facts),
            recommended_control,
        )


class OECDRobustnessSecuritySafetyRule(BaseOECDRule):
    """Rule mapping safety failures, security vulnerabilities, or hallucinations to OECD Principle 1.4."""

    RULE_ID = "RULE-OECD-1.4-01"
    RULE_VERSION = "1.0.0"

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.OECD_AI_PRINCIPLES,
            target_identifier="OECD-P1.4",
            target_level=ControlLevel.PRINCIPLE,
            title="OECD Principle 1.4 — Robustness, security, and safety",
            description=(
                "Maps model instability, physical/operational safety hazards, prompt injection vulnerabilities, "
                "or system failures to OECD Principle 1.4."
            ),
            prerequisite_fact_keys=[
                "security_vulnerability",
                "system_instability",
                "safety_hazard",
                "adversarial_manipulation",
                "uncontrolled_output",
            ],
            applicability=OECDApplicability.DIRECTLY_IMPLICATED.value,
        )

    def evaluate(
        self, context: IncidentFactContext
    ) -> Optional[tuple[OECDApplicability, str, list[str], list[str], list[str], Optional[str]]]:
        prereq_tags = {
            "security_vulnerability",
            "system_instability",
            "safety_hazard",
            "adversarial_manipulation",
            "uncontrolled_output",
            "model_hallucination",
            "critical_failure",
        }
        matched_tags = prereq_tags.intersection(context.fact_tags)
        if not matched_tags and not any(
            sd.value in {"HEALTH_SAFETY", "CRITICAL_INFRASTRUCTURE"}
            for sd in context.sensitive_domains
        ):
            return None

        known_facts = [
            f"Observed robustness, security, or safety signals: {', '.join(sorted(matched_tags))}"
        ]
        if context.known_facts:
            known_facts.extend(context.known_facts[:3])

        rationale = (
            "Evidence documents technical instability, security vulnerabilities, or safety hazards "
            "under operational conditions. OECD Principle 1.4 establishes that AI systems should be "
            "robust, secure, and safe throughout their lifecycle and avoid posing unreasonable safety risks."
        )

        recommended_control = (
            "Perform comprehensive pre-deployment stress testing and establish automated circuit breakers."
        )

        return (
            OECDApplicability.DIRECTLY_IMPLICATED,
            rationale,
            known_facts,
            list(context.unknowns),
            list(context.disputed_facts),
            recommended_control,
        )


class OECDAccountabilityRule(BaseOECDRule):
    """Rule mapping absent organizational oversight or unclear responsibility to OECD Principle 1.5."""

    RULE_ID = "RULE-OECD-1.5-01"
    RULE_VERSION = "1.0.0"

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.OECD_AI_PRINCIPLES,
            target_identifier="OECD-P1.5",
            target_level=ControlLevel.PRINCIPLE,
            title="OECD Principle 1.5 — Accountability",
            description=(
                "Maps undefined roles, absent human oversight, delayed remediation, or unassigned "
                "organizational responsibility to OECD Principle 1.5."
            ),
            prerequisite_fact_keys=[
                "unclear_ownership",
                "absent_oversight",
                "delayed_remediation",
                "unassigned_responsibility",
            ],
            applicability=OECDApplicability.DIRECTLY_IMPLICATED.value,
        )

    def evaluate(
        self, context: IncidentFactContext
    ) -> Optional[tuple[OECDApplicability, str, list[str], list[str], list[str], Optional[str]]]:
        prereq_tags = {
            "unclear_ownership",
            "absent_oversight",
            "delayed_remediation",
            "unassigned_responsibility",
            "failed_incident_response",
        }
        matched_tags = prereq_tags.intersection(context.fact_tags)
        if not matched_tags:
            return None

        known_facts = [
            f"Observed governance accountability factors: {', '.join(sorted(matched_tags))}"
        ]
        if context.known_facts:
            known_facts.extend(context.known_facts[:3])

        applicability = OECDApplicability.DIRECTLY_IMPLICATED
        if "broader_lesson" in context.fact_tags:
            applicability = OECDApplicability.BROADER_GOVERNANCE_LESSON

        rationale = (
            "Evidence indicates gaps in operational oversight, organizational responsibility, or "
            "remediation mechanisms. OECD Principle 1.5 provides that AI actors should be accountable "
            "for the proper functioning of AI systems and adherence to trustworthiness principles."
        )

        recommended_control = (
            "Establish unambiguous organizational escalation paths and assign explicit accountability roles."
        )

        return (
            applicability,
            rationale,
            known_facts,
            list(context.unknowns),
            list(context.disputed_facts),
            recommended_control,
        )


class OECDInclusiveGrowthRule(BaseOECDRule):
    """Rule mapping societal, environmental, or economic well-being impacts to OECD Principle 1.1."""

    RULE_ID = "RULE-OECD-1.1-01"
    RULE_VERSION = "1.0.0"

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.OECD_AI_PRINCIPLES,
            target_identifier="OECD-P1.1",
            target_level=ControlLevel.PRINCIPLE,
            title="OECD Principle 1.1 — Inclusive growth, sustainable development, and well-being",
            description=(
                "Maps broader societal, environmental, economic equity, or public well-being externalities "
                "to OECD Principle 1.1."
            ),
            prerequisite_fact_keys=[
                "societal_externalities",
                "environmental_impact",
                "economic_displacement",
                "access_disruption",
            ],
            applicability=OECDApplicability.BROADER_GOVERNANCE_LESSON.value,
        )

    def evaluate(
        self, context: IncidentFactContext
    ) -> Optional[tuple[OECDApplicability, str, list[str], list[str], list[str], Optional[str]]]:
        prereq_tags = {
            "societal_externalities",
            "environmental_impact",
            "economic_displacement",
            "access_disruption",
            "community_wellbeing_impact",
        }
        matched_tags = prereq_tags.intersection(context.fact_tags)
        if not matched_tags and not any(
            sd.value in {"EMPLOYMENT", "EDUCATION"}
            for sd in context.sensitive_domains
        ):
            return None

        known_facts = [
            f"Observed societal or well-being impact factors: {', '.join(sorted(matched_tags))}"
        ]
        if context.known_facts:
            known_facts.extend(context.known_facts[:3])

        applicability = OECDApplicability.BROADER_GOVERNANCE_LESSON
        if "direct_societal_harm" in context.fact_tags:
            applicability = OECDApplicability.DIRECTLY_IMPLICATED

        rationale = (
            "Evidence documents systemic externalities on community well-being, ecological factors, or "
            "economic access. OECD Principle 1.1 calls for proactive stewardship in pursuit of beneficial "
            "outcomes for people and the planet, advancing inclusion and well-being."
        )

        recommended_control = (
            "Conduct holistic sustainability and societal externality review prior to widespread deployment."
        )

        return (
            applicability,
            rationale,
            known_facts,
            list(context.unknowns),
            list(context.disputed_facts),
            recommended_control,
        )


ALL_OECD_RULES: tuple[BaseOECDRule, ...] = (
    OECDFairnessPrivacyRule(),
    OECDTransparencyExplainabilityRule(),
    OECDRobustnessSecuritySafetyRule(),
    OECDAccountabilityRule(),
    OECDInclusiveGrowthRule(),
)
