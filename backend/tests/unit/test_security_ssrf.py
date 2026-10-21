"""Comprehensive unit tests for SSRF defense, DNS validation, and connection pinning.

Validates the 21 blocked IP ranges, obfuscated IP representations, IPv4-mapped IPv6,
6to4, Teredo, DNS rebinding immunity, TLS SNI preservation, redirect inspection,
and 5 MB content bounds / decompression bomb defense.

Governing Charter: Project Constitution (Rules 1, 9, 11, 14, 15, 16),
ADR-008, SEC-002, DEC-P4-003.
"""

from __future__ import annotations

import gzip
import http.client
import io
import ipaddress
import socket
import ssl
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from ai_incident_monitor.security import (
    BLOCKED_HOSTNAMES,
    BLOCKED_IPV4_RANGES,
    BLOCKED_IPV6_RANGES,
    BlockedHostnameError,
    BlockedIPError,
    ContentLimits,
    DecompressionBombError,
    DNSResolutionError,
    DNSValidator,
    InvalidURLError,
    MaxRedirectsExceededError,
    NormalizedURL,
    PayloadTooLargeError,
    PinnedHTTPConnection,
    PinnedHTTPSConnection,
    ProtocolDowngradeError,
    RedirectHop,
    RedirectInspector,
    SecureHTTPClient,
    SecureHTTPResponse,
    SNIVerificationError,
    SSRFError,
    URLPolicy,
    is_ip_blocked,
    parse_and_normalize_ip,
    validate_ip,
)


# =============================================================================
# 1. Blocked IP Range Tests (21 Blocked Ranges)
# =============================================================================


class TestBlockedIPRanges:
    """Verifies that all 21 RFC-defined blocked IP ranges are rejected."""

    @pytest.mark.parametrize(
        "ip_str, expected_range_name",
        [
            ("0.0.0.0", "0.0.0.0/8 (Current network)"),
            ("0.255.255.255", "0.0.0.0/8"),
            ("10.0.0.1", "10.0.0.0/8 (RFC 1918 Private)"),
            ("10.255.255.254", "10.0.0.0/8 (RFC 1918 Private)"),
            ("100.64.0.1", "100.64.0.0/10 (Carrier-Grade NAT)"),
            ("100.127.255.254", "100.64.0.0/10 (Carrier-Grade NAT)"),
            ("127.0.0.1", "127.0.0.0/8 (Loopback)"),
            ("127.255.255.254", "127.0.0.0/8 (Loopback)"),
            ("169.254.1.1", "169.254.0.0/16 (Link-Local)"),
            ("169.254.169.254", "169.254.0.0/16 (Cloud Metadata)"),
            ("172.16.0.1", "172.16.0.0/12 (RFC 1918 Private)"),
            ("172.31.255.254", "172.16.0.0/12 (RFC 1918 Private)"),
            ("192.0.0.1", "192.0.0.0/24 (IETF Protocol)"),
            ("192.0.2.1", "192.0.2.0/24 (TEST-NET-1)"),
            ("192.88.99.1", "192.88.99.0/24 (6to4 Relay)"),
            ("192.168.1.1", "192.168.0.0/16 (RFC 1918 Private)"),
            ("192.168.254.254", "192.168.0.0/16 (RFC 1918 Private)"),
            ("198.18.0.1", "198.18.0.0/15 (Benchmarking)"),
            ("198.19.255.254", "198.18.0.0/15 (Benchmarking)"),
            ("198.51.100.1", "198.51.100.0/24 (TEST-NET-2)"),
            ("203.0.113.1", "203.0.113.0/24 (TEST-NET-3)"),
            ("224.0.0.1", "224.0.0.0/4 (Multicast)"),
            ("239.255.255.250", "224.0.0.0/4 (Multicast)"),
            ("240.0.0.1", "240.0.0.0/4 (Reserved)"),
            ("255.255.255.255", "255.255.255.255/32 (Broadcast)"),
        ],
    )
    def test_ipv4_blocked_ranges(self, ip_str: str, expected_range_name: str) -> None:
        blocked, reason = is_ip_blocked(ip_str)
        assert blocked is True, f"Expected {ip_str} to be blocked ({expected_range_name})"
        with pytest.raises(BlockedIPError):
            validate_ip(ip_str)

    @pytest.mark.parametrize(
        "ip_str, expected_range_name",
        [
            ("::", "::/128 (IPv6 Unspecified)"),
            ("::1", "::1/128 (IPv6 Loopback)"),
            ("::ffff:127.0.0.1", "::ffff:0:0/96 (IPv4-mapped IPv6)"),
            ("::ffff:169.254.169.254", "::ffff:0:0/96 (IPv4-mapped IPv6 Metadata)"),
            ("fc00::1", "fc00::/7 (IPv6 Unique Local ULA)"),
            ("fd12:3456:789a::1", "fc00::/7 (IPv6 Unique Local ULA)"),
            ("fe80::1", "fe80::/10 (IPv6 Link-Local)"),
            ("fe80::dead:beef", "fe80::/10 (IPv6 Link-Local)"),
        ],
    )
    def test_ipv6_blocked_ranges(self, ip_str: str, expected_range_name: str) -> None:
        blocked, reason = is_ip_blocked(ip_str)
        assert blocked is True, f"Expected {ip_str} to be blocked ({expected_range_name})"
        with pytest.raises(BlockedIPError):
            validate_ip(ip_str)

    def test_total_blocked_range_count_is_21(self) -> None:
        # 16 IPv4 + 5 IPv6 = 21 ranges
        assert len(BLOCKED_IPV4_RANGES) == 16
        assert len(BLOCKED_IPV6_RANGES) == 5
        assert len(BLOCKED_IPV4_RANGES) + len(BLOCKED_IPV6_RANGES) == 21

    @pytest.mark.parametrize(
        "public_ip",
        [
            "93.184.216.34",  # example.com
            "8.8.8.8",         # Google Public DNS
            "1.1.1.1",         # Cloudflare Public DNS
            "151.101.1.140",   # Fastly CDN
            "2606:2800:220:1:248:1893:25c8:1946",  # example.com IPv6
            "2001:4860:4860::8888",                # Google DNS IPv6
        ],
    )
    def test_permitted_public_ips_not_blocked(self, public_ip: str) -> None:
        blocked, reason = is_ip_blocked(public_ip)
        assert blocked is False, f"Expected public IP {public_ip} to be permitted, got reason: {reason}"
        validated = validate_ip(public_ip)
        assert str(validated) == public_ip


# =============================================================================
# 2. Obfuscated IP Formats & Bypass Attempts
# =============================================================================


class TestObfuscatedIPFormats:
    """Verifies that decimal, octal, hex, and dual-mapped representations are caught."""

    @pytest.mark.parametrize(
        "raw_literal, expected_canonical",
        [
            ("2130706433", "127.0.0.1"),   # Decimal representation of 127.0.0.1
            ("0177.0.0.1", "127.0.0.1"),   # Octal representation
            ("0x7f000001", "127.0.0.1"),   # Hex representation
            ("127.1", "127.0.0.1"),        # Shortened class-A notation
            ("0x7f.1", "127.0.0.1"),       # Mixed hex/decimal
            ("017700000001", "127.0.0.1"), # Octal integer
        ],
    )
    def test_obfuscated_ipv4_representations_resolve_and_block(
        self, raw_literal: str, expected_canonical: str
    ) -> None:
        parsed = parse_and_normalize_ip(raw_literal)
        assert parsed is not None, f"Failed to parse obfuscated IP {raw_literal}"
        assert str(parsed) == expected_canonical
        with pytest.raises(BlockedIPError):
            validate_ip(raw_literal)

    def test_ipv4_mapped_ipv6_loopback_evasion_blocked(self) -> None:
        # Attacker tries ::ffff:127.0.0.1 to bypass IPv4 loopback filters
        with pytest.raises(BlockedIPError) as exc_info:
            validate_ip("::ffff:127.0.0.1")
        assert "IPv4-mapped" in str(exc_info.value) or "blocked" in str(exc_info.value)

    def test_ipv4_mapped_ipv6_metadata_evasion_blocked(self) -> None:
        # Attacker tries ::ffff:169.254.169.254
        with pytest.raises(BlockedIPError) as exc_info:
            validate_ip("::ffff:169.254.169.254")
        assert "IPv4-mapped" in str(exc_info.value) or "blocked" in str(exc_info.value)

    def test_6to4_embedded_loopback_blocked(self) -> None:
        # 2002:7f00:0001:: embeds 127.0.0.1
        with pytest.raises(BlockedIPError) as exc_info:
            validate_ip("2002:7f00:0001::")
        assert "6to4" in str(exc_info.value) or "blocked" in str(exc_info.value)

    def test_teredo_embedded_blocked_ip(self) -> None:
        # Teredo embeds client/server IPv4. If client IPv4 is in TEST-NET-1 (192.0.2.45):
        addr_str = "2001:0000:4136:e378:8000:63bf:3fff:fdd2"
        # 3fff:fdd2 = ~192.0.2.45
        with pytest.raises(BlockedIPError) as exc_info:
            validate_ip(addr_str)
        assert "Teredo" in str(exc_info.value) or "blocked" in str(exc_info.value)


# =============================================================================
# 3. Hostname Validation & Punycode Normalization
# =============================================================================


class TestHostnameAndDNSValidation:
    """Verifies hostname sanitization, blocked metadata domains, and IDN punycode."""

    def test_blocked_cloud_metadata_hostnames(self) -> None:
        validator = DNSValidator()
        blocked_names = [
            "localhost",
            "metadata.google.internal",
            "metadata",
            "instance-data",
            "metadata.internal",
            "foo.localhost",
            "service.local",
            "internal-host.internal",
            "myhost.localdomain",
        ]
        for host in blocked_names:
            with pytest.raises(BlockedHostnameError):
                validator.validate_hostname(host)

    def test_unicode_punycode_normalization(self) -> None:
        validator = DNSValidator()
        # Russian domain: пример.испытание -> xn--e1afmkfd.xn--80akhbyknj4f
        ascii_host = validator.validate_hostname("пример.испытание")
        assert ascii_host == "xn--e1afmkfd.xn--80akhbyknj4f"

    def test_invalid_hostname_length_rejected(self) -> None:
        validator = DNSValidator()
        # Exceeds 253 characters
        long_host = ("a" * 60 + ".") * 5 + "com"
        with pytest.raises(InvalidURLError):
            validator.validate_hostname(long_host)

        # Label exceeds 63 characters
        long_label = "a" * 64 + ".example.com"
        with pytest.raises(InvalidURLError):
            validator.validate_hostname(long_label)

    def test_empty_hostname_rejected(self) -> None:
        validator = DNSValidator()
        with pytest.raises(InvalidURLError):
            validator.validate_hostname("")


# =============================================================================
# 4. Outbound URL Policy Tests
# =============================================================================


class TestURLPolicy:
    """Verifies URL normalization, scheme enforcement, and port filtering."""

    def test_https_default_scheme_accepted(self) -> None:
        policy = URLPolicy()
        norm = policy.validate_and_normalize("https://example.com/feed.xml?format=rss")
        assert norm.scheme == "https"
        assert norm.host == "example.com"
        assert norm.port == 443
        assert norm.path == "/feed.xml"
        assert norm.query == "format=rss"
        assert norm.normalized_url == "https://example.com/feed.xml?format=rss"
        assert norm.host_header == "example.com"

    def test_http_rejected_by_default(self) -> None:
        policy = URLPolicy(allow_http=False)
        with pytest.raises(InvalidURLError) as exc_info:
            policy.validate_and_normalize("http://example.com/feed.xml")
        assert "Disallowed URL scheme 'http'" in str(exc_info.value)

    def test_http_allowed_when_explicitly_configured(self) -> None:
        policy = URLPolicy(allow_http=True)
        norm = policy.validate_and_normalize("http://example.com/feed.xml")
        assert norm.scheme == "http"
        assert norm.port == 80

    @pytest.mark.parametrize(
        "bad_scheme_url",
        [
            "file:///etc/passwd",
            "ftp://ftp.example.com/file.txt",
            "gopher://gopher.example.com/",
            "dict://dict.example.com/",
            "ldap://ldap.example.com/dc=example",
        ],
    )
    def test_dangerous_schemes_rejected(self, bad_scheme_url: str) -> None:
        policy = URLPolicy(allow_http=True)
        with pytest.raises(InvalidURLError):
            policy.validate_and_normalize(bad_scheme_url)

    def test_credential_stripping(self) -> None:
        policy = URLPolicy(strip_credentials=True)
        norm = policy.validate_and_normalize("https://admin:secret123@example.com/feed.xml")
        assert norm.host == "example.com"
        assert "secret123" not in norm.normalized_url

    def test_credentials_forbidden_when_strip_disabled(self) -> None:
        policy = URLPolicy(strip_credentials=False)
        with pytest.raises(InvalidURLError):
            policy.validate_and_normalize("https://admin:secret123@example.com/feed.xml")

    def test_non_standard_port_rejected_by_default(self) -> None:
        policy = URLPolicy(allowed_ports={443})
        with pytest.raises(InvalidURLError):
            policy.validate_and_normalize("https://example.com:8443/feed.xml")

    def test_fragment_is_stripped(self) -> None:
        policy = URLPolicy()
        norm = policy.validate_and_normalize("https://example.com/feed.xml#heading-1")
        assert "#" not in norm.normalized_url

    def test_host_allowlist_enforcement(self) -> None:
        policy = URLPolicy(allowed_hosts={"news.ycombinator.com", "arxiv.org"})
        norm = policy.validate_and_normalize("https://arxiv.org/abs/2301.00001")
        assert norm.host == "arxiv.org"

        with pytest.raises(InvalidURLError) as exc_info:
            policy.validate_and_normalize("https://unapproved.com/feed.xml")
        assert "not in the permitted outbound allowlist" in str(exc_info.value)


# =============================================================================
# 5. DNS Rebinding / TOCTOU Simulation & Connection Pinning (DEC-P4-003)
# =============================================================================


class TestDNSRebindingAndConnectionPinning:
    """Verifies that connection pinning defeats TOCTOU DNS rebinding."""

    def test_mock_dns_rebinding_simulation_prevented_by_pinning(self) -> None:
        """Simulate an attacker who changes DNS records between check and connect.

        Our architecture:
        1. Pre-flight DNS resolution validates IP 93.184.216.34 and pins it.
        2. The TCP socket connects directly to the pinned IP literal.
        3. Attacker DNS mutating to 127.0.0.1 has zero effect because connect()
           uses the pinned IP literal, not the hostname.
        """
        dns_call_count = 0

        def alternating_resolver(hostname: str, port: int) -> list[tuple]:
            nonlocal dns_call_count
            dns_call_count += 1
            if dns_call_count == 1:
                # First lookup returns public IP
                return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]
            # Rebinding attempt: subsequent lookup returns loopback
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port))]

        validator = DNSValidator(resolver=alternating_resolver)
        # Step 1: Pre-flight resolution
        validated_ips = validator.resolve_and_validate("rebinding-attacker.com", 443)
        assert validated_ips == ["93.184.216.34"]

        # Step 2: Connection is pinned directly to 93.184.216.34
        # Even if a second resolution were attempted, the connection factory binds to pinned_ip
        pinned_ip = validated_ips[0]
        conn = PinnedHTTPSConnection(
            validated_ip=pinned_ip,
            original_host="rebinding-attacker.com",
            port=443,
        )
        assert conn.validated_ip == "93.184.216.34"
        assert conn.host == "rebinding-attacker.com"
        assert conn.port == 443

    def test_multi_ip_dns_response_with_one_blocked_ip_is_rejected(self) -> None:
        """If a hostname resolves to both a public IP and a private/metadata IP, reject immediately."""
        def split_resolver(hostname: str, port: int) -> list[tuple]:
            return [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port)),
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", port)),
            ]

        validator = DNSValidator(resolver=split_resolver)
        with pytest.raises(BlockedIPError) as exc_info:
            validator.resolve_and_validate("split-dns-attacker.com", 443)
        assert "169.254.169.254" in str(exc_info.value)

    def test_pinned_connection_rejects_blocked_ip_in_constructor(self) -> None:
        """Defense-in-depth: PinnedHTTPSConnection validates the IP before connecting."""
        with pytest.raises(BlockedIPError):
            PinnedHTTPSConnection(
                validated_ip="127.0.0.1",
                original_host="example.com",
            )

        with pytest.raises(BlockedIPError):
            PinnedHTTPSConnection(
                validated_ip="169.254.169.254",
                original_host="example.com",
            )


# =============================================================================
# 6. TLS SNI & Certificate Validation Preservation (DEC-P4-003)
# =============================================================================


class TestTLSSNIPreservation:
    """Verifies that connection pinning preserves TLS SNI and server certificate validation."""

    def test_tls_wrap_socket_receives_original_hostname_for_sni(self) -> None:
        """Verify that wrap_socket receives server_hostname=original_host."""
        mock_raw_sock = MagicMock()
        mock_ssl_sock = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.wrap_socket.return_value = mock_ssl_sock

        conn = PinnedHTTPSConnection(
            validated_ip="93.184.216.34",
            original_host="feed.example.com",
            port=443,
            ssl_context=mock_ctx,
        )

        with patch("socket.create_connection", return_value=mock_raw_sock) as mock_create_conn:
            conn.connect()
            # Verified: TCP connects to pinned IP literal
            mock_create_conn.assert_called_once_with(
                ("93.184.216.34", 443),
                10.0,
                None,
            )
            # Verified: wrap_socket is called with original_host for SNI & cert verification
            mock_ctx.wrap_socket.assert_called_once_with(
                mock_raw_sock,
                server_hostname="feed.example.com",
            )
            assert conn.sock == mock_ssl_sock

    def test_certificate_validation_failure_raises_sni_verification_error(self) -> None:
        """When the certificate presented by the server does not match original_host, raise SNIVerificationError."""
        mock_raw_sock = MagicMock()
        mock_ctx = MagicMock()
        # Simulate SSL certificate mismatch
        mock_ctx.wrap_socket.side_effect = ssl.SSLCertVerificationError(
            1, "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: Hostname mismatch"
        )

        conn = PinnedHTTPSConnection(
            validated_ip="93.184.216.34",
            original_host="mismatch.example.com",
            port=443,
            ssl_context=mock_ctx,
        )

        with patch("socket.create_connection", return_value=mock_raw_sock):
            with pytest.raises(SNIVerificationError) as exc_info:
                conn.connect()
            assert "TLS certificate validation failed" in str(exc_info.value)
            # Ensure raw socket is closed upon failure
            mock_raw_sock.close.assert_called_once()


# =============================================================================
# 7. Redirect Inspector Tests
# =============================================================================


class TestRedirectInspector:
    """Verifies redirect limits, hop-by-hop DNS validation, and downgrade prevention."""

    def test_safe_single_hop_redirect(self) -> None:
        def mock_resolver(h: str, p: int) -> list[tuple]:
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", p))]

        validator = DNSValidator(resolver=mock_resolver)
        inspector = RedirectInspector(dns_validator=validator)

        current = NormalizedURL(
            scheme="https",
            host="example.com",
            port=443,
            path="/feed",
            query="",
            normalized_url="https://example.com/feed",
        )

        hop = inspector.inspect_hop(
            current_url=current,
            location_header="/feed.xml",
            current_hop_count=0,
        )
        assert hop.hop_number == 1
        assert hop.target_url.normalized_url == "https://example.com/feed.xml"
        assert hop.validated_ips == ["93.184.216.34"]
        assert hop.is_cross_origin is False

    def test_max_redirects_exceeded_raises_error(self) -> None:
        inspector = RedirectInspector(max_redirects=3)
        current = NormalizedURL(
            scheme="https",
            host="example.com",
            port=443,
            path="/step3",
            query="",
            normalized_url="https://example.com/step3",
        )
        with pytest.raises(MaxRedirectsExceededError) as exc_info:
            inspector.inspect_hop(
                current_url=current,
                location_header="/step4",
                current_hop_count=3,  # Already at limit 3
            )
        assert "Exceeded maximum allowed redirect hops" in str(exc_info.value)

    def test_protocol_downgrade_https_to_http_forbidden(self) -> None:
        policy = URLPolicy(allow_http=True)  # even if HTTP is enabled in policy
        inspector = RedirectInspector(url_policy=policy)
        current = NormalizedURL(
            scheme="https",
            host="example.com",
            port=443,
            path="/secure",
            query="",
            normalized_url="https://example.com/secure",
        )
        with pytest.raises(ProtocolDowngradeError) as exc_info:
            inspector.inspect_hop(
                current_url=current,
                location_header="http://example.com/insecure",
                current_hop_count=0,
            )
        assert "Insecure protocol downgrade forbidden" in str(exc_info.value)

    def test_redirect_to_cloud_metadata_blocked(self) -> None:
        def mock_resolver(h: str, p: int) -> list[tuple]:
            if h == "metadata.google.internal":
                return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", p))]
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", p))]

        validator = DNSValidator(resolver=mock_resolver)
        inspector = RedirectInspector(dns_validator=validator)
        current = NormalizedURL(
            scheme="https",
            host="example.com",
            port=443,
            path="/feed",
            query="",
            normalized_url="https://example.com/feed",
        )
        with pytest.raises((BlockedIPError, BlockedHostnameError)):
            inspector.inspect_hop(
                current_url=current,
                location_header="https://metadata.google.internal/computeMetadata/v1/",
                current_hop_count=0,
            )

    def test_cross_origin_redirect_sanitizes_credentials(self) -> None:
        inspector = RedirectInspector()
        hop = RedirectHop(
            hop_number=1,
            source_url="https://example.com/source",
            target_url=NormalizedURL(
                scheme="https",
                host="other-domain.com",
                port=443,
                path="/target",
                query="",
                normalized_url="https://other-domain.com/target",
            ),
            validated_ips=["93.184.216.34"],
            is_cross_origin=True,
        )
        headers = {
            "Authorization": "Bearer token123",
            "Cookie": "session=abc",
            "User-Agent": "AIIncidentMonitor/0.2.0",
        }
        sanitized = inspector.sanitize_headers_for_hop(headers, hop)
        assert "Authorization" not in sanitized
        assert "Cookie" not in sanitized
        assert sanitized["User-Agent"] == "AIIncidentMonitor/0.2.0"


# =============================================================================
# 8. Content Limits & Decompression Guard Tests
# =============================================================================


class TestContentLimits:
    """Verifies the 5 MB payload limit and streaming decompression bomb guard."""

    def test_content_length_header_over_5mb_raises_payload_too_large(self) -> None:
        limits = ContentLimits(max_bytes=5 * 1024 * 1024)
        # 6 MB header
        with pytest.raises(PayloadTooLargeError) as exc_info:
            limits.check_content_length_header(str(6 * 1024 * 1024))
        assert "exceeds maximum allowed limit" in str(exc_info.value)

    def test_uncompressed_stream_exceeding_5mb_raises_payload_too_large(self) -> None:
        limits = ContentLimits(max_bytes=1000, chunk_size=200)
        oversized_data = b"X" * 1500
        stream = io.BytesIO(oversized_data)
        with pytest.raises(PayloadTooLargeError):
            limits.read_stream(stream)

    def test_valid_compressed_payload_decompresses_cleanly(self) -> None:
        limits = ContentLimits()
        original_data = b"<rss><channel><title>AI Incident News</title></channel></rss>"
        compressed = gzip.compress(original_data)
        stream = io.BytesIO(compressed)
        decompressed = limits.read_stream(stream, content_encoding="gzip")
        assert decompressed == original_data

    def test_decompression_bomb_ratio_violation_raises_error(self) -> None:
        """A gzip stream where uncompressed/compressed exceeds ratio limit."""
        # Create 1 MB of repetitive data (compresses to ~1 KB, ratio ~1000:1)
        limits = ContentLimits(
            max_bytes=5 * 1024 * 1024,
            max_decompression_ratio=5.0,
            chunk_size=1024,
        )
        # To trigger the ratio check threshold (> 100 KB compressed), compress ~20MB
        # Or test with lower threshold
        bomb_data = b"A" * (2 * 1024 * 1024)  # 2MB uncompressed
        compressed = gzip.compress(bomb_data)

        # Custom limits with lower threshold for unit testing
        with patch("ai_incident_monitor.security.content_limits.RATIO_EVALUATION_THRESHOLD_BYTES", 100):
            stream = io.BytesIO(compressed)
            with pytest.raises(DecompressionBombError) as exc_info:
                limits.read_stream(stream, content_encoding="gzip")
            assert "Decompression expansion ratio" in str(exc_info.value) or "exceeded" in str(exc_info.value)

    def test_decompressed_payload_exceeding_ceiling_raises_error(self) -> None:
        """Decompressed output exceeding max_bytes ceiling."""
        limits = ContentLimits(max_bytes=1000)
        # 5000 bytes compresses to ~30 bytes (< 1000), but expands to 5000 (> 1000)
        data = b"0" * 5000
        compressed = gzip.compress(data)
        stream = io.BytesIO(compressed)
        with pytest.raises(DecompressionBombError) as exc_info:
            limits.read_stream(stream, content_encoding="gzip")
        assert "exceeded maximum limit" in str(exc_info.value)


# =============================================================================
# 9. SecureHTTPClient End-to-End Mock Integration
# =============================================================================


class TestSecureHTTPClient:
    """Verifies that SecureHTTPClient orchestrates URL, DNS, connection, redirect, and content bounds."""

    def test_successful_get_request(self) -> None:
        def mock_resolver(h: str, p: int) -> list[tuple]:
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", p))]

        validator = DNSValidator(resolver=mock_resolver)

        # Mock connection factory
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.getheader.side_effect = lambda h: {
            "Content-Length": "24",
            "Content-Type": "application/xml",
        }.get(h)
        mock_response.getheaders.return_value = [("Content-Type", "application/xml")]
        mock_response.read.side_effect = [b"<xml>valid feed</xml>", b""]

        mock_conn = MagicMock()
        mock_conn.getresponse.return_value = mock_response

        def mock_conn_factory(*args: Any, **kwargs: Any) -> Any:
            return mock_conn

        client = SecureHTTPClient(
            dns_validator=validator,
            connection_factory=mock_conn_factory,
        )

        resp = client.get("https://example.com/feed.xml")
        assert resp.status_code == 200
        assert resp.is_success is True
        assert resp.body == b"<xml>valid feed</xml>"
        assert resp.text == "<xml>valid feed</xml>"
        assert resp.pinned_ip == "93.184.216.34"
        assert resp.final_url == "https://example.com/feed.xml"
        assert len(resp.redirect_history) == 0

    def test_get_request_following_safe_redirect(self) -> None:
        def mock_resolver(h: str, p: int) -> list[tuple]:
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", p))]

        validator = DNSValidator(resolver=mock_resolver)

        # First response: 301 Redirect to /rss.xml
        mock_resp_1 = MagicMock()
        mock_resp_1.status = 301
        mock_resp_1.getheader.side_effect = lambda h: {"Location": "/rss.xml"}.get(h)

        # Second response: 200 OK
        mock_resp_2 = MagicMock()
        mock_resp_2.status = 200
        mock_resp_2.getheader.side_effect = lambda h: {"Content-Length": "12"}.get(h)
        mock_resp_2.getheaders.return_value = [("Content-Type", "application/rss+xml")]
        mock_resp_2.read.side_effect = [b"<rss>ok</rss>", b""]

        mock_conn_1 = MagicMock()
        mock_conn_1.getresponse.return_value = mock_resp_1
        mock_conn_2 = MagicMock()
        mock_conn_2.getresponse.return_value = mock_resp_2

        connections = [mock_conn_1, mock_conn_2]

        def mock_conn_factory(*args: Any, **kwargs: Any) -> Any:
            return connections.pop(0)

        client = SecureHTTPClient(
            dns_validator=validator,
            connection_factory=mock_conn_factory,
        )

        resp = client.get("https://example.com/feed")
        assert resp.status_code == 200
        assert resp.body == b"<rss>ok</rss>"
        assert resp.final_url == "https://example.com/rss.xml"
        assert len(resp.redirect_history) == 1
        assert resp.redirect_history[0].hop_number == 1
        assert resp.redirect_history[0].target_url.normalized_url == "https://example.com/rss.xml"

    def test_get_request_aborts_if_initial_dns_points_to_blocked_ip(self) -> None:
        def mock_resolver(h: str, p: int) -> list[tuple]:
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", p))]

        validator = DNSValidator(resolver=mock_resolver)
        client = SecureHTTPClient(dns_validator=validator)

        with pytest.raises(BlockedIPError):
            client.get("https://evil-loopback.com/feed.xml")
