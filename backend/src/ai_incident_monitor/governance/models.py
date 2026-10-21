"""Strict Pydantic v2 schemas and domain models for governance framework reference sets and audit events."""

from __future__ import annotations

from datetime import date, datetime
import re
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ai_incident_monitor.governance.enums import (
    ControlLevel,
    FrameworkCode,
    FrameworkStatus,
    GovernanceAuditEventType,
)

# Immutable statutory disclaimer mandated by Constitutional Rules 10 & 11 and LGL-001
EU_AI_ACT_STATUTORY_DISCLAIMER: str = (
    "INFORMATIONAL SCREENING ONLY — NOT LEGAL ADVICE. This assessment reflects an "
    "automated preliminary screening of reported incident facts against Regulation (EU) "
    "2024/1689 concepts. It does not constitute a judicial, regulatory, or professional "
    "legal determination of non-compliance, liability, or statutory applicability. "
    "Absence of judicial adjudication precludes any finding of breach."
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
