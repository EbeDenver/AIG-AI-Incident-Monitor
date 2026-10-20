"""Security exceptions for AI Incident Monitor ingestion.

Governing Charter: Project Constitution (Rules 1, 9, 11, 14, 15, 16),
ADR-008, SEC-002 (Connector Security Model).
"""

from __future__ import annotations


class SecurityError(Exception):
    """Base class for all ingestion security violations."""


class SSRFError(SecurityError):
    """Base class for Server-Side Request Forgery violations."""


class InvalidURLError(SSRFError):
    """Raised when a URL scheme, port, format, or credential policy is violated."""


class BlockedIPError(SSRFError):
    """Raised when an IP address belongs to any of the 21 blocked IP ranges."""

    def __init__(self, ip: str, reason: str = "IP is in a blocked network range") -> None:
        super().__init__(f"Blocked IP address '{ip}': {reason}")
        self.ip = ip
        self.reason = reason


class BlockedHostnameError(SSRFError):
    """Raised when a hostname matches a blocked metadata or local domain."""

    def __init__(self, hostname: str, reason: str = "Hostname is blocked") -> None:
        super().__init__(f"Blocked hostname '{hostname}': {reason}")
        self.hostname = hostname
        self.reason = reason


class DNSResolutionError(SSRFError):
    """Raised when pre-flight DNS resolution fails, times out, or returns no records."""


class DNSRebindingDetectedError(SSRFError):
    """Raised when a DNS rebinding or TOCTOU address mutation is detected."""


class SNIVerificationError(SSRFError):
    """Raised when TLS SNI negotiation or certificate validation fails."""


class MaxRedirectsExceededError(SSRFError):
    """Raised when a redirect chain exceeds the maximum allowed hop count."""


class ProtocolDowngradeError(SSRFError):
    """Raised when a redirect attempts to downgrade from HTTPS to HTTP."""


class PayloadTooLargeError(SecurityError):
    """Raised when response payload exceeds the maximum allowed size (e.g. 5 MB)."""


class DecompressionBombError(SecurityError):
    """Raised when compressed payload expansion ratio or ceiling exceeds safe limits."""
