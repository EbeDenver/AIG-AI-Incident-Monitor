"""Unit tests for official arXiv API connector."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ai_incident_monitor.ingestion.connectors.arxiv import (
    ARXIV_APPROVED_HOST,
    ARXIV_DEFAULT_ENDPOINT,
    ArXivConnector,
)
from ai_incident_monitor.ingestion.connectors.base import (
    ConnectorDisabledError,
    DisallowedSourceError,
)
from ai_incident_monitor.ingestion.models import IngestionStatus, RetryPolicy
from ai_incident_monitor.security import (
    SecureHTTPClient,
    SecureHTTPResponse,
)

SAMPLE_ARXIV_RESPONSE = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <link href="http://arxiv.org/api/query?search_query=all:agent&amp;start=0&amp;max_results=1" rel="self" type="application/atom+xml"/>
  <title type="html">ArXiv Query: search_query=all:agent</title>
  <id>http://arxiv.org/api/12345</id>
  <updated>2026-10-20T00:00:00-04:00</updated>
  <entry>
    <id>http://arxiv.org/abs/2601.12345v1</id>
    <updated>2026-01-15T18:00:00Z</updated>
    <published>2026-01-15T18:00:00Z</published>
    <title>Defending Autonomous Coding Agents Against Indirect Injection</title>
    <summary>We present defense-in-depth isolation wrappers for autonomous agents.</summary>
    <author>
      <name>Dr. Jane Doe</name>
    </author>
    <author>
      <name>Prof. John Smith</name>
    </author>
    <link href="http://arxiv.org/abs/2601.12345v1" rel="alternate" type="text/html"/>
    <link title="pdf" href="http://arxiv.org/pdf/2601.12345v1" rel="related" type="application/pdf"/>
    <arxiv:primary_category xmlns:arxiv="http://arxiv.org/schemas/atom" term="cs.CR"/>
  </entry>
</feed>"""


class TestArXivConnector:
    """Verifies arXiv API allowlisting, rate-limiting, and epistemic signaling."""

    def test_arxiv_endpoint_allowlist_strictly_export_arxiv_org(self) -> None:
        mock_http = MagicMock(spec=SecureHTTPClient)
        connector = ArXivConnector(http_client=mock_http, enabled=True, rate_limit_seconds=0.0)

        assert connector.metadata.allowed_source_hosts == frozenset({ARXIV_APPROVED_HOST})

        # Scraping main website arxiv.org is forbidden
        with pytest.raises(DisallowedSourceError) as exc_info:
            connector.fetch_and_parse("https://arxiv.org/abs/2601.12345")
        assert "not in approved allowlist" in str(exc_info.value)

        # Non-arxiv hosts are forbidden
        with pytest.raises(DisallowedSourceError):
            connector.fetch_and_parse("https://google.com/search")

    def test_disabled_by_default_outside_test_mode(self) -> None:
        mock_http = MagicMock(spec=SecureHTTPClient)
        with patch.dict("os.environ", {}, clear=True):
            connector = ArXivConnector(http_client=mock_http)
            assert connector.is_enabled is False
            with pytest.raises(ConnectorDisabledError):
                connector.query("all:test")

    def test_query_url_builder(self) -> None:
        mock_http = MagicMock(spec=SecureHTTPClient)
        connector = ArXivConnector(http_client=mock_http, enabled=True, rate_limit_seconds=0.0)

        url = connector.build_query_url("all:agent", start=0, max_results=10)
        assert url.startswith(ARXIV_DEFAULT_ENDPOINT)
        assert "search_query=all%3Aagent" in url
        assert "max_results=10" in url
        assert "start=0" in url

        # Max results ceiling capped at 50
        capped_url = connector.build_query_url("all:agent", max_results=500)
        assert "max_results=50" in capped_url

    def test_query_parsing_and_epistemic_context_signal(self) -> None:
        mock_http = MagicMock(spec=SecureHTTPClient)
        mock_resp = SecureHTTPResponse(
            status_code=200,
            headers={"Content-Type": "application/atom+xml"},
            body=SAMPLE_ARXIV_RESPONSE,
            final_url=f"{ARXIV_DEFAULT_ENDPOINT}?search_query=all%3Aagent",
            pinned_ip="128.84.21.199",
        )
        mock_http.get.return_value = mock_resp

        connector = ArXivConnector(
            http_client=mock_http,
            enabled=True,
            rate_limit_seconds=0.0,
            contact_url="https://aiguardiansllc.us/bot",
            contact_email="bot@aiguardiansllc.us",
        )

        result = connector.query("all:agent", max_results=1)
        assert result.status == IngestionStatus.SUCCESS
        assert result.item_count == 1

        item = result.items[0]
        assert item.title == "Defending Autonomous Coding Agents Against Indirect Injection"
        # Canonical URL is HTTPS abstract page
        assert item.canonical_url == "https://arxiv.org/abs/2601.12345v1"
        assert "We present defense-in-depth" in item.summary_snippet
        # Critical rule: Must be explicitly marked as research context signal, not an incident
        assert item.is_research_context is True
        assert item.metadata["signal_type"] == "RESEARCH_CONTEXT_SIGNAL_NOT_INCIDENT"
        assert "RESEARCH / CONTEXT SIGNAL" in item.metadata["disclaimer"]

        # User-Agent check: includes responsible contact info
        call_headers = mock_http.get.call_args[1]["headers"]
        assert "AIIncidentMonitor/0.2.0" in call_headers["User-Agent"]
        assert "mailto:bot@aiguardiansllc.us" in call_headers["User-Agent"]

    def test_pdf_links_are_never_followed_or_downloaded(self) -> None:
        """Verify that PDF URLs in feed entries are ignored and not fetched."""
        mock_http = MagicMock(spec=SecureHTTPClient)
        mock_resp = SecureHTTPResponse(
            status_code=200,
            headers={"Content-Type": "application/atom+xml"},
            body=SAMPLE_ARXIV_RESPONSE,
            final_url=f"{ARXIV_DEFAULT_ENDPOINT}?search_query=all%3Aagent",
            pinned_ip="128.84.21.199",
        )
        mock_http.get.return_value = mock_resp

        connector = ArXivConnector(http_client=mock_http, enabled=True, rate_limit_seconds=0.0)
        result = connector.query("all:agent")

        # The only HTTP get call was the API query itself
        assert mock_http.get.call_count == 1
        # No get call for .pdf
        for call in mock_http.get.call_args_list:
            assert ".pdf" not in call[0][0]

    def test_single_connection_policy_enforced(self) -> None:
        mock_http = MagicMock(spec=SecureHTTPClient)
        connector = ArXivConnector(http_client=mock_http, enabled=True, rate_limit_seconds=0.0)
        assert connector.rate_limiter.single_connection_only is True
        assert connector.rate_limiter.min_interval_seconds == 0.0  # overridden in test
