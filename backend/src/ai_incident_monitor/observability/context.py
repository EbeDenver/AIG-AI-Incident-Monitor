"""Correlation context tracking and scoped stage execution for operational observability.

Governing Charter: Project Constitution (Rules 1, 10, 11, 14, 16),
PRD §5 (TST-001, AUD-004), Phase 7B Plan.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
import contextvars
from datetime import datetime, timezone
import time
from typing import Any, Optional
import uuid

from ai_incident_monitor.observability.enums import (
    OperationalEventType,
    OperationalOutcome,
    OperationalStage,
)
from ai_incident_monitor.observability.logger import log_operational_event
from ai_incident_monitor.observability.models import OperationalEventSchema
from ai_incident_monitor.observability.sanitizer import safe_exception_summary

_CURRENT_RUN_ID: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "current_run_id", default=None
)


def get_current_run_id() -> Optional[str]:
    """Return the active correlation run ID for the current context, or None."""
    return _CURRENT_RUN_ID.get()


def set_current_run_id(run_id: str) -> contextvars.Token[Optional[str]]:
    """Set the active correlation run ID for the current context."""
    return _CURRENT_RUN_ID.set(run_id)


def reset_current_run_id(token: contextvars.Token[Optional[str]]) -> None:
    """Reset the correlation run ID using the token returned by set_current_run_id."""
    _CURRENT_RUN_ID.reset(token)


@contextmanager
def run_scope(run_id: Optional[str] = None) -> Generator[str, None, None]:
    """Context manager binding a correlation run ID for a pipeline execution."""
    active_id = run_id or f"run_{uuid.uuid4().hex[:12]}"
    token = set_current_run_id(active_id)
    try:
        yield active_id
    finally:
        reset_current_run_id(token)


class StageContext:
    """Mutable context passed into a stage scope to accumulate record IDs, counts, and reasons."""

    def __init__(self, run_id: str, stage: OperationalStage) -> None:
        self.run_id = run_id
        self.stage = stage
        self.record_ids: dict[str, str] = {}
        self.counts: dict[str, int] = {}
        self.details: dict[str, Any] = {}
        self.reason_code: Optional[str] = None
        self.outcome: OperationalOutcome = OperationalOutcome.SUCCEEDED

    def set_record_id(self, key: str, value: str) -> None:
        self.record_ids[key] = value

    def set_count(self, key: str, count: int) -> None:
        self.counts[key] = count

    def add_count(self, key: str, delta: int = 1) -> None:
        self.counts[key] = self.counts.get(key, 0) + delta

    def set_outcome(self, outcome: OperationalOutcome, reason_code: Optional[str] = None) -> None:
        self.outcome = outcome
        if reason_code is not None:
            self.reason_code = reason_code


@contextmanager
def stage_scope(
    stage: OperationalStage,
    run_id: Optional[str] = None,
    initial_record_ids: Optional[dict[str, str]] = None,
) -> Generator[StageContext, None, None]:
    """Execute a processing stage with monotonic timing, correlation tracking, and event emission."""
    active_run_id = run_id or get_current_run_id() or f"run_{uuid.uuid4().hex[:12]}"
    ctx = StageContext(run_id=active_run_id, stage=stage)
    if initial_record_ids:
        ctx.record_ids.update(initial_record_ids)

    # 1. Emit STAGE_START event
    start_time = time.monotonic()
    start_event = OperationalEventSchema(
        run_id=active_run_id,
        stage=stage,
        event_type=OperationalEventType.STAGE_START,
        recorded_at_utc=datetime.now(timezone.utc),
        record_ids=ctx.record_ids,
    )
    log_operational_event(start_event)

    try:
        yield ctx
    except Exception as exc:
        duration_ms = (time.monotonic() - start_time) * 1000.0
        exc_type, exc_msg = safe_exception_summary(exc)

        # Distinguish validation/blocking errors from unexpected technical failures
        if "validation" in exc_type.lower() or "blocked" in exc_type.lower() or "collision" in exc_msg.lower():
            outcome = OperationalOutcome.BLOCKED_VALIDATION
            reason_code = ctx.reason_code or f"{exc_type.upper()}_BLOCKED"
        elif "constitutional" in exc_type.lower():
            outcome = OperationalOutcome.BLOCKED_VALIDATION
            reason_code = "CONSTITUTIONAL_RULE_BLOCKED"
        else:
            outcome = OperationalOutcome.FAILED_TECHNICAL
            reason_code = ctx.reason_code or f"{exc_type.upper()}_ERROR"

        err_event = OperationalEventSchema(
            run_id=active_run_id,
            stage=stage,
            event_type=OperationalEventType.STAGE_COMPLETE,
            recorded_at_utc=datetime.now(timezone.utc),
            duration_ms=round(duration_ms, 2),
            outcome=outcome,
            reason_code=reason_code,
            record_ids=ctx.record_ids,
            counts=ctx.counts,
            details={"error_type": exc_type, "error_summary": exc_msg},
        )
        log_operational_event(err_event)
        raise

    duration_ms = (time.monotonic() - start_time) * 1000.0
    complete_event = OperationalEventSchema(
        run_id=active_run_id,
        stage=stage,
        event_type=OperationalEventType.STAGE_COMPLETE,
        recorded_at_utc=datetime.now(timezone.utc),
        duration_ms=round(duration_ms, 2),
        outcome=ctx.outcome,
        reason_code=ctx.reason_code,
        record_ids=ctx.record_ids,
        counts=ctx.counts,
        details=ctx.details,
    )
    log_operational_event(complete_event)
