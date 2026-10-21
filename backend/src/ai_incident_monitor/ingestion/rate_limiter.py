"""Per-connector thread-safe rate limiter and concurrency guard.

Governing Charter: Project Constitution (Rules 1, 9, 11, 14, 15, 16),
ADR-008, SEC-002, OPS-002.
"""

from __future__ import annotations

from contextlib import contextmanager
import threading
import time
from typing import Generator

from ai_incident_monitor.ingestion.models import RateLimitPolicy


class ConnectorRateLimiter:
    """Enforces per-connector rate limits and single-connection concurrency guards."""

    def __init__(self, policy: RateLimitPolicy | None = None) -> None:
        self.policy = policy or RateLimitPolicy()
        self._lock = threading.Lock()
        self._connection_semaphore = threading.Semaphore(1) if self.policy.single_connection_only else None
        self._last_request_time: float = 0.0

    @property
    def min_interval_seconds(self) -> float:
        return self.policy.min_interval_seconds

    @property
    def single_connection_only(self) -> bool:
        return self.policy.single_connection_only

    def acquire(self) -> float:
        """Wait if necessary to satisfy min_interval_seconds since the last request.

        Returns:
            The number of seconds slept (0.0 if no sleep was needed).
        """
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            sleep_needed = self.policy.min_interval_seconds - elapsed

            if sleep_needed > 0:
                time.sleep(sleep_needed)
                self._last_request_time = time.monotonic()
                return sleep_needed
            else:
                self._last_request_time = now
                return 0.0

    @contextmanager
    def connection_guard(self) -> Generator[None, None, None]:
        """Context manager enforcing single active connection if policy requires it."""
        if self._connection_semaphore is not None:
            self._connection_semaphore.acquire()
            try:
                yield
            finally:
                self._connection_semaphore.release()
        else:
            yield
