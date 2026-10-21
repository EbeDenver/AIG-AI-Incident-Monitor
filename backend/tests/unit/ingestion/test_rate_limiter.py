"""Unit tests for per-connector rate limiting and concurrency guards."""

from __future__ import annotations

import threading
import time
from unittest.mock import patch

import pytest

from ai_incident_monitor.ingestion.models import RateLimitPolicy, RetryPolicy
from ai_incident_monitor.ingestion.rate_limiter import ConnectorRateLimiter


class TestConnectorRateLimiter:
    """Verifies per-connector rate limiting and concurrency locking."""

    def test_default_rate_limiter_allows_first_request_without_sleep(self) -> None:
        limiter = ConnectorRateLimiter(RateLimitPolicy(min_interval_seconds=1.0))
        slept = limiter.acquire()
        assert slept == 0.0

    def test_rapid_subsequent_request_enforces_interval(self) -> None:
        limiter = ConnectorRateLimiter(RateLimitPolicy(min_interval_seconds=0.1))
        limiter.acquire()
        start = time.monotonic()
        slept = limiter.acquire()
        elapsed = time.monotonic() - start
        assert slept > 0.0
        assert elapsed >= 0.08

    def test_single_connection_guard_blocks_concurrent_execution(self) -> None:
        policy = RateLimitPolicy(min_interval_seconds=0.0, single_connection_only=True)
        limiter = ConnectorRateLimiter(policy)

        execution_order: list[str] = []

        def worker_task(name: str, delay: float) -> None:
            with limiter.connection_guard():
                execution_order.append(f"{name}_start")
                time.sleep(delay)
                execution_order.append(f"{name}_end")

        t1 = threading.Thread(target=worker_task, args=("T1", 0.05))
        t2 = threading.Thread(target=worker_task, args=("T2", 0.05))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Because concurrency is strictly 1, one worker must completely finish before the other starts
        assert execution_order in (
            ["T1_start", "T1_end", "T2_start", "T2_end"],
            ["T2_start", "T2_end", "T1_start", "T1_end"],
        )


class TestRetryPolicy:
    """Verifies exponential backoff, jitter, and non-retryable status codes."""

    def test_429_is_retryable_with_exponential_backoff(self) -> None:
        policy = RetryPolicy(max_retries=3, base_delay_seconds=1.0, jitter_factor=0.0)
        should_retry, delay, reason = policy.evaluate_retry(
            attempt=0, cumulative_wait=0.0, status_code=429
        )
        assert should_retry is True
        assert delay == 1.0  # 1.0 * (2^0)

        should_retry_2, delay_2, _ = policy.evaluate_retry(
            attempt=1, cumulative_wait=1.0, status_code=429
        )
        assert should_retry_2 is True
        assert delay_2 == 2.0  # 1.0 * (2^1)

        should_retry_3, delay_3, _ = policy.evaluate_retry(
            attempt=2, cumulative_wait=3.0, status_code=429
        )
        assert should_retry_3 is True
        assert delay_3 == 4.0  # 1.0 * (2^2)

    def test_honors_retry_after_header_seconds(self) -> None:
        policy = RetryPolicy(max_retries=3, base_delay_seconds=1.0, jitter_factor=0.0)
        should_retry, delay, reason = policy.evaluate_retry(
            attempt=0,
            cumulative_wait=0.0,
            status_code=429,
            retry_after_header="5",
        )
        assert should_retry is True
        assert delay == 5.0
        assert "Retry-After" in reason

    def test_honors_retry_after_http_date(self) -> None:
        policy = RetryPolicy(max_retries=3, base_delay_seconds=1.0, jitter_factor=0.0)
        # 10 seconds in the future
        future_date = "Wed, 21 Oct 2026 07:28:00 GMT"
        with patch("ai_incident_monitor.ingestion.models.datetime") as mock_dt:
            from datetime import datetime, timezone
            mock_dt.strptime.return_value = datetime(2026, 10, 21, 7, 28, 10, tzinfo=timezone.utc)
            mock_dt.now.return_value = datetime(2026, 10, 21, 7, 28, 0, tzinfo=timezone.utc)
            should_retry, delay, reason = policy.evaluate_retry(
                attempt=0,
                cumulative_wait=0.0,
                status_code=429,
                retry_after_header=future_date,
            )
            assert should_retry is True
            assert delay == 10.0

    def test_max_retries_exhaustion(self) -> None:
        policy = RetryPolicy(max_retries=2)
        should_retry, delay, reason = policy.evaluate_retry(
            attempt=2, cumulative_wait=5.0, status_code=503
        )
        assert should_retry is False
        assert "Max retries" in reason

    def test_cumulative_wait_ceiling_enforced(self) -> None:
        policy = RetryPolicy(max_retries=5, max_cumulative_wait_seconds=10.0, jitter_factor=0.0)
        # Attempt 3: delay would be 8s, cumulative_wait is 5s (5 + 8 = 13 > 10)
        should_retry, delay, reason = policy.evaluate_retry(
            attempt=3, cumulative_wait=5.0, status_code=503
        )
        assert should_retry is False
        assert "exceed ceiling" in reason

    @pytest.mark.parametrize("status_code", [400, 401, 403, 404, 405, 410, 422])
    def test_permanent_4xx_errors_never_retried(self, status_code: int) -> None:
        policy = RetryPolicy()
        should_retry, delay, reason = policy.evaluate_retry(
            attempt=0, cumulative_wait=0.0, status_code=status_code
        )
        assert should_retry is False
        assert "not retryable" in reason

    @pytest.mark.parametrize("status_code", [408, 409, 425, 429, 500, 502, 503, 504])
    def test_transient_status_codes_retried(self, status_code: int) -> None:
        policy = RetryPolicy()
        should_retry, delay, reason = policy.evaluate_retry(
            attempt=0, cumulative_wait=0.0, status_code=status_code
        )
        assert should_retry is True
        assert "is retryable" in reason
