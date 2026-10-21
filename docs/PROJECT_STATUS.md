# PROJECT STATUS & MATURITY DASHBOARD
**Project:** AI Incident Monitor
**Organization:** AI Guardians LLC
**Document Identifier:** STAT-001
**Last Updated:** 2026-10-21
**Current Milestone:** Phase 5 (AIG-ISI Severity Scoring Engine & Governance Mappings) — INCREMENT 2A COMPLETED (Branch: `phase5-inc2a-reference-foundation`)
**Overall Status:** GREEN (Phase 5 Increment 2A Complete, 432/432 Tests Passing, 0 Failures, Provenance Chain Valid)

---

## 1. Milestone Roadmap & Phase Progress

| Phase | Description | Target Deliverables | Status | Completion Date |
| :---: | :--- | :--- | :---: | :---: |
| **Phase 1** | **Foundational Governing Documentation** | 11 governing docs, Git repo init, .gitignore, ADR-001..005, RTM | **COMPLETED** | **2026-10-07** |
| **Phase 2** | **Core Schemas & Epistemic Models** | Pydantic v2 models, epistemic typing, 29 golden fixtures, 89 tests | **COMPLETED** | **2026-10-19** |
| **Phase 3** | **Data Foundation & Manual Import Engine** | SQLAlchemy 2.0 ORM, dual-engine Alembic, repositories, CSV/JSON/XLSX import, CWE-1236 sanitizer, 4-tier dedup, append-only audit, 144 tests | **COMPLETED** | **2026-10-19** |
| **Phase 4** | **Secure Ingestion Connectors & Provenance** | SSRF defense, RSS/arXiv connectors, OECD adapter, raw staging store, 30-day purge, manifest hash chaining, XML containment, 197 tests | **COMPLETED** | **2026-10-20** |
| **Phase 5** | **AIG-ISI Scoring & Governance Map** | AIG-ISI engine, factor rationales, OECD/NIST/EU Act mappers | **IN PROGRESS (Inc 1 Merged, Inc 2A Complete)** | Target: Phase 5 |
| **Phase 6** | Editorial Pipeline & Human Review | Substack generator, neutral tone linter, HITL review CLI | Planned | Phase 6 Session |
| **Phase 7** | End-to-End Harness & Observability | Orchestration, telemetry, multi-Mac test suite, monitoring, Cloudflare deployment prep | Planned | Phase 7 Session |

---

## 2. Requirements Traceability Coverage Summary

Based on [`docs/REQUIREMENTS_TRACEABILITY.md`](REQUIREMENTS_TRACEABILITY.md):

* **Total Tracked Requirements**: 69
* **Priority Breakdown**: 47 P0 (Critical), 22 P1 (High), 0 P2
* **Current Status**:
  - `VERIFIED (Phase 1 Baseline)`: 7 requirements
    - `GIT-001`: GitHub repository as single source of truth.
    - `GIT-002`: Cross-Mac portability and path-agnostic design.
    - `GIT-003`: Exclusion of mutable databases and local caches via `.gitignore`.
    - `GIT-004`: Versioned ADR recording in `docs/DECISIONS.md`.
    - `GIT-005`: Session lifecycle documentation sync (`PROJECT_STATUS.md`, `NEXT_SESSION.md`).
    - `PRI-002`: Copyright fair-use compliance (no raw articles in Git).
    - `SEC-003`: Zero-secret enforcement via `.gitignore` and git hygiene.
  - `VERIFIED (Phase 2 Schemas & Models)`: 13 requirements
    - `EVD-001`: Zero fabrication guarantees (evidence grounding checks).
    - `EVD-002`: Epistemic tri-state modeling (`UNKNOWN` is not coerced to zero).
    - `EVD-003`: Claim categorical classification (5 epistemic tiers).
    - `EVD-004`: Mandatory evidence linkage (URI, timestamp, quotation offsets).
    - `EVD-005`: Verbatim direct quotation validation (`QuoteSpan` offsets).
    - `EVD-006`: Orthogonal separation of Incident Severity and Evidence Confidence.
    - `SEV-004`: Strict segregation of Actual Harm vs Potential Harm.
    - `SEV-005`: Non-monetization constraint for human dignity and physical harm.
    - `PRI-004`: Sanitized synthetic test fixtures (22 golden + 7 invalid).
    - `TST-001`: Automated test suite with zero test failures (144 tests pass in 3.50s).
    - `TST-003`: Negative testing suite validating rejection of ungrounded data.
    - `TST-004`: Property/invariant testing that `UNKNOWN` is never coerced to zero.
    - `AUD-003`: Immutable and append-only assessment records (`frozen=True`).
  - `VERIFIED (Phase 3 Data Foundation & Import)`: 3 requirements
    - `SRC-002`: Cryptographic SHA-256 digest computation and persistence upon ingestion (`compute_file_sha256`, `raw_import_records`).
    - `SRC-004`: Multi-source incident deduplication and human review queue (`DeduplicationEngine`, `dedup_candidates`).
    - `AUD-004`: Tamper-evident, append-only audit trail for all stage transitions (`AuditRepository`, `AuditLogModel`).
  - `VERIFIED (Phase 4 Ingestion Connectors)`: 10 requirements
    - `SEC-004`: SSRF prevention, URL sanitization, 21 blocked IP ranges, and connection pinning (`SecureHTTPClient`, `DEC-P4-003`).
    - `SRC-001`: Pluggable source connectors for RSS news feeds and arXiv research API (`BaseConnector`, `RSSConnector`, `ArXivConnector`).
    - `SRC-002`: Cryptographic provenance manifests and sequential hash chaining (`IngestionManifest`, `verify_provenance_chain`, `ADR-010`).
    - `SRC-003`: Mandatory structured XML containment (`<untrusted_source_content>`) prior to LLM processing (`UntrustedSourceContentEnvelope`, `ADR-011`).
    - `SRC-005`: Unstable endpoint resilience, exponential backoff, jitter, and failure fallbacks (`RetryPolicy`).
    - `SEC-001`: Adversarial prompt-injection defense test suite and triage classifier (`detect_prompt_injection_signals`).
    - `SEC-002`: Read-only ingestion and extraction sandboxing (`llm_contract`).
    - `OPS-002`: Per-connector rate-limiting and concurrency controls (`ConnectorRateLimiter`).
    - `GOV-001` (Partial): OECD export adapter support for manual official exports and fixtures without web scraping (`OECDExportAdapter`, `ADR-009`).
    - `PRI-002`: Git hygiene and fair-use retention via raw feed payload staging store (`.data/raw_feeds/`) and automated 30-day purge TTL job.
  - `VERIFIED (Phase 5 Increment 1 Scoring Foundation)`: 5 requirements
    - `SEV-001`: Deterministic, explainable multi-dimensional AIG-ISI scoring across 8 dimensions (`ai_incident_monitor.scoring.engine`).
    - `SEV-002`: Explicit, human-readable evidentiary rationales per dimension alongside composite score (`DimensionScore.rationale`, `ScoreOverride.rationale`).
    - `SEV-003`: Structural isolation of AIG-ISI from external regulatory classifications (`ADR-012`).
    - `SEV-006`: Automated review holds for high-severity assessments (`ReviewGate.TIER_4_OR_5`, `ReviewStatus.PENDING_REVIEW`).
    - `TST-002`: Deterministic golden-fixture test suite validating AIG-ISI severity scoring repeatability across model versions (`calibration_fixtures.json`, `test_calibration_benchmarks.py`).
  - `PLANNED (Phases 5–7)`: 31 requirements
* **Total Verified**: 38 / 69 (55.1%)

---

## 3. Active Risk & Mitigation Register

| Risk ID | Description | Severity | Impact | Mitigation Strategy | Status |
| :---: | :--- | :--- | :--- | :--- | :--- |
| **RSK-001** | Indirect Prompt Injection in Incident Text | HIGH | Agent diversion during extraction | Mandatory `<untrusted_source_content>` XML wrapper isolation; read-only extraction prompts with zero tool execution rights (`SEC-001`, `SEC-002`). | MITIGATED IN DESIGN & FIXTURE |
| **RSK-002** | Aggregation Skew (Unknown vs Zero) | HIGH | Distorted safety benchmarks | Schema-level `MonetaryAmount` & `DateWithPrecision` enforcing `null` for unknown; verified via unit tests (`TST-004`). | VERIFIED IN CODE |
| **RSK-003** | Copyright Infringement Claims | MEDIUM | Legal DMCA liability | Raw article bodies excluded from Git; stored as SHA-256 digests and fair-use quote spans only (`PRI-002`, `PRI-004`, `ADR-003`). | VERIFIED IN CODE |
| **RSK-004** | LLM Hallucinated Citations | HIGH | Credibility collapse | Mandatory verification requiring extracted quotes to match source offsets (`EVD-004`, `EVD-005`). | VERIFIED IN CODE |
| **RSK-005** | Formula Injection in Spreadsheet Imports | HIGH | Remote code execution on analyst export | Formula neutralization sanitizer prepending `'` to dangerous formula triggers per CWE-1236 (`DEC-P3-004`, `ADR-007`). | VERIFIED IN CODE |
| **RSK-006** | Accidental Audit Trail Modification | CRITICAL | Regulatory and constitutional violation | Hard `ImmutabilityViolationError` raised on any update/delete query against `audit_logs` (`AUD-004`, `ADR-007`). | VERIFIED IN CODE |

---

## 4. Phase 3 Verification & Acceptance Criteria

All Phase 3 deliverables have been implemented, tested, and verified on `feature/data-foundation-import`:

- [x] **Relational Persistence Architecture**: 10 SQLAlchemy 2.0 ORM models in `backend/src/ai_incident_monitor/db/models/` mapping 1:1 to Phase 2 domain entities with deterministic naming conventions (`pk_`, `fk_`, `uq_`, `ck_`, `ix_`).
- [x] **Dual-Engine Support**: PostgreSQL 16 container (`postgres:16-alpine` on port 5432) via `backend/docker-compose.yml`; SQLite 3 fallback in `$REPO_ROOT/.data/dev.db` for offline developer testing (`DEC-P3-001`).
- [x] **Alembic Migration Engine**: Initial migration `001_initial_data_foundation.py` creating 14 tables with selective SQLite batch alter support (`render_as_batch=True`) and foreign key check hooks (`DEC-P3-004 Refined`).
- [x] **Typed Repository Layer**: 5 typed repositories (`IncidentRepository`, `ClaimRepository`, `SourceRepository`, `AuditRepository`, `ImportRepository`) providing clean CRUD and transaction boundaries.
- [x] **Append-Only Audit Logging**: Hard runtime immutability enforcement raising `ImmutabilityViolationError` on any attempt to update or delete records in `audit_logs` (Rule 16/17, `AUD-004`).
- [x] **Multi-Format Manual Importers**: Streaming CSV parser, robust JSON parser (arrays, objects, NDJSON), and openpyxl `read_only=True, data_only=True` XLSX parser with 10MB size limits and 5,000 row limits.
- [x] **Formula Injection Defense (CWE-1236)**: Sanitizer neutralizing `=,+,-,@,\t,\r` triggers by prepending single quotes; openpyxl `data_only=True` treats missing cached formula values strictly as `None`/`UNKNOWN` without defaulting to zero.
- [x] **4-Tier Deduplication Waterfall**: Tier 1 exact ID, Tier 2 exact URL auto-linking; Tier 3 near-duplicate candidate routing to human review queue (`dedup_candidates`); Tier 4 distinct incident dossiers (`DEC-P3-003`). Zero automated merging of dossiers (Rule 14).
- [x] **Comprehensive Test Suite**: 144 automated tests passing (139 unit + 5 integration) in under 4 seconds with zero regressions.
- [x] **Developer Workflow Makefile**: Standardized targets (`make test`, `make test-unit`, `make test-integration`, `make migrate`, `make db-up`, `make db-down`, `make clean`).
- [x] **Architectural Record**: `ADR-007` ratified and documented in `docs/DECISIONS.md`.

---

## 5. Active Blockers & Outstanding Decisions

* **Active Blockers**: 0
* **Approved Decisions**:
  - `ADR-006`: Pydantic v2 core epistemic schemas and golden fixtures ratified.
  - `ADR-007`: Relational data foundation, dual-engine migrations, and manual ingestion ratified.
  - `ADR-008`: Secure ingestion connectors, cryptographic provenance, and SSRF defense ratified (`DEC-P4-001` through `DEC-P4-004`).
  - `ADR-009`: OECD Official Export Adapter without web scraping ratified.
  - `ADR-010`: Cryptographic Ingestion Manifests and Sequential Hash Chaining ratified.
  - `ADR-011`: Structured XML Source Containment and LLM Isolation ratified.
  - `ADR-012`: AIG-ISI Scoring Methodology and Mathematical Formulation ratified.
  - `ADR-013`: Orthogonal Evidence Confidence and Uncertainty Bounds ratified.
  - `ADR-014`: Ten Automated Review Workflow Gates and Override Governance ratified.
  - `ADR-015`: Relational Schema and Audit Trail for Severity Assessments ratified.

---

## 6. Phase 4 Delivery Increments & Tracking

Phase 4 delivered in 4 increments, fully verified and merged via PR #3:
- [x] **Increment 1 (Verified)**: URL policy, DNS resolution, connection pinning transport (SSRF defense, 21 blocked IP ranges, SNI preservation), redirect inspector, content limits. (85 tests)
- [x] **Increment 2 (Verified)**: Base connector framework, per-connector rate limiter, exponential backoff with jitter, RSS/Atom connector with HTML sanitization & bozo handling, arXiv connector with strict single-connection policy. (42 tests)
- [x] **Increment 3 (Verified)**: OECD export adapter (DEC-P4-001, ADR-009), raw feed staging store (`.data/raw_feeds/`, DEC-P4-002), 30-day purge TTL job with audit logging. (23 tests)
- [x] **Increment 4 (Verified)**: Ingestion run manifests, sequential cryptographic hash chaining (DEC-P4-004, ADR-010), genesis null anchor, XML containment wrapper (`<untrusted_source_content>`, ADR-011), adversarial prompt-injection triage detector, future LLM contract, and 21 end-to-end integration tests. (47 tests)

---

## 7. Phase 5 Delivery Increments & Tracking

Phase 5 Increment 1 delivered, verified, and merged to `main` via PR #4 (`19db6c3`):
- [x] **Increment 1 (Verified & Merged to main)**: AIG-ISI multi-dimensional scoring core, 8 weighted dimensions (100 total), mathematical bounds, 5 severity tiers, 10 automated review gates, auditable score overrides, relational persistence (`SeverityAssessmentModel`, `SeverityRepository`), Alembic migration `002_aig_isi_severity_foundation.py`, machine-readable spec `aig-isi-1.0.yaml`, calibration guide with 6 archetypes, 41 scoring unit/calibration tests (382 total tests passing).
- [x] **Increment 2A (Verified on `phase5-inc2a-reference-foundation`)**: Reference Library & Relational Data Foundation:
  - Reference Library: Canonical reference files for OECD (`frameworks/oecd/oecd-principles-2024.yaml`), NIST AI RMF (`frameworks/nist/nist-ai-rmf-1.0.yaml`), and EU AI Act (`frameworks/eu-ai-act/eu-ai-act-2024-1689.yaml`), anchored by `frameworks/manifest.json` with SHA-256 integrity digests over raw UTF-8 bytes.
  - Domain Schemas: Strict Pydantic v2 schemas (`extra='forbid'`, `frozen=True`) with anti-fabrication validations and statutory legal disclaimers.
  - Standalone Loader: Zero-dependency pure-Python block YAML parser and canonical JSON manifest validator (`reference_loader.py`).
  - Relational Schema: Alembic migration `003_governance_framework_mappings.py` adding 6 relational tables (`framework_reference_sets`, `framework_controls`, `incident_framework_mappings`, `eu_legal_relevance_screens`, `mapping_evidence_links`, `governance_audit_logs`) with verified clean downgrade.
  - Typed Governance Repository: `GovernanceRepository` enforcing in-place mutation prevention on approved records (`ImmutabilityViolationError`), supersession versioning, and cryptographic audit hash chaining.
  - Automated Verification: 50 new tests (49 unit + 1 migration upgrade/downgrade), bringing repository test suite to 432 passed tests (exceeding requirement of at least 430 total tests) with 0 failures and 0 warnings.
- [ ] **Increment 2B (Planned - Awaiting User Approval)**: Deterministic mapping engines for OECD AI Principles and NIST AI RMF.
- [ ] **Increment 2C (Planned - Awaiting User Approval)**: EU AI Act informational regulatory screening engine.
