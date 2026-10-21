# CONNECTOR SECURITY MODEL & SSRF DEFENSE SPECIFICATION
**Project:** AI Incident Monitor  
**Organization:** AI Guardians LLC  
**Document Identifier:** SEC-002  
**Version:** 1.0.0  
**Effective Date:** 2026-10-20  
**Governing Charter:** [Project Constitution](PROJECT_CONSTITUTION.md) (Rules 1, 9, 11, 14, 15, 16), [ADR-008](DECISIONS.md#adr-008-secure-ingestion-connectors-cryptographic-provenance-and-ssrf-defense)  

---

## 1. Threat Model & Ingestion Attack Vectors

The AI Incident Monitor retrieves external feeds and documents from public sources (e.g., RSS/Atom news feeds, arXiv metadata, and authorized exports). Because feed URLs may be submitted by external users, discovered via automated aggregators, or referenced in untrusted content, the outbound network boundary is a primary attack vector.

```
┌────────────────────────────────────────────────────────────────────────┐
│                   INGESTION NETWORK THREAT VECTORS                     │
├─────────────────────┬──────────────────────────────────────────────────┤
│ Threat Vector       │ Description & Attack Mechanism                   │
├─────────────────────┼──────────────────────────────────────────────────┤
│ 1. Server-Side      │ Attacker supplies a URL pointing to internal     │
│    Request Forgery  │ infrastructure, cloud metadata (169.254.169.254), │
│    (SSRF)           │ loopback services (127.0.0.1:5432), or container  │
│                     │ bridge subnets (Docker 172.17.0.0/16).           │
├─────────────────────┼──────────────────────────────────────────────────┤
│ 2. DNS Rebinding    │ Attacker registers a domain whose DNS TTL is 0;   │
│    (TOCTOU Attack)  │ initial validation lookup returns a public IP,   │
│                     │ but subsequent connect lookup returns 127.0.0.1. │
├─────────────────────┼──────────────────────────────────────────────────┤
│ 3. TLS SNI Mismatch │ Naive connection to an IP address with Host      │
│    & Downgrades     │ header override breaks TLS SNI, allows MITM, or  │
│                     │ causes certificate verification bypass.          │
├─────────────────────┼──────────────────────────────────────────────────┤
│ 4. Open Redirect    │ Target feed URL initially points to public host   │
│    Chains           │ but redirects (301/302) to internal subnet or    │
│                     │ downgrades from HTTPS to unencrypted HTTP.       │
├─────────────────────┼──────────────────────────────────────────────────┤
│ 5. Decompression    │ Attacker serves a 10 KB gzip-compressed payload  │
│    Bombs (DoS)      │ that expands into 10 GB of zeros upon read,       │
│                     │ exhausting memory and disk resources.            │
├─────────────────────┼──────────────────────────────────────────────────┤
│ 6. Obfuscated IP    │ Decimal (2130706433), octal (0177.0.0.1), hex    │
│    Representations  │ (0x7f000001), or IPv4-mapped IPv6 evasions.      │
└─────────────────────┴──────────────────────────────────────────────────┘
```

---

## 2. Blocked IP Range Architecture (21 Blocked Ranges)

All resolved IP addresses are normalized using standard POSIX and Python `ipaddress` parsers to prevent representation bypasses (decimal, octal, hex, and dword formats). Any IP falling within any of the following 21 ranges is rejected immediately before any TCP connection can be initiated:

| Index | Subnet / Range | Designation | RFC / Authority | Risk Profile |
| :---: | :--- | :--- | :--- | :--- |
| **1** | `0.0.0.0/8` | Current network ("this" host) | RFC 1122 | Local routing ambiguity |
| **2** | `10.0.0.0/8` | Private-Use Subnet | RFC 1918 | Internal VPC / corporate network |
| **3** | `100.64.0.0/10` | Carrier-Grade NAT | RFC 6598 | Service provider shared infrastructure |
| **4** | `127.0.0.0/8` | Loopback addresses | RFC 1122 | Host localhost, internal microservices |
| **5** | `169.254.0.0/16` | IPv4 Link-Local / Cloud Metadata | RFC 3927 | AWS/GCP/Azure/OCI metadata (`169.254.169.254`) |
| **6** | `172.16.0.0/12` | Private-Use Subnet | RFC 1918 | Docker bridge networks, internal subnets |
| **7** | `192.0.0.0/24` | IETF Protocol Assignments | RFC 6890 | Reserved protocol assignments |
| **8** | `192.0.2.0/24` | Documentation (TEST-NET-1) | RFC 5737 | Non-routable documentation network |
| **9** | `192.88.99.0/24` | 6to4 Relay Anycast (Deprecated) | RFC 7526 | Anycast routing risks |
| **10** | `192.168.0.0/16` | Private-Use Subnet | RFC 1918 | Home/office subnets, internal LANs |
| **11** | `198.18.0.0/15` | Network Benchmark Tests | RFC 2544 | Benchmark test equipment |
| **12** | `198.51.100.0/24` | Documentation (TEST-NET-2) | RFC 5737 | Non-routable documentation network |
| **13** | `203.0.113.0/24` | Documentation (TEST-NET-3) | RFC 5737 | Non-routable documentation network |
| **14** | `224.0.0.0/4` | Multicast | RFC 5771 | Multicast group membership |
| **15** | `240.0.0.0/4` | Reserved for Future Use | RFC 1112 | Non-standard routing behavior |
| **16** | `255.255.255.255/32` | Limited Broadcast | RFC 919 | Local segment broadcast |
| **17** | `::/128` | IPv6 Unspecified address | RFC 4291 | Local machine bind ambiguity |
| **18** | `::1/128` | IPv6 Loopback address | RFC 4291 | IPv6 localhost |
| **19** | `::ffff:0:0/96` | IPv4-mapped IPv6 | RFC 4291 | Dual-stack bypass (e.g. `::ffff:127.0.0.1`) |
| **20** | `fc00::/7` | IPv6 Unique Local (ULA) | RFC 4193 | Private IPv6 corporate subnets |
| **21** | `fe80::/10` | IPv6 Link-Local | RFC 4291 | Unrouted IPv6 neighbor discovery |

In addition, reserved cloud metadata hostnames (`metadata.google.internal`, `instance-data`) are blocked directly at the domain validation stage.

---

## 3. Validated-Destination Connection Pinning (DEC-P4-003)

### 3.1 The DNS Rebinding (TOCTOU) Problem
Traditional HTTP clients suffer from a Time-of-Check to Time-of-Use (TOCTOU) vulnerability:
1. Application resolves `evil.com` -> `93.184.216.34` (Public, Valid).
2. Application initiates HTTP request: the underlying HTTP client resolves `evil.com` a second time.
3. Attacker DNS server returns `169.254.169.254` (Cloud Metadata).
4. Request connects to cloud metadata service, exposing credentials.

### 3.2 The Anti-Pattern: Naive IP Replacement
Replacing the URL's hostname with the validated IP (`https://93.184.216.34/feed.xml`) and setting `Host: evil.com` causes:
- Broken TLS Server Name Indication (SNI) negotiation.
- TLS certificate validation failure because the certificate does not match the IP address.
- If certificate verification is disabled to work around this, the client becomes vulnerable to man-in-the-middle (MITM) attacks.

### 3.3 The Validated Connection Pinning Solution
We implement a custom HTTP transport / connection factory:
1. **Pre-flight DNS Resolution**: Resolve hostname to all A and AAAA records via standard OS resolver.
2. **Exhaustive IP Range Check**: Validate **every** returned IP against the 21 blocked ranges. If ANY resolved IP belongs to a blocked range, fail immediately (`SecurityException`).
3. **Socket Pinning**: Open the raw TCP socket directly to a single validated IP address on the designated port (443).
4. **SNI-Preserving TLS Handshake**: Perform the TLS handshake on that connected socket using the **original hostname** as `server_hostname`. The server certificate must validate against that hostname.
5. **HTTP Host Transmission**: Transmit the standard HTTP/1.1 or HTTP/2 request with `Host: <original_hostname>`.

```
┌────────────────────────────────────────────────────────────────────────┐
│              VALIDATED CONNECTION PINNING FLOWCHART                    │
└────────────────────────────────────────────────────────────────────────┘

    URL: https://example.com/feed.xml
                 │
                 ▼
    [ Parse & Normalize URL ] ─── (Reject non-HTTPS, bad port, credentials)
                 │
                 ▼
    [ Resolve DNS (A/AAAA) ] ─── (Get IP list: [93.184.216.34])
                 │
                 ▼
    [ Check 21 Blocked Ranges ] ──► Any blocked? ──► REJECT (SecurityException)
                 │ All clean
                 ▼
    [ Open TCP Socket ] ───────► Connect to 93.184.216.34:443
                 │
                 ▼
    [ TLS Wrap Socket ] ───────► server_hostname="example.com"
                 │               (Verify cert matches example.com)
                 ▼
    [ Transmit HTTP Request ] ─► Host: example.com
```

---

## 4. Redirect Hop Inspector

1. **Hop Count Enforcement**: A maximum of 3 redirect hops is permitted. Exceeding 3 hops raises `MaxRedirectsExceededError`.
2. **Per-Hop Independent Validation**: Every redirect destination URL (`Location` header) is parsed, canonicalized, resolved via DNS, and validated against all 21 blocked IP ranges before following.
3. **Downgrade Prohibition**: Any redirect from `https://` to `http://` raises `ProtocolDowngradeError`.
4. **Credential Stripping**: Cross-origin redirects strip sensitive headers (`Authorization`, `Cookie`).

---

## 5. Content Bounds & Decompression Safety

1. **Max Payload Cap**: Default maximum response size is 5,242,880 bytes (5.0 MB).
2. **Streaming Read**: Responses are streamed in 64 KB chunks. If total bytes read exceed 5 MB, the connection is aborted immediately (`PayloadTooLargeError`).
3. **Decompression Ratio Guard**: When decompressing `gzip` or `deflate` content:
   - Max decompression ratio: 5:1 (uncompressed size cannot exceed 5x compressed size once over 100 KB).
   - Absolute uncompressed ceiling: 5,242,880 bytes (5.0 MB).
   - Exceeding either limit raises `DecompressionBombError`.

---

## 6. Unicode & Punycode Domain Normalization

To prevent Internationalized Domain Name (IDN) homograph attacks and bypasses:
1. Domains are converted to ASCII via Punycode (`idna.encode()`).
2. Confusable characters, right-to-left override markers, and non-printable characters are rejected.
3. Hex and octal IP address strings disguised as hostnames are resolved and checked as IP literals.

---

## 7. Ingestion Connector Isolation & Network Bypass Prohibition

1. **Mandatory Secure Gateway Routing**: Every connector (`RSSConnector`, `ArXivConnector`, future `OECDAdapter`) must inherit from `BaseConnector` and execute all outbound network requests strictly through an injected `SecureHTTPClient`.
2. **Parser Network Isolation**: Third-party parser libraries (e.g., `feedparser`, XML parsers) are strictly prohibited from receiving URL strings. All payload bytes are retrieved first via `SecureHTTPClient`, validated in memory, and passed to parsers strictly as raw byte streams.
3. **XXE Entity Bomb Defense**: Feed payloads are pre-screened with `defusedxml` to block XML external entity expansion (Billion Laughs, DTD attacks) prior to feed structure processing.
4. **HTML Sanitization & Copyright Boundary**: All feed HTML is sanitized to plain text snippets (maximum 500 characters) adhering to fair-use doctrine. Full article bodies and PDFs are never downloaded or stored.

---

## 8. Connector Configuration & Rate-Limiting Policy Guide

| Setting | RSS / Atom Connector | arXiv API Connector |
| :--- | :--- | :--- |
| **Default Endpoint Allowlist** | Configured per-source allowlist (e.g. `safe-news.org`) | Exactly `export.arxiv.org` |
| **Allowed Scheme** | `https` only | `https` only |
| **Min Request Interval** | 1.0 second | 3.0 seconds |
| **Concurrency Ceiling** | Per-instance queue | Strict 1 connection mutex |
| **Default Enablement** | Enabled (`True`) | Disabled (`False`) via `ARXIV_CONNECTOR_ENABLED` |
| **Payload Ceiling** | 5.0 MB | 5.0 MB |
| **Epistemic Classification** | Unverified Allegation | Research Context Signal (Not an Incident) |
| **User-Agent Header** | `AIIncidentMonitor/0.2.0 (+<contact_url>)` | `AIIncidentMonitor/0.2.0 (+<contact_url>; mailto:<contact_email>)` |
| **Conditional Requests** | `ETag` and `Last-Modified` | `ETag` and `Last-Modified` |
| **PDF Downloads** | Banned | Banned |

