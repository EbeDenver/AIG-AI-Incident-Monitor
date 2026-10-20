"""Ingestion subsystem for AI Incident Monitor.

Governing Charter: Project Constitution (Rules 1, 9, 11, 14, 15, 16),
ADR-008, SEC-002, DEC-P4-001, DEC-P4-002, DEC-P4-003, DEC-P4-004.
"""

from ai_incident_monitor.ingestion.connectors import (
    ARXIV_APPROVED_HOST,
    ARXIV_DEFAULT_ENDPOINT,
    ArXivConnector,
    BaseConnector,
    ConnectorDisabledError,
    ConnectorError,
    ConnectorParseError,
    DisallowedSourceError,
    RSSConnector,
    sanitize_html_to_snippet,
)
from ai_incident_monitor.ingestion.models import (
    ConnectorExecutionResult,
    ConnectorMetadata,
    ConnectorType,
    IngestedItem,
    IngestionStatus,
    RateLimitPolicy,
    RetryDecision,
    RetryPolicy,
)
from ai_incident_monitor.ingestion.rate_limiter import ConnectorRateLimiter

__all__ = [
    # Models
    "ConnectorMetadata",
    "ConnectorType",
    "IngestionStatus",
    "RetryDecision",
    "RetryPolicy",
    "RateLimitPolicy",
    "IngestedItem",
    "ConnectorExecutionResult",
    "ConnectorRateLimiter",
    # Connectors
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
]
