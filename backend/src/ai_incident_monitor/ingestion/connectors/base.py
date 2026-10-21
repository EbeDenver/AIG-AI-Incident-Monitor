"""Pluggable base connector interface, lifecycle, and resilient fetch orchestration.

Governing Charter: Project Constitution (Rules 1, 9, 11, 14, 15, 16),
ADR-008, SEC-002, OPS-002.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import hashlib
import time
from typing import Any
import urllib.parse

from ai_incident_monitor.ingestion.models import (
    ConnectorExecutionResult,
    ConnectorMetadata,
    IngestedItem,
    IngestionStatus,
    RateLimitPolicy,
    RetryDecision,
    RetryPolicy,
)
from ai_incident_monitor.ingestion.rate_limiter import ConnectorRateLimiter
from ai_incident_monitor.security import (
    SecureHTTPClient,
    SecureHTTPResponse,
    SecurityError,
)


class ConnectorError(Exception):
    """Base exception for connector execution errors."""


class ConnectorDisabledError(ConnectorError):
    """Raised when an operation is attempted on a disabled connector."""


class DisallowedSourceError(ConnectorError):
    """Raised when a fetch target host is not in the connector's approved allowlist."""


class ConnectorParseError(ConnectorError):
    """Raised when payload parsing fails due to malformed or unparseable input."""


class BaseConnector(ABC):
    """Abstract base class for all pluggable source ingestion connectors.

    Enforces:
    - Mandatory routing of all network traffic through SecureHTTPClient (SSRF defense).
    - Per-connector rate limiting and concurrency control.
    - Exponential backoff with jitter on transient failures (429, 503, timeouts).
    - Strict adherence to source domain allowlists.
    - Zero direct use of unshielded network libraries.
    """

    def __init__(
        self,
        metadata: ConnectorMetadata,
        http_client: SecureHTTPClient,
        *,
        rate_limit_policy: RateLimitPolicy | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self.metadata = metadata
        self.http_client = http_client
        self.rate_limit_policy = rate_limit_policy or RateLimitPolicy()
        self.retry_policy = retry_policy or RetryPolicy()
        self.rate_limiter = ConnectorRateLimiter(self.rate_limit_policy)

    @property
    def name(self) -> str:
        return self.metadata.name

    @property
    def is_enabled(self) -> bool:
        return self.metadata.enabled

    def validate_target_host(self, url: str) -> str:
        """Validate that the target URL's host is in the approved source allowlist.

        Returns:
            The normalized hostname string.

        Raises:
            DisallowedSourceError: If the host is not permitted.
        """
        parsed = urllib.parse.urlsplit(url)
        host = (parsed.hostname or "").lower().strip()
        if not host:
            raise DisallowedSourceError(f"Could not determine valid hostname from '{url}'")

        if self.metadata.allowed_source_hosts and host not in self.metadata.allowed_source_hosts:
            raise DisallowedSourceError(
                f"Host '{host}' is not in approved allowlist for connector '{self.name}'. "
                f"Allowed hosts: {sorted(self.metadata.allowed_source_hosts)}"
            )
        return host

    @abstractmethod
    def health_check(self) -> bool:
        """Verify connector operational health without full payload ingestion."""
        ...

    @abstractmethod
    def _parse_payload(
        self,
        raw_bytes: bytes,
        source_url: str,
        response: SecureHTTPResponse,
    ) -> tuple[list[IngestedItem], bool, str | None]:
        """Parse raw payload bytes into IngestedItems.

        Returns:
            (items, is_malformed, malformed_details)
        """
        ...

    def fetch_and_parse(
        self,
        url: str,
        *,
        etag: str | None = None,
        last_modified: str | None = None,
        custom_headers: dict[str, str] | None = None,
    ) -> ConnectorExecutionResult:
        """Execute a secured, rate-limited, retried fetch and parse run."""
        start_time = time.monotonic()

        if not self.is_enabled:
            raise ConnectorDisabledError(f"Connector '{self.name}' is currently disabled")

        # Validate target host against connector's specific allowlist
        self.validate_target_host(url)

        headers = dict(custom_headers or {})
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified

        retry_history: list[RetryDecision] = []
        cumulative_wait = 0.0
        attempt = 0

        with self.rate_limiter.connection_guard():
            while True:
                # Enforce per-connector rate limit
                self.rate_limiter.acquire()

                resp: SecureHTTPResponse | None = None
                caught_exc: Exception | None = None

                try:
                    resp = self.http_client.get(url, headers=headers)
                except SecurityError:
                    # Security and SSRF errors are NEVER retried
                    raise
                except Exception as exc:
                    caught_exc = exc

                # Check if request succeeded (200 OK)
                if resp is not None and resp.is_success:
                    payload_bytes = resp.body
                    payload_sha256 = hashlib.sha256(payload_bytes).hexdigest()

                    resp_etag = resp.headers.get("etag") or resp.headers.get("ETag")
                    resp_last_modified = (
                        resp.headers.get("last-modified") or resp.headers.get("Last-Modified")
                    )

                    try:
                        items, is_malformed, malformed_details = self._parse_payload(
                            payload_bytes, resp.final_url, resp
                        )
                    except SecurityError:
                        # Security violations (e.g. XXE entity expansion) must propagate directly
                        raise
                    except Exception as exc:
                        raise ConnectorParseError(
                            f"Connector '{self.name}' failed parsing payload from '{url}': {exc}"
                        ) from exc

                    if is_malformed:
                        status = IngestionStatus.PARTIAL if items else IngestionStatus.FAILED
                    else:
                        status = IngestionStatus.SUCCESS

                    return ConnectorExecutionResult(
                        connector_name=self.name,
                        source_url=url,
                        status=status,
                        status_code=resp.status_code,
                        items=items,
                        raw_payload_bytes=payload_bytes,
                        payload_sha256=payload_sha256,
                        etag=resp_etag,
                        last_modified=resp_last_modified,
                        is_malformed=is_malformed,
                        malformed_details=malformed_details,
                        retry_history=retry_history,
                        execution_seconds=time.monotonic() - start_time,
                    )

                # Check for 304 Not Modified
                if resp is not None and resp.status_code == 304:
                    return ConnectorExecutionResult(
                        connector_name=self.name,
                        source_url=url,
                        status=IngestionStatus.NOT_MODIFIED,
                        status_code=304,
                        items=[],
                        raw_payload_bytes=b"",
                        payload_sha256=hashlib.sha256(b"").hexdigest(),
                        etag=etag,
                        last_modified=last_modified,
                        retry_history=retry_history,
                        execution_seconds=time.monotonic() - start_time,
                    )

                # Evaluate retry
                status_code = resp.status_code if resp is not None else None
                retry_after_hdr = None
                if resp is not None:
                    retry_after_hdr = resp.headers.get("retry-after") or resp.headers.get("Retry-After")

                should_retry, delay, reason = self.retry_policy.evaluate_retry(
                    attempt=attempt,
                    cumulative_wait=cumulative_wait,
                    status_code=status_code,
                    retry_after_header=retry_after_hdr,
                    exception=caught_exc,
                )

                decision = RetryDecision(
                    attempt=attempt + 1,
                    status_code=status_code,
                    delay_seconds=delay,
                    reason=reason,
                )
                retry_history.append(decision)

                if should_retry:
                    time.sleep(delay)
                    cumulative_wait += delay
                    attempt += 1
                    continue

                # Retry exhausted or non-retryable failure
                err_msg = (
                    f"Connector '{self.name}' fetch failed for '{url}' "
                    f"(status={status_code}, error={caught_exc}): {reason}"
                )
                return ConnectorExecutionResult(
                    connector_name=self.name,
                    source_url=url,
                    status=IngestionStatus.FAILED,
                    status_code=status_code,
                    items=[],
                    raw_payload_bytes=b"",
                    payload_sha256=hashlib.sha256(b"").hexdigest(),
                    retry_history=retry_history,
                    execution_seconds=time.monotonic() - start_time,
                    malformed_details=err_msg,
                )
