"""OECD AI Incidents and Hazards Monitor (AIM) syndicated live feed connector.

Retrieves documented real-world AI incident and hazard records syndicated from the
OECD AIM platform, preserving canonical oecd.ai URLs, incident dates, and taxonomies,
routing them strictly as primary incident reports through SecureHTTPClient.

Governing Charter: Project Constitution (Rules 1, 2, 3, 7, 9, 11, 14, 15, 16),
ADR-008, ADR-009, DEC-P4-001.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any
import urllib.parse

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
    detect_prompt_injection_signals,
    sanitize_feed_text,
)

logger = logging.getLogger(__name__)

OECD_AIM_DEFAULT_ENDPOINT = "https://fail.ticker.io/data/wire.json"
OECD_AIM_APPROVED_HOST = "fail.ticker.io"


class OECDAIMFeedConnector(BaseConnector):
    """Secure connector for the syndicated OECD AI Incidents and Hazards Monitor live stream."""

    def __init__(
        self,
        *,
        http_client: SecureHTTPClient,
        metadata: ConnectorMetadata | None = None,
        rate_limit_seconds: float = 2.0,
        retry_policy: RetryPolicy | None = None,
        enabled: bool = True,
        max_snippet_length: int = 500,
    ) -> None:
        meta = metadata or ConnectorMetadata(
            name="oecd_aim_feed_connector",
            version="1.0.0",
            connector_type=ConnectorType.OECD_AIM_FEED,
            enabled=enabled,
            allowed_source_hosts=frozenset({OECD_AIM_APPROVED_HOST}),
            description="Live syndicated feed of OECD AI Incidents and Hazards Monitor (AIM) events",
        )

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
        self.max_snippet_length = max_snippet_length

    def health_check(self) -> bool:
        """Verify endpoint responsiveness."""
        try:
            res = self.http_client.get(OECD_AIM_DEFAULT_ENDPOINT)
            return res.is_success
        except Exception as exc:
            logger.warning(f"OECD AIM health check failed: {exc}")
            return False

    def _parse_payload(
        self,
        raw_bytes: bytes,
        source_url: str,
        response: SecureHTTPResponse,
    ) -> tuple[list[IngestedItem], bool, str | None]:
        """Parse raw JSON payload from the OECD AIM syndicated feed."""
        if not raw_bytes or not raw_bytes.strip():
            return [], True, "Empty feed payload"

        try:
            data = json.loads(raw_bytes.decode("utf-8"))
        except Exception as exc:
            return [], True, f"JSON decode error: {exc}"

        raw_items = data.get("items")
        if not isinstance(raw_items, list):
            return [], True, "Feed JSON missing 'items' list"

        items: list[IngestedItem] = []
        is_malformed = False
        malformed_details = None

        for idx, entry in enumerate(raw_items):
            if not isinstance(entry, dict):
                continue

            item_id = str(entry.get("id") or f"unidentified-{idx}").strip()
            title = str(entry.get("title") or "Untitled AI Incident").strip()
            published_date = str(entry.get("date") or "").strip() or None
            raw_url = str(entry.get("url") or "").strip()

            if raw_url:
                canonical_url = raw_url
            else:
                canonical_url = f"https://oecd.ai/en/incidents/{item_id}"

            raw_summary = str(entry.get("summary_full") or entry.get("summary") or "").strip()
            san_result = sanitize_feed_text(raw_summary)
            snippet = san_result.cleaned_text
            if len(snippet) > self.max_snippet_length:
                snippet = snippet[:self.max_snippet_length].rstrip() + "..."

            # Evaluate prompt injection signals
            inj_result = detect_prompt_injection_signals(
                raw_summary,
                had_bidi=san_result.removed_bidi_count > 0,
                had_zero_width=san_result.removed_zero_width_count > 0,
            )

            # Compute content hash
            content_sig = f"{canonical_url}|{title}|{published_date or ''}"
            item_sha256 = hashlib.sha256(content_sig.encode("utf-8")).hexdigest()

            source_id = f"SRC-OECD-{item_id}"

            raw_dict = {
                "id": item_id,
                "title": title,
                "date": published_date,
                "summary": snippet,
                "url": canonical_url,
                "tags": entry.get("tags", []),
                "level": entry.get("level", "incident"),
                "country": entry.get("country"),
                "publisher": "OECD AI Incidents and Hazards Monitor (AIM)",
                "curated": entry.get("curated", True),
                "has_injection_signals": len(inj_result.signal_codes) > 0,
            }

            item = IngestedItem(
                source_id=source_id,
                connector_name=self.name,
                title=title,
                published_date=published_date,
                summary_snippet=snippet,
                canonical_url=canonical_url,
                content_sha256=item_sha256,
                raw_item_dict=raw_dict,
                is_research_context=False,
            )
            items.append(item)

        return items, is_malformed, malformed_details
