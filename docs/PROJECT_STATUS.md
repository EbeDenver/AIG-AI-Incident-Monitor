# PROJECT STATUS & MATURITY DASHBOARD
**Project:** AI Incident Monitor
**Organization:** AI Guardians LLC
**Document Identifier:** STAT-001
**Last Updated:** 2026-10-29
**Current Milestone:** Phase 7B (Local Pipeline Observability & Operational Diagnostics) — COMPLETED (Branch: `phase7b-local-observability-diagnostics`)
**Overall Status:** GREEN (Phase 7B Complete, 789 Tests Passing, Provenance Chain Valid)

---

## 1. Milestone Roadmap & Phase Progress

| Phase | Description | Target Deliverables | Status | Completion Date |
| :---: | :--- | :--- | :---: | :---: |
| **Phase 1** | **Foundational Governing Documentation** | 11 governing docs, Git repo init, .gitignore, ADR-001..005, RTM | **COMPLETED** | **2026-10-07** |
| **Phase 2** | **Core Schemas & Epistemic Models** | Pydantic v2 models, epistemic typing, 29 golden fixtures, 89 tests | **COMPLETED** | **2026-10-19** |
| **Phase 3** | **Data Foundation & Manual Import Engine** | SQLAlchemy 2.0 ORM, dual-engine Alembic, repositories, CSV/JSON/XLSX import, CWE-1236 sanitizer, 4-tier dedup, append-only audit, 144 tests | **COMPLETED** | **2026-10-19** |
| **Phase 4** | **Secure Ingestion Connectors & Provenance** | SSRF defense, RSS/arXiv connectors, OECD adapter, raw staging store, 30-day purge, manifest hash chaining, XML containment, 197 tests | **COMPLETED** | **2026-10-20** |
| **Phase 5** | **AIG-ISI Scoring & Governance Map** | AIG-ISI engine, factor rationales, OECD/NIST/EU Act mappers, output linter, eligibility gates | **COMPLETED** | **2026-10-23** |
| **Phase 6A** | **Editorial Foundation & Review CLI** | Dossier models, Migration 006, source selector, assembly, validator, review state machine, CLI | **COMPLETED** | **2026-10-23** |
| **Phase 6B** | **Editorial Renderers & Local Dossier Export** | Deterministic Markdown/JSON renderers, 3 presentation profiles, export manifest, safe atomic exporter, export CLI | **COMPLETED** | **2026-10-24** |
| **Phase 7A** | **Offline End-to-End Verification Harness** | Offline E2E test suite covering full workflow, synthetic fixtures, 17 failure/edge scenarios, network denial guard | **COMPLETED** | **2026-10-29** |
| **Phase 7B** | **Pipeline Observability & Diagnostics** | Telemetry, pipeline health checks, diagnostics CLI, operational metrics | **COMPLETED** | **2026-10-29** |

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
  - `VERIFIED (Phase 5 Increment 2B Governance Mapping Engine)`: 3 requirements
    - `GOV-001`: Deterministic OECD AI Principles mapping engine (`GovernanceMappingEngine`, `ALL_OECD_RULES`).
    - `GOV-002`: Deterministic NIST AI RMF 1.0 core functions, categories, and subcategories mapping engine (`GovernanceMappingEngine`, `ALL_NIST_RULES`).
    - `GOV-005`: Governance mapping orthogonality to AIG-ISI severity scoring (`test_aig_isi_severity_score_does_not_affect_mapping`).
  - `VERIFIED (Phase 5 Increment 2C-1 EU Screen Foundation)`: 5 requirements
    - `GOV-004`: Clear separation of statutory jurisdictional applicability and conceptual relevance (`EURelevanceLevel`, `EUNexusAssessment`).
    - `AUD-001`: Prohibition of automated model self-approval via `is_human=True` check in `transition_eu_screen_status`.
    - `AUD-002`: Authenticated human reviewer enforcement in `verify_output_eligibility`.
    - `LGL-002`: Mandatory versioned disclaimer enforcement (`EU_AI_ACT_DISCLAIMER_V2`, `'2024-1689-v2'`).
    - `LGL-003`: Distinction between statutory applicability and non-binding informational relevance across all domain schemas.
  - `VERIFIED (Phase 5 Increment 2C Complete)`: 2 requirements
    - `GOV-003`: EU AI Act categorization screening (delivered across 2C-1, 2C-2, 2C-3A, and 2C-3B; verified by 96 unit tests in test_eu_output_linter.py and test_eu_output_eligibility.py).
    - `LGL-001`: Never assert unadjudicated violations (schema and regex guards in 2C-1/2C-2; deterministic output linter and fail-closed gates in 2C-3B).
  - `VERIFIED (Phase 7B Observability & Diagnostics)`: 1 requirement
    - `OPS-001`: Structured JSON logging for all pipeline operations, connector runs, and evaluation cycles (`OperationalEventSchema`, `OperationalJSONLogger`, `stage_scope`, `LocalDiagnosticsRunner`).
  - `PLANNED (Phases 6–7 / Next Milestones)`: 20 requirements
* **Total Verified**: 49 / 69 (71.0%)

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
- [x] **Increment 2B (Verified & Merged to main)**: Deterministic mapping engines for OECD AI Principles and NIST AI RMF:
  - Pure deterministic rule evaluators for OECD AI Principles and NIST AI RMF 1.0 functions, categories, and subcategories.
  - Relational persistence migration `004_oecd_nist_mapping_provenance.py` and `GovernanceMappingService`.
  - Specificity and hierarchy enforcement, independent orthogonal confidence scoring model, review gates, and 52 new tests (484 total tests).
- [x] **Increment 2C-1 (Verified & Merged to main)**: EU AI Act Informational Relevance Screen Foundation:
  - Relational schema migration `005_eu_screen_foundation.py` adding `eu_screen_rule_traces` and `review_status` state machine.
  - Controlled vocabularies, mandatory versioned disclaimer (`EU_AI_ACT_DISCLAIMER_V2`), output-eligibility guard (`verify_output_eligibility`), and cryptographic audit trail. (484 total tests).
- [x] **Increment 2C-2 (Verified & Merged to main)**: EU AI Act Core Deterministic Fact Evaluators:
  - Deterministic evaluators for territorial/market nexus (Article 2), AI-system definitional context (Article 3(1)), actor role attribution (Article 3(2)–(8)), temporal alignment, and epistemic gaps with neutral follow-up questions.
  - Non-legal language validation (`validate_no_legal_language`), fine-grained rule traces, and 32 new tests (516 total tests).
- [x] **Increment 2C-3A (Verified on `phase5-inc2c3a-eu-conceptual-relevance`)**: EU AI Act Conceptual Relevance Engine:
  - Deterministic, evidence-grounded screening engine (`EURelevanceScreeningEngine`) evaluating 28 specific conceptual rules across 6 rule families: Article 5 (points a–h), Annex III (points 1–8), Article 50 (points 1, 2, 4), GPAI (Articles 51 and 53), Operational Controls (Articles 10, 12, 14, 15, 72, 73), and Serious Incident harm thresholds (Article 3(49)).
  - Automatic parent control linkage (`EU-ART-5`, `EU-ART-6`, `EU-ART-50`).
  - Mandatory `PENDING_REVIEW` routing, orthogonal confidence scoring, zero-evidence modesty, and strict prohibition of legal determination language.
  - 40 new unit tests (556 total tests passing), 0 failures, verified provenance chain.
- [ ] **Increment 2C-3B (Planned - Deferred)**: EU Output Linter and Final Review Gate Integration:
  - Output linter (`eu_output_linter.py`), final external-use eligibility verification integration, reviewer-attestation validation.
- [ ] **Increment 2D (Planned)**: Governance reporting and publishing workflows.

---

## 8. Phase 6 Delivery Tracking

- [x] **Phase 6A (Verified & Merged to main)**: Editorial Foundations & Review CLI:
  - Migration 006 relational schema (`006_editorial_dossiers_and_review.py`).
  - Source selector (`EditorialSourceSelector`), assembly engine (`EditorialDossierAssembler`), validation engine (`EditorialValidator`), review state machine (`EditorialReviewStateMachine`), and typed repository (`EditorialRepository`).
  - CLI commands (`select-candidates`, `assemble-dossier`, `inspect-dossier`, `submit-for-review`, `approve-dossier`, `reject-dossier`).
  - 48 tests (705 total tests passing).
- [x] **Phase 6B (Verified & Merged to main)**: Editorial Renderers & Local Dossier Export:
  - Deterministic Markdown renderer (`EditorialMarkdownRenderer`) across 3 presentation profiles (`DEEP_DIVE_DOSSIER`, `EXECUTIVE_BRIEF`, `RAPID_ALERT`) and 2 artifact purposes (`INTERNAL_REVIEW_COPY`, `APPROVED_EDITORIAL_COPY`).
  - Deterministic JSON package renderer (`EditorialJSONRenderer`) with non-self-referential payload hashing.
  - Safe local exporter (`EditorialDossierExporter`) with collision protection, path traversal defenses, symlink rejection, atomic write, and drift detection.
  - Export provenance manifest (`EditorialExportManifest`).
  - Local export CLI (`export-dossier`).
  - 36 renderer unit tests + 7 CLI integration tests (741 total tests passing).

---

## 9. Phase 7A Delivery Tracking

- [x] **Phase 7A (Verified on `phase7a-offline-e2e-harness`)**: Offline End-to-End Verification Harness:
  - Dedicated synthetic fixtures under `backend/tests/fixtures/e2e/` (RSS, Atom, malformed XML, prompt injection, EU-relevant, OECD JSON).
  - Comprehensive 17-scenario offline end-to-end integration test suite (`backend/tests/integration/test_end_to_end_pipeline.py`).
  - Complete workflow verification: Ingestion $\to$ Deduplication $\to$ Evidence Graph $\to$ Deterministic Scoring/Mapping $\to$ Dossier Assembly $\to$ Review Copy Rendering $\to$ Explicit Test-Human Review (Rule 14) $\to$ Approved Local Export $\to$ Cryptographic Hash Verification.
  - Negative failure resilience: missing evidence, corrupted XML, prompt injection containment, provenance hash divergence, post-assembly source drift, untrusted reference data, ineligible EU commentary exclusion, transaction rollback, symlink and path traversal safety, automated approval denial, and network denial enforcement.
  - Multi-Mac isolation using dynamic `tmp_path` fixtures; zero production code modifications.
  - 17 new integration tests (758 total tests passing, 0 failures, 0 warnings in ~9.05s); provenance chain verified with 0 anomalies.

---

## 10. Phase 7B Delivery Tracking

- [x] **Phase 7B (Verified on `phase7b-local-observability-diagnostics`)**: Local Pipeline Observability & Operational Diagnostics:
  - **Structured Operational Telemetry (`ai_incident_monitor.observability`)**:
    - Small, versioned operational event schema (`OperationalEventSchema`, `v1.0.0`) capturing `run_id`, `stage`, `event_type`, `recorded_at_utc`, `duration_ms` (monotonic clock), `outcome`, `reason_code`, safe `record_ids`, and `counts`.
    - Controlled outcome states: `SUCCEEDED`, `FAILED_TECHNICAL`, `BLOCKED_VALIDATION`, `AWAITING_HUMAN_REVIEW`, and `SKIPPED` (clearly differentiating pending-review or validation stops from technical faults).
    - Context-safe correlation tracking via `contextvars.ContextVar` (`run_scope`, `stage_scope`) with automatic duration measurement and correlation isolation across concurrent or sequential runs.
    - Security & data minimization: log injection defenses (CWE-117 newline and CR stripping, null byte removal), credential and token masking (`mask_sensitive_dict`), and safe exception summaries forbidding raw exception locals or stack frames.
    - Standard-library JSON logger (`ai_incident_monitor.observability`) with fail-soft, non-fatal logging policy (telemetry errors never abort core business transactions, while mandatory audit logs remain fail-closed).
    - In-memory run metrics collector (`RunMetricsCollector`, `RunMetricsSummary`) with accurate counts: `items_received`, `items_accepted`, `items_rejected`, `duplicates_detected`, `assessments_completed`, `dossiers_assembled`, `validation_blocks`, `review_required_outcomes`, `export_successes`, `export_failures`.
  - **Local Operational Diagnostics Runner & CLI (`ai_incident_monitor.diagnostics`)**:
    - Safe, non-mutating operational diagnostics runner (`LocalDiagnosticsRunner`) evaluating 6 read-only environment checks:
      1. `CONFIGURATION`: Verifies database URL and runtime configuration presence with masked credentials.
      2. `DATABASE`: Verifies connectivity via read-only SQL ping query (`SELECT 1`).
      3. `SCHEMA`: Inspects table presence (`incidents`, `evidence_records`, `claim_records`, `source_references`, `editorial_dossiers`, `framework_reference_sets`, `governance_audit_logs`) without auto-repair or running migrations.
      4. `REFERENCE_LIBRARY`: Verifies cryptographic SHA-256 byte digests of OECD, NIST, and EU AI Act YAML files against `frameworks/manifest.json`.
      5. `STORAGE_PATHS`: Read-only, non-mutating accessibility checks of export and staging paths (zero test files written).
      6. `PIPELINE_COMPONENTS`: Readiness validation of scoring, validator, and rendering engines.
    - Standalone diagnostics CLI (`python -m ai_incident_monitor.diagnostics.cli` or `make diagnose`) supporting human-readable formatted table and `--json` machine-readable output.
    - Integrated `diagnose` subcommand in editorial review CLI (`python -m ai_incident_monitor.editorial.cli diagnose [--json]`).
    - Standardized exit codes: 0 = HEALTHY, 1 = DEGRADED, 2 = UNHEALTHY.
  - **Service Instrumentation**:
    - Instrumented `IngestionPipeline.execute_run()` with `stage_scope(OperationalStage.INGESTION)` recording items received, accepted, and deduplicated.
    - Instrumented `EditorialDossierExporter.export()` with `stage_scope(OperationalStage.LOCAL_EXPORT)` recording export attempts, successes, collisions, and validation blocks.
  - **Unit & Integration Test Suite (31 new tests, 789 total tests passing)**:
    - `backend/tests/unit/observability/test_models_and_events.py` (11 unit tests).
    - `backend/tests/unit/observability/test_context_and_metrics.py` (7 unit tests).
    - `backend/tests/unit/diagnostics/test_diagnostics_runner.py` (9 unit tests).
    - `backend/tests/integration/test_diagnostics_cli.py` (4 CLI integration tests).
