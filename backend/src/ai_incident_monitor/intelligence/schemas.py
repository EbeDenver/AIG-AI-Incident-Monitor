"""Strict Pydantic v2 application schema for Evidence-Grounded Incident Enrichment.

Normative Specification: Ai-incident-manager-guide.pdf (§1–§3),
amended by Section B (No-Approval Amendment: advisory quality warnings only,
no workflow gates, no reviewer keys, no attestations).
"""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, Field


class AssessmentStatus(str, Enum):
    """Overall status of the enrichment evaluation."""

    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    ADVISORY_REVIEW = "ADVISORY_REVIEW"


class ClaimClassification(str, Enum):
    """Categorical classification of an atomic claim per Constitutional Rule 3."""

    CONFIRMED_FACT = "CONFIRMED_FACT"
    ATTRIBUTED_ALLEGATION = "ATTRIBUTED_ALLEGATION"
    TECHNICAL_UNCERTAINTY = "TECHNICAL_UNCERTAINTY"
    DISPUTED_FACT = "DISPUTED_FACT"


class VerificationStatus(str, Enum):
    """Empirical verification status independent of attribution confidence."""

    VERIFIED = "VERIFIED"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    CONTESTED = "CONTESTED"
    NOT_ASSESSABLE = "NOT_ASSESSABLE"


class ConfidenceTier(str, Enum):
    """Confidence tier in attribution or evidential backing."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class AIInvolvementRole(str, Enum):
    """Demonstrated role of the AI component."""

    PRIMARY = "PRIMARY"
    CONTRIBUTING = "CONTRIBUTING"
    ENABLING = "ENABLING"
    INCIDENTAL = "INCIDENTAL"
    ALLEGED = "ALLEGED"
    NOT_ESTABLISHED = "NOT_ESTABLISHED"


class AutonomyLevel(str, Enum):
    """Degree of documented autonomy."""

    AUTONOMOUS_EXECUTION = "AUTONOMOUS_EXECUTION"
    HUMAN_DIRECTED = "HUMAN_DIRECTED"
    ASSISTIVE = "ASSISTIVE"
    UNKNOWN = "UNKNOWN"


class HumanOversightStatus(str, Enum):
    """State of human oversight observed during the incident."""

    EFFECTIVE = "EFFECTIVE"
    DEFICIENT = "DEFICIENT"
    ABSENT = "ABSENT"
    UNKNOWN = "UNKNOWN"


class CausalStatus(str, Enum):
    """Established causal link between AI behavior and observed harms."""

    CONFIRMED_CAUSE = "CONFIRMED_CAUSE"
    PROBABLE_CONTRIBUTOR = "PROBABLE_CONTRIBUTOR"
    POSSIBLE_CONTRIBUTOR = "POSSIBLE_CONTRIBUTOR"
    UNSUPPORTED_SPECULATION = "UNSUPPORTED_SPECULATION"
    CAUSALITY_NOT_ESTABLISHED = "CAUSALITY_NOT_ESTABLISHED"


class MaterialityLevel(str, Enum):
    """Materiality and significance of an uncertainty or claim."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class SourceTypeCategory(str, Enum):
    """Source provenance classification."""

    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"
    AGGREGATOR = "AGGREGATOR"


class ControlType(str, Enum):
    """Type of organizational risk control."""

    PREVENTIVE = "PREVENTIVE"
    DETECTIVE = "DETECTIVE"
    CORRECTIVE = "CORRECTIVE"


# ------------------------------------------------------------------------------
# Component Models (Resolving all object/array shapes explicitly from the guide)
# ------------------------------------------------------------------------------

class IncidentSummary(BaseModel):
    """High-level summary of reported events and verified outcomes."""

    reported_event: str = Field(
        ...,
        description="Factual summary of the event as reported in the immediate source.",
    )
    verified_outcome: Optional[str] = Field(
        default=None,
        description="Outcomes established by independent corroborating evidence, or null.",
    )
    affected_entities: list[str] = Field(
        default_factory=list,
        description="Named organizations, targets, or victim groups cited in the evidence.",
    )
    event_date: Optional[str] = Field(
        default=None,
        description="Date of occurrence in YYYY-MM-DD or YYYY format if documented, or null.",
    )
    reporting_date: Optional[str] = Field(
        default=None,
        description="Date of primary reporting or feed syndication in YYYY-MM-DD format.",
    )


class EnrichmentClaim(BaseModel):
    """Atomic claim extracted and evaluated against source evidence."""

    claim_id: str = Field(
        ...,
        description="Unique claim identifier within the dossier (e.g. C001, C002).",
    )
    statement: str = Field(
        ...,
        description="Narrowly stated factual, causal, or attributive claim.",
    )
    classification: ClaimClassification = Field(
        ...,
        description="Epistemic category: CONFIRMED_FACT, ATTRIBUTED_ALLEGATION, TECHNICAL_UNCERTAINTY, or DISPUTED_FACT.",
    )
    verification_status: VerificationStatus = Field(
        ...,
        description="Empirical status: VERIFIED, PARTIALLY_VERIFIED, UNVERIFIED, CONTESTED, or NOT_ASSESSABLE.",
    )
    confidence: ConfidenceTier = Field(
        ...,
        description="Attribution or evidential confidence: LOW, MEDIUM, or HIGH.",
    )
    supporting_evidence_ids: list[str] = Field(
        default_factory=list,
        description="Identifiers of supporting evidence items from the provenance package (e.g. ['E001']).",
    )
    contradicting_evidence_ids: list[str] = Field(
        default_factory=list,
        description="Identifiers of contradicting or conflicting evidence items, if any.",
    )
    reasoning_summary: str = Field(
        ...,
        description="Concise rationale for the assigned classification and verification status.",
    )
    advisory_review_flag: bool = Field(
        default=False,
        description="Advisory flag indicating that the claim involves material ambiguity or unverified severity (advisory warning only; no approval gate).",
    )


class AIInvolvement(BaseModel):
    """Technical evaluation of AI system involvement, autonomy, and oversight."""

    role: AIInvolvementRole = Field(
        ...,
        description="Role: PRIMARY, CONTRIBUTING, ENABLING, INCIDENTAL, ALLEGED, or NOT_ESTABLISHED.",
    )
    system_name: Optional[str] = Field(
        default=None,
        description="Documented name of the AI tool, model, or product, or null if undisclosed.",
    )
    documented_capabilities: list[str] = Field(
        default_factory=list,
        description="Specific demonstrated AI capabilities cited in the evidence (e.g. code generation, automated scanning).",
    )
    autonomy_level: AutonomyLevel = Field(
        default=AutonomyLevel.UNKNOWN,
        description="Autonomy: AUTONOMOUS_EXECUTION, HUMAN_DIRECTED, ASSISTIVE, or UNKNOWN.",
    )
    human_oversight: HumanOversightStatus = Field(
        default=HumanOversightStatus.UNKNOWN,
        description="Human oversight: EFFECTIVE, DEFICIENT, ABSENT, or UNKNOWN.",
    )
    supporting_evidence_ids: list[str] = Field(
        default_factory=list,
        description="Evidence IDs directly substantiating the AI involvement finding.",
    )
    assessment: str = Field(
        ...,
        description="Technical narrative distinguishing documented AI behavior from speculative extrapolation.",
    )


class CausalAssessment(BaseModel):
    """Rigorous causal evaluation separating correlation from demonstrated causality."""

    observed_outcomes: list[str] = Field(
        default_factory=list,
        description="Documented physical, economic, operational, or legal harms.",
    )
    reported_mechanisms: list[str] = Field(
        default_factory=list,
        description="Mechanisms through which the AI system reportedly produced or accelerated the outcome.",
    )
    supported_causal_links: list[str] = Field(
        default_factory=list,
        description="Causal connections substantiated by direct technical or judicial evidence.",
    )
    hypotheses: list[str] = Field(
        default_factory=list,
        description="Plausible but unproven explanatory hypotheses.",
    )
    alternative_explanations: list[str] = Field(
        default_factory=list,
        description="Non-AI or confounding factors (e.g. human error, existing security misconfiguration).",
    )
    causal_status: CausalStatus = Field(
        default=CausalStatus.CAUSALITY_NOT_ESTABLISHED,
        description="Causal status: CONFIRMED_CAUSE, PROBABLE_CONTRIBUTOR, POSSIBLE_CONTRIBUTOR, UNSUPPORTED_SPECULATION, or CAUSALITY_NOT_ESTABLISHED.",
    )
    confidence: ConfidenceTier = Field(
        default=ConfidenceTier.LOW,
        description="Confidence in the causal assessment based on available evidence.",
    )
    evidence_ids: list[str] = Field(
        default_factory=list,
        description="Evidence IDs supporting the causal evaluation.",
    )


class UncertaintyItem(BaseModel):
    """Identified technical, operational, or factual unknown."""

    question: str = Field(
        ...,
        description="Specific unresolved question regarding technical behavior or impact.",
    )
    materiality: MaterialityLevel = Field(
        ...,
        description="Materiality: LOW, MEDIUM, or HIGH.",
    )
    evidence_needed: str = Field(
        ...,
        description="Nature of evidence required to resolve the question (e.g. system logs, audit reports).",
    )


class DisputedFactItem(BaseModel):
    """Contested factual assertion with conflicting evidence accounts."""

    claim_id: str = Field(
        ...,
        description="Identifier of the disputed claim.",
    )
    assertion: str = Field(
        ...,
        description="The specific contested factual statement.",
    )
    conflicting_sources: list[str] = Field(
        default_factory=list,
        description="Names of sources providing conflicting accounts.",
    )
    conflicting_evidence_ids: list[str] = Field(
        default_factory=list,
        description="Evidence IDs presenting conflicting evidence.",
    )
    analysis: str = Field(
        ...,
        description="Analysis of the dispute, explaining differences in methodology, perspective, or timing.",
    )


class ProvenanceItem(BaseModel):
    """Verifiable metadata for an evidence item."""

    evidence_id: str = Field(
        ...,
        description="Unique evidence identifier (e.g. E001).",
    )
    source_title: str = Field(
        ...,
        description="Title of the source publication or document.",
    )
    publisher: str = Field(
        ...,
        description="Publishing entity or organization.",
    )
    url: Optional[str] = Field(
        default=None,
        description="Canonical URL of the source article or document.",
    )
    published_at: Optional[str] = Field(
        default=None,
        description="Publication date string if known.",
    )
    retrieved_at: Optional[str] = Field(
        default=None,
        description="Retrieval timestamp in ISO 8601 format.",
    )
    source_type: SourceTypeCategory = Field(
        default=SourceTypeCategory.AGGREGATOR,
        description="Type: PRIMARY, SECONDARY, or AGGREGATOR.",
    )
    excerpt: str = Field(
        ...,
        description="Verbatim excerpt or passage from the source supporting the claims.",
    )
    locator: Optional[str] = Field(
        default=None,
        description="Section, paragraph, or byte-offset locator within the source document.",
    )
    limitations: str = Field(
        default="No specific limitations noted.",
        description="Known limitations of the source (e.g. secondary hearsay, brief summary, corporate self-report).",
    )


class OrganizationalControlItem(BaseModel):
    """Practical preventive, detective, or corrective control."""

    risk: str = Field(
        ...,
        description="Specific organizational, technical, or governance risk addressed by the control.",
    )
    control: str = Field(
        ...,
        description="Concrete, actionable safeguard or architectural control requirement.",
    )
    control_type: ControlType = Field(
        ...,
        description="Control type: PREVENTIVE, DETECTIVE, or CORRECTIVE.",
    )
    incident_specific: bool = Field(
        default=False,
        description="True if addressing a demonstrated failure in this incident; False if a broadly applicable defense-in-depth measure.",
    )
    validation_test: str = Field(
        ...,
        description="Concrete method to test and verify the operational effectiveness of the control.",
    )
    evidence_ids: list[str] = Field(
        default_factory=list,
        description="Evidence IDs supporting the need for this control.",
    )


class DecisionMakerGuidance(BaseModel):
    """Practical guidance tailored for executive leadership and AI decision-makers."""

    key_implications: list[str] = Field(
        default_factory=list,
        description="Strategic, operational, or legal implications leadership must understand.",
    )
    decisions_to_consider: list[str] = Field(
        default_factory=list,
        description="Immediate or near-term governance and risk decisions warranted by the incident.",
    )
    evidence_required: list[str] = Field(
        default_factory=list,
        description="Data, audit telemetry, or vendor disclosures required before making informed decisions.",
    )
    effectiveness_measures: list[str] = Field(
        default_factory=list,
        description="Metrics and KPIs to measure ongoing control effectiveness.",
    )


class ConsultantGuidance(BaseModel):
    """Practical guidance tailored for AI transformation consultants and risk advisors."""

    discovery_questions: list[str] = Field(
        default_factory=list,
        description="Targeted diagnostic questions to uncover client vulnerabilities to similar incidents.",
    )
    assessment_activities: list[str] = Field(
        default_factory=list,
        description="Audit, architecture review, and penetration testing activities to assess exposure.",
    )
    architecture_considerations: list[str] = Field(
        default_factory=list,
        description="System integration, permission boundary, and workflow security patterns.",
    )
    implementation_controls: list[str] = Field(
        default_factory=list,
        description="Detailed technical requirements for safe AI system deployment.",
    )
    acceptance_criteria: list[str] = Field(
        default_factory=list,
        description="Testable criteria clients should enforce before signing off on AI deployments.",
    )


class QualityReview(BaseModel):
    """Automated quality assessment metrics (calculated independently by the application)."""

    unsupported_claim_count: int = Field(
        default=0,
        description="Count of claims lacking verifiable evidence linkages.",
    )
    unresolved_evidence_gaps: list[str] = Field(
        default_factory=list,
        description="Identified evidentiary gaps or missing citations.",
    )
    advisory_human_review_flag: bool = Field(
        default=False,
        description="Advisory flag indicating that the dossier contains material uncertainties or discrepancies (non-blocking warning; no approval gate).",
    )
    review_reasons: list[str] = Field(
        default_factory=list,
        description="Specific reasons advisory review was flagged.",
    )


# ------------------------------------------------------------------------------
# Master Dossier Container (Conforming strictly to Guide §3)
# ------------------------------------------------------------------------------

class IncidentEnrichmentDossier(BaseModel):
    """Full evidence-grounded incident enrichment dossier."""

    incident_id: str = Field(..., description="Canonical incident identifier.")
    assessment_status: AssessmentStatus = Field(
        default=AssessmentStatus.COMPLETE,
        description="Status: COMPLETE, PARTIAL, or ADVISORY_REVIEW.",
    )
    incident_summary: IncidentSummary
    claims: list[EnrichmentClaim] = Field(default_factory=list)
    ai_involvement: AIInvolvement
    causal_assessment: CausalAssessment
    uncertainties: list[UncertaintyItem] = Field(default_factory=list)
    disputed_facts: list[DisputedFactItem] = Field(default_factory=list)
    provenance: list[ProvenanceItem] = Field(default_factory=list)
    organizational_controls: list[OrganizationalControlItem] = Field(default_factory=list)
    decision_maker_guidance: DecisionMakerGuidance
    consultant_guidance: ConsultantGuidance
    quality_review: QualityReview = Field(
        default_factory=QualityReview,
        description="Automated quality assessment metrics (calculated independently by application validator).",
    )


# ------------------------------------------------------------------------------
# Backward Compatibility Models (Legacy prototype integration)
# ------------------------------------------------------------------------------

class EvidenceSufficiency(str, Enum):
    """Categorical evaluation of raw evidentiary completeness."""

    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    LIMITED_EVIDENCE = "LIMITED_EVIDENCE"


class IncidentExplanation(BaseModel):
    """Structured, evidence-grounded explanation of the incident events."""

    executive_summary: str = Field(
        ...,
        description="2-3 sentence factual executive summary of the verified event.",
    )
    event_chronology: list[str] = Field(
        default_factory=list,
        description="Chronological sequence of verified reported events.",
    )
    ai_system_role: str = Field(
        ...,
        description="Specific technical role played by the AI component, or explicit limited-evidence note.",
    )
    affected_stakeholders: list[str] = Field(
        default_factory=list,
        description="Directly impacted parties, organizations, or user groups.",
    )
    documented_consequences: list[str] = Field(
        default_factory=list,
        description="Observed and reported technical, physical, economic, or legal outcomes.",
    )
    unknowns_and_disputes: list[str] = Field(
        default_factory=list,
        description="Unresolved factual disputes, withheld information, or missing postmortem details.",
    )
    evidence_limitations: str = Field(
        default="",
        description="Explicit caveats regarding data source directness, hearsay, or brevity.",
    )
    sufficiency: EvidenceSufficiency = Field(
        default=EvidenceSufficiency.LIMITED_EVIDENCE,
        description="Qualitative assessment of raw evidence sufficiency.",
    )


class PreparednessGuidance(BaseModel):
    """Practical, actionable organizational guidance for enterprise defense and resilience."""

    applicable_profiles: list[str] = Field(
        default_factory=list,
        description="Enterprise or system profiles vulnerable to similar failure modes.",
    )
    early_warning_indicators: list[str] = Field(
        default_factory=list,
        description="Operational warning signs, telemetry anomalies, or threshold deviations.",
    )
    prioritized_preventive_controls: list[str] = Field(
        default_factory=list,
        description="High-priority technical safeguards, architecture patterns, and defense-in-depth measures.",
    )
    detection_mechanisms: list[str] = Field(
        default_factory=list,
        description="Continuous monitoring, logging, and automated alert mechanisms.",
    )
    incident_response_actions: list[str] = Field(
        default_factory=list,
        description="Immediate containment, quarantine, human escalation, and recovery protocols.",
    )
    responsible_functions: list[str] = Field(
        default_factory=list,
        description="Organizational roles and business units accountable for implementing safeguards.",
    )
    validation_methods: list[str] = Field(
        default_factory=list,
        description="Practical verification methods, chaos testing, penetration testing, or red-teaming steps.",
    )


class IncidentEnrichmentPayload(BaseModel):
    """Master structured output container for incident intelligence enrichment."""

    prompt_version: str = Field(default="1.0.0")
    explanation: IncidentExplanation
    preparedness: PreparednessGuidance
