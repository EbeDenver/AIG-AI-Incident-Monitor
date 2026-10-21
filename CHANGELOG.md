# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Phase 4] - 2026-10-20

### Merged
- Pull Request [#3](https://github.com/EbeDenver/AIG-AI-Incident-Monitor/pull/3): `feat: Phase 4 secure ingestion connectors and provenance`
- Merge Commit SHA: `d2e9362133c968616ae21da25ba85b05c22fcfcf` (short: `d2e9362`)
- Merged into: `main` from `feature/secure-ingestion-connectors`
- Verification: 341 passed tests (320 unit, 21 integration) with zero regressions; cryptographic provenance chain verified via `make verify-provenance-chain`

### Added
- **SSRF Defense and Secure Transport (`SecureHTTPClient`)**:
  - Validated-destination connection pinning (`DEC-P4-003`, `ADR-008`), preserving TLS SNI, certificate validation, and HTTP Host header.
  - Comprehensive blocklist of 21 private, loopback, link-local, multicast, cloud metadata, and special-purpose IP ranges (IPv4 and IPv6).
  - DNS resolution pre-flight validation preventing DNS-rebinding attacks.
  - Strict redirect inspector (maximum 3 hops) re-evaluating each hop through security policy.
  - Hard content bounds (5 MB maximum response size, streaming byte counter).
- **Pluggable Source Connectors (`BaseConnector`)**:
  - `RSSConnector`: RSS 2.0 and Atom news feed ingestion using feedparser over pre-fetched bytes with defusedxml XML pre-screening, Bleach HTML/CSS sanitization, and bozo-error tracking.
  - `ArXivConnector`: Export-only official arXiv API integration (`export.arxiv.org`), research signal labeling (`is_research_paper=True`), strict 1-connection limit with 3.0-second delay between queries, and explicit PDF-download blocking.
  - `ConnectorRateLimiter`: Per-connector token-bucket/leaky-bucket rate limiter with concurrency guards and `Retry-After` header adherence.
  - `RetryPolicy`: Exponential backoff with jitter restricted strictly to transient failures (429, 503, select 5xx, network timeouts). Zero retries on 4xx validation or security-policy failures.
- **OECD Export-Only Adapter (`OECDExportAdapter`)**:
  - Strict adherence to `DEC-P4-001` and `ADR-009`: official file exports (CSV, JSON, XLSX), operator uploads, and recorded test fixtures only.
  - Zero web scraping, zero polling of undocumented UI/API endpoints, zero dynamic UI reverse-engineering.
  - Explicit `source_mode` tracking (`MANUAL_EXPORT`, `OFFICIAL_API_DISABLED`, `TEST_FIXTURE`).
  - CWE-1236 formula neutralization for spreadsheet exports.
- **Raw Feed Payload Staging Store (`RawPayloadStagingStore`)**:
  - Staging store rooted at `.data/raw_feeds/` (strictly Gitignored per `DEC-P4-002` and `ADR-008`).
  - Atomic writes with restricted file permissions (`0600`), path-traversal rejection, and SHA-256 integrity verification.
  - Raw payload purge CLI command (`ai-incident-monitor purge-staged-feeds` / `make purge-raw-feeds`) enforcing a 30-day retention TTL, dry-run support, active-run and legal-hold protection, and append-only audit logging.
- **Cryptographic Provenance Manifests (`IngestionManifest`)**:
  - Canonical JSON serialization (UTF-8, deterministic key ordering, UTC ISO 8601 timestamps, explicit schema version `1.0.0`).
  - Sequential SHA-256 hash chaining (`ADR-010`) linking every manifest to its predecessor (`previous_manifest_sha256`), anchored to genesis null.
  - Verification command `make verify-provenance-chain` ensuring end-to-end chain integrity.
- **Untrusted Source Content Isolation & Containment (`UntrustedSourceContentEnvelope`)**:
  - Structured XML envelope (`<untrusted_source_content>`) isolating external text before LLM exposure (`ADR-011`).
  - Strict escaping of XML delimiters, HTML/CSS tags, control characters, and Unicode normalization (NFKC).
  - CWE-1236 formula prefix neutralization.
  - Adversarial prompt-injection triage signal detector (`detect_prompt_injection_signals`) flagging high-risk injection patterns into review queues.
  - Future LLM boundary contract enforcing read-only extraction, schema conformity, and zero tool dispatch.

### Hard Boundaries Enforced in Phase 4
- **No Live Production Scheduling**: All connectors and pipelines execute on-demand via CLI or test invocations; no background cron or daemon workers.
- **No Web Scraping or Undocumented Polling**: OECD adapter strictly requires export files or fixtures; zero reverse-engineering of dynamic web applications.
- **No LLM Execution or Tool Dispatch**: LLM containment envelopes and prompt injection detectors stage untrusted text safely; no LLM inference, autonomous agents, or scoring engines are invoked.
- **No Full Article Storage or Copyright Infringement**: Raw articles and payloads are excluded from Git; stored only in Gitignored staging with 30-day purge TTL; domain models store only short, fair-use quotation spans with cryptographic offsets.
- **No Bypassing SecureHTTPClient**: Direct use of raw `requests`, `urllib`, or `httpx` is prohibited; all connectors must route through `SecureHTTPClient`.
- **Application-Level Manifest Chain**: Ingestion manifests provide cryptographic provenance hash chaining across runs without requiring external ledger infrastructure.

### Next Milestone Policy
- **Phase 5 (AIG-ISI Severity Scoring Engine & Governance Mappings) is planning-only until separately approved.**
