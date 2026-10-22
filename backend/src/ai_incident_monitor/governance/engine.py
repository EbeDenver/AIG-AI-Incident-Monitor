"""Deterministic, evidence-grounded governance framework mapping engine.

Implements pure, reproducible mapping for:
- OECD AI Principles (2024 update)
- NIST AI Risk Management Framework (RMF 1.0)

Enforces non-negotiable safety rules:
- Evidence first (zero evidence = zero mapping)
- No fabricated framework references
- NIST hierarchy validation (Function -> Category -> Subcategory)
- Strict exclusion of legal/compliance conclusions
- Decoupling from AIG-ISI severity scoring
"""

from __future__ import annotations

from typing import Any, Optional

from ai_incident_monitor.domain.common import ConstitutionalViolationError
from ai_incident_monitor.governance.confidence import calculate_mapping_confidence
from ai_incident_monitor.governance.enums import (
    ControlLevel,
    FrameworkCode,
    FrameworkStatus,
    GovernanceConfidence,
    MappingStatus,
    NISTApplicability,
    OECDApplicability,
)
from ai_incident_monitor.governance.models import (
    FrameworkControlSchema,
    FrameworkReferenceSetSchema,
    IncidentFactContext,
    MappingCandidate,
    validate_no_legal_language,
)
from ai_incident_monitor.governance.review_gates import evaluate_review_gates
from ai_incident_monitor.governance.rules.nist_rules import ALL_NIST_RULES, BaseNISTRule
from ai_incident_monitor.governance.rules.oecd_rules import ALL_OECD_RULES, BaseOECDRule


class GovernanceMappingEngine:
    """Deterministic, rule-based engine mapping incident facts to OECD and NIST frameworks."""

    def __init__(
        self,
        reference_sets: dict[FrameworkCode, FrameworkReferenceSetSchema],
        oecd_rules: Optional[tuple[BaseOECDRule, ...]] = None,
        nist_rules: Optional[tuple[BaseNISTRule, ...]] = None,
    ) -> None:
        """Initialize engine with validated reference sets and rule registries.

        Args:
            reference_sets: Mapping of framework code to validated FrameworkReferenceSetSchema.
            oecd_rules: Optional custom tuple of OECD rules; defaults to ALL_OECD_RULES.
            nist_rules: Optional custom tuple of NIST rules; defaults to ALL_NIST_RULES.
        """
        self.reference_sets = reference_sets
        self.oecd_rules = oecd_rules if oecd_rules is not None else ALL_OECD_RULES
        self.nist_rules = nist_rules if nist_rules is not None else ALL_NIST_RULES

        # Index controls by (framework_code, external_identifier)
        self._control_index: dict[tuple[FrameworkCode, str], FrameworkControlSchema] = {}
        for code, ref_set in reference_sets.items():
            for ctrl in ref_set.controls:
                self._control_index[(code, ctrl.external_identifier)] = ctrl

    def map_incident(
        self,
        context: IncidentFactContext,
    ) -> list[MappingCandidate]:
        """Deterministically evaluate OECD and NIST mapping candidates for an incident.

        Args:
            context: IncidentFactContext with evidence records, claims, known facts, and unknowns.

        Returns:
            Deterministic list of MappingCandidate objects.
        """
        candidates: list[MappingCandidate] = []

        # Enforce Safety Rule 1: No evidence = No mapping
        if not context.evidence_records:
            return []

        valid_evidence_ids = {
            ev.get("id") for ev in context.evidence_records if ev.get("id")
        }
        if not valid_evidence_ids:
            return []

        # 1. Evaluate OECD Rules
        if FrameworkCode.OECD_AI_PRINCIPLES in self.reference_sets:
            ref_set_oecd = self.reference_sets[FrameworkCode.OECD_AI_PRINCIPLES]
            for rule in self.oecd_rules:
                candidate = self._evaluate_oecd_rule(rule, context, ref_set_oecd, valid_evidence_ids)
                if candidate is not None:
                    candidates.append(candidate)

        # 2. Evaluate NIST Rules
        if FrameworkCode.NIST_AI_RMF in self.reference_sets:
            ref_set_nist = self.reference_sets[FrameworkCode.NIST_AI_RMF]
            for rule in self.nist_rules:
                candidate = self._evaluate_nist_rule(rule, context, ref_set_nist, valid_evidence_ids)
                if candidate is not None:
                    candidates.append(candidate)

        return candidates

    def _evaluate_oecd_rule(
        self,
        rule: BaseOECDRule,
        context: IncidentFactContext,
        ref_set: FrameworkReferenceSetSchema,
        valid_evidence_ids: set[str],
    ) -> Optional[MappingCandidate]:
        """Evaluate a single OECD rule against context."""
        meta = rule.metadata

        # Safety Rule 2: Verify target identifier exists in official reference set
        control_key = (FrameworkCode.OECD_AI_PRINCIPLES, meta.target_identifier)
        ctrl = self._control_index.get(control_key)
        if ctrl is None or ctrl.status != FrameworkStatus.ACTIVE:
            raise ConstitutionalViolationError(
                f"Safety Rule 2: Target OECD identifier '{meta.target_identifier}' not found or inactive "
                f"in validated reference set version '{ref_set.version}'."
            )

        eval_res = rule.evaluate(context)
        if eval_res is None:
            return None

        applicability, rationale, known_facts, unknowns, disputed_facts, recommended_control = eval_res

        # Safety Rule 7: Strictly ban legal determination language
        validate_no_legal_language(rationale, field_name=f"{meta.rule_id} rationale")
        validate_no_legal_language(recommended_control, field_name=f"{meta.rule_id} recommended_control")

        # Associate relevant evidence IDs (must be from incident)
        linked_evidence_ids = sorted(list(valid_evidence_ids))

        # Calculate confidence
        confidence_breakdown = calculate_mapping_confidence(
            evidence_records=context.evidence_records,
            target_level=meta.target_level,
            has_unknowns=bool(unknowns),
            has_disputed_facts=bool(disputed_facts),
        )

        is_insufficient = applicability == OECDApplicability.INSUFFICIENT_EVIDENCE

        # Review gatekeeper
        review_eval = evaluate_review_gates(
            target_level=meta.target_level,
            confidence=confidence_breakdown.level,
            has_disputed_facts=bool(disputed_facts),
            sensitive_domains=context.sensitive_domains,
            is_insufficient_evidence=is_insufficient,
        )

        return MappingCandidate(
            incident_id=context.incident_id,
            framework_code=FrameworkCode.OECD_AI_PRINCIPLES,
            reference_set_id=f"refset_oecd_{ref_set.version}",
            reference_set_version=ref_set.version,
            framework_control_id=None,
            target_identifier=meta.target_identifier,
            mapping_level=meta.target_level,
            applicability=applicability.value,
            confidence=confidence_breakdown.level,
            mapping_status=review_eval.status,
            rule_id=meta.rule_id,
            rule_version=meta.rule_version,
            rationale=rationale,
            evidence_ids=linked_evidence_ids,
            known_facts=known_facts,
            unknowns=unknowns,
            disputed_facts=disputed_facts,
            recommended_control_or_follow_up=recommended_control,
            review_gate_triggers=review_eval.gate_triggers,
            confidence_breakdown=confidence_breakdown,
        )

    def _evaluate_nist_rule(
        self,
        rule: BaseNISTRule,
        context: IncidentFactContext,
        ref_set: FrameworkReferenceSetSchema,
        valid_evidence_ids: set[str],
    ) -> Optional[MappingCandidate]:
        """Evaluate a single NIST rule against context, enforcing strict hierarchy."""
        meta = rule.metadata

        # Safety Rule 2: Verify target identifier exists in official reference set
        control_key = (FrameworkCode.NIST_AI_RMF, meta.target_identifier)
        ctrl = self._control_index.get(control_key)
        if ctrl is None or ctrl.status != FrameworkStatus.ACTIVE:
            raise ConstitutionalViolationError(
                f"Safety Rule 2: Target NIST identifier '{meta.target_identifier}' not found or inactive "
                f"in validated reference set version '{ref_set.version}'."
            )

        # Hierarchy validation for Category and Subcategory
        parent_cat: Optional[str] = None
        parent_func: Optional[str] = None

        if meta.target_level == ControlLevel.SUBCATEGORY:
            # 1. Must have parent category in reference set
            if not ctrl.parent_identifier:
                raise ConstitutionalViolationError(
                    f"NIST subcategory '{meta.target_identifier}' missing parent_identifier in reference set."
                )
            parent_ctrl = self._control_index.get((FrameworkCode.NIST_AI_RMF, ctrl.parent_identifier))
            if parent_ctrl is None:
                raise ConstitutionalViolationError(
                    f"NIST subcategory '{meta.target_identifier}' references non-existent parent "
                    f"'{ctrl.parent_identifier}'."
                )
            parent_cat = parent_ctrl.external_identifier
            if not parent_ctrl.parent_identifier:
                raise ConstitutionalViolationError(
                    f"NIST category '{parent_ctrl.external_identifier}' missing parent function identifier."
                )
            parent_func_ctrl = self._control_index.get((FrameworkCode.NIST_AI_RMF, parent_ctrl.parent_identifier))
            if parent_func_ctrl is None:
                raise ConstitutionalViolationError(
                    f"NIST category '{parent_ctrl.external_identifier}' references non-existent parent function."
                )
            parent_func = parent_func_ctrl.external_identifier

            # Specificity constraint: Subcategories require at least one HIGHLY_SPECIFIC evidence record
            has_high_specificity = any(
                str(ev.get("specificity", "")).upper() == "HIGHLY_SPECIFIC"
                for ev in context.evidence_records
            )
            if not has_high_specificity:
                # Subcategory mapping cannot be created from broad or vague evidence
                return None

        elif meta.target_level == ControlLevel.CATEGORY:
            if not ctrl.parent_identifier:
                raise ConstitutionalViolationError(
                    f"NIST category '{meta.target_identifier}' missing parent function identifier."
                )
            parent_func_ctrl = self._control_index.get((FrameworkCode.NIST_AI_RMF, ctrl.parent_identifier))
            if parent_func_ctrl is None:
                raise ConstitutionalViolationError(
                    f"NIST category '{meta.target_identifier}' references non-existent parent function."
                )
            parent_func = parent_func_ctrl.external_identifier

        eval_res = rule.evaluate(context)
        if eval_res is None:
            return None

        applicability, rationale, known_facts, unknowns, disputed_facts, recommended_control = eval_res

        # Safety Rule 7: Strictly ban legal determination language
        validate_no_legal_language(rationale, field_name=f"{meta.rule_id} rationale")
        validate_no_legal_language(recommended_control, field_name=f"{meta.rule_id} recommended_control")

        linked_evidence_ids = sorted(list(valid_evidence_ids))

        # Calculate confidence
        confidence_breakdown = calculate_mapping_confidence(
            evidence_records=context.evidence_records,
            target_level=meta.target_level,
            has_unknowns=bool(unknowns),
            has_disputed_facts=bool(disputed_facts),
        )

        is_insufficient = applicability == NISTApplicability.INSUFFICIENT_EVIDENCE

        # Review gatekeeper
        review_eval = evaluate_review_gates(
            target_level=meta.target_level,
            confidence=confidence_breakdown.level,
            has_disputed_facts=bool(disputed_facts),
            sensitive_domains=context.sensitive_domains,
            is_insufficient_evidence=is_insufficient,
        )

        return MappingCandidate(
            incident_id=context.incident_id,
            framework_code=FrameworkCode.NIST_AI_RMF,
            reference_set_id=f"refset_nist_{ref_set.version}",
            reference_set_version=ref_set.version,
            framework_control_id=None,
            target_identifier=meta.target_identifier,
            mapping_level=meta.target_level,
            applicability=applicability.value,
            confidence=confidence_breakdown.level,
            mapping_status=review_eval.status,
            rule_id=meta.rule_id,
            rule_version=meta.rule_version,
            rationale=rationale,
            evidence_ids=linked_evidence_ids,
            known_facts=known_facts,
            unknowns=unknowns,
            disputed_facts=disputed_facts,
            recommended_control_or_follow_up=recommended_control,
            parent_category_identifier=parent_cat,
            parent_function_identifier=parent_func,
            review_gate_triggers=review_eval.gate_triggers,
            confidence_breakdown=confidence_breakdown,
        )
