"""Controlled enumerations for the editorial pipeline and review workflow.

Enforces Constitutional Rules 1, 3, 10, 12, 14, 15, and 17.
"""

from __future__ import annotations

from enum import Enum


class EditorialDossierStatus(str, Enum):
    """Lifecycle status of an editorial dossier."""

    DRAFT = "DRAFT"
    ASSEMBLED = "ASSEMBLED"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED_INFORMATIONAL = "APPROVED_INFORMATIONAL"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class EditorialEntryType(str, Enum):
    """Classification of an incident entry within a dossier."""

    PRIMARY = "PRIMARY"
    RELATED = "RELATED"
    CONTEXT = "CONTEXT"


class EditorialScopeType(str, Enum):
    """Scope and periodic grouping of an editorial dossier."""

    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    INCIDENT_DEEP_DIVE = "INCIDENT_DEEP_DIVE"
    CUSTOM = "CUSTOM"


class EditorialReviewAction(str, Enum):
    """Human review actions performed on an editorial dossier."""

    SUBMIT_FOR_REVIEW = "SUBMIT_FOR_REVIEW"
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    SUPERSEDE = "SUPERSEDE"


class EditorialValidationSeverity(str, Enum):
    """Severity classification of editorial validation findings."""

    BLOCKING = "BLOCKING"
    WARNING = "WARNING"
    INFORMATIONAL = "INFORMATIONAL"


class EditorialValidationCode(str, Enum):
    """Stable, machine-readable validation finding codes."""

    PASS = "PASS"
    BLOCKED_PROHIBITED_TERM = "BLOCKED_PROHIBITED_TERM"
    BLOCKED_MISSING_DISCLAIMER = "BLOCKED_MISSING_DISCLAIMER"
    BLOCKED_DISCLAIMER_MISMATCH = "BLOCKED_DISCLAIMER_MISMATCH"
    BLOCKED_MISSING_EVIDENCE = "BLOCKED_MISSING_EVIDENCE"
    BLOCKED_UNAPPROVED_EU_SCREEN = "BLOCKED_UNAPPROVED_EU_SCREEN"
    BLOCKED_UNRESOLVED_UNKNOWN = "BLOCKED_UNRESOLVED_UNKNOWN"
    BLOCKED_INSUFFICIENT_DATA = "BLOCKED_INSUFFICIENT_DATA"
    BLOCKED_NON_HUMAN_REVIEWER = "BLOCKED_NON_HUMAN_REVIEWER"
    BLOCKED_SOURCE_DRIFT = "BLOCKED_SOURCE_DRIFT"
    BLOCKED_EMPTY_DOSSIER = "BLOCKED_EMPTY_DOSSIER"
    BLOCKED_UNAPPROVED_STATUS = "BLOCKED_UNAPPROVED_STATUS"
    BLOCKED_SCHEMA_ERROR = "BLOCKED_SCHEMA_ERROR"


class EditorialAuditEventType(str, Enum):
    """Append-only audit event types for editorial dossier lifecycle."""

    CREATE_DOSSIER = "CREATE_DOSSIER"
    ASSEMBLE_DOSSIER = "ASSEMBLE_DOSSIER"
    VALIDATE_DOSSIER = "VALIDATE_DOSSIER"
    SUBMIT_FOR_REVIEW = "SUBMIT_FOR_REVIEW"
    APPROVE_DOSSIER = "APPROVE_DOSSIER"
    REJECT_DOSSIER = "REJECT_DOSSIER"
    SUPERSEDE_DOSSIER = "SUPERSEDE_DOSSIER"
    EXPORT_DOSSIER = "EXPORT_DOSSIER"


class EditorialExportFormat(str, Enum):
    """Artifact format for local editorial export."""

    MARKDOWN = "MARKDOWN"
    JSON = "JSON"
    ALL = "ALL"  # CLI/export selection indicating both Markdown, JSON, and manifest


class EditorialPresentationProfile(str, Enum):
    """Presentation profile controlling editorial depth, structure, and detail level."""

    DEEP_DIVE_DOSSIER = "DEEP_DIVE_DOSSIER"
    EXECUTIVE_BRIEF = "EXECUTIVE_BRIEF"
    RAPID_ALERT = "RAPID_ALERT"


class EditorialArtifactPurpose(str, Enum):
    """Operational purpose and governance authority of an exported artifact."""

    INTERNAL_REVIEW_COPY = "INTERNAL_REVIEW_COPY"
    APPROVED_EDITORIAL_COPY = "APPROVED_EDITORIAL_COPY"
