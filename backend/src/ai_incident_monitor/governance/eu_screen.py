"""Deterministic, evidence-grounded EU AI Act informational relevance screening engine.

Phase 5 Increment 2C-3A Implementation:
Orchestrates core deterministic fact evaluators and conceptual relevance rules against
the validated EU AI Act reference library (frameworks/eu-ai-act/eu-ai-act-2024-1689.yaml).

Mandatory Safety Invariants:
1. Evidence First: Zero verified incident evidence records = zero affirmative findings.
2. Validated References Only: All evaluated concepts must strictly resolve to active canonical
   reference identifiers. Fabricated or unvalidated references trigger ConstitutionalViolationError.
3. Informational Governance Screen ONLY: Does NOT determine statutory applicability, jurisdiction,
   actor classification, compliance, noncompliance, liability, breach, or violation.
4. Epistemic Modesty: Missing facts are preserved as explicit unknowns; no negative inference.
5. Conflicting Facts: Disputed evidence remains explicit and forces review routing.
6. Mandatory PENDING_REVIEW: Every screen and conceptual finding unconditionally enters PENDING_REVIEW.
   No automated process may approve, publish, or declare eligible for external use.
7. Orthogonal Governance Confidence: Independent from AIG-ISI severity and OECD/NIST confidence.
8. Lexical Safety: Strict prohibition of legal conclusion terminology via validate_no_legal_language.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from ai_incident_monitor.domain.common import ConstitutionalViolationError
from ai_incident_monitor.governance.enums import (
    ControlLevel,
    EUActorRoleConfidence,
    EUConceptualRelevanceLevel,
    EUEvidenceStrength,
    EUNexusAssessment,
    EURelevanceLevel,
    EUScreenStatus,
    EUSeriousIncidentRelevance,
    EUTimingAssessment,
    FrameworkCode,
    FrameworkStatus,
    GovernanceConfidence,
)
from ai_incident_monitor.governance.models import (
    EU_AI_ACT_DISCLAIMER_V2,
    EU_AI_ACT_DISCLAIMER_VERSION,
    EUConceptualEvaluationResult,
    EUConceptualFinding,
    EULegalRelevanceScreenSchema,
    EUScreenRuleTraceSchema,
    FrameworkControlSchema,
    FrameworkReferenceSetSchema,
    IncidentFactContext,
    validate_no_legal_language,
)
from ai_incident_monitor.governance.rules.eu_conceptual_relevance_rules import (
    ALL_EU_CONCEPTUAL_RULES,
    BaseEUConceptualRule,
    evaluate_eu_conceptual_context,
)
from ai_incident_monitor.governance.rules.eu_fact_rules import (
    EU_ART_2_IDENTIFIER,
    EU_ART_3_1_IDENTIFIER,
    EUFactEvaluationResult,
    evaluate_eu_fact_context,
)

DEFAULT_EU_REF_ID = "eu-ai-act-2024-1689"


class EURelevanceScreeningEngine:
    """Deterministic, rule-based screening engine evaluating incident facts against the EU AI Act."""

    def __init__(
        self,
        reference_set: FrameworkReferenceSetSchema,
        conceptual_rules: Optional[tuple[BaseEUConceptualRule, ...]] = None,
    ) -> None:
        """Initialize screening engine with validated EU AI Act reference set and conceptual rules.

        Args:
            reference_set: Validated FrameworkReferenceSetSchema for EU AI Act.
            conceptual_rules: Optional custom tuple of conceptual rules; defaults to ALL_EU_CONCEPTUAL_RULES.

        Raises:
            ConstitutionalViolationError: If reference set is invalid or any rule targets an unvalidated control.
        """
        if reference_set.framework_code != FrameworkCode.EU_AI_ACT and reference_set.version != "2024/1689":
            raise ConstitutionalViolationError(
                f"EURelevanceScreeningEngine requires EU AI Act reference set, got '{reference_set.framework_code}'."
            )

        self.reference_set = reference_set
        self.conceptual_rules = (
            conceptual_rules if conceptual_rules is not None else ALL_EU_CONCEPTUAL_RULES
        )

        # Index controls by external identifier
        self._control_index: dict[str, FrameworkControlSchema] = {}
        self._parent_map: dict[str, str] = {}

        for ctrl in reference_set.controls:
            self._control_index[ctrl.external_identifier] = ctrl
            if ctrl.parent_identifier:
                self._parent_map[ctrl.external_identifier] = ctrl.parent_identifier

        # Safety Rule 2: Validate that all conceptual rules target active canonical controls
        for rule in self.conceptual_rules:
            target = rule.target_identifier
            ctrl = self._control_index.get(target)
            if ctrl is None or ctrl.status != FrameworkStatus.ACTIVE:
                raise ConstitutionalViolationError(
                    f"Safety Rule 2: Target EU identifier '{target}' not found or inactive "
                    f"in validated reference set version '{reference_set.version}'."
                )

    def evaluate_facts(self, context: IncidentFactContext) -> EUFactEvaluationResult:
        """Run core deterministic fact evaluators for nexus, AI-system, roles, timing, and gaps."""
        ref_id = getattr(self.reference_set, "reference_set_id", None) or DEFAULT_EU_REF_ID
        return evaluate_eu_fact_context(context, reference_set_id=ref_id)

    def evaluate_conceptual(self, context: IncidentFactContext) -> EUConceptualEvaluationResult:
        """Run deterministic conceptual relevance evaluators across Article 5, Annex III, 50, GPAI, ops."""
        ref_id = getattr(self.reference_set, "reference_set_id", None) or DEFAULT_EU_REF_ID
        return evaluate_eu_conceptual_context(
            context,
            reference_set_id=ref_id,
            custom_rules=self.conceptual_rules,
        )

    def screen_incident(self, context: IncidentFactContext) -> EULegalRelevanceScreenSchema:
        """Deterministically screen an incident fact context and assemble an immutable screen schema.

        Args:
            context: IncidentFactContext with verified evidence records, claims, known facts, and unknowns.

        Returns:
            Validated EULegalRelevanceScreenSchema in PENDING_REVIEW state.
        """
        ref_id = getattr(self.reference_set, "reference_set_id", None) or DEFAULT_EU_REF_ID

        # Safety Rule 1: Zero evidence records = Zero affirmative findings (Epistemic Modesty)
        if not context.evidence_records:
            modesty_rationale = "Screening cannot proceed due to absence of verified evidence records."
            validate_no_legal_language(modesty_rationale, field_name="modesty_rationale")
            return EULegalRelevanceScreenSchema(
                incident_id=context.incident_id,
                reference_set_id=ref_id,
                screen_version="1.0.0",
                status=EUScreenStatus.PENDING_REVIEW,
                relevance_level=EURelevanceLevel.INSUFFICIENT_INFORMATION,
                nexus_assessment=EUNexusAssessment.INSUFFICIENT_NEXUS_INFORMATION,
                ai_system_context="INSUFFICIENT_INFORMATION",
                actor_roles=[],
                actor_role_confidence=EUActorRoleConfidence.UNKNOWN,
                conceptual_risk_areas=[],
                potentially_relevant_reference_ids=[],
                operational_relevance_areas=[],
                serious_incident_relevance=EUSeriousIncidentRelevance.INSUFFICIENT_INFORMATION,
                timing_assessment=EUTimingAssessment.NOT_ASSESSED,
                known_facts=[],
                unknowns=["No verified incident evidence records available for screening."],
                disputed_facts=[],
                missing_facts=["Verified primary or observational evidence records"],
                follow_up_questions=["Are there documented evidence records verifying the reported incident events?"],
                rationale=modesty_rationale,
                confidence=GovernanceConfidence.INSUFFICIENT,
                disclaimer_version=EU_AI_ACT_DISCLAIMER_VERSION,
                disclaimer_text=EU_AI_ACT_DISCLAIMER_V2,
                evidence_ids=[],
                rule_traces=[],
                generated_by="EURelevanceScreeningEngine/1.0",
                metadata_json={"conceptual_findings": []},
            )

        # 1. Evaluate Core Factual Context
        fact_res = self.evaluate_facts(context)

        # 2. Evaluate Conceptual Relevance
        conceptual_res = self.evaluate_conceptual(context)

        # Safety Rule 2: Ensure all findings target validated reference controls
        for finding in conceptual_res.findings:
            if finding.reference_id not in self._control_index:
                raise ConstitutionalViolationError(
                    f"Safety Rule 2: Finding references unvalidated control '{finding.reference_id}'."
                )

        # 3. Aggregate Reference Identifiers & Categories
        matched_ref_ids: set[str] = set()

        # Include nexus and AI system foundational controls if affirmative
        if fact_res.nexus_assessment == EUNexusAssessment.POSSIBLE_EU_NEXUS:
            if EU_ART_2_IDENTIFIER in self._control_index:
                matched_ref_ids.add(EU_ART_2_IDENTIFIER)

        if fact_res.ai_system_context.value == "MEETS_DEFINITION":
            if EU_ART_3_1_IDENTIFIER in self._control_index:
                matched_ref_ids.add(EU_ART_3_1_IDENTIFIER)

        for finding in conceptual_res.findings:
            matched_ref_ids.add(finding.reference_id)
            # Add parent control if defined in reference set
            parent_id = self._parent_map.get(finding.reference_id)
            if parent_id and parent_id in self._control_index:
                matched_ref_ids.add(parent_id)

        sorted_ref_ids = sorted(list(matched_ref_ids))

        # 4. Resolve Informational Relevance Level
        has_affirmative_findings = any(
            f.relevance_level in {
                EUConceptualRelevanceLevel.POTENTIALLY_RELEVANT_FOR_QUALIFIED_REVIEW,
                EUConceptualRelevanceLevel.CONCEPTUALLY_RELEVANT,
            }
            for f in conceptual_res.findings
        )

        if has_affirmative_findings:
            relevance_level = EURelevanceLevel.CONCEPTUAL_RELEVANCE
        elif fact_res.nexus_assessment == EUNexusAssessment.NO_EU_NEXUS_IDENTIFIED:
            relevance_level = EURelevanceLevel.OUTSIDE_APPARENT_SCOPE
        else:
            relevance_level = EURelevanceLevel.INSUFFICIENT_INFORMATION

        # 5. Deduplicate and Harmonize Known Facts, Unknowns, and Disputed Facts
        dedup_known: list[str] = []
        for kf in fact_res.known_facts + [item for f in conceptual_res.findings for item in f.known_facts]:
            if kf and kf not in dedup_known:
                dedup_known.append(kf)

        dedup_unknowns: list[str] = []
        for unk in fact_res.unknowns + [item for f in conceptual_res.findings for item in f.unknowns]:
            if unk and unk not in dedup_unknowns:
                dedup_unknowns.append(unk)

        dedup_disputed: list[str] = []
        for df in fact_res.disputed_facts + list(context.disputed_facts) + [item for f in conceptual_res.findings for item in f.disputed_facts]:
            if df and df not in dedup_disputed:
                dedup_disputed.append(df)

        # 6. Orthogonal Governance Confidence Calculation
        if dedup_disputed or "disputed" in context.fact_tags:
            screen_confidence = GovernanceConfidence.LOW
        elif any(ev.get("corroboration_status") == "FULLY_CORROBORATED" for ev in context.evidence_records):
            screen_confidence = GovernanceConfidence.HIGH
        elif dedup_unknowns:
            screen_confidence = GovernanceConfidence.MEDIUM
        else:
            screen_confidence = GovernanceConfidence.MEDIUM

        # 7. Synthesize Composite Rationale
        if conceptual_res.findings:
            composite_rationale = (
                f"Informational relevance screen for incident '{context.incident_id}': "
                f"Territorial nexus evaluated as {fact_res.nexus_assessment.value}; "
                f"technical context evaluated as {fact_res.ai_system_context.value}. "
                f"Evaluated {len(conceptual_res.findings)} conceptual findings across reference controls: "
                f"[{', '.join(sorted_ref_ids)}]. "
                "All findings are non-binding informational governance observations routed to PENDING_REVIEW."
            )
        else:
            composite_rationale = (
                f"Informational fact screening for incident '{context.incident_id}': "
                f"Territorial nexus evaluated as {fact_res.nexus_assessment.value}; "
                f"technical context evaluated as {fact_res.ai_system_context.value}. "
                "No direct engagement with Article 5, Annex III, Article 50, GPAI, or operational control concepts "
                "was identified in currently verified evidence."
            )

        validate_no_legal_language(composite_rationale, field_name="composite_rationale")

        # 8. Collect Rule Traces and Evidence IDs
        all_traces: list[EUScreenRuleTraceSchema] = list(fact_res.rule_traces) + list(conceptual_res.rule_traces)
        valid_evidence_ids = sorted(list({ev.get("id") for ev in context.evidence_records if ev.get("id")}))

        # 9. Formulate Final Validated Schema
        return EULegalRelevanceScreenSchema(
            incident_id=context.incident_id,
            reference_set_id=ref_id,
            screen_version="1.0.0",
            status=EUScreenStatus.PENDING_REVIEW,
            relevance_level=relevance_level,
            nexus_assessment=fact_res.nexus_assessment,
            ai_system_context=fact_res.ai_system_context.value,
            actor_roles=[r.value for r in fact_res.actor_roles],
            actor_role_confidence=fact_res.actor_role_confidence,
            conceptual_risk_areas=conceptual_res.conceptual_risk_areas,
            potentially_relevant_reference_ids=sorted_ref_ids,
            operational_relevance_areas=conceptual_res.operational_relevance_areas,
            serious_incident_relevance=conceptual_res.serious_incident_relevance,
            timing_assessment=fact_res.timing_assessment,
            known_facts=dedup_known,
            unknowns=dedup_unknowns,
            disputed_facts=dedup_disputed,
            missing_facts=list(fact_res.missing_facts),
            follow_up_questions=list(fact_res.follow_up_questions),
            rationale=composite_rationale,
            confidence=screen_confidence,
            disclaimer_version=EU_AI_ACT_DISCLAIMER_VERSION,
            disclaimer_text=EU_AI_ACT_DISCLAIMER_V2,
            evidence_ids=valid_evidence_ids,
            rule_traces=all_traces,
            generated_by="EURelevanceScreeningEngine/1.0",
            metadata_json={
                "conceptual_findings": [f.model_dump() for f in conceptual_res.findings],
            },
        )
