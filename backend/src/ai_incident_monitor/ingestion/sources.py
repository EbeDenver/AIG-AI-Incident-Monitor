"""Configured ingestion source definitions and role classification.

Governing Charter: Project Constitution (Rules 1, 3, 4, 11, 14, 15, 16),
ADR-008, SEC-002, OPS-002.
"""

from __future__ import annotations

from enum import Enum
import json
import os
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from ai_incident_monitor.db.session import get_repo_root
from ai_incident_monitor.ingestion.models import ConnectorType


class SourceRole(str, Enum):
    """Epistemic role of an ingestion source."""

    PRIMARY_INCIDENT_REPORT = "primary_incident_report"
    SUPPLEMENTARY_RESEARCH_CONTEXT = "supplementary_research_context"
    OFFICIAL_MANUAL_EXPORT = "offline_official_export"


class SourceConfig(BaseModel):
    """Validated configuration for an individual ingestion source."""

    source_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    connector_type: ConnectorType
    role: SourceRole
    endpoint_url: str = ""
    allowed_hosts: list[str] = Field(default_factory=list)
    query_params: dict[str, Any] = Field(default_factory=dict)
    rate_limit_seconds: float = Field(default=1.0, ge=0.0)
    enabled: bool = False
    description: str = ""

    @property
    def is_live_feed(self) -> bool:
        """Indicates whether this source can be polled over the network."""
        return (
            self.connector_type in (ConnectorType.RSS, ConnectorType.ATOM, ConnectorType.ARXIV)
            and bool(self.endpoint_url)
            and self.endpoint_url.startswith(("http://", "https://"))
        )

    @property
    def is_primary_incident_source(self) -> bool:
        """Indicates whether distinct items from this source create primary incident records."""
        return self.role == SourceRole.PRIMARY_INCIDENT_REPORT


DEFAULT_CONFIG_PATH = Path("config") / "sources.json"


def get_default_sources() -> list[SourceConfig]:
    """Return fallback source definitions if configuration file is not present."""
    return [
        SourceConfig(
            source_id="oecd_aim_live",
            name="OECD AI Incidents and Hazards Monitor (Live Feed)",
            connector_type=ConnectorType.OECD_AIM_FEED,
            role=SourceRole.PRIMARY_INCIDENT_REPORT,
            endpoint_url="https://fail.ticker.io/data/wire.json",
            allowed_hosts=["fail.ticker.io"],
            query_params={},
            rate_limit_seconds=2.0,
            enabled=True,
            description="Live syndicated feed of OECD AI Incidents and Hazards Monitor (AIM) events. Provides primary AI incident records linking canonically to oecd.ai.",
        ),
        SourceConfig(
            source_id="arxiv_research",
            name="arXiv AI Research Papers",
            connector_type=ConnectorType.ARXIV,
            role=SourceRole.SUPPLEMENTARY_RESEARCH_CONTEXT,
            endpoint_url="https://export.arxiv.org/api/query",
            allowed_hosts=["export.arxiv.org"],
            query_params={
                "search_query": "cat:cs.AI AND (incident OR safety OR \"failure mode\")",
                "max_results": 25,
            },
            rate_limit_seconds=3.0,
            enabled=os.environ.get("ARXIV_CONNECTOR_ENABLED", "false").lower() in ("true", "1", "yes"),
            description="Supplementary academic research context. Ingested papers provide research signals and citations; they are not classified as primary incidents.",
        ),
        SourceConfig(
            source_id="rss_incident_feed",
            name="Primary AI Incident News Stream",
            connector_type=ConnectorType.RSS,
            role=SourceRole.PRIMARY_INCIDENT_REPORT,
            endpoint_url="",
            allowed_hosts=[],
            query_params={},
            rate_limit_seconds=1.0,
            enabled=False,
            description="Primary AI incident reporting feed. Pending operator specification of approved live news or incident feed URL.",
        ),
        SourceConfig(
            source_id="oecd_export",
            name="OECD AI Incidents Monitor (Official Export)",
            connector_type=ConnectorType.OECD_EXPORT,
            role=SourceRole.OFFICIAL_MANUAL_EXPORT,
            endpoint_url="file://local",
            allowed_hosts=[],
            query_params={},
            rate_limit_seconds=0.0,
            enabled=True,
            description="Official OECD AIM export files. Processed via manual offline workflow (DEC-P4-001); skipped during unattended polling.",
        ),
    ]


def load_source_configs(config_path: Optional[Path] = None) -> list[SourceConfig]:
    """Load and validate ingestion source configurations.
    
    Reads from config/sources.json relative to repository root if present.
    """
    repo_root = get_repo_root()
    path = config_path or (repo_root / DEFAULT_CONFIG_PATH)

    if not path.exists():
        return get_default_sources()

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return get_default_sources()
        return [SourceConfig(**item) for item in data]
    except Exception:
        return get_default_sources()
