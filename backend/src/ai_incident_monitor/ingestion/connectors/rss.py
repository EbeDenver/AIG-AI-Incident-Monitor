"""Secure RSS and Atom feed connector.

Retrieves feeds strictly through SecureHTTPClient, parses in-memory bytes
with defusedxml and feedparser (never passing URLs to parser libraries),
sanitizes HTML summaries into fair-use snippets, tracks parse anomalies (bozo),
and resolves relative links against approved feed source URLs.

Governing Charter: Project Constitution (Rules 1, 9, 11, 14, 15, 16),
ADR-008, SEC-002, PRI-002.
"""

from __future__ import annotations

import hashlib
import html
import re
from typing import Any
import urllib.parse

import defusedxml.common
import defusedxml.ElementTree as dET
import feedparser

from ai_incident_monitor.ingestion.connectors.base import (
    BaseConnector,
    ConnectorParseError,
)
from ai_incident_monitor.ingestion.models import (
    ConnectorMetadata,
    ConnectorType,
    IngestedItem,
    RateLimitPolicy,
    RetryPolicy,
)
from ai_incident_monitor.security import (
    SecureHTTPClient,
    SecureHTTPResponse,
    SecurityError,
)

DEFAULT_MAX_SNIPPET_LENGTH: int = 500
HTML_TAG_REGEX: re.Pattern[str] = re.compile(r"<[^>]+>")
WHITESPACE_REGEX: re.Pattern[str] = re.compile(r"\s+")


def sanitize_html_to_snippet(
    raw_html_or_text: str,
    *,
    max_length: int = DEFAULT_MAX_SNIPPET_LENGTH,
) -> str:
    """Strip HTML tags, unescape HTML entities, and truncate to fair-use snippet length."""
    if not raw_html_or_text:
        return ""

    # Strip HTML tags
    stripped = HTML_TAG_REGEX.sub(" ", raw_html_or_text)
    # Unescape HTML entities (&amp; -> &, &lt; -> <, etc.)
    unescaped = html.unescape(stripped)
    # Normalize whitespace
    normalized = WHITESPACE_REGEX.sub(" ", unescaped).strip()

    if len(normalized) > max_length:
        return normalized[:max_length].rstrip() + "..."
    return normalized


class RSSConnector(BaseConnector):
    """Hardened RSS 2.0 and Atom 1.0 feed connector."""

    def __init__(
        self,
        *,
        http_client: SecureHTTPClient,
        metadata: ConnectorMetadata | None = None,
        allowed_source_hosts: set[str] | frozenset[str] | None = None,
        max_snippet_length: int = DEFAULT_MAX_SNIPPET_LENGTH,
        strict_bozo: bool = False,
        rate_limit_policy: RateLimitPolicy | None = None,
        retry_policy: RetryPolicy | None = None,
        enabled: bool = True,
    ) -> None:
        hosts = frozenset(h.lower() for h in (allowed_source_hosts or set()))
        meta = metadata or ConnectorMetadata(
            name="rss_news_connector",
            version="1.0.0",
            connector_type=ConnectorType.RSS,
            enabled=enabled,
            allowed_source_hosts=hosts,
            description="Secure RSS and Atom feed connector for approved news feeds",
        )
        super().__init__(
            metadata=meta,
            http_client=http_client,
            rate_limit_policy=rate_limit_policy,
            retry_policy=retry_policy,
        )
        self.max_snippet_length = max_snippet_length
        self.strict_bozo = strict_bozo

    def health_check(self) -> bool:
        """Connector health verification."""
        return self.is_enabled

    def _parse_payload(
        self,
        raw_bytes: bytes,
        source_url: str,
        response: SecureHTTPResponse,
    ) -> tuple[list[IngestedItem], bool, str | None]:
        """Parse raw feed bytes safely.

        1. Pre-flight check with defusedxml to block XXE entity expansions.
        2. Feedparser parses in-memory bytes only (zero network activity).
        3. Sanitizes HTML summaries, resolves relative URLs, and hashes items.
        """
        if not raw_bytes or not raw_bytes.strip():
            return [], True, "Empty feed payload"

        # 1. XML Security: Pre-screen bytes with defusedxml for XXE entity bombs
        try:
            dET.fromstring(raw_bytes)
        except defusedxml.common.DefusedXmlException as exc:
            raise SecurityError(f"Malicious XML entity detected by defusedxml: {exc}") from exc
        except Exception:
            # Not strict XML or has minor syntax issues that feedparser's robust parser can handle
            pass

        # 2. Feedparser parses in-memory bytes
        # Note: raw_bytes is passed directly as data, NOT a URL.
        feed = feedparser.parse(raw_bytes)

        is_malformed = False
        malformed_details: str | None = None

        if getattr(feed, "bozo", 0) != 0:
            is_malformed = True
            bozo_exc = getattr(feed, "bozo_exception", None)
            malformed_details = f"Feed bozo parse warning/error: {bozo_exc}"

            if self.strict_bozo and len(feed.entries) == 0:
                raise ConnectorParseError(f"Malformed feed rejected under strict_bozo policy: {bozo_exc}")

        items: list[IngestedItem] = []
        feed_channel_title = getattr(feed.feed, "title", "Unknown Feed")

        for idx, entry in enumerate(feed.entries):
            title = getattr(entry, "title", "").strip() or "Untitled Entry"
            raw_link = getattr(entry, "link", "").strip()

            # Resolve relative links against the source URL
            if raw_link:
                canonical_link = urllib.parse.urljoin(source_url, raw_link)
            else:
                canonical_link = f"{source_url}#entry-{idx}"

            published_date = getattr(entry, "published", None) or getattr(entry, "updated", None)

            # Extract and sanitize summary / content
            raw_summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
            if not raw_summary and getattr(entry, "content", None):
                content_list = entry.content
                if content_list and isinstance(content_list, list):
                    raw_summary = content_list[0].get("value", "")

            snippet = sanitize_html_to_snippet(raw_summary, max_length=self.max_snippet_length)

            # Compute item content hash
            content_sig = f"{canonical_link}|{title}|{published_date or ''}"
            item_sha256 = hashlib.sha256(content_sig.encode("utf-8")).hexdigest()

            # Generate prefixed source ID
            source_id = f"SRC-RSS-{item_sha256[:12]}"

            raw_dict = {
                "title": title,
                "link": canonical_link,
                "published": published_date,
                "author": getattr(entry, "author", None),
                "tags": [t.get("term") for t in getattr(entry, "tags", []) if t.get("term")],
                "summary_snippet": snippet,
            }

            item = IngestedItem(
                source_id=source_id,
                connector_name=self.name,
                title=title,
                canonical_url=canonical_link,
                published_date=published_date,
                summary_snippet=snippet,
                content_sha256=item_sha256,
                raw_item_dict=raw_dict,
                metadata={
                    "feed_title": feed_channel_title,
                    "feed_source_url": source_url,
                    "bozo": bool(getattr(feed, "bozo", 0)),
                },
                is_research_context=False,
            )
            items.append(item)

        return items, is_malformed, malformed_details
