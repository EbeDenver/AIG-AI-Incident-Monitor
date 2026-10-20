"""Official arXiv API ingestion connector.

Retrieves research paper metadata strictly from the official export.arxiv.org API
through SecureHTTPClient, adhering to a 1-connection, 3-second rate limit,
filtering out PDF links, and explicitly labeling results as research/context signals.

Governing Charter: Project Constitution (Rules 1, 9, 11, 14, 15, 16),
ADR-008, SEC-002, OPS-002.
"""

from __future__ import annotations

import hashlib
import os
from typing import Any
import urllib.parse

import defusedxml.common
import defusedxml.ElementTree as dET
import feedparser

from ai_incident_monitor.ingestion.connectors.base import (
    BaseConnector,
    ConnectorParseError,
    DisallowedSourceError,
)
from ai_incident_monitor.ingestion.connectors.rss import sanitize_html_to_snippet
from ai_incident_monitor.ingestion.models import (
    ConnectorExecutionResult,
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

ARXIV_APPROVED_HOST = "export.arxiv.org"
ARXIV_DEFAULT_ENDPOINT = "https://export.arxiv.org/api/query"
DEFAULT_CONTACT_URL = "https://aiguardiansllc.us/bot"
DEFAULT_CONTACT_EMAIL = "bot@aiguardiansllc.us"
MAX_RESULTS_CEILING = 50


class ArXivConnector(BaseConnector):
    """Secure arXiv API metadata connector."""

    def __init__(
        self,
        *,
        http_client: SecureHTTPClient,
        metadata: ConnectorMetadata | None = None,
        contact_url: str = DEFAULT_CONTACT_URL,
        contact_email: str = DEFAULT_CONTACT_EMAIL,
        rate_limit_seconds: float = 3.0,
        retry_policy: RetryPolicy | None = None,
        enabled: bool | None = None,
    ) -> None:
        # Configuration switch: Disabled by default outside test environments
        # Checked via env var ARXIV_CONNECTOR_ENABLED
        if enabled is not None:
            is_enabled = enabled
        else:
            is_enabled = os.environ.get("ARXIV_CONNECTOR_ENABLED", "false").lower() in ("true", "1", "yes")

        meta = metadata or ConnectorMetadata(
            name="arxiv_research_connector",
            version="1.0.0",
            connector_type=ConnectorType.ARXIV,
            enabled=is_enabled,
            allowed_source_hosts=frozenset({ARXIV_APPROVED_HOST}),
            description="Official arXiv API metadata connector for AI research context",
        )

        # Strict policy: single connection, min 3.0s between requests
        rate_policy = RateLimitPolicy(
            min_interval_seconds=rate_limit_seconds,
            single_connection_only=True,
        )

        super().__init__(
            metadata=meta,
            http_client=http_client,
            rate_limit_policy=rate_policy,
            retry_policy=retry_policy,
        )
        self.contact_url = contact_url
        self.contact_email = contact_email

    @property
    def user_agent(self) -> str:
        """Responsible user agent identification string."""
        return f"AIIncidentMonitor/0.2.0 (+{self.contact_url}; mailto:{self.contact_email})"

    def health_check(self) -> bool:
        """Connector health verification."""
        return self.is_enabled

    def build_query_url(
        self,
        search_query: str,
        *,
        start: int = 0,
        max_results: int = 10,
        sort_by: str = "submittedDate",
        sort_order: str = "descending",
    ) -> str:
        """Build a validated query URL against export.arxiv.org."""
        if not search_query or not search_query.strip():
            raise ValueError("search_query must be a non-empty string")

        capped_max = min(max(1, max_results), MAX_RESULTS_CEILING)
        params = {
            "search_query": search_query.strip(),
            "start": max(0, start),
            "max_results": capped_max,
            "sortBy": sort_by,
            "sortOrder": sort_order,
        }
        query_string = urllib.parse.urlencode(params)
        return f"{ARXIV_DEFAULT_ENDPOINT}?{query_string}"

    def query(
        self,
        search_query: str,
        *,
        start: int = 0,
        max_results: int = 10,
    ) -> ConnectorExecutionResult:
        """Execute an official arXiv API search query."""
        url = self.build_query_url(search_query, start=start, max_results=max_results)
        custom_headers = {"User-Agent": self.user_agent}
        return self.fetch_and_parse(url, custom_headers=custom_headers)

    def _parse_payload(
        self,
        raw_bytes: bytes,
        source_url: str,
        response: SecureHTTPResponse,
    ) -> tuple[list[IngestedItem], bool, str | None]:
        """Parse raw Atom XML payload returned by the arXiv API."""
        if not raw_bytes or not raw_bytes.strip():
            return [], True, "Empty arXiv response"

        # XML entity protection
        try:
            dET.fromstring(raw_bytes)
        except defusedxml.common.DefusedXmlException as exc:
            raise SecurityError(f"Malicious XML entity detected in arXiv response: {exc}") from exc
        except Exception:
            pass

        feed = feedparser.parse(raw_bytes)
        is_malformed = bool(getattr(feed, "bozo", 0))
        malformed_details = str(getattr(feed, "bozo_exception", "")) if is_malformed else None

        items: list[IngestedItem] = []

        for entry in feed.entries:
            raw_id = getattr(entry, "id", "")
            title = getattr(entry, "title", "").strip().replace("\n", " ") or "Untitled arXiv Paper"

            # Normalize canonical abstract link (prefer https://arxiv.org/abs/...)
            canonical_url = raw_id.replace("http://", "https://")
            for link in getattr(entry, "links", []):
                # Never follow or store PDF links
                href = link.get("href", "")
                if link.get("rel") == "alternate" and "abs" in href:
                    canonical_url = href.replace("http://", "https://")
                    break

            published = getattr(entry, "published", None)
            raw_summary = getattr(entry, "summary", "").strip().replace("\n", " ")
            abstract_snippet = sanitize_html_to_snippet(raw_summary, max_length=1000)

            authors = [a.name for a in getattr(entry, "authors", []) if hasattr(a, "name")]
            primary_cat = getattr(entry, "arxiv_primary_category", {}).get("term", "cs.AI")

            # SHA-256 content hash
            sig = f"{canonical_url}|{title}|{published or ''}"
            item_sha256 = hashlib.sha256(sig.encode("utf-8")).hexdigest()
            source_id = f"SRC-ARXIV-{item_sha256[:12]}"

            raw_dict = {
                "arxiv_id": raw_id,
                "title": title,
                "authors": authors,
                "primary_category": primary_cat,
                "published": published,
                "abstract_snippet": abstract_snippet,
                "canonical_url": canonical_url,
            }

            item = IngestedItem(
                source_id=source_id,
                connector_name=self.name,
                title=title,
                canonical_url=canonical_url,
                published_date=published,
                summary_snippet=abstract_snippet,
                content_sha256=item_sha256,
                raw_item_dict=raw_dict,
                metadata={
                    "authors": authors,
                    "primary_category": primary_cat,
                    "signal_type": "RESEARCH_CONTEXT_SIGNAL_NOT_INCIDENT",
                    "disclaimer": "RESEARCH / CONTEXT SIGNAL — NOT A VERIFIED AI INCIDENT RECORD",
                },
                is_research_context=True,
            )
            items.append(item)

        return items, is_malformed, malformed_details
