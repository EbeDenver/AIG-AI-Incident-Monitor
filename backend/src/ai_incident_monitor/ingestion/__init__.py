"""Ingestion subsystem for AI Incident Monitor.

Governing Charter: Project Constitution (Rules 1, 9, 11, 14, 15, 16),
ADR-008, ADR-009, SEC-002, DEC-P4-001, DEC-P4-002, DEC-P4-003, DEC-P4-004.
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
from ai_incident_monitor.ingestion.oecd_adapter import (
    OECDExportAdapter,
    OECDRecord,
    OECDSourceMode,
)
from ai_incident_monitor.ingestion.purge import (
    PurgeAuditEvent,
    PurgeResult,
    purge_staged_feeds,
)
from ai_incident_monitor.ingestion.rate_limiter import ConnectorRateLimiter
from ai_incident_monitor.ingestion.staging import (
    DEFAULT_MAX_STAGED_PAYLOAD_BYTES,
    DEFAULT_RETENTION_DAYS,
    DEFAULT_STAGING_DIR_NAME,
    RawPayloadStagingStore,
    StagingError,
    StagingMetadataRecord,
    StagingPayloadTooLargeError,
    StagingSecurityError,
    StagingStatus,
)

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
    # OECD Adapter (DEC-P4-001)
    "OECDExportAdapter",
    "OECDRecord",
    "OECDSourceMode",
    # Raw Payload Staging & Retention (DEC-P4-002)
    "DEFAULT_STAGING_DIR_NAME",
    "DEFAULT_RETENTION_DAYS",
    "DEFAULT_MAX_STAGED_PAYLOAD_BYTES",
    "StagingStatus",
    "StagingError",
    "StagingSecurityError",
    "StagingPayloadTooLargeError",
    "StagingMetadataRecord",
    "RawPayloadStagingStore",
    # Purge Command (DEC-P4-002)
    "PurgeAuditEvent",
    "PurgeResult",
    "purge_staged_feeds",
]
