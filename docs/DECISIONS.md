# ARCHITECTURAL DECISION RECORDS (ADRs)
**Project:** AI Incident Monitor  
**Organization:** AI Guardians LLC  
**Document Identifier:** ADR-000  
**Status:** ACTIVE REGISTRY  

---

## Architecture Decision Record Template

```markdown
### ADR-XXX: [Short Title]
* **Date**: YYYY-MM-DD
* **Status**: PROPOSED | RATIFIED | SUPERSEDED
* **Deciders**: AI Guardians LLC Leadership / Engineering
* **Context**: What problem or architectural constraint prompted this decision?
* **Decision**: What specific architecture, pattern, or constraint was adopted?
* **Consequences**:
  - Positive impacts and capabilities enabled
  - Negative impacts, trade-offs, or additional engineering overhead
```

---

## Ratified Architectural Decisions

### ADR-001: Adoption of Foundational Project Constitution and 17 Non-Negotiable Rules
* **Date**: 2026-10-07
* **Status**: RATIFIED
* **Deciders**: AI Guardians LLC Leadership, Antigravity AI
* **Context**: Building an automated AI incident monitoring system carries extreme risks of hallucination, sensationalism, legal liability, and false reporting. Standard LLM agents tend to extrapolate missing data, fabricate quotes, and flatten nuanced legal distinctions.
* **Decision**: Ratified [`docs/PROJECT_CONSTITUTION.md`](PROJECT_CONSTITUTION.md) establishing 17 non-negotiable rules with absolute primacy over all code, agent prompts, and workflows.
* **Consequences**:
  - Ensures unassailable epistemic integrity and defensibility.
  - Requires automated pre-commit and CI validators to enforce rule adherence.
  - Strictly bans LLM self-approval and mandates human review before publishing.

---

### ADR-002: Architectural Decoupling of AIG-ISI from Regulatory Frameworks
* **Date**: 2026-10-07
* **Status**: RATIFIED
* **Deciders**: AI Guardians LLC Methodology Team
* **Context**: Public AI incident databases frequently conflate regulatory classifications (e.g. EU AI Act High-Risk), safety severity, and media virality. This introduces severe jurisdictional bias and skews technical severity analysis.
* **Decision**: Architect the AI Guardians Incident Severity Index (AIG-ISI) as a completely autonomous, orthogonal methodology. AIG-ISI is calculated based on empirical dimensions (Harm, Autonomy, Reversibility, Scope), completely decoupled from OECD principles, NIST AI RMF, EU AI Act categorization, or media click volume. Regulatory mappings are preserved as parallel, non-interfering metadata layers.
* **Consequences**:
  - AIG-ISI scores remain globally valid regardless of legal jurisdiction.
  - Changes in EU regulations do not retroactively alter empirical safety severity scores.
  - Schema requires separate data structures: `SeverityAssessment` vs `GovernanceMapping`.

---

### ADR-003: Copyright Compliance and Zero Raw Ingestion Storage in Git
* **Date**: 2026-10-07
* **Status**: RATIFIED
* **Deciders**: Legal & Engineering
* **Context**: Scraping full-text news articles and committing them to a Git repository violates copyright law, risks DMCA takedowns, and bloats the git repository history with megabytes of ephemeral HTML.
* **Decision**: Git shall store only metadata, canonical URLs, archive timestamps, SHA-256 cryptographic digests, and minimal fair-use direct quote spans anchored by byte offsets. Raw scraped payloads are held strictly in an out-of-tree, gitignored local cache directory (`.data/cache/`) or private storage, never in Git.
* **Consequences**:
  - Full copyright compliance under fair-use doctrine.
  - Lightweight, auditable Git repository.
  - Requires SHA-256 provenance verification to prove extracted quotes match source payloads.

---

### ADR-004: Explicit Tri-State Epistemic Modeling (Unknown Is Not Zero)
* **Date**: 2026-10-07
* **Status**: RATIFIED
* **Deciders**: AI Safety & Data Architecture
* **Context**: Standard relational databases and data pipelines frequently default missing or nullable numerical attributes to `0`. In AI incident tracking, if financial damage or casualty counts are unreported, treating them as `0` yields catastrophic analytical falsehoods.
* **Decision**: Codify explicit tri-state/Option epistemic types across all data models (`EpistemicValue[T]`). Missing data is preserved as `UNKNOWN`. Database queries and analytical functions are barred from using `COALESCE(field, 0)` and must report unknown tallies alongside known averages.
* **Consequences**:
  - Prevents erroneous conclusions that an incident caused zero damage when damage was merely unquantified.
  - Requires custom Pydantic validators and query abstractions in Phase 2.

---

### ADR-005: Multi-Mac Development Parity and Git as Single Source of Truth
* **Date**: 2026-10-07
* **Status**: RATIFIED
* **Deciders**: Engineering & Operations
* **Context**: Development occurs across multiple macOS workstations (Darwin/arm64) and automated agent sessions. Machine-specific paths, hidden local dependencies, and untracked configs lead to brittle execution failures across sessions.
* **Decision**: Establish the GitHub repository as the single source of truth for all code, documentation, prompts, migrations, tests, and synthetic fixtures. All tooling and file paths must be strictly path-agnostic and cross-Mac compatible.
* **Consequences**:
  - Seamless agent session transitions across machines.
  - Zero local environment drift or machine lock-in.
  - Mandates strict session startup and closeout synchronization protocols in `AGENTS.md`.

---

### ADR-006: Core Epistemic Schemas, Pydantic v2 Domain Models, and Golden Fixtures
* **Date**: 2026-10-07
* **Status**: RATIFIED
* **Deciders**: AI Guardians LLC Engineering, Antigravity AI
* **Context**: Enforcing the 17 Non-Negotiable Rules in the Project Constitution requires software-level mathematical invariants rather than relying solely on LLM prompt instructions. Without immutable typing and deterministic validators, systems inevitably succumb to prompt drift, null-coercion to zero, fabricated citations, and self-approval.
* **Decision**: Implement core domain entities as immutable Pydantic v2 models (`frozen=True`, `extra="forbid"`):
  1. Strongly typed prefixed UUIDs (`SourceId`, `EvidenceId`, `ClaimId`, `IncidentId`, `ReviewId`, `UncertaintyId`).
  2. Controlled vocabularies via 22 string enums (`EpistemicStatus`, `ClaimType`, `SourceAuthority`, `HarmType`, etc.).
  3. Epistemic tri-state modeling in `MonetaryAmount` and `DateWithPrecision`, guaranteeing `UNKNOWN` is never coerced to zero.
  4. Mandatory evidence linkage for facts, numeric claims, and root causes; human approval mandatory for legal claims.
  5. Cryptographic source provenance (`ContentHash` SHA-256) and strict character-offset quote spans (`QuoteSpan`).
  6. Human review models strictly requiring `is_human=True` (`ReviewerIdentity`), structurally preventing LLM self-approval.
  7. Strict separation of `machine_recommended_status` and `human_approved` in `AuditMetadata`.
  8. 29 sanitized demonstration fixtures (22 valid golden, 7 invalid negative) labeled `DEMONSTRATION DATA — NOT A REAL INCIDENT`.
* **Consequences**:
  - Constitutional rules are enforced as hard Python validation errors (`ConstitutionalViolationError`, `UngroundedClaimError`, `InvalidMonetaryStateError`).
  - Zero database, ORM, network, or external LLM dependencies in the core domain layer.
  - Comprehensive automated test suite (89 unit tests) guarantees zero regressions.

---

### ADR-007: Relational Data Foundation, Dual-Engine Migrations, and Manual Ingestion
* **Date**: 2026-10-19
* **Status**: RATIFIED
* **Deciders**: AI Guardians LLC Leadership, Antigravity AI
* **Context**: Persisting the approved Phase 2 Pydantic domain models requires a relational database foundation capable of running locally in Docker, supporting rapid offline testing on macOS, executing schema migrations, preserving raw ingested payloads, preventing spreadsheet formula injection attacks, and implementing a deterministic deduplication waterfall.
* **Decision**: Implement Phase 3 persistence and manual import engine governed by:
  1. **Dual Engine Support**: Primary development targets local PostgreSQL 16 (`postgres:16-alpine` via Docker Compose); SQLite 3 is retained as a zero-dependency fallback for rapid, offline unit test runs on macOS (`DEC-P3-001`).
  2. **Hybrid Epistemic Ingestion**: Store file metadata, SHA-256 digest, and raw row JSON snapshots in `raw_import_records` in the database. Raw uploaded files are staged in `$REPO_ROOT/.data/raw_imports/` (strictly gitignored) with a 30-day purge TTL (`DEC-P3-002`). Zero full-text copyrighted news articles are stored in Git or the database (ADR-003, Rule 16).
  3. **4-Tier Deduplication Waterfall**: Exact Source ID (Tier 1) and exact normalized Canonical URL (Tier 2) auto-link to existing incidents. Near-duplicate matches (Tier 3: title similarity >= 0.90 + event date within $\pm 2$ days) are routed to an explicit `POTENTIAL_DUPLICATE` human review queue (`dedup_candidates`). Zero automated merges of separate incident dossiers (Rule 14, `DEC-P3-003`).
  4. **PostgreSQL-Native Migrations with Selective SQLite Batching**: Standard PostgreSQL-native migration behavior is the default primary path. SQLite batch table recreation (`render_as_batch=True`) is used selectively with foreign-key isolation and mandatory `PRAGMA foreign_key_check;` (`DEC-P3-004 Refined`).
  5. **Formula Injection Sanitization (CWE-1236)**: Neutralize spreadsheet formula execution triggers (`=`, `+`, `-`, `@`, `\t`, `\r`) by prepending a single quote (`'`), while openpyxl `data_only=True` treats missing cached formula values strictly as `None` / `UNKNOWN` without defaulting to zero.
  6. **Append-Only Audit Logging**: All lifecycle actions (CREATE, UPDATE, SUPERSEDE, REVIEW, IMPORT) append immutable records to `audit_logs`. Deletion or modification raises `ImmutabilityViolationError` (Rule 16/17, AUD-003).
* **Consequences**:
  - Full relational persistence layer covering all Phase 2 domain entities.
  - Zero network dependencies during test execution (140/140 unit and integration tests passing).
  - Ready for future automated connectors, Gemini analysis, and Cloudflare subdomain ingress (`incidents.aiguardiansllc.us`).

---

### ADR-008: Secure Ingestion Connectors, Cryptographic Provenance, and SSRF Defense
* **Date**: 2026-10-20
* **Status**: RATIFIED
* **Deciders**: AI Guardians LLC Leadership, Antigravity AI
* **Context**: Phase 4 extends the AI Incident Monitor to ingest external feeds (RSS, arXiv, OECD exports) while strictly observing constitutional rules (Rule 1, Rule 9, Rule 11, Rule 14, Rule 15, Rule 16). Ingesting external feeds introduces severe attack surfaces: Server-Side Request Forgery (SSRF) targeting internal networks and cloud metadata (`169.254.169.254`), DNS rebinding (TOCTOU) attacks bypassing initial DNS checks, TLS SNI mismatches, denial of service via oversized feeds and decompression bombs, copyright violations from storing full raw articles in Git, and untracked feed alteration.
* **Decision**: Adopt a defense-in-depth architecture ratified across four core decisions:
  1. **OECD Integration Architecture (DEC-P4-001, Option A)**:
     - Utilize a pluggable OECD adapter operating strictly on offline structured exports, fixtures, and officially documented file formats.
     - Zero live scraping, polling, or reverse-engineering of undocumented OECD web or UI API endpoints.
     - The adapter interface is standardized so an authorized official API or approved bulk connector can be enabled in the future with zero changes to downstream pipeline contracts.
  2. **Raw Feed Storage & Retention Policy (DEC-P4-002, Option A)**:
     - Database persistence is strictly limited to metadata, canonical URLs, structured parsed fields, cryptographic provenance hashes (`SHA-256`), and minimal fair-use direct snippets.
     - Full raw payloads are staged strictly in a gitignored local or object storage staging area (`.data/raw_feeds/`) governed by a configurable 30-day purge TTL.
     - Zero raw feed payloads, full article bodies, or copyrighted text are committed to GitHub or permanently retained in the relational database.
  3. **SSRF Defense and DNS-Rebinding Connection Pinning (DEC-P4-003, Option A with Constraints)**:
     - Enforce a strict outbound URL policy: HTTPS only by default (HTTP permitted only in explicit local test environments), blocked non-HTTP schemes (`file://`, `gopher://`, `ftp://`), stripped userinfo credentials, and default port 443.
     - Pre-flight DNS resolution and IP validation rejecting 21 blocked IP ranges: RFC 1918 private subnets, loopback, link-local, carrier-grade NAT, multicast, broadcast, documentation, benchmarking, IPv6 unique local, IPv6 link-local, IPv4-mapped IPv6, 6to4, Teredo, and cloud metadata endpoints (`169.254.169.254`, `metadata.google.internal`).
     - Connection pinning: Establish TCP connections directly to the pre-validated IP address while preserving the original hostname for TLS SNI negotiation, certificate validation, and the HTTP `Host` header. Simplistic IP-replacement that breaks TLS certificate verification is explicitly prohibited.
     - Validate every redirect hop independently up to a maximum of 3 hops; prohibit HTTPS-to-HTTP downgrades.
     - Enforce strict content bounds: maximum 5 MB payload size and streaming decompression expansion ratio limits.
  4. **Sequential Ingestion-Run Hash Chaining (DEC-P4-004, Option A)**:
     - Ingestion manifests record a tamper-evident cryptographic hash chain where each run links to `previous_manifest_sha256`.
     - The genesis manifest links to a deterministic 64-character zero-hash anchor (`0000000000000000000000000000000000000000000000000000000000000000`).
     - This provides immutable audit traceability and sequence verification for all ingestion runs without distributed consensus or blockchain overhead.
  5. **Decoupled & Deferred Scheduler**:
     - Background scheduling (cron/daemon) is decoupled from the core ingestion pipeline and deferred. Phase 4 operations are invoked deterministically via CLI commands and Makefile targets.
* **Consequences**:
  - Full mitigation of SSRF, DNS rebinding, decompression bombs, and cloud metadata theft.
  - Provable copyright compliance under fair-use doctrine.
  - Complete cryptographic auditability across all feed ingestion runs.
  - Zero live network dependencies during automated test execution.

---

### ADR-009: OECD Export-Only Adapter Architecture and Zero-Scraping Mandate
* **Date**: 2026-10-20
* **Status**: RATIFIED
* **Deciders**: AI Guardians LLC Leadership, Antigravity AI
* **Context**: The OECD AI Incidents Monitor (OECD.AI AIM) provides valuable public incident data. Scraping or polling undocumented OECD UI or internal API endpoints violates terms of service, introduces brittle external dependencies, and risks pipeline failures.
* **Decision**: Adopt a strict export-only adapter architecture (`OECDExportAdapter`):
  1. Ingestion is restricted to three official modes: `MANUAL_OFFICIAL_EXPORT` (operator upload), `RECORDED_TEST_FIXTURE` (sanitized fixtures), and `FUTURE_OFFICIAL_API_DISABLED` (disabled by default placeholder).
  2. Zero live web scraping, undocumented API polling, or reverse engineering of dynamic UI calls.
  3. Support CSV, JSON, and XLSX imports with formula injection defense (CWE-1236).
  4. Preserve raw OECD records without overwriting original fields; treat OECD classifications as source metadata rather than proven legal or causal findings.
  5. Missing OECD record IDs trigger a `requires_dedup_review` flag for human deduplication rather than inventing synthetic IDs.
* **Consequences**:
  - Guaranteed stability and defensibility of the OECD ingestion pipeline.
  - Full decoupling from volatile OECD frontend website changes.
  - Zero network dependencies for OECD data ingestion.



