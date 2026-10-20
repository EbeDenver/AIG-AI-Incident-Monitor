"""Outbound URL policy enforcement and normalization.

Validates scheme, host, port, credentials, and structure to enforce
strict egress hygiene and prevent SSRF attacks.

Governing Charter: Project Constitution (Rules 1, 9, 11, 14, 15, 16),
ADR-008, SEC-002 (Connector Security Model).
"""

from __future__ import annotations

from dataclasses import dataclass
import urllib.parse

from ai_incident_monitor.security.dns_validation import DNSValidator
from ai_incident_monitor.security.exceptions import InvalidURLError


@dataclass(frozen=True)
class NormalizedURL:
    """Immutable representation of a normalized, validated outbound URL."""

    scheme: str
    host: str
    port: int
    path: str
    query: str
    normalized_url: str

    @property
    def request_uri(self) -> str:
        """HTTP Request-URI path and query component."""
        path = self.path or "/"
        if self.query:
            return f"{path}?{self.query}"
        return path

    @property
    def host_header(self) -> str:
        """Standard HTTP Host header value."""
        default_port = 443 if self.scheme == "https" else 80
        if self.port == default_port:
            return self.host
        return f"{self.host}:{self.port}"


class URLPolicy:
    """Enforces egress URL policies and normalization rules."""

    def __init__(
        self,
        *,
        allow_http: bool = False,
        allowed_schemes: set[str] | None = None,
        allowed_ports: set[int] | None = None,
        allowed_hosts: set[str] | None = None,
        allowed_host_suffixes: tuple[str, ...] | None = None,
        strip_credentials: bool = True,
        dns_validator: DNSValidator | None = None,
    ) -> None:
        self.allow_http = allow_http
        self.strip_credentials = strip_credentials
        self.dns_validator = dns_validator or DNSValidator()

        if allowed_schemes is not None:
            self.allowed_schemes = {s.lower() for s in allowed_schemes}
        else:
            self.allowed_schemes = {"https", "http"} if allow_http else {"https"}

        if allowed_ports is not None:
            self.allowed_ports = set(allowed_ports)
        else:
            self.allowed_ports = {80, 443} if allow_http else {443}

        self.allowed_hosts = {h.lower() for h in allowed_hosts} if allowed_hosts else None
        self.allowed_host_suffixes = (
            tuple(s.lower() for s in allowed_host_suffixes) if allowed_host_suffixes else None
        )

    def validate_and_normalize(self, raw_url: str) -> NormalizedURL:
        """Parse, validate, and normalize an outbound URL string.

        Raises:
            InvalidURLError: If the URL fails scheme, host, port, or structure checks.
        """
        if not raw_url or not isinstance(raw_url, str):
            raise InvalidURLError("URL must be a non-empty string")

        url_str = raw_url.strip()
        if not url_str:
            raise InvalidURLError("URL cannot be empty or whitespace only")

        # Strip fragment before parsing
        url_without_frag, _ = urllib.parse.urldefrag(url_str)

        try:
            parsed = urllib.parse.urlsplit(url_without_frag)
        except Exception as exc:
            raise InvalidURLError(f"Malformed URL structure: {exc}") from exc

        scheme = parsed.scheme.lower()
        if not scheme:
            raise InvalidURLError(f"URL is missing an explicit scheme: '{raw_url}'")

        if scheme not in self.allowed_schemes:
            raise InvalidURLError(
                f"Disallowed URL scheme '{scheme}'. Permitted schemes: {sorted(self.allowed_schemes)}"
            )

        if not parsed.netloc:
            raise InvalidURLError(f"URL is missing host/network location: '{raw_url}'")

        # Extract hostname, port, and credentials
        hostname = parsed.hostname
        if not hostname:
            raise InvalidURLError(f"Could not parse valid hostname from URL: '{raw_url}'")

        # Handle user credentials in netloc
        if parsed.username or parsed.password:
            if not self.strip_credentials:
                raise InvalidURLError("Embedded credentials in URLs are strictly forbidden")

        # Validate hostname via DNS validator rules
        normalized_host = self.dns_validator.validate_hostname(hostname)

        # Allowlist check if configured
        if self.allowed_hosts is not None and normalized_host not in self.allowed_hosts:
            if self.allowed_host_suffixes is None or not any(
                normalized_host.endswith(sfx) for sfx in self.allowed_host_suffixes
            ):
                raise InvalidURLError(
                    f"Host '{normalized_host}' is not in the permitted outbound allowlist"
                )

        # Port resolution
        port = parsed.port
        if port is None:
            port = 443 if scheme == "https" else 80

        if port not in self.allowed_ports:
            raise InvalidURLError(
                f"Port {port} is not in the permitted outbound ports: {sorted(self.allowed_ports)}"
            )

        # Path normalization
        path = parsed.path or "/"
        query = parsed.query

        # Construct normalized URL string
        default_port = 443 if scheme == "https" else 80
        netloc = normalized_host if port == default_port else f"{normalized_host}:{port}"
        normalized_str = urllib.parse.urlunsplit((scheme, netloc, path, query, ""))

        return NormalizedURL(
            scheme=scheme,
            host=normalized_host,
            port=port,
            path=path,
            query=query,
            normalized_url=normalized_str,
        )
