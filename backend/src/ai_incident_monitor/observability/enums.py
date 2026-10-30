"""Controlled enumerations for local operational observability and telemetry.

Governing Charter: Project Constitution (Rules 1, 10, 11, 14, 16),
PRD §5 (TST-001, AUD-004), Phase 7B Plan.
"""

from __future__ import annotations

from enum import Enum


class OperationalStage(str, Enum):
    """Pipeline processing stages instrumented for observability."""

    INGESTION = "INGESTION"
    DEDUPLICATION = "DEDUPLICATION"
    EVIDENCE_PERSISTENCE = "EVIDENCE_PERSISTENCE"
    SEVERITY_SCORING = "SEVERITY_SCORING"
    GOVERNANCE_MAPPING = "GOVERNANCE_MAPPING"
    EDITORIAL_ASSEMBLY = "EDITORIAL_ASSEMBLY"
    EDITORIAL_VALIDATION = "EDITORIAL_VALIDATION"
    EDITORIAL_REVIEW = "EDITORIAL_REVIEW"
    LOCAL_EXPORT = "LOCAL_EXPORT"
    DIAGNOSTICS = "DIAGNOSTICS"
    SYSTEM = "SYSTEM"


class OperationalEventType(str, Enum):
    """Lifecycle event types within an operational run."""

    STAGE_START = "STAGE_START"
    STAGE_COMPLETE = "STAGE_COMPLETE"
    RUN_SUMMARY = "RUN_SUMMARY"
    CHECK_EVALUATED = "CHECK_EVALUATED"


class OperationalOutcome(str, Enum):
    """Controlled outcomes for operational stages and overall runs."""

    SUCCEEDED = "SUCCEEDED"
    FAILED_TECHNICAL = "FAILED_TECHNICAL"
    BLOCKED_VALIDATION = "BLOCKED_VALIDATION"
    AWAITING_HUMAN_REVIEW = "AWAITING_HUMAN_REVIEW"
    SKIPPED = "SKIPPED"
