"""Pydantic schemas for the public read-only API consumed by external systems (e.g. Codex AI Guardians Portal).

Governing Principles:
1. Strict segregation of synthetic/mock data from live intelligence.
2. Zero server internals, zero database IDs, zero reviewer keys, zero filesystem paths.
3. WCAG AAA/AA accessible color tokens and clear categorical taxonomy.
4. Mandatory legal non-advice disclaimers on regulatory intelligence.
"""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class PublicCategoryDTO(BaseModel):
    """Accessible categorical classification metadata."""

    category_key: str = Field(..., description="Unique key for category (e.g. CYBERSECURITY).")
    display_name: str = Field(..., description="Human-readable category title.")
    short_label: str = Field(..., description="Compact category label.")
    icon: str = Field(..., description="Unicode icon symbol.")
    text_symbol: str = Field(..., description="Accessible non-emoji text badge representation.")
    description: str = Field(..., description="Detailed description of category scope.")
    border_hex: str = Field(..., description="WCAG-compliant border hex color.")
    bg_hex: str = Field(..., description="WCAG-compliant background hex color.")
    text_hex: str = Field(..., description="WCAG-compliant high-contrast text hex color.")


class PublicSourceReferenceDTO(BaseModel):
    """Attributed source reference with cryptographic provenance and retrieval metadata."""

    source_id: Optional[str] = Field(default=None, description="Stable source reference ID (e.g. SRC-001).")
    source_name: str = Field(..., description="Name of the reporting entity or publisher.")
    url: Optional[str] = Field(default=None, description="Sanitized canonical source URL.")
    epistemic_role: str = Field(..., description="Epistemic role (Primary Incident Stream, Research Context, Offline Export).")
    published_at: Optional[str] = Field(default=None, description="Publication timestamp string if available.")
    retrieval_date: Optional[str] = Field(default=None, description="Timestamp when source was retrieved/ingested.")
    content_hash: Optional[str] = Field(default=None, description="SHA-256 cryptographic digest of source payload where known.")
    locator: Optional[str] = Field(default=None, description="Section, locator, or document anchor where available.")


class PublicAtomicClaimDTO(BaseModel):
    """Granular verified claim substantiated by evidence."""

    claim_id: str = Field(..., description="Unique claim identifier.")
    assertion: str = Field(..., description="Factual claim assertion.")
    classification: str = Field(..., description="Claim classification (CONFIRMED_FACT, ATTRIBUTED_ALLEGATION, etc.).")
    verification_status: str = Field(..., description="Verification status (VERIFIED, UNVERIFIED, CONTESTED, etc.).")
    confidence: str = Field(..., description="Confidence tier (HIGH, MEDIUM, LOW).")
    supporting_evidence_ids: list[str] = Field(default_factory=list, description="IDs of evidence items substantiating this claim.")
    evidence_excerpts: list[str] = Field(default_factory=list, description="Direct excerpts from source documents grounding this claim.")
    reasoning_summary: Optional[str] = Field(default=None, description="Epistemic rationale justifying classification.")


class PublicAIInvolvementDTO(BaseModel):
    """Evaluated role and autonomy of the AI system."""

    role: str = Field(..., description="AI role: PRIMARY, CONTRIBUTING, ENABLING, INCIDENTAL, ALLEGED, or NOT_ESTABLISHED.")
    autonomy: str = Field(..., description="Autonomy: AUTONOMOUS_EXECUTION, HUMAN_DIRECTED, ASSISTIVE, or UNKNOWN.")
    human_oversight: str = Field(..., description="Oversight status: EFFECTIVE, DEFICIENT, ABSENT, or UNKNOWN.")
    assessment: str = Field(..., description="Narrative evaluation distinguishing documented AI behavior from conjecture.")


class PublicCausalAssessmentDTO(BaseModel):
    """Evidence-grounded causal evaluation."""

    causal_status: str = Field(..., description="Causal status (CONFIRMED_CAUSE, PROBABLE_CONTRIBUTOR, etc.).")
    confidence: str = Field(..., description="Confidence in causal finding (HIGH, MEDIUM, LOW).")
    observed_outcomes: list[str] = Field(default_factory=list, description="Documented physical, economic, or legal harms.")
    reported_mechanisms: list[str] = Field(default_factory=list, description="Mechanisms through which AI reportedly produced harm.")
    supported_causal_links: list[str] = Field(default_factory=list, description="Substantiated causal links.")
    alternative_explanations: list[str] = Field(default_factory=list, description="Non-AI confounding factors.")


class PublicOrganizationalControlDTO(BaseModel):
    """Concrete organizational safeguard or control."""

    risk: str = Field(..., description="Specific organizational, technical, or governance risk.")
    control: str = Field(..., description="Concrete, actionable safeguard or architectural requirement.")
    control_type: str = Field(..., description="Type: PREVENTIVE, DETECTIVE, or CORRECTIVE.")
    incident_specific: bool = Field(default=False, description="Whether control directly addresses specific incident mechanisms.")


class PublicDecisionMakerGuidanceDTO(BaseModel):
    """Executive and board guidance conforming to Guide §3."""

    executive_summary: str = Field(default="", description="Concise non-technical briefing for leadership.")
    board_briefing: str = Field(default="", description="Strategic governance briefing.")
    strategic_priorities: list[str] = Field(default_factory=list, description="High-priority organizational remediation items.")
    budget_allocation_recommendations: list[str] = Field(default_factory=list, description="Recommended resource investments.")
    key_implications: list[str] = Field(default_factory=list, description="Strategic, operational, or legal implications leadership must understand.")
    decisions_to_consider: list[str] = Field(default_factory=list, description="Immediate or near-term governance and risk decisions warranted by the incident.")
    evidence_required: list[str] = Field(default_factory=list, description="Data, audit telemetry, or vendor disclosures required before making informed decisions.")
    effectiveness_measures: list[str] = Field(default_factory=list, description="Metrics and KPIs to measure ongoing control effectiveness.")


class PublicPractitionerGuidanceDTO(BaseModel):
    """Technical and operational engineering guidance conforming to Guide §3."""

    immediate_actions: list[str] = Field(default_factory=list, description="First-24-hour containment actions.")
    short_term_hardening: list[str] = Field(default_factory=list, description="30-day architectural hardening steps.")
    architectural_guidance: list[str] = Field(default_factory=list, description="Systemic design patterns.")
    testing_requirements: list[str] = Field(default_factory=list, description="Specific evaluations, red-teaming, or stress tests.")
    discovery_questions: list[str] = Field(default_factory=list, description="Targeted diagnostic questions to uncover client vulnerabilities.")
    assessment_activities: list[str] = Field(default_factory=list, description="Audit, architecture review, and penetration testing activities.")
    architecture_considerations: list[str] = Field(default_factory=list, description="System integration, permission boundary, and workflow security patterns.")
    implementation_controls: list[str] = Field(default_factory=list, description="Detailed technical requirements for safe AI system deployment.")
    acceptance_criteria: list[str] = Field(default_factory=list, description="Testable criteria clients should enforce before signing off on AI deployments.")


class PublicIntelligenceDTO(BaseModel):
    """Structured incident intelligence dossier."""

    is_available: bool = Field(..., description="Whether intelligence is available.")
    model_provider: Optional[str] = Field(default=None, description="Provider: claude, gemini, or mock.")
    model_name: Optional[str] = Field(default=None, description="Exact model ID invoked.")
    generated_at: Optional[str] = Field(default=None, description="Generation timestamp in ISO format.")
    is_synthetic_mock: bool = Field(default=False, description="True if output was synthetically generated by mock heuristics.")
    assessment_status: str = Field(default="COMPLETE", description="COMPLETE, PARTIAL, or ADVISORY_REVIEW.")
    advisory_review_flag: bool = Field(default=False, description="Advisory quality flag indicating unresolved uncertainties.")
    review_reasons: list[str] = Field(default_factory=list, description="Reasons for advisory quality flag.")
    summary: Optional[str] = Field(default=None, description="Intelligence executive summary.")
    ai_involvement: Optional[PublicAIInvolvementDTO] = Field(default=None, description="AI involvement breakdown.")
    causal_assessment: Optional[PublicCausalAssessmentDTO] = Field(default=None, description="Causal assessment breakdown.")
    atomic_claims: list[PublicAtomicClaimDTO] = Field(default_factory=list, description="Atomic claims list.")
    organizational_controls: list[PublicOrganizationalControlDTO] = Field(default_factory=list, description="Organizational safeguards.")
    decision_maker_guidance: Optional[PublicDecisionMakerGuidanceDTO] = Field(default=None, description="Executive guidance.")
    practitioner_guidance: Optional[PublicPractitionerGuidanceDTO] = Field(default=None, description="Technical guidance.")


class PublicEUAIActGapDTO(BaseModel):
    """Specific compliance gap finding under EU AI Act."""

    article: str = Field(..., description="EU AI Act Article reference (e.g. Article 14 Human Oversight).")
    gap_status: str = Field(..., description="DOCUMENTED_GAP, POTENTIAL_GAP, NO_GAP_DEMONSTRATED, INSUFFICIENT_EVIDENCE, or NOT_YET_APPLICABLE.")
    finding: str = Field(..., description="Analytical finding explaining the compliance gap or status.")


class PublicEUAIActDTO(BaseModel):
    """EU AI Act regulatory compliance assessment."""

    is_available: bool = Field(..., description="Whether EU AI Act assessment is available.")
    jurisdiction_status: str = Field(..., description="APPLICABLE, NOT_APPLICABLE, or UNDETERMINED under Article 2.")
    classification: str = Field(..., description="PROHIBITED_PRACTICE, HIGH_RISK_ANNEX_I, HIGH_RISK_ANNEX_III, TRANSPARENCY_ONLY, GPAI_MODEL, etc.")
    annex_reference: Optional[str] = Field(default=None, description="Annex I or III reference if classified as high-risk.")
    article_73_serious_incident: Optional[dict[str, Any]] = Field(default=None, description="Article 73 serious incident evaluation.")
    enforcement_status: str = Field(..., description="ACTIVE_LAW, NOT_YET_APPLICABLE, or PENDING under November 2026 baseline.")
    enforcement_notes: str = Field(..., description="Timeline guidance explaining enforceability.")
    assessment_date: Optional[str] = Field(default=None, description="Timestamp of EU regulatory assessment in ISO format.")
    legal_framework_version: str = Field(
        default="EU Regulation 2024/1689 (AI Act) - November 2026 Baseline",
        description="Statutory reference baseline version.",
    )
    governance_sources: list[str] = Field(
        default_factory=list,
        description="Statutory articles, recitals, and official guidance references considered.",
    )
    qualifications_and_limitations: list[str] = Field(
        default_factory=list,
        description="Epistemic limitations, caveats, or missing factual disclosures affecting assessment.",
    )
    review_status: str = Field(
        default="AUTOMATED_STATUTORY_TRIAGE",
        description="Descriptive regulatory assessment status (e.g. AUTOMATED_STATUTORY_TRIAGE).",
    )
    identified_gaps: list[PublicEUAIActGapDTO] = Field(default_factory=list, description="Identified compliance gaps.")
    disclaimer: str = Field(
        default="This automated regulatory impact assessment is generated for technical research and compliance preparedness only. It does not constitute formal legal advice, regulatory determination, or EU conformity certification.",
        description="Mandatory legal disclaimer."
    )


class CatalogFreshnessDTO(BaseModel):
    """Catalog synchronization and data freshness metadata."""

    latest_ingestion_time: Optional[str] = Field(default=None, description="ISO timestamp of most recently ingested incident.")
    total_sources_count: int = Field(default=0, description="Total number of attributed primary sources in catalog.")
    catalog_version: str = Field(default="2.0.0", description="Contract and catalog specification version.")
    database_environment: str = Field(default="development", description="Underlying database environment ('production' or 'development').")


class PublicIncidentSummaryDTO(BaseModel):
    """Lightweight summary of an incident for listing and catalog explorer views."""

    incident_id: str = Field(..., description="Canonical incident identifier (e.g. INC-2026-3DC33C).")
    title: str = Field(..., description="Incident title.")
    summary: str = Field(..., description="Factual incident summary.")
    event_date: Optional[str] = Field(default=None, description="Event date string (YYYY-MM-DD) if known.")
    discovered_date: Optional[str] = Field(default=None, description="Date or timestamp incident was recorded.")
    primary_category: str = Field(..., description="Primary category key.")
    category_display_name: str = Field(..., description="Human-readable category title.")
    category_color: str = Field(..., description="Category border and accent hex color.")
    category_bg_color: str = Field(..., description="Category background hex color.")
    severity: str = Field(..., description="Assessed severity (CRITICAL, HIGH, MEDIUM, LOW, NOT_ASSESSED).")
    status: str = Field(..., description="Investigation status.")
    has_intelligence: bool = Field(..., description="Whether intelligence is available (excluding mock if filtered).")
    intelligence_status: str = Field(..., description="Status badge: LIVE_ENRICHED, SYNTHETIC_MOCK, PENDING_ANALYSIS, NOT_ENRICHED.")
    is_synthetic_mock: bool = Field(default=False, description="True if enrichment is from mock heuristics.")
    sources_count: int = Field(default=0, description="Number of independent source references.")


class PublicIncidentListResponse(BaseModel):
    """Paginated collection of incident summaries."""

    items: list[PublicIncidentSummaryDTO] = Field(..., description="List of incidents on current page.")
    total: int = Field(..., description="Total incidents matching filter criteria.")
    page: int = Field(..., description="Current page number.")
    page_size: int = Field(..., description="Page size limit.")
    total_pages: int = Field(..., description="Total number of pages.")
    freshness: Optional[CatalogFreshnessDTO] = Field(default=None, description="Catalog synchronization and freshness metadata.")


class PublicIncidentDetailDTO(PublicIncidentSummaryDTO):
    """Comprehensive incident detail view with intelligence and regulatory assessments."""

    sources: list[PublicSourceReferenceDTO] = Field(default_factory=list, description="Independent source references.")
    unknowns: list[str] = Field(default_factory=list, description="Factual uncertainties identified during investigation.")
    intelligence: Optional[PublicIntelligenceDTO] = Field(default=None, description="Detailed LLM intelligence dossier if available.")
    eu_ai_act_compliance: Optional[PublicEUAIActDTO] = Field(default=None, description="EU AI Act regulatory compliance assessment.")
