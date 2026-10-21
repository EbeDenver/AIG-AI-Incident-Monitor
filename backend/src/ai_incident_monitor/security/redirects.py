"""Redirect inspection and hop validation.

Enforces a 3-hop ceiling, blocks HTTPS-to-HTTP protocol downgrades,
and performs independent pre-flight DNS and SSRF checks on every hop.

Governing Charter: Project Constitution (Rules 1, 9, 11, 14, 15, 16),
ADR-008, SEC-002 (Connector Security Model).
"""

from __future__ import annotations

from dataclasses import dataclass
import urllib.parse

from ai_incident_monitor.security.dns_validation import DNSValidator
from ai_incident_monitor.security.exceptions import (
    MaxRedirectsExceededError,
    ProtocolDowngradeError,
)
from ai_incident_monitor.security.url_policy import NormalizedURL, URLPolicy

DEFAULT_MAX_REDIRECTS: int = 3


@dataclass(frozen=True)
class RedirectHop:
    """Details of a single validated redirect hop."""

    hop_number: int
    source_url: str
    target_url: NormalizedURL
    validated_ips: list[str]
    is_cross_origin: bool


class RedirectInspector:
    """Inspects and validates HTTP redirect hops."""

    def __init__(
        self,
        *,
        max_redirects: int = DEFAULT_MAX_REDIRECTS,
        url_policy: URLPolicy | None = None,
        dns_validator: DNSValidator | None = None,
    ) -> None:
        self.max_redirects = max_redirects
        self.dns_validator = dns_validator or DNSValidator()
        self.url_policy = url_policy or URLPolicy(dns_validator=self.dns_validator)

    def inspect_hop(
        self,
        *,
        current_url: NormalizedURL,
        location_header: str,
        current_hop_count: int,
    ) -> RedirectHop:
        """Inspect and validate a single redirect hop.

        Args:
            current_url: The URL that issued the redirect.
            location_header: Raw 'Location' header value from HTTP 3xx response.
            current_hop_count: Number of redirects followed so far (0-indexed).

        Returns:
            RedirectHop containing validated target URL and resolved IPs.

        Raises:
            MaxRedirectsExceededError: If current_hop_count >= max_redirects.
            ProtocolDowngradeError: If redirect attempts to downgrade HTTPS -> HTTP.
            BlockedIPError: If target host resolves to a blocked IP.
            BlockedHostnameError: If target hostname is blocked.
            InvalidURLError: If target URL violates scheme, port, or syntax policy.
        """
        if current_hop_count >= self.max_redirects:
            raise MaxRedirectsExceededError(
                f"Exceeded maximum allowed redirect hops ({self.max_redirects}). "
                f"Aborted redirect from '{current_url.normalized_url}' to '{location_header}'"
            )

        # Resolve relative URLs against current_url
        absolute_target = urllib.parse.urljoin(current_url.normalized_url, location_header.strip())

        # Validate URL syntax and policy
        target_norm = self.url_policy.validate_and_normalize(absolute_target)

        # Check for protocol downgrade (HTTPS -> HTTP)
        if current_url.scheme == "https" and target_norm.scheme == "http":
            raise ProtocolDowngradeError(
                f"Insecure protocol downgrade forbidden: attempted redirect from "
                f"'{current_url.normalized_url}' (HTTPS) to '{target_norm.normalized_url}' (HTTP)"
            )

        # Resolve target hostname and check all IPs against 21 blocked ranges
        validated_ips = self.dns_validator.resolve_and_validate(target_norm.host, target_norm.port)

        # Origin comparison for header stripping
        is_cross_origin = (
            current_url.scheme != target_norm.scheme
            or current_url.host != target_norm.host
            or current_url.port != target_norm.port
        )

        return RedirectHop(
            hop_number=current_hop_count + 1,
            source_url=current_url.normalized_url,
            target_url=target_norm,
            validated_ips=validated_ips,
            is_cross_origin=is_cross_origin,
        )

    def sanitize_headers_for_hop(
        self,
        headers: dict[str, str],
        hop: RedirectHop,
    ) -> dict[str, str]:
        """Strip sensitive credentials when redirecting cross-origin."""
        if not hop.is_cross_origin:
            return dict(headers)

        sanitized = dict(headers)
        sensitive_headers = ("authorization", "cookie", "proxy-authorization")
        for key in list(sanitized.keys()):
            if key.lower() in sensitive_headers:
                del sanitized[key]
        return sanitized
