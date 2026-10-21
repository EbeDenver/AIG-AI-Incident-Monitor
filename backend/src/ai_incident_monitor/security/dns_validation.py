"""DNS validation and IP blocklist enforcement.

Defends against SSRF, internal network scanning, cloud metadata exfiltration,
and DNS rebinding TOCTOU attacks across 21 blocked IP ranges.

Governing Charter: Project Constitution (Rules 1, 9, 11, 14, 15, 16),
ADR-008, SEC-002 (Connector Security Model).
"""

from __future__ import annotations

import ipaddress
import re
import socket
from typing import Callable, Sequence

from ai_incident_monitor.security.exceptions import (
    BlockedHostnameError,
    BlockedIPError,
    DNSResolutionError,
    InvalidURLError,
)

# -----------------------------------------------------------------------------
# 21 Blocked IP Ranges (RFC Reference Standard)
# -----------------------------------------------------------------------------

BLOCKED_IPV4_RANGES: tuple[ipaddress.IPv4Network, ...] = (
    ipaddress.IPv4Network("0.0.0.0/8"),          # 1. Current network / RFC 1122
    ipaddress.IPv4Network("10.0.0.0/8"),         # 2. Private-Use / RFC 1918
    ipaddress.IPv4Network("100.64.0.0/10"),      # 3. Carrier-Grade NAT / RFC 6598
    ipaddress.IPv4Network("127.0.0.0/8"),        # 4. Loopback / RFC 1122
    ipaddress.IPv4Network("169.254.0.0/16"),     # 5. Link-Local / Cloud Metadata / RFC 3927
    ipaddress.IPv4Network("172.16.0.0/12"),      # 6. Private-Use / RFC 1918
    ipaddress.IPv4Network("192.0.0.0/24"),       # 7. IETF Protocol Assignments / RFC 6890
    ipaddress.IPv4Network("192.0.2.0/24"),       # 8. Documentation (TEST-NET-1) / RFC 5737
    ipaddress.IPv4Network("192.88.99.0/24"),     # 9. 6to4 Relay Anycast / RFC 7526
    ipaddress.IPv4Network("192.168.0.0/16"),     # 10. Private-Use / RFC 1918
    ipaddress.IPv4Network("198.18.0.0/15"),      # 11. Benchmark Tests / RFC 2544
    ipaddress.IPv4Network("198.51.100.0/24"),    # 12. Documentation (TEST-NET-2) / RFC 5737
    ipaddress.IPv4Network("203.0.113.0/24"),     # 13. Documentation (TEST-NET-3) / RFC 5737
    ipaddress.IPv4Network("224.0.0.0/4"),        # 14. Multicast / RFC 5771
    ipaddress.IPv4Network("240.0.0.0/4"),        # 15. Reserved for Future Use / RFC 1112
    ipaddress.IPv4Network("255.255.255.255/32"), # 16. Limited Broadcast / RFC 919
)

BLOCKED_IPV6_RANGES: tuple[ipaddress.IPv6Network, ...] = (
    ipaddress.IPv6Network("::/128"),             # 17. IPv6 Unspecified / RFC 4291
    ipaddress.IPv6Network("::1/128"),            # 18. IPv6 Loopback / RFC 4291
    ipaddress.IPv6Network("::ffff:0:0/96"),      # 19. IPv4-mapped IPv6 / RFC 4291
    ipaddress.IPv6Network("fc00::/7"),           # 20. IPv6 Unique Local (ULA) / RFC 4193
    ipaddress.IPv6Network("fe80::/10"),          # 21. IPv6 Link-Local / RFC 4291
)

# Hostnames explicitly blocked to prevent internal cloud metadata probing
BLOCKED_HOSTNAMES: frozenset[str] = frozenset({
    "localhost",
    "metadata.google.internal",
    "metadata",
    "instance-data",
    "metadata.internal",
})

BLOCKED_HOSTNAME_SUFFIXES: tuple[str, ...] = (
    ".localhost",
    ".local",
    ".internal",
    ".localdomain",
    ".lan",
    ".home.arpa",
)


def parse_and_normalize_ip(host_or_ip: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """Attempt to parse host_or_ip as an IPv4 or IPv6 address literal.

    Supports dotted decimal, bracketed IPv6, IPv4-mapped IPv6, and obfuscated
    representations (decimal, octal, hex) via inet_aton normalization.
    Returns None if the string is not an IP literal.
    """
    cleaned = host_or_ip.strip()
    if cleaned.startswith("[") and cleaned.endswith("]"):
        cleaned = cleaned[1:-1]

    # 1. Standard ipaddress parser
    try:
        return ipaddress.ip_address(cleaned)
    except ValueError:
        pass

    # 2. Check for numeric / octal / hex representations using socket.inet_aton
    # Restrict to strings that could be numeric/hex/octal tokens to avoid false positives
    if re.match(r"^(?:0x[0-9a-fA-F]+|\d+)(?:\.(?:0x[0-9a-fA-F]+|\d+)){0,3}$", cleaned):
        try:
            packed = socket.inet_aton(cleaned)
            return ipaddress.IPv4Address(packed)
        except (OSError, ValueError):
            pass

    return None


def is_ip_blocked(
    ip: str | ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> tuple[bool, str]:
    """Check if an IP address falls within any of the 21 blocked IP ranges.

    Returns (True, reason) if blocked, or (False, "") if permitted.
    """
    if isinstance(ip, str):
        parsed = parse_and_normalize_ip(ip)
        if parsed is None:
            return False, ""
        addr = parsed
    else:
        addr = ip

    # If it's an IPv4 address
    if isinstance(addr, ipaddress.IPv4Address):
        for net in BLOCKED_IPV4_RANGES:
            if addr in net:
                return True, f"IPv4 address in blocked range {net}"
        if addr.is_loopback or addr.is_private or addr.is_link_local or addr.is_multicast or addr.is_reserved or addr.is_unspecified:
            return True, "IPv4 address is loopback, private, link-local, multicast, or reserved"
        return False, ""

    # If it's an IPv6 address
    if isinstance(addr, ipaddress.IPv6Address):
        # Check IPv4-mapped IPv6 (::ffff:x.x.x.x)
        if addr.ipv4_mapped is not None:
            blocked, reason = is_ip_blocked(addr.ipv4_mapped)
            if blocked:
                return True, f"IPv4-mapped IPv6 target is blocked: {reason}"

        # Check 6to4 (2002::/16)
        if addr.sixtofour is not None:
            blocked, reason = is_ip_blocked(addr.sixtofour)
            if blocked:
                return True, f"6to4 embedded IPv4 target is blocked: {reason}"

        # Check Teredo (2001:0000::/32)
        if addr.teredo is not None:
            server_ip, client_ip = addr.teredo
            blocked_srv, reason_srv = is_ip_blocked(server_ip)
            if blocked_srv:
                return True, f"Teredo server IPv4 is blocked: {reason_srv}"
            blocked_cli, reason_cli = is_ip_blocked(client_ip)
            if blocked_cli:
                return True, f"Teredo client IPv4 is blocked: {reason_cli}"

        # Check 21 blocked IPv6 ranges
        for net_v6 in BLOCKED_IPV6_RANGES:
            if addr in net_v6:
                return True, f"IPv6 address in blocked range {net_v6}"

        if addr.is_loopback or addr.is_private or addr.is_link_local or addr.is_multicast or addr.is_reserved or addr.is_unspecified:
            return True, "IPv6 address is loopback, private, link-local, multicast, or reserved"

        return False, ""

    return False, ""


def validate_ip(ip: str | ipaddress.IPv4Address | ipaddress.IPv6Address) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    """Validate that an IP is not in any blocked range; raises BlockedIPError if blocked."""
    if isinstance(ip, str):
        parsed = parse_and_normalize_ip(ip)
        if parsed is None:
            raise InvalidURLError(f"Invalid IP address literal: '{ip}'")
        addr = parsed
    else:
        addr = ip

    blocked, reason = is_ip_blocked(addr)
    if blocked:
        raise BlockedIPError(str(addr), reason=reason)
    return addr


ResolverType = Callable[[str, int], Sequence[tuple[int, int, int, str, tuple]]]


def default_socket_resolver(hostname: str, port: int) -> Sequence[tuple[int, int, int, str, tuple]]:
    """Standard OS resolver wrapper using socket.getaddrinfo."""
    try:
        return socket.getaddrinfo(
            hostname,
            port,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise DNSResolutionError(f"DNS resolution failed for '{hostname}': {exc}") from exc


class DNSValidator:
    """Validates hostnames and resolves them while strictly enforcing IP blocklists."""

    def __init__(
        self,
        resolver: ResolverType | None = None,
        blocked_hostnames: frozenset[str] = BLOCKED_HOSTNAMES,
        blocked_suffixes: tuple[str, ...] = BLOCKED_HOSTNAME_SUFFIXES,
    ) -> None:
        self.resolver = resolver or default_socket_resolver
        self.blocked_hostnames = blocked_hostnames
        self.blocked_suffixes = blocked_suffixes

    def validate_hostname(self, hostname: str) -> str:
        """Validate and normalize a hostname string.

        Punycode-encodes Internationalized Domain Names (IDN) and ensures
        no blocked hostnames or invalid characters are present.
        """
        if not hostname:
            raise InvalidURLError("Hostname cannot be empty")

        cleaned = hostname.strip().lower()

        # Check for bracketed IPv6
        if cleaned.startswith("[") and cleaned.endswith("]"):
            cleaned = cleaned[1:-1]

        # Check blocked hostnames
        if cleaned in self.blocked_hostnames:
            raise BlockedHostnameError(cleaned, "Explicitly blocked internal/metadata hostname")

        for suffix in self.blocked_suffixes:
            if cleaned.endswith(suffix):
                raise BlockedHostnameError(cleaned, f"Hostname matches blocked internal suffix '{suffix}'")

        # Punycode normalization for IDN
        try:
            ascii_hostname = cleaned.encode("idna").decode("ascii")
        except Exception as exc:
            raise InvalidURLError(f"Invalid domain name encoding for '{hostname}': {exc}") from exc

        # Basic label length check (RFC 1035)
        if len(ascii_hostname) > 253:
            raise InvalidURLError("Hostname exceeds maximum length of 253 characters")

        for label in ascii_hostname.split("."):
            if len(label) > 63:
                raise InvalidURLError(f"Hostname label '{label}' exceeds 63 characters")

        return ascii_hostname

    def resolve_and_validate(self, hostname: str, port: int = 443) -> list[str]:
        """Resolve a hostname to all IP addresses and ensure none are blocked.

        Returns a list of validated IP address strings.
        Raises:
            BlockedIPError: If ANY resolved IP is in a blocked range.
            BlockedHostnameError: If the hostname is blocked.
            DNSResolutionError: If resolution fails or returns no records.
        """
        # If the input is already an IP literal
        ip_literal = parse_and_normalize_ip(hostname)
        if ip_literal is not None:
            validate_ip(ip_literal)
            return [str(ip_literal)]

        normalized_host = self.validate_hostname(hostname)

        # Query DNS
        addrinfo = self.resolver(normalized_host, port)
        if not addrinfo:
            raise DNSResolutionError(f"DNS resolution for '{normalized_host}' returned no records")

        resolved_ips: list[str] = []
        for entry in addrinfo:
            sockaddr = entry[4]
            ip_str = sockaddr[0]
            # Strip IPv6 zone id / interface scope if present (e.g. fe80::1%en0)
            if "%" in ip_str:
                ip_str = ip_str.split("%")[0]

            # Validate each IP
            validated = validate_ip(ip_str)
            resolved_ips.append(str(validated))

        if not resolved_ips:
            raise DNSResolutionError(f"No valid IP addresses resolved for '{normalized_host}'")

        return resolved_ips
