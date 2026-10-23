"""Strict Pydantic v2 schemas and domain models for governance framework reference sets and audit events."""

from __future__ import annotations

from datetime import date, datetime, timezone
import re
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ai_incident_monitor.domain.common import ConstitutionalViolationError
from ai_incident_monitor.governance.enums import (
    ControlLevel,
    EUActorRoleConfidence,
    EUConceptType,
    EUConceptualRelevanceLevel,
    EUEvidenceStrength,
    EUNexusAssessment,
    EURelevanceLevel,
    EUScreenStatus,
    EUSeriousIncidentRelevance,
    EUTimingAssessment,
    FrameworkCode,
    FrameworkStatus,
    GovernanceAuditEventType,
    GovernanceConfidence,
    MappingStatus,
    NISTApplicability,
    OECDApplicability,
    SensitiveDomain,
)

# Immutable statutory disclaimers mandated by Constitutional Rules 10 & 11 and LGL-001/LGL-002
EU_AI_ACT_STATUTORY_DISCLAIMER: str = (
    "INFORMATIONAL SCREENING ONLY — NOT LEGAL ADVICE. This assessment reflects an "
    "automated preliminary screening of reported incident facts against Regulation (EU) "
    "2024/1689 concepts. It does not constitute a judicial, regulatory, or professional "
    "legal determination of non-compliance, liability, or statutory applicability. "
    "Absence of judicial adjudication precludes any finding of breach."
)

EU_AI_ACT_DISCLAIMER_VERSION: str = "2024-1689-v2"
EU_AI_ACT_DISCLAIMER_V2: str = (
    "Informational governance screen only. This assessment is based on currently recorded "
    "incident evidence and is not legal advice, a legal determination, or a finding of "
    "compliance or noncompliance. Applicability of the EU AI Act depends on facts, "
    "jurisdiction, role, intended purpose, timing, and other circumstances that may be "
    "incomplete or disputed. Qualified legal counsel should assess any legal obligations."
)

SHA256_HEX_REGEX = re.compile(r"^[a-f0-9]{64}$")
URL_SCHEME_REGEX = re.compile(r"^https?://[^\s/$.?#].[^\s]*$")


class FrameworkControlSchema(BaseModel):
    """Schema for a single principle, function, category, subcategory, or article node."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    external_identifier: str = Field(
        min_length=1,
        max_length=64,
        description="Unique, authoritative external identifier (e.g., OECD-P1.2, NIST-GOVERN-1.1)",
    )
    parent_identifier: Optional[str] = Field(
        default=None,
        max_length=64,
        description="External identifier of the parent node, or None if top-level",
    )
    title: str = Field(
        min_length=1,
        max_length=255,
        description="Concise official title of the principle or control",
    )
    description: str = Field(
        min_length=1,
        description="Official text or neutral summary of the principle/control",
    )
    control_level: ControlLevel = Field(
        description="Structural granularity level (PRINCIPLE, FUNCTION, CATEGORY, SUBCATEGORY, ARTICLE, ANNEX)",
    )
    framework_function: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Framework function grouping (e.g., GOVERN, MAP, MEASURE, MANAGE)",
    )
    category: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Category classification string",
    )
    subcategory: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Subcategory classification string",
    )
    article_number: Optional[str] = Field(
        default=None,
        max_length=30,
        description="Statutory article or section citation (e.g. Article 5(1)(a))",
    )
    effective_date: Optional[date] = Field(
        default=None,
        description="Statutory or administrative effective date if applicable",
    )
    applicability_notes: Optional[str] = Field(
        default=None,
        description="Neutral explanatory notes regarding relevance criteria",
    )
    source_locator: str = Field(
        min_length=1,
        max_length=255,
        description="Exact pinpoint citation in official publication (MANDATORY)",
    )
    status: FrameworkStatus = Field(
        default=FrameworkStatus.ACTIVE,
        description="Lifecycle status of this control node",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Extensible metadata payload",
    )


class FrameworkReferenceSetSchema(BaseModel):
    """Schema for a complete, versioned framework reference set."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    framework_code: FrameworkCode = Field(
        description="Approved framework enumeration code",
    )
    framework_name: str = Field(
        min_length=1,
        max_length=255,
        description="Full formal name of the framework",
    )
    version: str = Field(
        min_length=1,
        max_length=30,
        description="Version or statutory citation identifier",
    )
    source_url: str = Field(
        description="Official publication URL",
    )
    publisher: str = Field(
        min_length=1,
        max_length=100,
        description="Authoritative publisher organization",
    )
    retrieved_at_utc: datetime = Field(
        description="UTC timestamp when reference text was retrieved",
    )
    verified_at_utc: datetime = Field(
        description="UTC timestamp of human verification",
    )
    verified_by: str = Field(
        min_length=1,
        max_length=64,
        description="Identifier of authorized human verifier",
    )
    license_notes: Optional[str] = Field(
        default=None,
        description="Copyright or open government license terms",
    )
    status: FrameworkStatus = Field(
        default=FrameworkStatus.ACTIVE,
        description="Reference set lifecycle status",
    )
    supersedes_reference_set_id: Optional[str] = Field(
        default=None,
        max_length=64,
        description="ID of previously active reference set if superseding",
    )
    controls: list[FrameworkControlSchema] = Field(
        min_length=1,
        description="List of all control nodes belonging to this reference set",
    )

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, v: str) -> str:
        if not URL_SCHEME_REGEX.match(v):
            raise ValueError(f"Invalid official_source_url: '{v}' must be an http or https URL.")
        return v

    @model_validator(mode="after")
    def validate_controls_integrity(self) -> FrameworkReferenceSetSchema:
        """Enforce identifier uniqueness and strict parent reference validity."""
        seen_ids: set[str] = set()
        for ctrl in self.controls:
            if ctrl.external_identifier in seen_ids:
                raise ValueError(
                    f"Duplicate external_identifier '{ctrl.external_identifier}' found in framework '{self.framework_code}'."
                )
            seen_ids.add(ctrl.external_identifier)

        for ctrl in self.controls:
            if ctrl.parent_identifier is not None:
                if ctrl.parent_identifier == ctrl.external_identifier:
                    raise ValueError(
                        f"Control '{ctrl.external_identifier}' cannot reference itself as parent."
                    )
                if ctrl.parent_identifier not in seen_ids:
                    raise ValueError(
                        f"Control '{ctrl.external_identifier}' references unknown parent_identifier "
                        f"'{ctrl.parent_identifier}' in framework '{self.framework_code}'."
                    )

        return self


class ManifestEntrySchema(BaseModel):
    """Schema for a single framework entry in frameworks/manifest.json."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    framework_code: FrameworkCode
    version: str = Field(min_length=1, max_length=30)
    file_path: str = Field(min_length=1)
    content_sha256: str = Field(description="SHA-256 of raw UTF-8 on-disk YAML bytes")
    publisher: str = Field(min_length=1, max_length=100)
    official_source_url: str
    retrieved_at_utc: datetime
    verified_at_utc: datetime
    verified_by: str = Field(min_length=1, max_length=64)
    license_notes: Optional[str] = None

    @field_validator("content_sha256")
    @classmethod
    def validate_sha256(cls, v: str) -> str:
        if not SHA256_HEX_REGEX.match(v):
            raise ValueError(f"Invalid content_sha256: '{v}' must be a 64-character lowercase hex string.")
        return v

    @field_validator("official_source_url")
    @classmethod
    def validate_official_url(cls, v: str) -> str:
        if not URL_SCHEME_REGEX.match(v):
            raise ValueError(f"Invalid official_source_url: '{v}' must be an http or https URL.")
        return v


class FrameworkManifestSchema(BaseModel):
    """Schema for the top-level frameworks/manifest.json file."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    manifest_version: str = Field(min_length=1)
    updated_at_utc: datetime
    hashing_methodology: str = Field(min_length=1)
    frameworks: list[ManifestEntrySchema] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_manifest_uniqueness(self) -> FrameworkManifestSchema:
        seen_codes: set[FrameworkCode] = set()
        seen_paths: set[str] = set()
        for entry in self.frameworks:
            if entry.framework_code in seen_codes:
                raise ValueError(f"Duplicate framework_code '{entry.framework_code}' in manifest.")
            seen_codes.add(entry.framework_code)

            if entry.file_path in seen_paths:
                raise ValueError(f"Duplicate file_path '{entry.file_path}' in manifest.")
            seen_paths.add(entry.file_path)

        return self


class GovernanceActorIdentity(BaseModel):
    """Authenticated actor performing a governance state transition or review."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    actor_id: str = Field(min_length=1, max_length=64)
    is_human: bool = Field(description="Must be True for review approvals; LLMs cannot approve themselves")
    role: Optional[str] = Field(default=None, max_length=64)


class GovernanceAuditEvent(BaseModel):
    """Immutable audit record tracking a governance transition or review action."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1, max_length=64)
    entity_type: str = Field(min_length=1, max_length=64)
    entity_id: str = Field(min_length=1, max_length=64)
    transition_type: GovernanceAuditEventType
    actor: GovernanceActorIdentity
    timestamp_utc: datetime
    before_state_digest: Optional[str] = Field(
        default=None,
        description="SHA-256 digest of before state JSON, or None for initial creation",
    )
    after_state_digest: str = Field(
        description="SHA-256 digest of after state JSON",
    )
    event_hash: str = Field(
        description="SHA-256 of canonical event payload chained to previous_event_hash",
    )
    previous_event_hash: Optional[str] = Field(
        default=None,
        description="SHA-256 of previous event in sequence, or None for genesis event",
    )
    details: dict[str, Any] = Field(default_factory=dict)

    @field_validator("after_state_digest", "event_hash")
    @classmethod
    def validate_event_hashes(cls, v: str) -> str:
        if not SHA256_HEX_REGEX.match(v):
            raise ValueError(f"Invalid hash '{v}': must be 64-character lowercase hex.")
        return v


# ------------------------------------------------------------------------------
# Increment 2B: Governance Mapping Engine Schemas
# ------------------------------------------------------------------------------

PROHIBITED_LEGAL_TERMS: frozenset[str] = frozenset({
    "violation",
    "violations",
    "breach",
    "breaches",
    "illegal",
    "unlawful",
    "compliant",
    "noncompliant",
    "non-compliant",
    "statutory duty",
    "statutory duties",
})

PROHIBITED_LEGAL_REGEX = re.compile(
    r"\b(violation|violations|breach|breaches|illegal|unlawful|compliant|noncompliant|non-compliant|statutory\s+dut(?:y|ies))\b",
    re.IGNORECASE,
)


def validate_no_legal_language(text: Optional[str], field_name: str = "text") -> None:
    """Validate that text does not contain prohibited legal determination terminology per Safety Rule 7."""
    if not text:
        return
    match = PROHIBITED_LEGAL_REGEX.search(text)
    if match:
        raise ValueError(
            f"Prohibited legal determination language detected in {field_name}: '{match.group(0)}'. "
            "Governance mapping rationales must remain non-judicial relevance observations only."
        )


class IncidentFactContext(BaseModel):
    """Structured incident context and evidence payload passed into the governance mapping engine."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    incident_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=255)
    summary: str = Field(default="")
    claims: list[dict[str, Any]] = Field(default_factory=list)
    evidence_records: list[dict[str, Any]] = Field(default_factory=list)
    known_facts: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    disputed_facts: list[str] = Field(default_factory=list)
    sensitive_domains: list[SensitiveDomain] = Field(default_factory=list)
    fact_tags: list[str] = Field(default_factory=list)
    system_context: dict[str, Any] = Field(default_factory=dict)
    incident_date: Optional[date] = Field(
        default=None,
        description="Verified or reported date of incident occurrence if established",
    )


class ConfidenceFactorBreakdown(BaseModel):
    """Factor-by-factor breakdown of confidence calculation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    score: float = Field(ge=0.0, le=100.0)
    level: GovernanceConfidence
    evidence_count: int = Field(ge=0)
    directness_score: float = Field(ge=0.0)
    corroboration_score: float = Field(ge=0.0)
    specificity_score: float = Field(ge=0.0)
    unknowns_penalty: float = Field(ge=0.0)
    disputed_penalty: float = Field(ge=0.0)
    granularity_penalty: float = Field(ge=0.0)
    rationale: str = Field(min_length=1)


class ReviewGateEvaluation(BaseModel):
    """Evaluation result for review state machine routing."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: MappingStatus
    gate_triggers: list[str] = Field(default_factory=list)
    requires_human_review: bool
    reason: str


class MappingRuleMetadata(BaseModel):
    """Typed metadata describing a deterministic governance mapping rule."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str = Field(min_length=1, max_length=64)
    rule_version: str = Field(min_length=1, max_length=30)
    framework_code: FrameworkCode
    target_identifier: str = Field(min_length=1, max_length=64)
    target_level: ControlLevel
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)
    prerequisite_fact_keys: list[str] = Field(default_factory=list)
    applicability: str
    parent_category_identifier: Optional[str] = None
    parent_function_identifier: Optional[str] = None


class MappingCandidate(BaseModel):
    """Structured candidate governance mapping generated deterministically by the mapping engine."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    incident_id: str = Field(min_length=1, max_length=64)
    framework_code: FrameworkCode
    reference_set_id: str = Field(min_length=1, max_length=64)
    reference_set_version: str = Field(min_length=1, max_length=30)
    framework_control_id: Optional[str] = Field(default=None, max_length=64)
    target_identifier: str = Field(min_length=1, max_length=64)
    mapping_level: ControlLevel
    applicability: str
    confidence: GovernanceConfidence
    mapping_status: MappingStatus = MappingStatus.CANDIDATE
    rule_id: str = Field(min_length=1, max_length=64)
    rule_version: str = Field(min_length=1, max_length=30)
    rationale: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    known_facts: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    disputed_facts: list[str] = Field(default_factory=list)
    recommended_control_or_follow_up: Optional[str] = None
    parent_category_identifier: Optional[str] = None
    parent_function_identifier: Optional[str] = None
    review_gate_triggers: list[str] = Field(default_factory=list)
    confidence_breakdown: Optional[ConfidenceFactorBreakdown] = None
    generated_by: str = Field(default="DeterministicGovernanceEngine/1.0", max_length=64)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("evidence_ids")
    @classmethod
    def validate_evidence_ids_non_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("Safety Rule 1: Every mapping must contain one or more evidence references.")
        return v

    @field_validator("rationale")
    @classmethod
    def validate_rationale_legal_language(cls, v: str) -> str:
        validate_no_legal_language(v, field_name="rationale")
        return v

    @field_validator("known_facts", "unknowns", "disputed_facts")
    @classmethod
    def validate_facts_legal_language(cls, v: list[str]) -> list[str]:
        for item in v:
            validate_no_legal_language(item, field_name="fact_item")
        return v

    @field_validator("recommended_control_or_follow_up")
    @classmethod
    def validate_follow_up_legal_language(cls, v: Optional[str]) -> Optional[str]:
        validate_no_legal_language(v, field_name="recommended_control_or_follow_up")
        return v

    @model_validator(mode="after")
    def validate_nist_hierarchy_and_references(self) -> MappingCandidate:
        if self.framework_code == FrameworkCode.NIST_AI_RMF:
            if self.mapping_level == ControlLevel.SUBCATEGORY:
                if not self.parent_category_identifier:
                    raise ValueError(
                        f"NIST subcategory mapping '{self.target_identifier}' must store parent_category_identifier."
                    )
                if not self.parent_function_identifier:
                    raise ValueError(
                        f"NIST subcategory mapping '{self.target_identifier}' must store parent_function_identifier."
                    )
            elif self.mapping_level == ControlLevel.CATEGORY:
                if not self.parent_function_identifier:
                    raise ValueError(
                        f"NIST category mapping '{self.target_identifier}' must store parent_function_identifier."
                    )
        return self


# ------------------------------------------------------------------------------
# Increment 2C-1: EU Informational Screen Foundation Schemas & Guards
# ------------------------------------------------------------------------------


class OutputIneligibleError(ConstitutionalViolationError):
    """Raised when an EU AI Act screen fails output-eligibility requirements."""

    pass


class EUScreenRuleTraceSchema(BaseModel):
    """Typed trace of a deterministic screening rule evaluation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Optional[str] = None
    screen_id: Optional[str] = None
    rule_id: str = Field(min_length=1, max_length=64)
    rule_version: str = Field(min_length=1, max_length=30)
    reference_set_id: str = Field(min_length=1, max_length=64)
    matched_condition_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EULegalRelevanceScreenSchema(BaseModel):
    """Domain schema for an informational EU AI Act relevance screen."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Optional[str] = None
    incident_id: str = Field(min_length=1, max_length=64)
    reference_set_id: str = Field(min_length=1, max_length=64)
    screen_version: str = Field(default="1.0.0", max_length=30)
    status: EUScreenStatus = Field(default=EUScreenStatus.DRAFT)
    relevance_level: EURelevanceLevel = Field(default=EURelevanceLevel.INSUFFICIENT_INFORMATION)
    nexus_assessment: EUNexusAssessment = Field(default=EUNexusAssessment.INSUFFICIENT_NEXUS_INFORMATION)
    ai_system_context: str = Field(default="INSUFFICIENT_INFORMATION", max_length=40)
    actor_roles: list[str] = Field(default_factory=list)
    actor_role_confidence: EUActorRoleConfidence = Field(default=EUActorRoleConfidence.UNKNOWN)
    conceptual_risk_areas: list[str] = Field(default_factory=list)
    potentially_relevant_reference_ids: list[str] = Field(default_factory=list)
    operational_relevance_areas: list[str] = Field(default_factory=list)
    serious_incident_relevance: EUSeriousIncidentRelevance = Field(
        default=EUSeriousIncidentRelevance.INSUFFICIENT_INFORMATION
    )
    timing_assessment: EUTimingAssessment = Field(default=EUTimingAssessment.NOT_ASSESSED)
    known_facts: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    disputed_facts: list[str] = Field(default_factory=list)
    missing_facts: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    rationale: str = Field(default="")
    confidence: GovernanceConfidence = Field(default=GovernanceConfidence.INSUFFICIENT)
    disclaimer_version: str = Field(default=EU_AI_ACT_DISCLAIMER_VERSION, max_length=30)
    disclaimer_text: str = Field(default=EU_AI_ACT_DISCLAIMER_V2)
    evidence_ids: list[str] = Field(default_factory=list)
    rule_traces: list[EUScreenRuleTraceSchema] = Field(default_factory=list)
    generated_by: str = Field(default="DeterministicGovernanceEngine/1.0", max_length=64)
    reviewed_by: Optional[str] = Field(default=None, max_length=64)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reviewed_at: Optional[datetime] = None
    supersedes_screen_id: Optional[str] = None
    superseded_by_id: Optional[str] = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)

    @property
    def screen_status(self) -> EUScreenStatus:
        return self.status

    @field_validator("disclaimer_version")
    @classmethod
    def validate_disclaimer_version(cls, v: str) -> str:
        if v != EU_AI_ACT_DISCLAIMER_VERSION:
            raise ValueError(
                f"Invalid disclaimer_version '{v}': must be '{EU_AI_ACT_DISCLAIMER_VERSION}'."
            )
        return v

    @field_validator("disclaimer_text")
    @classmethod
    def validate_disclaimer_text(cls, v: str) -> str:
        if v != EU_AI_ACT_DISCLAIMER_V2:
            raise ValueError(
                "Mandatory disclaimer text mismatch: disclaimer must match approved EU_AI_ACT_DISCLAIMER_V2 exactly."
            )
        return v

    @field_validator("rationale")
    @classmethod
    def validate_screen_rationale_legal_language(cls, v: str) -> str:
        validate_no_legal_language(v, field_name="rationale")
        return v

    @field_validator("known_facts", "unknowns", "disputed_facts", "missing_facts", "follow_up_questions")
    @classmethod
    def validate_screen_facts_legal_language(cls, v: list[str]) -> list[str]:
        for item in v:
            validate_no_legal_language(item, field_name="fact_or_question_item")
        return v


class EUConceptualFinding(BaseModel):
    """Structured, evidence-grounded finding evaluating conceptual relevance to a single EU AI Act control."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str = Field(min_length=1, max_length=64)
    rule_version: str = Field(min_length=1, max_length=30)
    reference_id: str = Field(min_length=1, max_length=64)
    control_title: str = Field(min_length=1, max_length=255)
    source_locator: str = Field(min_length=1, max_length=255)
    concept_type: EUConceptType
    relevance_level: EUConceptualRelevanceLevel
    evidence_strength: EUEvidenceStrength
    evidence_ids: list[str] = Field(default_factory=list)
    known_facts: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    disputed_facts: list[str] = Field(default_factory=list)
    rationale: str = Field(min_length=1)
    matched_condition_ids: list[str] = Field(default_factory=list)
    confidence: GovernanceConfidence = Field(default=GovernanceConfidence.MEDIUM)
    review_routing: EUScreenStatus = Field(default=EUScreenStatus.PENDING_REVIEW)

    @field_validator("rationale")
    @classmethod
    def validate_finding_rationale_legal_language(cls, v: str) -> str:
        validate_no_legal_language(v, field_name="finding_rationale")
        return v

    @field_validator("known_facts", "unknowns", "disputed_facts")
    @classmethod
    def validate_finding_facts_legal_language(cls, v: list[str]) -> list[str]:
        for item in v:
            validate_no_legal_language(item, field_name="finding_fact_item")
        return v


class EUConceptualEvaluationResult(BaseModel):
    """Consolidated outcome of all EU AI Act conceptual relevance evaluations."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    incident_id: str = Field(min_length=1, max_length=64)
    reference_set_id: str = Field(default="eu-ai-act-2024-1689", max_length=64)
    reference_set_version: str = Field(default="2024/1689", max_length=30)
    reference_content_hash: str = Field(
        default="c5b25d21a4b4c7ec022f8b8c0b39dae48f1b9a96041f89ad082d5bfaff2b2d11",
        max_length=64,
    )
    findings: list[EUConceptualFinding] = Field(default_factory=list)
    rule_traces: list[EUScreenRuleTraceSchema] = Field(default_factory=list)
    conceptual_risk_areas: list[str] = Field(default_factory=list)
    potentially_relevant_reference_ids: list[str] = Field(default_factory=list)
    operational_relevance_areas: list[str] = Field(default_factory=list)
    serious_incident_relevance: EUSeriousIncidentRelevance = Field(
        default=EUSeriousIncidentRelevance.INSUFFICIENT_INFORMATION
    )
    status: EUScreenStatus = Field(default=EUScreenStatus.PENDING_REVIEW)
    rationale: str = Field(default="")

    @field_validator("rationale")
    @classmethod
    def validate_composite_rationale_legal_language(cls, v: str) -> str:
        validate_no_legal_language(v, field_name="composite_rationale")
        return v


class EUReviewerAttestationSchema(BaseModel):
    """Immutable human reviewer attestation required for informational screen approval.

    Constitutional Rules 12, 13, 14 & 15:
    Automated self-approval is forbidden. Approval of informational screens strictly requires
    an authenticated human reviewer attesting to evidence verification, neutral methodology,
    and non-legal determination status.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    attestor_id: str = Field(min_length=1, max_length=64, description="Identifier of the authenticated human reviewer")
    attestor_role: str = Field(min_length=1, max_length=64, description="Role of the authenticated reviewer")
    is_human: bool = Field(description="Must be strictly True; automated self-attestation is forbidden.")
    attested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    statement_confirmed: bool = Field(description="Confirms review of evidence and non-legal-determination status.")
    attestation_statement: str = Field(
        default=(
            "I confirm that this informational governance screen has been evaluated strictly "
            "against recorded evidence, reflects preliminary informational relevance rather "
            "than a legal determination or advice, and adheres to AI Guardians governance standards."
        )
    )
    evidence_verified: bool = Field(default=True, description="Confirms primary evidence was examined")
    linter_checked: bool = Field(default=True, description="Confirms non-legal language validation")

    @field_validator("is_human")
    @classmethod
    def validate_is_human(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("Reviewer attestation requires is_human=True; automated attestation is strictly forbidden.")
        return v

    @field_validator("statement_confirmed")
    @classmethod
    def validate_statement_confirmed(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("Reviewer attestation statement must be confirmed.")
        return v


def verify_output_eligibility(
    screen: Any,
    evidence_links: Optional[list[Any]] = None,
    reviewer_attestation: Optional[EUReviewerAttestationSchema | dict[str, Any]] = None,
    reference_set: Optional[Any] = None,
    raise_error: bool = False,
) -> tuple[bool, list[str]]:
    """Verify whether an EU informational screen satisfies output-eligibility criteria.

    Constitutional Rules 10, 11, 12, 13, 14 & 15 (Phase 5 Increment 2C-3B):
    Fails closed and blocks external/reporting output unless all 7 gates are satisfied:
    1. Approved informational state: status must be APPROVED_INFORMATIONAL.
    2. Valid immutable disclaimer: disclaimer_version == '2024-1689-v2' and disclaimer_text == EU_AI_ACT_DISCLAIMER_V2.
    3. Required evidence links: at least one primary evidence link must be linked (minimum 1 required).
    4. Required authenticated human review: reviewed_by must be non-empty and reviewed_at must be set.
    5. Required human reviewer attestation: valid EUReviewerAttestationSchema with is_human=True,
       matching attestor_id, and confirmed statement.
    6. Verified and active reference set: if reference_set is provided, it must not be stale, deprecated, or superseded.
    7. Output linter clearance: EUOutputLinter passes with zero blocking findings across all fields.
    """
    reasons: list[str] = []

    # 1. State check
    raw_status = getattr(screen, "status", None)
    if raw_status is None and isinstance(screen, dict):
        raw_status = screen.get("status")
    status_str = raw_status.value if hasattr(raw_status, "value") else str(raw_status)
    if status_str != EUScreenStatus.APPROVED_INFORMATIONAL.value:
        reasons.append(
            f"Screen status is '{status_str}'; must be '{EUScreenStatus.APPROVED_INFORMATIONAL.value}' for output eligibility."
        )

    # 2. Disclaimer check
    disclaimer_version = getattr(screen, "disclaimer_version", None)
    if disclaimer_version is None and isinstance(screen, dict):
        disclaimer_version = screen.get("disclaimer_version")
    if disclaimer_version != EU_AI_ACT_DISCLAIMER_VERSION:
        reasons.append(
            f"Invalid disclaimer version '{disclaimer_version}'; expected '{EU_AI_ACT_DISCLAIMER_VERSION}'."
        )

    disclaimer_text = getattr(screen, "disclaimer_text", None)
    if disclaimer_text is None and isinstance(screen, dict):
        disclaimer_text = screen.get("disclaimer_text")
    if disclaimer_text != EU_AI_ACT_DISCLAIMER_V2:
        reasons.append(
            "Disclaimer text has been modified or does not match mandatory EU_AI_ACT_DISCLAIMER_V2."
        )

    # 3. Evidence links check
    if evidence_links is not None:
        link_count = len(evidence_links)
    elif hasattr(screen, "evidence_links") and screen.evidence_links:
        link_count = len(screen.evidence_links)
    elif hasattr(screen, "evidence_ids") and screen.evidence_ids:
        link_count = len(screen.evidence_ids)
    elif isinstance(screen, dict):
        link_count = len(screen.get("evidence_links") or screen.get("evidence_ids") or [])
    else:
        link_count = 0

    if link_count < 1:
        reasons.append("Screen lacks required primary evidence links (minimum 1 required).")

    # 4. Human review check
    reviewed_by = getattr(screen, "reviewed_by", None)
    if reviewed_by is None and isinstance(screen, dict):
        reviewed_by = screen.get("reviewed_by")
    if not reviewed_by or not str(reviewed_by).strip():
        reasons.append("Screen lacks authenticated reviewer identity (reviewed_by).")

    reviewed_at = getattr(screen, "reviewed_at", None)
    if reviewed_at is None and isinstance(screen, dict):
        reviewed_at = screen.get("reviewed_at")
    if not reviewed_at:
        reasons.append("Screen lacks review timestamp (reviewed_at).")

    # 5. Reviewer attestation check
    metadata_json = getattr(screen, "metadata_json", {}) or {}
    if not metadata_json and isinstance(screen, dict):
        metadata_json = screen.get("metadata_json", {}) or {}

    attestation_data = reviewer_attestation or metadata_json.get("reviewer_attestation")
    if not attestation_data:
        reasons.append("Screen lacks required human reviewer attestation (reviewer_attestation).")
    else:
        try:
            if isinstance(attestation_data, EUReviewerAttestationSchema):
                attestation_obj = attestation_data
            else:
                attestation_obj = EUReviewerAttestationSchema.model_validate(attestation_data)

            if not attestation_obj.is_human:
                reasons.append(
                    "Reviewer attestation must have is_human=True; automated attestation is strictly forbidden."
                )
            if not attestation_obj.statement_confirmed:
                reasons.append("Reviewer attestation statement was not confirmed.")
            if reviewed_by and attestation_obj.attestor_id != str(reviewed_by).strip():
                reasons.append(
                    f"Attestation attestor_id '{attestation_obj.attestor_id}' does not match screen reviewed_by '{reviewed_by}'."
                )
        except Exception as exc:
            reasons.append(f"Reviewer attestation validation failed: {exc}")

    # 6. Reference set check (if reference_set is provided)
    if reference_set is not None:
        ref_status = getattr(reference_set, "status", None)
        if ref_status is None and isinstance(reference_set, dict):
            ref_status = reference_set.get("status")
        ref_status_str = ref_status.value if hasattr(ref_status, "value") else str(ref_status)

        if ref_status_str in [FrameworkStatus.SUPERSEDED.value, FrameworkStatus.DEPRECATED.value]:
            reasons.append(
                f"Screen is based on a stale or superseded reference set '{getattr(reference_set, 'id', 'unknown')}'."
            )

        ref_code = getattr(reference_set, "framework_code", None)
        if ref_code is None and isinstance(reference_set, dict):
            ref_code = reference_set.get("framework_code")
        ref_code_str = ref_code.value if hasattr(ref_code, "value") else str(ref_code)
        ref_id = str(getattr(reference_set, "id", "") or "")

        if ref_code_str != FrameworkCode.EU_AI_ACT.value and "eu-ai-act" not in ref_id:
            reasons.append(
                f"Screen references non-EU AI Act framework reference set '{ref_id}'."
            )

    # 7. Output linter check
    try:
        from ai_incident_monitor.governance.eu_output_linter import (
            EULinterResult,
            EUOutputLinter,
        )

        linter = EUOutputLinter()
        linter_report = linter.lint_screen(
            screen,
            reference_set=reference_set,
            evidence_links=evidence_links,
            check_eligibility_prerequisites=False,  # Already handled in gates 1-4 above
        )
        if not linter_report.is_clean:
            for finding in linter_report.findings:
                if finding.blocked_boolean:
                    reasons.append(
                        f"Output linter blocked ({finding.finding_code}) in {finding.field_name}: {finding.message}"
                    )
    except Exception as exc:
        reasons.append(f"Output linter execution failure (fail-closed): {exc}")

    is_eligible = len(reasons) == 0
    if not is_eligible and raise_error:
        screen_id = getattr(screen, "id", "unknown") if not isinstance(screen, dict) else screen.get("id", "unknown")
        raise OutputIneligibleError(
            f"EU Screen '{screen_id}' is ineligible for external/reporting output: "
            + "; ".join(reasons)
        )

    return is_eligible, reasons
