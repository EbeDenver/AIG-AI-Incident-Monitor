"""Pydantic v2 schemas for operational telemetry events and run metrics summaries.

Governing Charter: Project Constitution (Rules 1, 10, 11, 14, 16),
PRD §5 (TST-001, AUD-004), Phase 7B Plan.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ai_incident_monitor.observability.enums import (
    OperationalEventType,
    OperationalOutcome,
    OperationalStage,
)
from ai_incident_monitor.observability.sanitizer import (
    mask_sensitive_dict,
    sanitize_log_string,
)

OPERATIONAL_SCHEMA_VERSION = "1.0.0"


class OperationalEventSchema(BaseModel):
    """Structured, sanitized telemetry event recorded at operational boundaries."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = Field(default=OPERATIONAL_SCHEMA_VERSION, min_length=1, max_length=16)
    run_id: str = Field(min_length=1, max_length=64, description="Correlation ID for operational run")
    stage: OperationalStage = Field(description="Pipeline stage being executed")
    event_type: OperationalEventType = Field(description="Lifecycle event type")
    recorded_at_utc: datetime = Field(description="UTC timestamp of event occurrence")
    duration_ms: Optional[float] = Field(default=None, ge=0.0, description="Stage duration measured via monotonic clock")
    outcome: Optional[OperationalOutcome] = Field(default=None, description="Controlled stage outcome")
    reason_code: Optional[str] = Field(default=None, max_length=64, description="Controlled reason or error code")
    record_ids: dict[str, str] = Field(default_factory=dict, description="Safe entity identifiers (dossier_id, incident_id)")
    counts: dict[str, int] = Field(default_factory=dict, description="Run-level metric counts for the stage")
    details: dict[str, Any] = Field(default_factory=dict, description="Sanitized, masked auxiliary context")

    @field_validator("recorded_at_utc")
    @classmethod
    def validate_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    @field_validator("reason_code")
    @classmethod
    def sanitize_reason(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return sanitize_log_string(v, max_length=64)

    @field_validator("details")
    @classmethod
    def mask_details(cls, v: dict[str, Any]) -> dict[str, Any]:
        return mask_sensitive_dict(v)

    @field_validator("record_ids")
    @classmethod
    def sanitize_record_ids(cls, v: dict[str, str]) -> dict[str, str]:
        return {
            sanitize_log_string(k, max_length=32): sanitize_log_string(str(val), max_length=64)
            for k, val in v.items()
        }

    @field_validator("counts")
    @classmethod
    def validate_counts(cls, v: dict[str, int]) -> dict[str, int]:
        for k, count in v.items():
            if count < 0:
                raise ValueError(f"Count '{k}' cannot be negative: {count}")
        return v


class RunMetricsSummary(BaseModel):
    """Aggregated run-level metrics summary derived in-memory for an operational run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = Field(default=OPERATIONAL_SCHEMA_VERSION, min_length=1, max_length=16)
    run_id: str = Field(min_length=1, max_length=64)
    started_at_utc: datetime
    completed_at_utc: datetime
    total_duration_ms: float = Field(ge=0.0)
    stage_durations_ms: dict[str, float] = Field(default_factory=dict)

    # Clearly defined count metrics:
    items_received: int = Field(default=0, ge=0, description="Raw items/records parsed from incoming sources")
    items_accepted: int = Field(default=0, ge=0, description="Items meeting schema & eligibility criteria")
    items_rejected: int = Field(default=0, ge=0, description="Items rejected during ingestion/validation")
    duplicates_detected: int = Field(default=0, ge=0, description="Duplicate incoming reports deduplicated (4-tier dedup)")
    assessments_completed: int = Field(default=0, ge=0, description="Deterministic severity & governance assessments completed")
    dossiers_assembled: int = Field(default=0, ge=0, description="Editorial dossiers assembled from candidate pools")
    validation_blocks: int = Field(default=0, ge=0, description="Dossier or candidate evaluations halted by validation findings")
    review_required_outcomes: int = Field(default=0, ge=0, description="Work items routed to pending human review (Rule 14)")
    export_successes: int = Field(default=0, ge=0, description="Artifact packages successfully exported to disk")
    export_failures: int = Field(default=0, ge=0, description="Export attempts that failed or were blocked")

    overall_outcome: OperationalOutcome = Field(description="Overall outcome of the operational run")
