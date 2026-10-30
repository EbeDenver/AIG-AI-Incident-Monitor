"""Pydantic v2 schemas for local operational diagnostics reports.

Governing Charter: Project Constitution (Rules 1, 10, 11, 14, 16),
PRD §5 (TST-001, AUD-004), Phase 7B Plan.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ai_incident_monitor.diagnostics.enums import CheckCategory, CheckStatus
from ai_incident_monitor.observability.sanitizer import mask_sensitive_dict, sanitize_log_string

DIAGNOSTICS_SCHEMA_VERSION = "1.0.0"


class DiagnosticCheckResult(BaseModel):
    """Result of an individual safe, read-only diagnostic check."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1, max_length=64, description="Check name")
    category: CheckCategory = Field(description="Operational check category")
    status: CheckStatus = Field(description="Check health status")
    reason_code: str = Field(min_length=1, max_length=64, description="Controlled outcome reason code")
    message: str = Field(description="Human-readable check summary")
    details: dict[str, Any] = Field(default_factory=dict, description="Safe, masked context details")

    @field_validator("message")
    @classmethod
    def sanitize_msg(cls, v: str) -> str:
        return sanitize_log_string(v, max_length=500)

    @field_validator("details")
    @classmethod
    def mask_check_details(cls, v: dict[str, Any]) -> dict[str, Any]:
        return mask_sensitive_dict(v)


class DiagnosticReport(BaseModel):
    """Complete diagnostic report synthesizing all evaluated operational checks."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = Field(default=DIAGNOSTICS_SCHEMA_VERSION, min_length=1, max_length=16)
    evaluated_at_utc: datetime = Field(description="UTC timestamp of diagnostic evaluation")
    overall_status: CheckStatus = Field(description="Overall operational health status")
    exit_code: int = Field(ge=0, le=2, description="Standardized exit code (0=HEALTHY, 1=DEGRADED, 2=UNHEALTHY)")
    checks: list[DiagnosticCheckResult] = Field(description="List of evaluated diagnostic checks")

    @field_validator("evaluated_at_utc")
    @classmethod
    def validate_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)
