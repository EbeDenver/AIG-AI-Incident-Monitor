"""Ingestion security, SSRF defense, and connection pinning subsystem.

Governing Charter: Project Constitution (Rules 1, 9, 11, 14, 15, 16),
ADR-008, SEC-002 (Connector Security Model).
"""

from ai_incident_monitor.security.content_limits import (
    DEFAULT_MAX_BYTES,
    DEFAULT_MAX_DECOMPRESSION_RATIO,
    ContentLimits,
)
from ai_incident_monitor.security.dns_validation import (
    BLOCKED_HOSTNAMES,
    BLOCKED_IPV4_RANGES,
    BLOCKED_IPV6_RANGES,
    DNSValidator,
    is_ip_blocked,
    parse_and_normalize_ip,
    validate_ip,
)
from ai_incident_monitor.security.exceptions import (
    BlockedHostnameError,
    BlockedIPError,
    DecompressionBombError,
    DNSRebindingDetectedError,
    DNSResolutionError,
    InvalidURLError,
    MaxRedirectsExceededError,
    PayloadTooLargeError,
    ProtocolDowngradeError,
    SecurityError,
    SNIVerificationError,
    SSRFError,
)
from ai_incident_monitor.security.redirects import (
    DEFAULT_MAX_REDIRECTS,
    RedirectHop,
    RedirectInspector,
)
from ai_incident_monitor.security.ssrf import (
    PinnedHTTPConnection,
    PinnedHTTPSConnection,
    SecureHTTPClient,
    SecureHTTPResponse,
)
from ai_incident_monitor.security.url_policy import NormalizedURL, URLPolicy

__all__ = [
    # Exceptions
    "SecurityError",
    "SSRFError",
    "InvalidURLError",
    "BlockedIPError",
    "BlockedHostnameError",
    "DNSResolutionError",
    "DNSRebindingDetectedError",
    "SNIVerificationError",
    "MaxRedirectsExceededError",
    "ProtocolDowngradeError",
    "PayloadTooLargeError",
    "DecompressionBombError",
    # DNS Validation & IP Blocklist
    "BLOCKED_IPV4_RANGES",
    "BLOCKED_IPV6_RANGES",
    "BLOCKED_HOSTNAMES",
    "DNSValidator",
    "is_ip_blocked",
    "validate_ip",
    "parse_and_normalize_ip",
    # URL Policy
    "NormalizedURL",
    "URLPolicy",
    # Redirects
    "DEFAULT_MAX_REDIRECTS",
    "RedirectHop",
    "RedirectInspector",
    # Content Limits
    "DEFAULT_MAX_BYTES",
    "DEFAULT_MAX_DECOMPRESSION_RATIO",
    "ContentLimits",
    # SSRF & Connection Pinning
    "PinnedHTTPConnection",
    "PinnedHTTPSConnection",
    "SecureHTTPClient",
    "SecureHTTPResponse",
]
