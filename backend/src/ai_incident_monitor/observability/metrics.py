"""In-memory aggregation of run-level operational metrics.

Governing Charter: Project Constitution (Rules 1, 10, 11, 14, 16),
PRD §5 (TST-001, AUD-004), Phase 7B Plan.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime, timezone
import time
from typing import Optional

from ai_incident_monitor.observability.enums import (
    OperationalEventType,
    OperationalOutcome,
    OperationalStage,
)
from ai_incident_monitor.observability.logger import (
    add_event_listener,
    remove_event_listener,
)
from ai_incident_monitor.observability.models import (
    OperationalEventSchema,
    RunMetricsSummary,
)


class RunMetricsCollector:
    """In-memory collector accumulating operational metric counts and stage timings for a run."""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.started_at_utc = datetime.now(timezone.utc)
        self._start_monotonic = time.monotonic()
        self.stage_durations_ms: dict[str, float] = {}
        self.counts: dict[str, int] = {
            "items_received": 0,
            "items_accepted": 0,
            "items_rejected": 0,
            "duplicates_detected": 0,
            "assessments_completed": 0,
            "dossiers_assembled": 0,
            "validation_blocks": 0,
            "review_required_outcomes": 0,
            "export_successes": 0,
            "export_failures": 0,
        }
        self.overall_outcome: OperationalOutcome = OperationalOutcome.SUCCEEDED

    def record_event(self, event: OperationalEventSchema) -> None:
        """Process an emitted operational event into aggregated metrics."""
        if event.run_id != self.run_id:
            return

        # Record stage timing if present
        if event.duration_ms is not None:
            self.stage_durations_ms[event.stage.value] = event.duration_ms

        # Update counts
        for k, v in event.counts.items():
            if k in self.counts:
                self.counts[k] += v

        # Update outcomes and block tracking
        if event.outcome == OperationalOutcome.BLOCKED_VALIDATION:
            self.counts["validation_blocks"] += 1
            if self.overall_outcome == OperationalOutcome.SUCCEEDED:
                self.overall_outcome = OperationalOutcome.BLOCKED_VALIDATION
        elif event.outcome == OperationalOutcome.AWAITING_HUMAN_REVIEW:
            self.counts["review_required_outcomes"] += 1
            if self.overall_outcome in (OperationalOutcome.SUCCEEDED, OperationalOutcome.BLOCKED_VALIDATION):
                self.overall_outcome = OperationalOutcome.AWAITING_HUMAN_REVIEW
        elif event.outcome == OperationalOutcome.FAILED_TECHNICAL:
            self.overall_outcome = OperationalOutcome.FAILED_TECHNICAL

    def increment(self, metric_name: str, delta: int = 1) -> None:
        """Manually increment a run metric count."""
        if metric_name in self.counts:
            self.counts[metric_name] += delta

    def finalize(self) -> RunMetricsSummary:
        """Produce the immutable RunMetricsSummary for this execution."""
        completed_at_utc = datetime.now(timezone.utc)
        total_duration_ms = (time.monotonic() - self._start_monotonic) * 1000.0

        return RunMetricsSummary(
            run_id=self.run_id,
            started_at_utc=self.started_at_utc,
            completed_at_utc=completed_at_utc,
            total_duration_ms=round(total_duration_ms, 2),
            stage_durations_ms=self.stage_durations_ms,
            items_received=self.counts["items_received"],
            items_accepted=self.counts["items_accepted"],
            items_rejected=self.counts["items_rejected"],
            duplicates_detected=self.counts["duplicates_detected"],
            assessments_completed=self.counts["assessments_completed"],
            dossiers_assembled=self.counts["dossiers_assembled"],
            validation_blocks=self.counts["validation_blocks"],
            review_required_outcomes=self.counts["review_required_outcomes"],
            export_successes=self.counts["export_successes"],
            export_failures=self.counts["export_failures"],
            overall_outcome=self.overall_outcome,
        )


@contextmanager
def track_run_metrics(run_id: str) -> Generator[RunMetricsCollector, None, None]:
    """Context manager attaching an in-memory RunMetricsCollector to operational events."""
    collector = RunMetricsCollector(run_id=run_id)
    listener = collector.record_event
    add_event_listener(listener)
    try:
        yield collector
    finally:
        remove_event_listener(listener)
