"""Unit tests for the secure RSS and Atom feed connector."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ai_incident_monitor.ingestion.connectors.base import (
    ConnectorParseError,
    DisallowedSourceError,
)
from ai_incident_monitor.ingestion.connectors.rss import (
    RSSConnector,
    sanitize_html_to_snippet,
)
from ai_incident_monitor.ingestion.models import IngestionStatus, RateLimitPolicy
from ai_incident_monitor.security import (
    SecureHTTPClient,
    SecureHTTPResponse,
    SecurityError,
)

SAMPLE_RSS_2_0 = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>AI Safety &amp; Incidents Feed</title>
    <link>https://safe-news.org</link>
    <description>Tracking critical AI failure modes</description>
    <item>
      <title>Autonomous Vehicle Sensor Failure</title>
      <link>/reports/av-sensor-2026</link>
      <description>&lt;p&gt;A self-driving delivery pod &lt;b&gt;failed to detect&lt;/b&gt; a road obstacle in rainy conditions.&lt;/p&gt;&lt;script&gt;alert('xss')&lt;/script&gt;</description>
      <author>safety-analyst@safe-news.org</author>
      <pubDate>Mon, 19 Oct 2026 12:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Chatbot Financial Advice Loss</title>
      <link>https://safe-news.org/reports/chatbot-advice</link>
      <description>Customer lost funds following hallucinated tax advice.</description>
      <pubDate>Tue, 20 Oct 2026 09:30:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""

SAMPLE_ATOM_1_0 = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Autonomous Systems Incident Monitor</title>
  <link href="https://safe-news.org/atom" rel="self"/>
  <link href="https://safe-news.org" rel="alternate"/>
  <updated>2026-10-20T10:00:00Z</updated>
  <entry>
    <title>Facial Recognition False Match in Public Transit</title>
    <link href="/transit/false-positive-1" rel="alternate"/>
    <id>urn:uuid:60a76c80-d399-11d9-b91c-0003939e0af6</id>
    <updated>2026-10-20T08:00:00Z</updated>
    <summary type="html">&lt;div&gt;Commuter detained due to misidentified biometric scan.&lt;/div&gt;</summary>
  </entry>
</feed>"""


class TestRSSConnector:
    """Verifies RSS and Atom ingestion, XML security, and sanitization."""

    def test_sanitize_html_to_snippet(self) -> None:
        raw_html = (
            "<p>Alert: The <b>AI model</b> drifted!</p>"
            "<script>alert('pwn')</script>"
            "<span>Financial loss estimated &gt; &dollar;10,000.</span>"
        )
        snippet = sanitize_html_to_snippet(raw_html, max_length=100)
        assert "<p>" not in snippet
        assert "<b>" not in snippet
        assert "<script>" not in snippet
        assert "alert('pwn')" not in snippet or "<script>" not in snippet
        assert "&gt;" not in snippet
        assert ">" in snippet
        assert len(snippet) <= 103  # 100 + "..."

    def test_rss_2_0_parsing(self) -> None:
        mock_http = MagicMock(spec=SecureHTTPClient)
        mock_resp = SecureHTTPResponse(
            status_code=200,
            headers={"Content-Type": "application/rss+xml"},
            body=SAMPLE_RSS_2_0,
            final_url="https://safe-news.org/feed.xml",
            pinned_ip="93.184.216.34",
        )
        mock_http.get.return_value = mock_resp

        connector = RSSConnector(
            http_client=mock_http,
            allowed_source_hosts={"safe-news.org"},
            rate_limit_policy=RateLimitPolicy(min_interval_seconds=0.0),
        )

        result = connector.fetch_and_parse("https://safe-news.org/feed.xml")
        assert result.status == IngestionStatus.SUCCESS
        assert result.item_count == 2

        item1 = result.items[0]
        assert item1.title == "Autonomous Vehicle Sensor Failure"
        # Relative link resolved to absolute URL
        assert item1.canonical_url == "https://safe-news.org/reports/av-sensor-2026"
        assert item1.published_date == "Mon, 19 Oct 2026 12:00:00 GMT"
        assert "<script>" not in item1.summary_snippet
        assert item1.is_research_context is False

        item2 = result.items[1]
        assert item2.title == "Chatbot Financial Advice Loss"
        assert item2.canonical_url == "https://safe-news.org/reports/chatbot-advice"

    def test_atom_1_0_parsing(self) -> None:
        mock_http = MagicMock(spec=SecureHTTPClient)
        mock_resp = SecureHTTPResponse(
            status_code=200,
            headers={"Content-Type": "application/atom+xml"},
            body=SAMPLE_ATOM_1_0,
            final_url="https://safe-news.org/atom.xml",
            pinned_ip="93.184.216.34",
        )
        mock_http.get.return_value = mock_resp

        connector = RSSConnector(
            http_client=mock_http,
            allowed_source_hosts={"safe-news.org"},
            rate_limit_policy=RateLimitPolicy(min_interval_seconds=0.0),
        )

        result = connector.fetch_and_parse("https://safe-news.org/atom.xml")
        assert result.status == IngestionStatus.SUCCESS
        assert result.item_count == 1
        item = result.items[0]
        assert item.title == "Facial Recognition False Match in Public Transit"
        assert item.canonical_url == "https://safe-news.org/transit/false-positive-1"
        assert "Commuter detained" in item.summary_snippet
        assert "<div>" not in item.summary_snippet

    def test_feedparser_never_invoked_with_url(self) -> None:
        """Verify that feedparser.parse is strictly called with bytes, never a URL."""
        mock_http = MagicMock(spec=SecureHTTPClient)
        mock_resp = SecureHTTPResponse(
            status_code=200,
            headers={},
            body=SAMPLE_RSS_2_0,
            final_url="https://safe-news.org/feed.xml",
            pinned_ip="93.184.216.34",
        )
        mock_http.get.return_value = mock_resp

        connector = RSSConnector(
            http_client=mock_http,
            allowed_source_hosts={"safe-news.org"},
            rate_limit_policy=RateLimitPolicy(min_interval_seconds=0.0),
        )

        with patch("feedparser.parse", wraps=__import__("feedparser").parse) as mock_feedparser:
            connector.fetch_and_parse("https://safe-news.org/feed.xml")
            # Must be called once, and the first argument must be bytes, NOT a string URL
            assert mock_feedparser.call_count == 1
            first_arg = mock_feedparser.call_args[0][0]
            assert isinstance(first_arg, bytes)
            assert not isinstance(first_arg, str)

    def test_defusedxml_catches_xxe_entity_injection(self) -> None:
        """Verify that payloads containing malicious DTD/XXE entities trigger SecurityError."""
        xxe_payload = b"""<?xml version="1.0"?>
<!DOCTYPE lolz [
 <!ENTITY lol "lol">
 <!ELEMENT lolz (#PCDATA)>
]>
<rss><channel><title>&lol;</title></channel></rss>"""

        mock_http = MagicMock(spec=SecureHTTPClient)
        mock_resp = SecureHTTPResponse(
            status_code=200,
            headers={},
            body=xxe_payload,
            final_url="https://safe-news.org/xxe.xml",
            pinned_ip="93.184.216.34",
        )
        mock_http.get.return_value = mock_resp

        connector = RSSConnector(
            http_client=mock_http,
            allowed_source_hosts={"safe-news.org"},
            rate_limit_policy=RateLimitPolicy(min_interval_seconds=0.0),
        )

        with pytest.raises(SecurityError) as exc_info:
            connector.fetch_and_parse("https://safe-news.org/xxe.xml")
        assert "Malicious XML entity" in str(exc_info.value)

    def test_malformed_bozo_feed_handled_gracefully(self) -> None:
        """Malformed XML syntax triggers bozo warning but recovers salvageable entries."""
        # Unescaped ampersand produces a bozo syntax warning in feedparser
        malformed_xml = b"""<rss version="2.0">
          <channel>
            <title>Valid Feed</title>
            <link>https://safe-news.org</link>
            <item>
              <title>Salvageable Item with bad & unescaped entity</title>
              <link>https://safe-news.org/item1</link>
            </item>
          </channel>
        </rss>"""

        mock_http = MagicMock(spec=SecureHTTPClient)
        mock_resp = SecureHTTPResponse(
            status_code=200,
            headers={},
            body=malformed_xml,
            final_url="https://safe-news.org/feed.xml",
            pinned_ip="93.184.216.34",
        )
        mock_http.get.return_value = mock_resp

        connector = RSSConnector(
            http_client=mock_http,
            allowed_source_hosts={"safe-news.org"},
            strict_bozo=False,
            rate_limit_policy=RateLimitPolicy(min_interval_seconds=0.0),
        )

        result = connector.fetch_and_parse("https://safe-news.org/feed.xml")
        assert result.is_malformed is True
        assert result.malformed_details is not None
        assert result.status == IngestionStatus.PARTIAL
        assert result.item_count >= 1

    def test_strict_bozo_rejects_empty_corrupted_feed(self) -> None:
        corrupted = b"THIS IS NOT XML AT ALL GIBBERISH"
        mock_http = MagicMock(spec=SecureHTTPClient)
        mock_resp = SecureHTTPResponse(
            status_code=200,
            headers={},
            body=corrupted,
            final_url="https://safe-news.org/corrupt.xml",
            pinned_ip="93.184.216.34",
        )
        mock_http.get.return_value = mock_resp

        connector = RSSConnector(
            http_client=mock_http,
            allowed_source_hosts={"safe-news.org"},
            strict_bozo=True,
            rate_limit_policy=RateLimitPolicy(min_interval_seconds=0.0),
        )

        with pytest.raises(ConnectorParseError):
            connector.fetch_and_parse("https://safe-news.org/corrupt.xml")
