"""Unit tests for operational correlation tracking, stage scopes, metrics aggregation, and logger resilience.

Governing Charter: Project Constitution (Rules 1, 10, 11, 14, 16),
PRD §5 (TST-001, AUD-004), Phase 7B Plan.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from ai_incident_monitor.domain.common import ConstitutionalViolationError
from ai_incident_monitor.observability.context import (
    get_current_run_id,
    run_scope,
    stage_scope,
)
from ai_incident_monitor.observability.enums import (
    OperationalEventType,
    OperationalOutcome,
    OperationalStage,
)
from ai_incident_monitor.observability.logger import (
    add_event_listener,
    clear_event_listeners,
    log_operational_event,
    remove_event_listener,
)
from ai_incident_monitor.observability.metrics import RunMetricsCollector, track_run_metrics
from ai_incident_monitor.observability.models import OperationalEventSchema


@pytest.fixture(autouse=True)
def clean_listeners():
    """Ensure in-memory listeners are cleared between test cases."""
    clear_event_listeners()
    yield
    clear_event_listeners()


class TestCorrelationContextAndStageScope:
    """Validate correlation tracking and monotonic stage scoping."""

    def test_run_scope_binding_and_isolation(self) -> None:
        assert get_current_run_id() is None

        with run_scope("run_alpha") as r1:
            assert r1 == "run_alpha"
            assert get_current_run_id() == "run_alpha"

            # Nested scope
            with run_scope("run_nested") as r_inner:
                assert r_inner == "run_nested"
                assert get_current_run_id() == "run_nested"

            # Outer restored cleanly
            assert get_current_run_id() == "run_alpha"

        # Cleared completely
        assert get_current_run_id() is None

    def test_stage_scope_records_events_and_duration(self) -> None:
        recorded_events: list[OperationalEventSchema] = []
        add_event_listener(recorded_events.append)

        with run_scope("run_test_stages"):
            with stage_scope(OperationalStage.INGESTION, initial_record_ids={"feed_id": "feed_123"}) as ctx:
                ctx.set_count("items_received", 5)
                ctx.set_count("items_accepted", 4)
                ctx.set_record_id("batch_id", "batch_abc")
                ctx.set_outcome(OperationalOutcome.SUCCEEDED)

        assert len(recorded_events) == 2
        start_ev, complete_ev = recorded_events

        assert start_ev.event_type == OperationalEventType.STAGE_START
        assert start_ev.stage == OperationalStage.INGESTION
        assert start_ev.record_ids["feed_id"] == "feed_123"

        assert complete_ev.event_type == OperationalEventType.STAGE_COMPLETE
        assert complete_ev.duration_ms is not None
        assert complete_ev.duration_ms >= 0.0
        assert complete_ev.counts["items_received"] == 5
        assert complete_ev.counts["items_accepted"] == 4
        assert complete_ev.record_ids["batch_id"] == "batch_abc"
        assert complete_ev.outcome == OperationalOutcome.SUCCEEDED

    def test_stage_scope_maps_validation_and_constitutional_errors(self) -> None:
        recorded_events: list[OperationalEventSchema] = []
        add_event_listener(recorded_events.append)

        # 1. Constitutional violation -> BLOCKED_VALIDATION
        with pytest.raises(ConstitutionalViolationError):
            with stage_scope(OperationalStage.EDITORIAL_REVIEW, run_id="run_rule14"):
                raise ConstitutionalViolationError("Rule 14 violation: Automated self-approval forbidden.")

        assert len(recorded_events) == 2
        complete_ev = recorded_events[1]
        assert complete_ev.outcome == OperationalOutcome.BLOCKED_VALIDATION
        assert complete_ev.reason_code == "CONSTITUTIONAL_RULE_BLOCKED"

        # 2. ValueError/Validation error -> BLOCKED_VALIDATION
        recorded_events.clear()
        with pytest.raises(ValueError):
            with stage_scope(OperationalStage.LOCAL_EXPORT, run_id="run_val"):
                raise ValueError("Validation error: Destination file collision without overwrite.")

        complete_ev2 = recorded_events[1]
        assert complete_ev2.outcome == OperationalOutcome.BLOCKED_VALIDATION

        # 3. Technical error (e.g. ConnectionError/KeyError) -> FAILED_TECHNICAL
        recorded_events.clear()
        with pytest.raises(KeyError):
            with stage_scope(OperationalStage.INGESTION, run_id="run_tech"):
                raise KeyError("Internal missing dictionary key")

        complete_ev3 = recorded_events[1]
        assert complete_ev3.outcome == OperationalOutcome.FAILED_TECHNICAL


class TestRunMetricsAggregation:
    """Validate in-memory run metrics summary accumulation."""

    def test_run_metrics_collector_accurately_aggregates_counts(self) -> None:
        run_id = "run_metrics_test"
        with track_run_metrics(run_id) as collector:
            with stage_scope(OperationalStage.INGESTION, run_id=run_id) as s1:
                s1.set_count("items_received", 10)
                s1.set_count("items_accepted", 8)
                s1.set_count("duplicates_detected", 2)
                s1.set_outcome(OperationalOutcome.SUCCEEDED)

            with stage_scope(OperationalStage.SEVERITY_SCORING, run_id=run_id) as s2:
                s2.set_count("assessments_completed", 8)
                s2.set_outcome(OperationalOutcome.SUCCEEDED)

            with stage_scope(OperationalStage.EDITORIAL_ASSEMBLY, run_id=run_id) as s3:
                s3.set_count("dossiers_assembled", 1)
                s3.set_outcome(OperationalOutcome.AWAITING_HUMAN_REVIEW)

            with stage_scope(OperationalStage.LOCAL_EXPORT, run_id=run_id) as s4:
                s4.set_count("export_successes", 1)
                s4.set_outcome(OperationalOutcome.SUCCEEDED)

        summary = collector.finalize()

        assert summary.run_id == run_id
        assert summary.items_received == 10
        assert summary.items_accepted == 8
        assert summary.duplicates_detected == 2
        assert summary.assessments_completed == 8
        assert summary.dossiers_assembled == 1
        assert summary.export_successes == 1
        assert summary.review_required_outcomes == 1
        assert summary.overall_outcome == OperationalOutcome.AWAITING_HUMAN_REVIEW
        assert "INGESTION" in summary.stage_durations_ms
        assert "LOCAL_EXPORT" in summary.stage_durations_ms

    def test_metrics_collector_ignores_other_run_ids(self) -> None:
        target_run = "run_target"
        with track_run_metrics(target_run) as collector:
            # Emit event for a DIFFERENT run
            with stage_scope(OperationalStage.INGESTION, run_id="run_other") as s:
                s.set_count("items_received", 100)

        summary = collector.finalize()
        assert summary.items_received == 0


class TestLoggerResilienceAndNonFatalSink:
    """Validate that operational logger sink failures are non-fatal to business execution."""

    def test_logging_sink_failure_is_non_fatal(self) -> None:
        event = OperationalEventSchema(
            run_id="run_sink_fail",
            stage=OperationalStage.SYSTEM,
            event_type=OperationalEventType.STAGE_COMPLETE,
            recorded_at_utc=OperationalEventSchema.validate_utc(None or pytest.importorskip("datetime").datetime.now()),
        )

        # Simulate logger.info raising an OSError (e.g. disk full / closed stream)
        with patch.object(logging.Logger, "info", side_effect=OSError("Disk full / I/O error")):
            # Must NOT raise exception to caller
            log_operational_event(event)

    def test_listener_exception_is_non_fatal(self) -> None:
        def bad_listener(ev):
            raise RuntimeError("Broken listener crash")

        add_event_listener(bad_listener)

        event = OperationalEventSchema(
            run_id="run_listener_fail",
            stage=OperationalStage.SYSTEM,
            event_type=OperationalEventType.STAGE_COMPLETE,
            recorded_at_utc=OperationalEventSchema.validate_utc(None or pytest.importorskip("datetime").datetime.now()),
        )

        # Must NOT raise
        log_operational_event(event)
