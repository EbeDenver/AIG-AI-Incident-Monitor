"""Unit tests for operational observability models, event schemas, and sanitization.

Governing Charter: Project Constitution (Rules 1, 10, 11, 14, 16),
PRD §5 (TST-001, AUD-004), Phase 7B Plan.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ai_incident_monitor.observability.enums import (
    OperationalEventType,
    OperationalOutcome,
    OperationalStage,
)
from ai_incident_monitor.observability.models import (
    OPERATIONAL_SCHEMA_VERSION,
    OperationalEventSchema,
    RunMetricsSummary,
)
from ai_incident_monitor.observability.sanitizer import (
    REDACTED_PLACEHOLDER,
    mask_sensitive_dict,
    safe_exception_summary,
    sanitize_log_string,
)


class TestOperationalEventSchemas:
    """Validate Pydantic v2 event and metrics schema constraints."""

    def test_valid_operational_event_creation(self) -> None:
        now = datetime.now(timezone.utc)
        event = OperationalEventSchema(
            run_id="run_test_001",
            stage=OperationalStage.INGESTION,
            event_type=OperationalEventType.STAGE_COMPLETE,
            recorded_at_utc=now,
            duration_ms=45.2,
            outcome=OperationalOutcome.SUCCEEDED,
            reason_code="FEED_PARSED_CLEANLY",
            record_ids={"feed_url": "https://example.com/feed.xml"},
            counts={"items_received": 10, "items_accepted": 8},
            details={"connector": "RSSConnector"},
        )

        assert event.schema_version == OPERATIONAL_SCHEMA_VERSION
        assert event.run_id == "run_test_001"
        assert event.stage == OperationalStage.INGESTION
        assert event.duration_ms == 45.2
        assert event.outcome == OperationalOutcome.SUCCEEDED
        assert event.counts["items_accepted"] == 8

        # Verify JSON round-trip serialization
        raw_json = event.model_dump_json()
        assert "run_test_001" in raw_json
        assert "FEED_PARSED_CLEANLY" in raw_json

    def test_naive_datetime_coerced_to_utc(self) -> None:
        naive = datetime(2026, 10, 29, 12, 0, 0)
        event = OperationalEventSchema(
            run_id="run_naive_test",
            stage=OperationalStage.SEVERITY_SCORING,
            event_type=OperationalEventType.STAGE_START,
            recorded_at_utc=naive,
        )
        assert event.recorded_at_utc.tzinfo == timezone.utc

    def test_negative_counts_rejected(self) -> None:
        with pytest.raises(ValueError, match="cannot be negative"):
            OperationalEventSchema(
                run_id="run_neg_count",
                stage=OperationalStage.INGESTION,
                event_type=OperationalEventType.STAGE_COMPLETE,
                recorded_at_utc=datetime.now(timezone.utc),
                counts={"items_received": -1},
            )

    def test_run_metrics_summary_creation(self) -> None:
        start = datetime.now(timezone.utc)
        end = datetime.now(timezone.utc)
        summary = RunMetricsSummary(
            run_id="run_summary_001",
            started_at_utc=start,
            completed_at_utc=end,
            total_duration_ms=125.5,
            stage_durations_ms={"INGESTION": 50.0, "LOCAL_EXPORT": 75.5},
            items_received=10,
            items_accepted=10,
            items_rejected=0,
            duplicates_detected=2,
            assessments_completed=1,
            dossiers_assembled=1,
            validation_blocks=0,
            review_required_outcomes=1,
            export_successes=1,
            export_failures=0,
            overall_outcome=OperationalOutcome.SUCCEEDED,
        )

        assert summary.items_received == 10
        assert summary.duplicates_detected == 2
        assert summary.total_duration_ms == 125.5
        assert summary.overall_outcome == OperationalOutcome.SUCCEEDED


class TestLogSanitizationAndInjectionDefense:
    """Validate log injection defense (CWE-117) and credential masking."""

    def test_cwe_117_newline_and_cr_stripping(self) -> None:
        injected = "Normal log line\nADMIN_OVERRIDE_INJECTED\r\nANOTHER_FAKE_ENTRY\0null_byte"
        sanitized = sanitize_log_string(injected)

        assert "\n" not in sanitized
        assert "\r" not in sanitized
        assert "\0" not in sanitized
        assert "Normal log line ADMIN_OVERRIDE_INJECTED ANOTHER_FAKE_ENTRY null_byte" in sanitized

    def test_control_character_stripping(self) -> None:
        # Non-printable control chars: 0x07 (bell), 0x08 (backspace), 0x1B (escape)
        bad_chars = "Hello\x07World\x08Test\x1b[31mRed"
        sanitized = sanitize_log_string(bad_chars)
        assert "\x07" not in sanitized
        assert "\x08" not in sanitized
        assert "\x1b" not in sanitized

    def test_mask_sensitive_dict_keys(self) -> None:
        data = {
            "api_key": "sk-1234567890abcdef",
            "db_password": "super_secret_db_pass",
            "auth_token": "Bearer ghp_validToken12345",
            "safe_counter": 42,
            "nested": {
                "secret_key": "nested_secret_val",
                "normal_field": "visible_value",
            },
            "list_items": [
                {"user_token": "list_token_123"},
                "plain_string",
            ],
        }

        masked = mask_sensitive_dict(data)

        assert masked["api_key"] == REDACTED_PLACEHOLDER
        assert masked["db_password"] == REDACTED_PLACEHOLDER
        assert masked["auth_token"] == REDACTED_PLACEHOLDER
        assert masked["safe_counter"] == 42
        assert masked["nested"]["secret_key"] == REDACTED_PLACEHOLDER
        assert masked["nested"]["normal_field"] == "visible_value"
        assert masked["list_items"][0]["user_token"] == REDACTED_PLACEHOLDER
        assert masked["list_items"][1] == "plain_string"

    def test_safe_exception_summary_no_stack_or_locals(self) -> None:
        secret_local = "SENSITIVE_LOCAL_VARIABLE"
        try:
            raise ValueError(f"Database error with token: {secret_local}\nSecond line error")
        except ValueError as exc:
            exc_type, exc_msg = safe_exception_summary(exc)

        assert exc_type == "ValueError"
        assert "\n" not in exc_msg
        assert "Database error with token:" in exc_msg
