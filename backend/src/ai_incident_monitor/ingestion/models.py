"""Data models and policy definitions for secure ingestion connectors.

Governing Charter: Project Constitution (Rules 1, 9, 11, 14, 15, 16),
ADR-008, SEC-002, DEC-P4-001, DEC-P4-002, DEC-P4-003, DEC-P4-004.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import random
import re
import time
from typing import Any


class ConnectorType(str, Enum):
    """Categorical type identifier for ingestion connectors."""

    RSS = "rss"
    ATOM = "atom"
    ARXIV = "arxiv"
    OECD_EXPORT = "oecd_export"
    CUSTOM = "custom"


class IngestionStatus(str, Enum):
    """Execution status of a connector ingestion run."""

    SUCCESS = "success"
    PARTIAL = "partial"
    NOT_MODIFIED = "not_modified"
    FAILED = "failed"
    DISABLED = "disabled"


@dataclass(frozen=True)
class ConnectorMetadata:
    """Metadata identifying a specific pluggable connector instance."""

    name: str
    version: str
    connector_type: ConnectorType
    enabled: bool
    allowed_source_hosts: frozenset[str]
    description: str
    policy_version: str = "1.0.0"


@dataclass
class RetryDecision:
    """Record of an automated backoff / retry decision."""

    attempt: int
    status_code: int | None
    delay_seconds: float
    reason: str
    timestamp_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class RetryPolicy:
    """Configurable exponential backoff and jitter policy.

    Retries only transient network timeouts, 429 (Rate Limit), 503 (Unavailable),
    and selected transient 5xx errors. Never retries permanent 4xx errors
    (except 408, 409, 425, 429) or security/SSRF violations.
    """

    RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({408, 409, 425, 429, 500, 502, 503, 504})

    def __init__(
        self,
        *,
        max_retries: int = 3,
        base_delay_seconds: float = 1.0,
        max_delay_seconds: float = 30.0,
        max_cumulative_wait_seconds: float = 60.0,
        jitter_factor: float = 0.5,
        retryable_status_codes: frozenset[int] = RETRYABLE_STATUS_CODES,
    ) -> None:
        self.max_retries = max_retries
        self.base_delay_seconds = base_delay_seconds
        self.max_delay_seconds = max_delay_seconds
        self.max_cumulative_wait_seconds = max_cumulative_wait_seconds
        self.jitter_factor = jitter_factor
        self.retryable_status_codes = retryable_status_codes

    def evaluate_retry(
        self,
        *,
        attempt: int,
        cumulative_wait: float,
        status_code: int | None = None,
        retry_after_header: str | None = None,
        exception: Exception | None = None,
    ) -> tuple[bool, float, str]:
        """Determine whether to retry and calculate delay seconds.

        Returns:
            (should_retry, delay_seconds, reason)
        """
        if attempt >= self.max_retries:
            return False, 0.0, f"Max retries ({self.max_retries}) reached"

        # Check if error is retryable
        is_retryable = False
        reason = "Unknown transient failure"

        if status_code is not None:
            if status_code in self.retryable_status_codes:
                is_retryable = True
                reason = f"HTTP {status_code} is retryable"
            else:
                return False, 0.0, f"HTTP {status_code} is not retryable"
        elif exception is not None:
            # Network timeouts and connection drops are transient
            exc_name = type(exception).__name__
            if "Timeout" in exc_name or "Connection" in exc_name or "OSError" in exc_name:
                is_retryable = True
                reason = f"Transient network exception: {exc_name}"
            else:
                return False, 0.0, f"Non-retryable exception: {exc_name}"

        if not is_retryable:
            return False, 0.0, "Non-retryable condition"

        # Calculate delay
        delay = self.base_delay_seconds * (2 ** attempt)

        # Honor Retry-After header if present
        if retry_after_header:
            parsed_after = self._parse_retry_after(retry_after_header)
            if parsed_after is not None:
                delay = max(delay, parsed_after)
                reason += f" (honored Retry-After: {parsed_after:.1f}s)"

        # Apply jitter
        if self.jitter_factor > 0:
            jitter = random.uniform(0, self.jitter_factor * delay)
            delay += jitter

        # Cap at max_delay_seconds
        delay = min(delay, self.max_delay_seconds)

        # Cap cumulative wait
        if cumulative_wait + delay > self.max_cumulative_wait_seconds:
            return False, 0.0, (
                f"Cumulative wait ({cumulative_wait + delay:.1f}s) "
                f"would exceed ceiling of {self.max_cumulative_wait_seconds:.1f}s"
            )

        return True, delay, reason

    @staticmethod
    def _parse_retry_after(header_val: str) -> float | None:
        """Parse Retry-After header value as seconds or HTTP-date."""
        cleaned = header_val.strip()
        # 1. Decimal or integer seconds
        try:
            return max(0.0, float(cleaned))
        except ValueError:
            pass
        # 2. HTTP-date format (RFC 7231)
        try:
            # e.g. "Wed, 21 Oct 2026 07:28:00 GMT"
            dt = datetime.strptime(cleaned, "%a, %d %b %Y %H:%M:%S GMT").replace(
                tzinfo=timezone.utc
            )
            now = datetime.now(timezone.utc)
            diff = (dt - now).total_seconds()
            return max(0.0, diff)
        except ValueError:
            return None


class RateLimitPolicy:
    """Configurable rate-limiting policy per connector."""

    def __init__(
        self,
        *,
        min_interval_seconds: float = 1.0,
        single_connection_only: bool = False,
    ) -> None:
        self.min_interval_seconds = max(0.0, min_interval_seconds)
        self.single_connection_only = single_connection_only


@dataclass(frozen=True)
class IngestedItem:
    """Normalized source item parsed from a feed or research query.

    Adheres to ADR-003 and fair-use copyright doctrine: stores only a short
    summary/snippet, canonical metadata, and content hash. Never stores full
    copyrighted article or paper text.
    """

    source_id: str
    connector_name: str
    title: str
    canonical_url: str
    published_date: str | None
    summary_snippet: str
    content_sha256: str
    raw_item_dict: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)
    is_research_context: bool = False  # Set to True for arXiv research signals


@dataclass
class ConnectorExecutionResult:
    """Comprehensive result of an ingestion connector execution run."""

    connector_name: str
    source_url: str
    status: IngestionStatus
    status_code: int | None
    items: list[IngestedItem]
    raw_payload_bytes: bytes
    payload_sha256: str
    etag: str | None = None
    last_modified: str | None = None
    is_malformed: bool = False
    malformed_details: str | None = None
    retry_history: list[RetryDecision] = field(default_factory=list)
    execution_seconds: float = 0.0

    @property
    def item_count(self) -> int:
        return len(self.items)

    @property
    def is_success(self) -> bool:
        return self.status in (IngestionStatus.SUCCESS, IngestionStatus.NOT_MODIFIED)
