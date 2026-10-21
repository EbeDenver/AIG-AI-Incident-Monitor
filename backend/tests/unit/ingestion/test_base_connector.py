"""Unit tests verifying BaseConnector contract enforcement, host allowlists, and retry loops."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ai_incident_monitor.ingestion.connectors.base import (
    BaseConnector,
    ConnectorDisabledError,
    DisallowedSourceError,
)
from ai_incident_monitor.ingestion.models import (
    ConnectorMetadata,
    ConnectorType,
    IngestedItem,
    IngestionStatus,
    RateLimitPolicy,
    RetryPolicy,
)
from ai_incident_monitor.security import (
    BlockedIPError,
    SecureHTTPClient,
    SecureHTTPResponse,
)


class DummyConnector(BaseConnector):
    """Concrete test implementation of BaseConnector."""

    def health_check(self) -> bool:
        return self.is_enabled

    def _parse_payload(
        self,
        raw_bytes: bytes,
        source_url: str,
        response: SecureHTTPResponse,
    ) -> tuple[list[IngestedItem], bool, str | None]:
        item = IngestedItem(
            source_id="SRC-DUMMY-1",
            connector_name=self.name,
            title="Dummy Title",
            canonical_url=f"{source_url}#1",
            published_date="2026-10-20T00:00:00Z",
            summary_snippet="Dummy snippet",
            content_sha256="abc123sha",
            raw_item_dict={"raw": "test"},
        )
        return [item], False, None


class TestBaseConnectorContract:
    """Verifies that BaseConnector enforces security, allowlists, and lifecycles."""

    def test_disabled_connector_raises_error(self) -> None:
        mock_http = MagicMock(spec=SecureHTTPClient)
        meta = ConnectorMetadata(
            name="disabled_connector",
            version="1.0.0",
            connector_type=ConnectorType.RSS,
            enabled=False,
            allowed_source_hosts=frozenset({"example.com"}),
            description="Test disabled",
        )
        connector = DummyConnector(metadata=meta, http_client=mock_http)
        assert connector.is_enabled is False

        with pytest.raises(ConnectorDisabledError) as exc_info:
            connector.fetch_and_parse("https://example.com/feed.xml")
        assert "is currently disabled" in str(exc_info.value)
        mock_http.get.assert_not_called()

    def test_disallowed_source_host_raises_error(self) -> None:
        mock_http = MagicMock(spec=SecureHTTPClient)
        meta = ConnectorMetadata(
            name="allowlist_connector",
            version="1.0.0",
            connector_type=ConnectorType.RSS,
            enabled=True,
            allowed_source_hosts=frozenset({"news.allowed.com", "reports.allowed.com"}),
            description="Test allowlist",
        )
        connector = DummyConnector(metadata=meta, http_client=mock_http)

        with pytest.raises(DisallowedSourceError) as exc_info:
            connector.fetch_and_parse("https://unapproved-source.com/feed.xml")
        assert "is not in approved allowlist" in str(exc_info.value)
        mock_http.get.assert_not_called()

    def test_successful_fetch_and_parse_lifecycle(self) -> None:
        mock_http = MagicMock(spec=SecureHTTPClient)
        mock_resp = SecureHTTPResponse(
            status_code=200,
            headers={"Content-Type": "application/xml", "ETag": '"xyz123"'},
            body=b"<xml>content</xml>",
            final_url="https://news.allowed.com/feed.xml",
            pinned_ip="93.184.216.34",
        )
        mock_http.get.return_value = mock_resp

        meta = ConnectorMetadata(
            name="test_conn",
            version="1.0.0",
            connector_type=ConnectorType.RSS,
            enabled=True,
            allowed_source_hosts=frozenset({"news.allowed.com"}),
            description="Test",
        )
        connector = DummyConnector(
            metadata=meta,
            http_client=mock_http,
            rate_limit_policy=RateLimitPolicy(min_interval_seconds=0.0),
        )

        result = connector.fetch_and_parse("https://news.allowed.com/feed.xml")
        assert result.status == IngestionStatus.SUCCESS
        assert result.status_code == 200
        assert result.item_count == 1
        assert result.items[0].title == "Dummy Title"
        assert result.etag == '"xyz123"'
        assert len(result.retry_history) == 0
        mock_http.get.assert_called_once()

    def test_conditional_request_304_not_modified(self) -> None:
        mock_http = MagicMock(spec=SecureHTTPClient)
        mock_resp = SecureHTTPResponse(
            status_code=304,
            headers={},
            body=b"",
            final_url="https://news.allowed.com/feed.xml",
            pinned_ip="93.184.216.34",
        )
        mock_http.get.return_value = mock_resp

        meta = ConnectorMetadata(
            name="test_conn",
            version="1.0.0",
            connector_type=ConnectorType.RSS,
            enabled=True,
            allowed_source_hosts=frozenset({"news.allowed.com"}),
            description="Test",
        )
        connector = DummyConnector(
            metadata=meta,
            http_client=mock_http,
            rate_limit_policy=RateLimitPolicy(min_interval_seconds=0.0),
        )

        result = connector.fetch_and_parse(
            "https://news.allowed.com/feed.xml",
            etag='"prev_etag"',
            last_modified="Mon, 19 Oct 2026 12:00:00 GMT",
        )
        assert result.status == IngestionStatus.NOT_MODIFIED
        assert result.status_code == 304
        assert result.item_count == 0
        # Verified conditional headers were passed to SecureHTTPClient
        call_headers = mock_http.get.call_args[1]["headers"]
        assert call_headers["If-None-Match"] == '"prev_etag"'
        assert call_headers["If-Modified-Since"] == "Mon, 19 Oct 2026 12:00:00 GMT"

    def test_transient_failure_retries_and_succeeds(self) -> None:
        mock_http = MagicMock(spec=SecureHTTPClient)
        # Attempt 1: 503 Service Unavailable
        resp_503 = SecureHTTPResponse(
            status_code=503,
            headers={},
            body=b"Unavailable",
            final_url="https://news.allowed.com/feed.xml",
            pinned_ip="93.184.216.34",
        )
        # Attempt 2: 200 OK
        resp_200 = SecureHTTPResponse(
            status_code=200,
            headers={},
            body=b"<xml>ok</xml>",
            final_url="https://news.allowed.com/feed.xml",
            pinned_ip="93.184.216.34",
        )
        mock_http.get.side_effect = [resp_503, resp_200]

        meta = ConnectorMetadata(
            name="retry_conn",
            version="1.0.0",
            connector_type=ConnectorType.RSS,
            enabled=True,
            allowed_source_hosts=frozenset({"news.allowed.com"}),
            description="Test retry",
        )
        retry_policy = RetryPolicy(max_retries=2, base_delay_seconds=0.01, jitter_factor=0.0)
        connector = DummyConnector(
            metadata=meta,
            http_client=mock_http,
            rate_limit_policy=RateLimitPolicy(min_interval_seconds=0.0),
            retry_policy=retry_policy,
        )

        with patch("time.sleep"):
            result = connector.fetch_and_parse("https://news.allowed.com/feed.xml")

        assert result.status == IngestionStatus.SUCCESS
        assert len(result.retry_history) == 1
        assert result.retry_history[0].status_code == 503
        assert mock_http.get.call_count == 2

    def test_security_violation_never_retried(self) -> None:
        mock_http = MagicMock(spec=SecureHTTPClient)
        # Simulate SSRF block during resolution
        mock_http.get.side_effect = BlockedIPError("169.254.169.254", "Cloud Metadata")

        meta = ConnectorMetadata(
            name="security_conn",
            version="1.0.0",
            connector_type=ConnectorType.RSS,
            enabled=True,
            allowed_source_hosts=frozenset({"news.allowed.com"}),
            description="Test",
        )
        connector = DummyConnector(
            metadata=meta,
            http_client=mock_http,
            rate_limit_policy=RateLimitPolicy(min_interval_seconds=0.0),
        )

        with pytest.raises(BlockedIPError):
            connector.fetch_and_parse("https://news.allowed.com/feed.xml")
        # Absolutely only called once — no retries for security errors
        assert mock_http.get.call_count == 1
