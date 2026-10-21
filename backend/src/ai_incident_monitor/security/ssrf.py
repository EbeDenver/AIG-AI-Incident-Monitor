"""SSRF defense and validated-destination connection pinning transport.

Eliminates DNS-rebinding TOCTOU vulnerabilities by pinning TCP sockets directly
to pre-validated IP addresses, while strictly preserving TLS SNI negotiation,
server certificate validation, and standard HTTP Host headers.

Governing Charter: Project Constitution (Rules 1, 9, 11, 14, 15, 16),
ADR-008, SEC-002 (Connector Security Model), DEC-P4-003.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import http.client
import socket
import ssl
import time
from typing import Callable

from ai_incident_monitor.security.content_limits import ContentLimits
from ai_incident_monitor.security.dns_validation import (
    DNSValidator,
    validate_ip,
)
from ai_incident_monitor.security.exceptions import (
    DNSResolutionError,
    InvalidURLError,
    SNIVerificationError,
    SSRFError,
)
from ai_incident_monitor.security.redirects import RedirectHop, RedirectInspector
from ai_incident_monitor.security.url_policy import NormalizedURL, URLPolicy

DEFAULT_USER_AGENT = "AIIncidentMonitor/0.2.0 (+https://aiguardiansllc.us/bot)"
DEFAULT_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class SecureHTTPResponse:
    """Immutable result of a secured HTTP request."""

    status_code: int
    headers: dict[str, str]
    body: bytes
    final_url: str
    pinned_ip: str
    redirect_history: list[RedirectHop] = field(default_factory=list)
    elapsed_seconds: float = 0.0

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300

    @property
    def text(self) -> str:
        """Decode body as UTF-8 with replacement for invalid bytes."""
        return self.body.decode("utf-8", errors="replace")


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    """HTTPS connection pinned to a pre-validated IP address.

    Preserves original hostname for TLS SNI and certificate validation.
    Prevents DNS rebinding by connecting directly to the pinned IP literal.
    """

    def __init__(
        self,
        validated_ip: str,
        original_host: str,
        port: int = 443,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        ssl_context: ssl.SSLContext | None = None,
    ) -> None:
        # Defense-in-depth: Re-verify the IP is not in any blocked range
        validate_ip(validated_ip)

        ctx = ssl_context or ssl.create_default_context()
        super().__init__(
            host=original_host,
            port=port,
            timeout=timeout,
            context=ctx,
        )
        self.ssl_context = ctx
        self.validated_ip = validated_ip
        self.original_host = original_host

    def connect(self) -> None:
        """Connect TCP socket directly to validated_ip and wrap with SNI for original_host."""
        try:
            # 1. Establish raw TCP connection to the pinned IP literal
            raw_sock = socket.create_connection(
                (self.validated_ip, self.port),
                self.timeout,
                self.source_address,
            )
        except OSError as exc:
            raise SSRFError(
                f"TCP connection failed to pinned IP '{self.validated_ip}:{self.port}': {exc}"
            ) from exc

        # 2. Negotiate TLS passing server_hostname=original_host
        # Enforces:
        # - TLS SNI in ClientHello
        # - Server certificate SAN/CN verification against original_host
        try:
            self.sock = self.ssl_context.wrap_socket(
                raw_sock,
                server_hostname=self.original_host,
            )
        except (ssl.SSLCertVerificationError, ssl.CertificateError) as exc:
            raw_sock.close()
            raise SNIVerificationError(
                f"TLS certificate validation failed for host '{self.original_host}' "
                f"at pinned destination {self.validated_ip}:{self.port}: {exc}"
            ) from exc
        except ssl.SSLError as exc:
            raw_sock.close()
            raise SNIVerificationError(
                f"TLS negotiation error for host '{self.original_host}' "
                f"at pinned destination {self.validated_ip}:{self.port}: {exc}"
            ) from exc


class PinnedHTTPConnection(http.client.HTTPConnection):
    """Unencrypted HTTP connection pinned to a pre-validated IP address.

    Permitted only when allow_http=True in local test environments.
    """

    def __init__(
        self,
        validated_ip: str,
        original_host: str,
        port: int = 80,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        validate_ip(validated_ip)
        super().__init__(
            host=original_host,
            port=port,
            timeout=timeout,
        )
        self.validated_ip = validated_ip
        self.original_host = original_host

    def connect(self) -> None:
        try:
            self.sock = socket.create_connection(
                (self.validated_ip, self.port),
                self.timeout,
                self.source_address,
            )
        except OSError as exc:
            raise SSRFError(
                f"TCP connection failed to pinned IP '{self.validated_ip}:{self.port}': {exc}"
            ) from exc


ConnectionFactoryType = Callable[
    [str, str, int, str, float, ssl.SSLContext | None],
    http.client.HTTPConnection | http.client.HTTPSConnection,
]


def default_connection_factory(
    scheme: str,
    validated_ip: str,
    original_host: str,
    port: int,
    timeout: float,
    ssl_context: ssl.SSLContext | None,
) -> http.client.HTTPConnection | http.client.HTTPSConnection:
    """Default connection builder returning PinnedHTTPSConnection or PinnedHTTPConnection."""
    if scheme == "https":
        return PinnedHTTPSConnection(
            validated_ip=validated_ip,
            original_host=original_host,
            port=port,
            timeout=timeout,
            ssl_context=ssl_context,
        )
    if scheme == "http":
        return PinnedHTTPConnection(
            validated_ip=validated_ip,
            original_host=original_host,
            port=port,
            timeout=timeout,
        )
    raise InvalidURLError(f"Unsupported scheme for pinned connection: '{scheme}'")


class SecureHTTPClient:
    """Production-grade hardened HTTP client enforcing SSRF and TOCTOU defense."""

    def __init__(
        self,
        *,
        url_policy: URLPolicy | None = None,
        dns_validator: DNSValidator | None = None,
        redirect_inspector: RedirectInspector | None = None,
        content_limits: ContentLimits | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        ssl_context: ssl.SSLContext | None = None,
        connection_factory: ConnectionFactoryType = default_connection_factory,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self.dns_validator = dns_validator or DNSValidator()
        self.url_policy = url_policy or URLPolicy(dns_validator=self.dns_validator)
        self.redirect_inspector = redirect_inspector or RedirectInspector(
            url_policy=self.url_policy,
            dns_validator=self.dns_validator,
        )
        self.content_limits = content_limits or ContentLimits()
        self.timeout = timeout
        self.ssl_context = ssl_context
        self.connection_factory = connection_factory
        self.user_agent = user_agent

    def get(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> SecureHTTPResponse:
        """Execute a hardened, SSRF-immune HTTP GET request with redirect inspection."""
        start_time = time.monotonic()

        # 1. Parse and validate initial URL
        norm_url = self.url_policy.validate_and_normalize(url)

        # 2. Resolve DNS and check all 21 blocked IP ranges
        validated_ips = self.dns_validator.resolve_and_validate(norm_url.host, norm_url.port)
        if not validated_ips:
            raise DNSResolutionError(f"No valid IP addresses found for '{norm_url.host}'")

        pinned_ip = validated_ips[0]
        current_url = norm_url
        current_pinned_ip = pinned_ip
        redirect_history: list[RedirectHop] = []

        active_headers = dict(headers or {})
        if "User-Agent" not in active_headers and "user-agent" not in active_headers:
            active_headers["User-Agent"] = self.user_agent
        if "Accept" not in active_headers and "accept" not in active_headers:
            active_headers["Accept"] = "*/*"

        while True:
            # 3. Create pinned connection
            conn = self.connection_factory(
                current_url.scheme,
                current_pinned_ip,
                current_url.host,
                current_url.port,
                self.timeout,
                self.ssl_context,
            )

            try:
                # Transmit request
                conn.request("GET", current_url.request_uri, headers=active_headers)
                resp = conn.getresponse()

                status = resp.status

                # Handle HTTP redirects (301, 302, 303, 307, 308)
                if status in (301, 302, 303, 307, 308):
                    loc_header = resp.getheader("Location")
                    if not loc_header:
                        raise InvalidURLError(
                            f"HTTP {status} redirect missing required 'Location' header"
                        )

                    hop = self.redirect_inspector.inspect_hop(
                        current_url=current_url,
                        location_header=loc_header,
                        current_hop_count=len(redirect_history),
                    )
                    redirect_history.append(hop)
                    active_headers = self.redirect_inspector.sanitize_headers_for_hop(
                        active_headers, hop
                    )

                    current_url = hop.target_url
                    current_pinned_ip = hop.validated_ips[0]
                    conn.close()
                    continue

                # 4. Check Content-Length before downloading
                self.content_limits.check_content_length_header(resp.getheader("Content-Length"))

                # 5. Stream and decompress payload safely
                content_encoding = resp.getheader("Content-Encoding")
                body = self.content_limits.read_stream(resp, content_encoding=content_encoding)

                # Collect response headers
                response_headers = {k: v for k, v in resp.getheaders()}
                elapsed = time.monotonic() - start_time

                return SecureHTTPResponse(
                    status_code=status,
                    headers=response_headers,
                    body=body,
                    final_url=current_url.normalized_url,
                    pinned_ip=current_pinned_ip,
                    redirect_history=redirect_history,
                    elapsed_seconds=elapsed,
                )
            finally:
                conn.close()
