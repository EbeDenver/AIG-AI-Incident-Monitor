"""Pluggable ingestion connectors package."""

from ai_incident_monitor.ingestion.connectors.arxiv import (
    ARXIV_APPROVED_HOST,
    ARXIV_DEFAULT_ENDPOINT,
    ArXivConnector,
)
from ai_incident_monitor.ingestion.connectors.base import (
    BaseConnector,
    ConnectorDisabledError,
    ConnectorError,
    ConnectorParseError,
    DisallowedSourceError,
)
from ai_incident_monitor.ingestion.connectors.oecd_aim import (
    OECD_AIM_APPROVED_HOST,
    OECD_AIM_DEFAULT_ENDPOINT,
    OECDAIMFeedConnector,
)
from ai_incident_monitor.ingestion.connectors.rss import (
    RSSConnector,
    sanitize_html_to_snippet,
)

__all__ = [
    "BaseConnector",
    "ConnectorError",
    "ConnectorDisabledError",
    "DisallowedSourceError",
    "ConnectorParseError",
    "RSSConnector",
    "sanitize_html_to_snippet",
    "ArXivConnector",
    "ARXIV_APPROVED_HOST",
    "ARXIV_DEFAULT_ENDPOINT",
    "OECDAIMFeedConnector",
    "OECD_AIM_APPROVED_HOST",
    "OECD_AIM_DEFAULT_ENDPOINT",
]
