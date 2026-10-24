"""Domain schemas and models for the editorial dossier pipeline.

Governing Charter: Project Constitution (Rules 1, 3, 10, 11, 12, 14, 15, 17),
ADR-001, ADR-004, ADR-014, ADR-020, PRD §4.7 (EDT-001..005, UIX-001).
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ai_incident_monitor.editorial.enums import (
    EditorialDossierStatus,
    EditorialEntryType,
    EditorialScopeType,
    EditorialValidationCode,
    EditorialValidationSeverity,
)

EDITORIAL_DISCLAIMER_VERSION: str = "editorial-v1"
EDITORIAL_DISCLAIMER_TEXT: str = (
    "Informational research dossier only. This document is compiled from recorded public reporting "
    "and observational evidence for technical research and monitoring purposes. It does not constitute "
    "legal advice, a formal regulatory finding, an adjudication of culpability, or a definitive determination "
    "of statutory compliance or noncompliance. Unverified allegations remain attributed to their respective "
    "sources and should not be construed as established facts."
)

EDITORIAL_ATTESTATION_STATEMENT: str = (
    "I confirm that I have conducted human editorial review of this dossier, verifying source attribution, "
    "factual hedging, distinction between established facts and unverified allegations, and strict non-legal "
    "language compliance in accordance with AI Guardians editorial standards."
)

SHA256_HEX_REGEX = re.compile(r"^[a-f0-9]{64}$")


def canonical_sha256(payload: Any) -> str:
    """Compute deterministic SHA-256 digest from JSON-serializable structure with sorted keys."""
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def normalize_iso_timestamp(dt: Optional[datetime]) -> Optional[str]:
    """Normalize datetime to UTC ISO string with 'Z' suffix for deterministic cross-engine hashing."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class EditorialEntryFact(BaseModel):
    """Structured fact or attributed allegation associated with an incident entry."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    statement: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    source_title: Optional[str] = None
    evidence_id: str = Field(min_length=1)
    is_allegation: bool = Field(default=False)
    attribution: str = Field(
        min_length=1,
        description="Source or reporting entity to which the claim is attributed",
    )


class EditorialEntryUnknown(BaseModel):
    """Documented epistemic void or unknown factor (Rule 2: Unknown is not zero)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    question: str = Field(min_length=1)
    domain: Optional[str] = None
    impact: Optional[str] = None


class EditorialEntryDispute(BaseModel):
    """Documented contradictory reporting or disputed factual assertion."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    topic: str = Field(min_length=1)
    position_a: str = Field(min_length=1)
    source_a: str = Field(min_length=1)
    position_b: str = Field(min_length=1)
    source_b: str = Field(min_length=1)


class EditorialDossierEntrySchema(BaseModel):
    """Structured entry representing an incident inside an editorial dossier."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    entry_id: str = Field(min_length=1, max_length=64)
    incident_id: str = Field(min_length=1, max_length=64)
    entry_order: int = Field(ge=1)
    entry_type: EditorialEntryType = Field(default=EditorialEntryType.PRIMARY)
    incident_title: str = Field(min_length=1, max_length=255)
    incident_summary: str = Field(min_length=1)
    incident_date_str: Optional[str] = None

    source_evidence_ids: list[str] = Field(default_factory=list)
    source_version_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    primary_source_url: Optional[str] = None
    primary_source_publisher: Optional[str] = None
    primary_source_published_date: Optional[str] = None

    known_facts: list[EditorialEntryFact] = Field(default_factory=list)
    unknowns: list[EditorialEntryUnknown] = Field(default_factory=list)
    disputed_claims: list[EditorialEntryDispute] = Field(default_factory=list)

    severity_tier: Optional[str] = None
    severity_score: Optional[float] = None

    eu_screen_id: Optional[str] = None
    eu_screen_status: Optional[str] = None
    eu_commentary: Optional[str] = None
    omitted_eu_reason: Optional[str] = None

    def canonical_dict(self) -> dict[str, Any]:
        """Deterministic dictionary for content hashing."""
        return {
            "entry_id": self.entry_id,
            "incident_id": self.incident_id,
            "entry_order": self.entry_order,
            "entry_type": self.entry_type.value,
            "incident_title": self.incident_title,
            "incident_summary": self.incident_summary,
            "incident_date_str": self.incident_date_str,
            "source_evidence_ids": sorted(self.source_evidence_ids),
            "source_version_hash": self.source_version_hash,
            "primary_source_url": self.primary_source_url,
            "primary_source_publisher": self.primary_source_publisher,
            "primary_source_published_date": self.primary_source_published_date,
            "known_facts": [
                {
                    "statement": f.statement,
                    "source_id": f.source_id,
                    "source_title": f.source_title,
                    "evidence_id": f.evidence_id,
                    "is_allegation": f.is_allegation,
                    "attribution": f.attribution,
                }
                for f in self.known_facts
            ],
            "unknowns": [
                {
                    "question": u.question,
                    "domain": u.domain,
                    "impact": u.impact,
                }
                for u in self.unknowns
            ],
            "disputed_claims": [
                {
                    "topic": d.topic,
                    "position_a": d.position_a,
                    "source_a": d.source_a,
                    "position_b": d.position_b,
                    "source_b": d.source_b,
                }
                for d in self.disputed_claims
            ],
            "severity_tier": self.severity_tier,
            "severity_score": self.severity_score,
            "eu_screen_id": self.eu_screen_id,
            "eu_screen_status": self.eu_screen_status,
            "eu_commentary": self.eu_commentary,
            "omitted_eu_reason": self.omitted_eu_reason,
        }


class EditorialDossierSummary(BaseModel):
    """Aggregate forensic summary of the assembled dossier."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    executive_summary: str = Field(min_length=1)
    key_themes: list[str] = Field(default_factory=list)
    total_incidents: int = Field(ge=0)
    total_evidence_links: int = Field(ge=0)
    disputed_incident_count: int = Field(ge=0)
    learning_and_prevention_themes: list[str] = Field(default_factory=list)

    def canonical_dict(self) -> dict[str, Any]:
        """Deterministic dictionary for content hashing."""
        return {
            "executive_summary": self.executive_summary,
            "key_themes": sorted(self.key_themes),
            "total_incidents": self.total_incidents,
            "total_evidence_links": self.total_evidence_links,
            "disputed_incident_count": self.disputed_incident_count,
            "learning_and_prevention_themes": sorted(self.learning_and_prevention_themes),
        }


class EditorialDossierSchema(BaseModel):
    """Domain model representing a complete editorial dossier."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1, max_length=64)
    version: int = Field(ge=1, default=1)
    title: str = Field(min_length=1, max_length=255)
    scope_type: EditorialScopeType = Field(default=EditorialScopeType.CUSTOM)
    coverage_period_start: Optional[datetime] = None
    coverage_period_end: Optional[datetime] = None
    status: EditorialDossierStatus = Field(default=EditorialDossierStatus.DRAFT)
    content_hash: Optional[str] = Field(default=None, pattern=r"^[a-f0-9]{64}$")

    disclaimer_version: str = Field(default=EDITORIAL_DISCLAIMER_VERSION)
    disclaimer_text: str = Field(default=EDITORIAL_DISCLAIMER_TEXT)
    methodology_notes: Optional[str] = None

    summary: EditorialDossierSummary
    entries: list[EditorialDossierEntrySchema] = Field(default_factory=list)
    metadata_json: dict[str, Any] = Field(default_factory=dict)

    generated_by: str = Field(default="EditorialDossierAssembler/1.0")
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    supersedes_dossier_id: Optional[str] = None
    superseded_by_id: Optional[str] = None
    rejection_reason: Optional[str] = None

    def canonical_content_dict(self) -> dict[str, Any]:
        """Deterministic canonical representation of all editorial content.

        Excludes mutable lifecycle state (e.g., reviewed_by, reviewed_at, status)
        so that the hash represents the exact editorial content being attested to.
        """
        return {
            "title": self.title,
            "scope_type": self.scope_type.value,
            "coverage_period_start": normalize_iso_timestamp(self.coverage_period_start),
            "coverage_period_end": normalize_iso_timestamp(self.coverage_period_end),
            "disclaimer_version": self.disclaimer_version,
            "disclaimer_text": self.disclaimer_text,
            "methodology_notes": self.methodology_notes,
            "summary": self.summary.canonical_dict(),
            "entries": [entry.canonical_dict() for entry in self.entries],
        }

    def compute_content_hash(self) -> str:
        """Compute the SHA-256 content hash of the canonical content."""
        return canonical_sha256(self.canonical_content_dict())


class EditorialReviewerAttestationSchema(BaseModel):
    """Immutable human reviewer attestation required for editorial dossier approval.

    Constitutional Rules 12, 14, 15:
    Automated self-approval is forbidden. Approval strictly requires an authenticated
    human reviewer attesting to factual integrity, attribution, uncertainty preservation,
    and compliance with AI Guardians editorial standards.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    reviewer_id: str = Field(min_length=1, max_length=64)
    reviewer_name: Optional[str] = Field(default=None, max_length=255)
    reviewer_role: str = Field(min_length=1, max_length=64)
    is_human: bool = Field(
        description="Must be strictly True; automated self-attestation is forbidden."
    )
    statement_confirmed: bool = Field(
        description="Confirms editorial review of attribution and non-legal-determination status."
    )
    attestation_statement: str = Field(default=EDITORIAL_ATTESTATION_STATEMENT)
    content_hash: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")
    dossier_id: str = Field(min_length=1, max_length=64)
    dossier_version: int = Field(ge=1)
    attested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_snapshots_verified: bool = Field(default=True)
    editorial_standards_verified: bool = Field(default=True)

    @field_validator("is_human")
    @classmethod
    def validate_is_human(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError(
                "Reviewer attestation requires is_human=True; automated self-approval is forbidden."
            )
        return v

    @field_validator("statement_confirmed")
    @classmethod
    def validate_statement_confirmed(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("Reviewer attestation statement must be explicitly confirmed.")
        return v


class EditorialValidationFinding(BaseModel):
    """Individual field-level validation finding."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_code: EditorialValidationCode
    severity: EditorialValidationSeverity
    field_path: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class EditorialValidationReport(BaseModel):
    """Consolidated validation report for an editorial dossier."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    is_valid: bool
    dossier_id: str
    dossier_version: int
    content_hash: Optional[str] = None
    total_findings: int
    blocking_count: int
    warning_count: int
    findings: list[EditorialValidationFinding]
    validated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EditorialCandidate(BaseModel):
    """Data transfer model for candidate incidents evaluated by EditorialSourceSelector."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    incident_id: str
    title: str
    summary: str
    incident_date_str: Optional[str] = None
    evidence_ids: list[str] = Field(default_factory=list)
    primary_source_url: Optional[str] = None
    primary_source_publisher: Optional[str] = None
    primary_source_date: Optional[str] = None
    source_version_hash: str
    severity_tier: Optional[str] = None
    severity_score: Optional[float] = None
    known_facts: list[dict[str, Any]] = Field(default_factory=list)
    unknowns: list[dict[str, Any]] = Field(default_factory=list)
    disputed_claims: list[dict[str, Any]] = Field(default_factory=list)
    eu_screen_id: Optional[str] = None
    eu_screen_status: Optional[str] = None
    eu_screen_eligible: bool = False
    eu_commentary: Optional[str] = None
    omitted_eu_reason: Optional[str] = None
    is_eligible: bool = True
    exclusion_reasons: list[str] = Field(default_factory=list)
