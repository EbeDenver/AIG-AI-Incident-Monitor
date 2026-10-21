# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Phase 5 Increment 1] - 2026-10-20

### Merged
- Pull Request [#4](https://github.com/EbeDenver/AIG-AI-Incident-Monitor/pull/4): `feat: Phase 5 Increment 1 AIG-ISI multi-dimensional scoring core`
- Merge Commit SHA: `19db6c35fc1ad854d40b0386f4508f04af571c63` (short: `19db6c3`)
- Merged into: `main` from `feature/aig-isi-scoring-engine`

### Added
- **AIG-ISI Multi-Dimensional Scoring Engine (`ai_incident_monitor.scoring`)**:
  - Deterministic implementation of AI Guardians Incident Severity Index version 1.0.0 (`ADR-012`).
  - Strict segregation of Actual Impact Severity and Potential Impact Severity into independent evaluations.
  - Eight approved dimensions totaling exactly 100 weight: Human Impact and Dignity (25), Financial and Property Impact (15), Trust and Reputational Impact (15), Privacy and Confidentiality Impact (15), Rights, Fairness, and Access Impact (10), Operational and Critical-Service Impact (10), Scale, Reach, and Propagation (5), Societal and Environmental Impact (5).
  - Explicit dimension scoring ($0..5$ or `null`/`UNKNOWN`), guaranteeing `UNKNOWN` is never coerced to zero.
  - Pure mathematical calculation engine for weighted contributions, lower evidence bounds, upper uncertainty bounds, score ranges, completeness percentages, and provisional normalized scores.
  - Five core severity tiers (Minimal 0–19, Moderate 20–39, Significant 40–59, Severe 60–79, Critical 80–100) and special status tiers (Unscored, Disputed, Superseded).
  - Orthogonal confidence levels (HIGH, MEDIUM, LOW, INSUFFICIENT) with strict floor protection for high human-impact claims.
  - Ten automated human-review workflow gates (`TIER_4_OR_5`, `LOW_CONFIDENCE`, `LOW_COMPLETENESS`, `ACTUAL_VS_POTENTIAL_DIVERGENCE`, `OVERRIDE_PRESENT`, `SERIOUS_INJURY_OR_DEATH`, `CRITICAL_INFRASTRUCTURE`, `SERIOUS_PRIVACY_IMPACT`, `SERIOUS_RIGHTS_IMPACT`, `MATERIALLY_DISPUTED_FACTS`).
  - Explicit, auditable manual override subsystem (`ScoreOverride`) requiring substantive rationale, reviewer ID, timestamp, and triggering mandatory review hold.
- **Relational Persistence Layer & Alembic Migration**:
  - `SeverityAssessmentModel` mapping full AIG-ISI records, dimension breakdowns, gates, and overrides.
  - Alembic migration `002_aig_isi_severity_foundation.py` with dual-engine PostgreSQL 16 and SQLite batch support.
  - Typed `SeverityRepository` integrated with append-only `AuditRepository` for full lifecycle traceability.
- **Methodology & Calibration Artifacts**:
  - Machine-readable specification: `frameworks/ai-guardians/aig-isi-1.0.yaml`.
  - Comprehensive methodology documentation: `docs/AIG_ISI_METHODOLOGY.md`.
  - Calibration guide and 6 canonical archetypes: `docs/AIG_ISI_CALIBRATION.md` and `frameworks/ai-guardians/calibration_fixtures.json`.
  - Relational ER diagram: `docs/ER_DIAGRAM.md`.
  - Scoring flow diagram: `docs/SCORING_FLOW.md`.
- **Testing & Verification**:
  - 41 new unit and calibration tests in `backend/tests/unit/scoring/` covering mathematical invariants, tier boundaries, review gates, overrides, repository persistence, and calibration archetypes.
  - Full test suite: **382 / 382 passed tests** with zero failures and zero regressions.

### Hard Boundaries Enforced in Phase 5 Increment 1
- Zero Gemini, LLM, or generative-AI calls.
- Zero live or scheduled external retrieval.
- Zero web scraping or undocumented API polling.
- Zero dashboard or public UI.
- Zero Substack, email, webhook, or publishing features.
- Zero Cloudflare deployment or domain configuration.
- Zero OECD, NIST AI RMF, or EU AI Act mapping execution yet (Increment 2).
- Zero automated legal or regulatory noncompliance determinations.

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
