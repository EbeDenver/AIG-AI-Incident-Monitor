# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Phase 5 Increment 2C-1] - 2026-10-22

### Added
- **Relational Schema Foundation & Alembic Migration 005 (`005_eu_ai_act_informational_screen.py`)**:
  - Added 16 epistemic, provenance, and audit columns to `eu_legal_relevance_screens`: `screen_version`, `status`, `relevance_level`, `nexus_assessment`, `ai_system_context`, `actor_role_confidence`, `conceptual_risk_areas`, `potentially_relevant_reference_ids`, `operational_relevance_areas`, `timing_assessment`, `known_facts`, `unknowns`, `disputed_facts`, `follow_up_questions`, `rationale`, `disclaimer_version`, `metadata_json`.
  - Created junction table `eu_screen_rule_traces` with foreign keys to `eu_legal_relevance_screens` (`CASCADE`) and `framework_reference_sets` (`RESTRICT`) for fine-grained rule evaluation tracking.
  - Full migration cycle verified (001 -> 002 -> 003 -> 004 -> 005 -> 004 -> 003 -> 002 -> base -> head) with SQLite batch alter support and zero foreign key violations.
- **Non-Judicial Controlled Vocabularies (`ai_incident_monitor.governance.enums`)**:
  - `EURelevanceLevel`: strictly non-legal categorization (`DIRECT_RELEVANCE`, `POSSIBLE_RELEVANCE`, `CONCEPTUAL_RELEVANCE`, `UNLIKELY_RELEVANCE`, `OUTSIDE_APPARENT_SCOPE`, `INSUFFICIENT_INFORMATION`).
  - `EUScreenStatus`: review workflow state machine (`DRAFT`, `CANDIDATE`, `PENDING_REVIEW`, `APPROVED_INFORMATIONAL`, `REJECTED`, `SUPERSEDED`, `INSUFFICIENT_EVIDENCE`).
  - `EUNexusAssessment`: non-liability territorial/market connection (`POSSIBLE_EU_NEXUS`, `NO_EU_NEXUS_EVIDENCE`, `INSUFFICIENT_NEXUS_INFORMATION`, `OUTSIDE_APPARENT_TERRITORIAL_SCOPE`).
  - `EUActorRoleConfidence`: epistemic certainty of actor roles (`IDENTIFIED_FROM_EVIDENCE`, `POSSIBLE_FROM_EVIDENCE`, `UNKNOWN`, `DISPUTED`).
  - `EUTimingAssessment`: temporal correspondence against reference metadata (`REFERENCE_METADATA_ALIGNS`, `INCIDENT_DATE_UNKNOWN`, `EFFECTIVE_DATE_UNCERTAIN`, `TEMPORAL_CONTEXT_REQUIRES_REVIEW`, `NOT_ASSESSED`).
  - `EUSeriousIncidentRelevance`: harm threshold correspondence (`POTENTIALLY_RELEVANT_FOR_REVIEW`, `CONCEPTUALLY_RELEVANT`, `INSUFFICIENT_INFORMATION`, `NOT_APPARENTLY_RELEVANT`).
  - Added `APPROVED_INFORMATIONAL` to `MappingStatus`.
- **Mandatory Versioned Disclaimer & Domain Schemas (`governance.models`)**:
  - Immutable versioned disclaimer `EU_AI_ACT_DISCLAIMER_VERSION = "2024-1689-v2"`.
  - Approved statutory disclaimer text `EU_AI_ACT_DISCLAIMER_V2` mandated across all schemas and repository operations.
  - Pydantic models `EULegalRelevanceScreenSchema` and `EUScreenRuleTraceSchema` enforcing non-legal language validation on all narrative and epistemic fields (`Safety Rule 7`, `LGL-001`).
- **State Machine & Human Review Primacy (`governance_repo.py`)**:
  - `transition_eu_screen_status`: Enforces mandatory human approval (`is_human=True`); machine self-approval raises `ConstitutionalViolationError` (`Rule 12/13`).
  - Hard immutability: In-place mutation of approved informational screens raises `ImmutabilityViolationError`.
  - Non-destructive append-only supersession via `supersede_eu_screen` with bidirectional lineage tracking (`supersedes_screen_id`, `superseded_by_id`).
- **Constitutional Output-Eligibility Guard (`verify_output_eligibility`)**:
  - Guard foundation that unconditionally blocks downstream reporting/publishing unless a screen has `APPROVED_INFORMATIONAL` state, valid versioned disclaimer (`2024-1689-v2`), at least one linked primary evidence record, and authenticated human review identity.
- **Append-Only Cryptographic Audit Trail**:
  - Records `CREATE_EU_SCREEN`, `TRANSITION_STATE`, `SUPERSEDE_EU_SCREEN`, and `ADD_EVIDENCE_LINK` with sequential SHA-256 hash chaining and tamper detection.
- **Testing & Quality Assurance**:
  - 20 new tests added (19 unit tests in `test_eu_screen_foundation.py` + 1 integration migration test update).
  - Total test suite: **484 / 484 passed tests** in ~5.3s with zero failures and zero warnings.
  - Provenance chain verified valid via `make verify-provenance-chain` (`is_valid: true`, 0 anomalies).
- **Architecture & Traceability Documentation**:
  - Ratified ADR-017 (`EU AI Act Informational Relevance Screen Foundation & Output Eligibility Guard`) in `docs/DECISIONS.md`.
  - Updated `docs/ER_DIAGRAM.md` documenting table 22 (`eu_screen_rule_traces`) and all new screen columns.
  - Updated `docs/REQUIREMENTS_TRACEABILITY.md` (`GOV-004`, `AUD-001`, `AUD-002`, `LGL-002`, `LGL-003` verified; `GOV-003`, `LGL-001` in progress).
  - Updated `docs/PROJECT_STATUS.md` and `docs/NEXT_SESSION.md`.

### Hard Boundaries Enforced in Phase 5 Increment 2C-1
- Phase 5 Increments 2C-2 and 2C-3 explicitly deferred and not started.
- Zero evaluation rules, screening logic, or conceptual scope rules implemented.
- `eu_screen.py`, `eu_ai_act_rules.py`, `EURelevanceScreeningEngine`, and `eu_output_linter.py` deferred until authorized sub-increments.
- Zero LLM, Gemini, embedding, or generative model calls.
- Zero live network retrieval, scraping, or external APIs.
- Zero UI/API endpoints, dashboard exposure, or publishing paths.
- Zero legal determinations, statutory applicability conclusions, or violation assertions.

## [Phase 5 Increment 2B] - 2026-10-21

### Added
- **Deterministic Governance Mapping Engine (`ai_incident_monitor.governance`)**:
  - Pure deterministic, evidence-grounded evaluator (`GovernanceMappingEngine`) mapping incident context against validated reference library files (`frameworks/manifest.json`).
  - Strict reference integrity and anti-fabrication enforcement: rejects unknown, inactive, or ungrounded framework identifiers with `ConstitutionalViolationError` (`Safety Rule 2`).
  - Evidence-first invariant: requires at least one verified evidence ID; zero evidence yields zero mappings (`Safety Rule 1`).
  - Complete decoupling from AIG-ISI severity scoring (`Safety Rule 4`, `GOV-005`).
- **OECD & NIST Deterministic Rule Libraries (`governance.rules`)**:
  - `oecd_rules.py`: Rules covering all five OECD AI Principles (2024 update: Principles 1.1–1.5), producing `DIRECTLY_IMPLICATED` or `BROADER_GOVERNANCE_LESSON` classifications.
  - `nist_rules.py`: Rules covering all four core Functions (`GOVERN`, `MAP`, `MEASURE`, `MANAGE`), 5 exact Categories (`GOVERN 1`, `GOVERN 2`, `MAP 1`, `MEASURE 2`, `MANAGE 1`), and 4 exact Subcategories (`GOVERN 1.1`, `MAP 1.1`, `MEASURE 2.1`, `MANAGE 1.1`).
  - Strict NIST hierarchy enforcement (Function -> Category -> Subcategory) with parent reference storage.
  - Specificity gate: NIST subcategory mappings strictly require verified `HIGHLY_SPECIFIC` primary evidence; general evidence remains at Function/Category level.
- **Independent Multi-Factor Confidence Scoring (`confidence.py`)**:
  - Combines evidence count, directness, corroboration, and specificity on a 0–100 scale into bounded levels (`HIGH`, `MEDIUM`, `LOW`, `INSUFFICIENT`).
  - Applies penalties for material unknowns (-15), disputed evidence (-25), and subcategory granularity (-15 to -30).
- **Review State Machine & Gatekeeper (`review_gates.py`)**:
  - Evaluates review gates routing candidates to `PENDING_REVIEW` for sensitive domains (`HEALTH_SAFETY`, `BIOMETRICS`, `LAW_ENFORCEMENT`, `CRITICAL_INFRASTRUCTURE`, `EMPLOYMENT`, `CREDIT`, `EDUCATION`), disputed facts, low confidence, or subcategory granularity.
  - Enforces mandatory human approval (`is_human=True`); machine self-approval raises `ConstitutionalViolationError` (`Rule 12/13`).
  - Enforces append-only supersession; mutating approved mappings raises `ImmutabilityViolationError`.
- **Relational Persistence & Migration 004**:
  - Alembic migration `004_oecd_nist_mapping_provenance.py` adding `rule_id` and `rule_version` columns to `incident_framework_mappings`.
  - Normalized junction storage in `mapping_evidence_links`.
  - Append-only cryptographic audit logging with chained SHA-256 event hashes.
- **Testing & Quality Assurance**:
  - 33 new automated tests (26 unit tests in `test_oecd_nist_mapping_engine.py` + 7 service/review tests in `test_mapping_service_and_review.py`).
  - Total test suite: **464 / 464 passed tests** in ~5.6s with zero failures and zero warnings.
  - Cryptographic provenance chain verified via `make verify-provenance-chain` (`is_valid: true`, 0 anomalies).
- **Methodology Documentation & Architecture Decision Records**:
  - Ratified ADR-016 (`Deterministic OECD and NIST AI RMF Governance Mapping Engine`) in `docs/DECISIONS.md`.
  - Authored `docs/GOVERNANCE_MAPPING_METHODOLOGY.md` (METH-002).
  - Updated `docs/ER_DIAGRAM.md` and `docs/REQUIREMENTS_TRACEABILITY.md` (`GOV-001`, `GOV-002`, `GOV-005` verified).

### Hard Boundaries Enforced in Phase 5 Increment 2B
- Phase 5 Increment 2C (EU AI Act screening) explicitly deferred and not started.
- Zero LLM, Gemini, or generative AI calls.
- Zero live external network calls, scrapers, or RSS background fetching.
- Zero UI, Substack, dashboard, or public publishing components.
- Zero legal violation determinations (Safety Rule 7, Constitutional Rules 10 & 11).

## [Phase 5 Increment 2A] - 2026-10-21

### Added
- **Governance Reference Library (`frameworks/`)**:
  - Cryptographic manifest `frameworks/manifest.json` registering official reference files with SHA-256 hashes computed over raw UTF-8 file bytes (`compute_file_sha256`) and canonical JSON manifest hashing (`compute_manifest_hash`).
  - OECD AI Principles reference definition `frameworks/oecd/oecd-principles-2024.yaml` (Principles 1.1–1.5) with official OECD legal locators.
  - NIST AI RMF 1.0 reference definition `frameworks/nist/nist-ai-rmf-1.0.yaml` (Functions GOVERN, MAP, MEASURE, MANAGE, 19 categories, 4 subcategories) with NIST SP 1270 locators.
  - Regulation (EU) 2024/1689 reference definition `frameworks/eu-ai-act/eu-ai-act-2024-1689.yaml` (Prohibited Practices, High-Risk systems, GPAI obligations, serious incidents, definitions) with neutral official citations and zero unadjudicated legal conclusions.
- **Domain Schemas & Zero-Dependency Reference Loader (`ai_incident_monitor.governance`)**:
  - Controlled vocabularies (`enums.py`) for framework codes, control levels, OECD/NIST/EU applicability categories, territorial nexus, risk classes, and audit event types.
  - Strict Pydantic v2 models (`models.py`) with `extra='forbid'`, `frozen=True`, anti-fabrication field validators, immutable statutory disclaimers, and audit event models.
  - Standalone pure-Python deterministic block YAML parser and manifest verification loader (`reference_loader.py`).
- **Relational Persistence Layer & Alembic Migration 003**:
  - Six relational models in `db/models/governance.py`: `FrameworkReferenceSetModel`, `FrameworkControlModel`, `IncidentFrameworkMappingModel`, `EULegalRelevanceScreenModel`, `MappingEvidenceLinkModel`, `GovernanceAuditLogModel`.
  - Migration `003_governance_framework_mappings.py` supporting PostgreSQL 16 and SQLite 3 with verified clean downgrade dropping only 003 tables.
- **Typed Governance Repository (`GovernanceRepository`)**:
  - Full CRUD operations for reference sets, controls, mappings, EU legal screens, and evidence links.
  - Hard immutability enforcement preventing in-place mutation of approved mappings or screens (`ImmutabilityViolationError`).
  - Non-destructive supersession workflow.
  - Append-only cryptographic audit trail with chained `event_hash = SHA256(canonical(event) + previous_hash)`.
- **Testing & Quality Assurance**:
  - 50 new automated tests (49 unit tests in `backend/tests/unit/governance/` + 1 full migration upgrade/downgrade test).
  - Total test suite: **432 / 432 passed tests** with zero failures and zero warnings (satisfying requirement of at least 430 total tests).
  - Cryptographic provenance chain verified via `make verify-provenance-chain` (`is_valid: true`).

### Hard Boundaries Enforced in Phase 5 Increment 2A
- Zero OECD or NIST mapping engines implemented (reserved for Increment 2B).
- Zero EU AI Act rule evaluators or classification engines implemented (reserved for Increment 2C).
- Zero LLM, Gemini, or generative AI calls.
- Zero live external network calls, scrapers, or RSS background fetching.
- Zero UI, Substack, dashboard, or public publishing components.
- Zero unadjudicated legal violation determinations (Constitutional Rule 10/11).
- All requirements traceability statuses remain `PLANNED` until formal acceptance review.

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
