# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Phase 7B] - 2026-10-29

### Added
- **Local Operational Observability & Structured Event Logging (`ai_incident_monitor.observability`)**:
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

## [Phase 7A] - 2026-10-29

### Added
- **Offline End-to-End Verification Harness (`backend/tests/integration/test_end_to_end_pipeline.py`)**:
  - Comprehensive 17-scenario end-to-end integration test harness executing the full supported pipeline offline:
    - `test_01_ordinary_attributed_reporting_without_per_incident_approval`: Ingestion -> containment -> 4-tier deduplication -> evidence graph -> AIG-ISI scoring -> OECD/NIST mapping -> candidate evaluation -> draft dossier assembly without per-incident human sign-off.
    - `test_02_dossier_creation_and_review_copy_rendering_before_approval`: Assembly and rendering of `INTERNAL_REVIEW_COPY` (Markdown & JSON) prior to approval, with review watermark banner and validation table.
    - `test_03_successful_explicit_test_human_approval_and_approved_export`: Full lifecycle through review submission, explicit test-human attestation sign-off (Rule 14), status transition to `APPROVED_INFORMATIONAL`, and export as `APPROVED_EDITORIAL_COPY`.
    - `test_04_duplicate_and_near_duplicate_input_handling`: Strict URL identity deduplication preventing duplicate incident ingestion.
    - `test_05_malformed_feed_input_resilience`: Ingestion containment and graceful error handling on truncated and corrupt XML feeds.
    - `test_06_missing_evidence_blocks_dossier_inclusion`: Editorial candidate eligibility exclusion when zero evidence records are linked.
    - `test_07_invalid_provenance_chain_detection`: Cryptographic hash chain validation detecting altered manifest content or hash divergence.
    - `test_08_source_and_content_drift_blocks_approval_and_export`: Detection of post-assembly mutations in underlying incident records, blocking human approval and approved export.
    - `test_09_invalid_reference_data_blocks_governance_mapping`: Tampered or unanchored governance reference data fails closed with `ConstitutionalViolationError`.
    - `test_10_ineligible_optional_eu_commentary_clean_omission`: Ineligible EU screens (unreviewed, unverified territorial nexus) omitted cleanly without blocking approved exports.
    - `test_11_database_and_audit_persistence_transaction_rollback`: Database transaction rollback on simulated constraint failure leaves zero orphaned state.
    - `test_12_interrupted_processing_and_idempotent_retry`: Repeated execution on identical feeds and candidate pools is safe and idempotent.
    - `test_13_partial_export_failure_and_cleanup`: Path collision protection without `--overwrite`, symlink destination rejection, and null byte injection rejection.
    - `test_14_unauthorized_and_automated_approval_attempts_blocked`: Autonomous agents (`is_human=False`), empty reviewer IDs, unconfirmed attestations, and unapproved exports strictly blocked by Rule 14.
    - `test_15_artifact_and_manifest_hash_verification`: Independent SHA-256 verification of disk artifacts against manifest digests.
    - `test_16_sensitive_data_and_secret_leakage_checks`: Redaction and absence of secrets, tokens, and unrestricted audit fields in exported Markdown and JSON.
    - `test_17_network_denial_enforcement`: Socket connection attempt denial guard verifying zero external network egress during pipeline execution.
- **Dedicated Synthetic Test Fixtures (`backend/tests/fixtures/e2e/`)**:
  - `rss_standard_incident.xml`: Synthetic RSS 2.0 incident feed item.
  - `atom_standard_incident.xml`: Synthetic Atom 1.0 incident feed item.
  - `rss_malformed.xml`: Intentionally malformed XML for parser resilience testing.
  - `rss_prompt_injection.xml`: Adversarial prompt injection payload for containment testing.
  - `rss_eu_relevant.xml`: Synthetic clinical triage incident for EU AI Act screening.
  - `synthetic_oecd_incident.json`: Synthetic OECD incident export schema fixture.

## [Phase 6B] - 2026-10-24

### Added
- **Deterministic Editorial Markdown Renderer (`EditorialMarkdownRenderer`)**:
  - Pure deterministic Markdown generation for editorial dossiers across three presentation profiles:
    - `DEEP_DIVE_DOSSIER`: Comprehensive technical analysis with full incident dossiers, epistemic segregation tables, and optional EU regulatory commentary.
    - `EXECUTIVE_BRIEF`: High-level strategic synthesis featuring KPI tables, severity distributions, and concise incident briefs.
    - `RAPID_ALERT`: Urgent operational alert detailing incident identification, severity tier, verified facts, and documented unknowns.
  - Distinct artifact purpose modes:
    - `INTERNAL_REVIEW_COPY`: Working draft rendered prior to human approval, complete with prominent unapproved watermark banner and validation findings breakdown.
    - `APPROVED_EDITORIAL_COPY`: Publication copy strictly requiring `APPROVED_INFORMATIONAL` status, zero source drift, matching content hash, zero blocking validation findings, and human reviewer attestation (Rule 14).
  - Robust formatting safeguards: active HTML tags stripped, markdown table pipe characters escaped, dangerous URL schemes (`javascript:`, `data:`, `file:`) neutralized.
- **Deterministic Editorial JSON Package Renderer (`EditorialJSONRenderer`)**:
  - Non-self-referential cryptographic hashing: computes `canonical_payload_hash` over deterministic export payload excluding file digests to avoid circular references.
  - Complete structured package including canonical dossier content, review metadata, validation findings, and sanitized allowlisted audit lineage (stripping tokens, passwords, and internal notes).
- **Artifact Provenance Manifest (`EditorialExportManifest`)**:
  - Machine-readable manifest linking `canonical_dossier_content_hash`, `canonical_payload_hash`, physical `artifact_file_hash`, generator versions, disclaimer version, and validation reports.
- **Safe Local Dossier Exporter (`EditorialDossierExporter`)**:
  - Path traversal and confinement guards: rejects null bytes and confines export targets to safe directories.
  - Symlink defense: strictly refuses to write into symlinked destination directories.
  - Overwrite protection: fails closed (exit code 3) on filename collisions unless `--overwrite` is explicitly specified.
  - Atomic two-stage write: writes to staging temp files (`.tmp_<uuid>_<filename>`), computes cryptographic digests, and invokes atomic `os.replace`.
  - Source drift detection: blocks approved export if underlying incident records were updated after dossier assembly.
  - Append-only audit logging: records `EXPORT_DOSSIER` events in `governance_audit_logs`.
  - Pure local staging in `.data/editorial_exports/` (git-ignored); zero external network calls, zero Substack API integration, zero automated distribution.
- **Local Review CLI Subcommand (`export-dossier`)**:
  - Added `export-dossier` command to `ai_incident_monitor.editorial.cli` with options `--format`, `--profile`, `--purpose`, `--output-dir`, `--overwrite`, `--dry-run`, `--is-human`, `--non-human`, and `--json`.
  - Standardized exit codes: 0 (success), 1 (validation/input error), 2 (unexpected error), 3 (collision without overwrite), 4 (constitutional violation).
- **Unit & Integration Test Suites**:
  - `backend/tests/unit/editorial/renderers/test_markdown_renderer.py` (15 unit tests).
  - `backend/tests/unit/editorial/renderers/test_json_renderer.py` (8 unit tests).
  - `backend/tests/unit/editorial/renderers/test_exporter_and_manifest.py` (13 unit tests).
  - `backend/tests/integration/test_editorial_export_cli.py` (7 CLI integration tests).

## [Phase 6A] - 2026-10-23

### Added
- **Editorial Relational Models & Migration 006 (`006_editorial_dossiers_and_review.py`)**:
  - Implemented `EditorialDossierModel`, `EditorialDossierEntryModel`, and `EditorialDossierReviewModel` in `backend/src/ai_incident_monitor/db/models/editorial.py`.
  - Established foreign key cascades, indices, and check constraints (`is_human = true OR is_human = 1`).
  - Added Alembic migration `006_editorial_dossiers_and_review.py` (down_revision: `005`), fully verified across upgrade/downgrade cycles.
- **Editorial Domain Models & Enums (`ai_incident_monitor.editorial.models`, `enums`)**:
  - Pydantic v2 domain models: `EditorialDossierSchema`, `EditorialDossierEntrySchema`, `EditorialReviewerAttestationSchema`, `EditorialValidationReport`, `EditorialCandidate`.
  - Canonical dictionary serialization and SHA-256 content hashing (`compute_content_hash()`).
  - Immutable research disclaimer (`EDITORIAL_DISCLAIMER_VERSION = "editorial-v1"`, `EDITORIAL_DISCLAIMER_TEXT`).
- **Editorial Source Selector (`EditorialSourceSelector`)**:
  - Authoritative workflow: ordinary attributed reporting enters draft dossiers without requiring prior human source approval.
  - Decoupled from EU screens: incidents without EU screens enter drafts cleanly.
  - Unapproved or missing EU screens are cleanly omitted with internal documented reasons without blocking ordinary incident reporting.
  - Fail-closed candidate exclusion only on concrete data integrity gaps (zero evidence, malformed title/summary).
  - Explicit preservation of conflicting reporting, disputed facts, and allegations.
- **Deterministic Assembly Engine (`EditorialDossierAssembler`)**:
  - Pure programmatic assembly with zero LLM or generative inference.
  - Deterministic entry sorting (severity score descending, incident ID ascending).
  - Epistemic tri-state separation of established facts, attributed allegations, unknowns, and disputes.
- **Editorial Safety Validator (`EditorialValidator`)**:
  - Field-level validation across title, narrative sections, facts, unknowns, and disputes.
  - Prohibits unadjudicated legal guilt and statutory violation claims while respecting a narrow qualified-language allowlist.
  - Standalone disclaimer validation avoiding false positives on terms like "compliance".
- **Review State Machine & Immutability (`EditorialReviewStateMachine`)**:
  - Strict lifecycle states: `DRAFT`, `ASSEMBLED`, `PENDING_REVIEW`, `APPROVED_INFORMATIONAL`, `REJECTED`, `SUPERSEDED`.
  - Human review primacy (`Rule 14`): automated agents cannot self-approve.
  - Single human review checkpoint: one dossier-level sign-off covers the entire multi-entry version.
  - Approved content is strictly immutable. Source drift detection blocks stale approvals.
- **Transactional Repository & Cryptographic Audit Log (`EditorialRepository`)**:
  - Transactional persistence for dossiers, entries, and review attestations.
  - Sequential SHA-256 hash chaining into `governance_audit_logs`.
- **Local Review CLI (`ai_incident_monitor.editorial.cli`)**:
  - Full operational subcommands: `select-candidates`, `assemble-dossier`, `inspect-dossier`, `validate-dossier`, `submit-for-review`, `approve-dossier`, `reject-dossier`, `supersede-dossier`, `verify-audit`.
  - Supports `--json`, `--dry-run`, non-zero exit codes, and non-TTY execution.
- **Unit & Integration Test Suites**:
  - `test_editorial_models.py`: schemas, canonical hashing, attestation validation.
  - `test_source_selector.py`: source selection policies, EU omission, disputed facts.
  - `test_dossier_assembly.py`: deterministic ordering, repeatable hashing, aggregations.
  - `test_editorial_validator.py`: safety linter, disclaimer verification, allowlist.
  - `test_editorial_review_and_repo.py`: review state transitions, immutability, source drift, audit logs.
  - `test_editorial_cli.py`: end-to-end CLI workflow, dry runs, json output.
  - `test_migrations.py`: 006 migration upgrade, foreign keys, selective downgrade.

## [Phase 5 Increment 2C-3B] - 2026-10-23

### Added
- **EU AI Act Output Safety Linter (`ai_incident_monitor.governance.eu_output_linter.EUOutputLinter`)**:
  - Implemented offline, deterministic regex- and token-based output linter inspecting all structured string and narrative fields across screen models and dictionaries.
  - Prohibited term detection across 11 pattern families: *violation*, *breach*, *illegal*, *unlawful*, *compliant*, *noncompliant*, *compliance failure*, *statutory/legal duty*, *must report*, *reportable*, *legally high-risk*, *prohibited practice*, *EU AI Act applies*, *obligation applies*, and *legal liability*.
  - Bypass resistance: normalizes case folding, underscores, hyphens, and whitespace padding (`non - compliant`, `high - risk  ai  system`).
  - Narrow qualified allowlist: preserves authorized informational clauses without false positives (`"finding of compliance or noncompliance"`, `"alleged violation"`, `"reported breach"`, `"potential high-risk area"`, `"conceptual relevance to Article 5"`, `"serious incident reporting relevance"`).
  - Emits structured finding reports (`EULinterReport`) with controlled result vocabulary (`EULinterResult`: `PASS`, `BLOCKED_PROHIBITED_TERM`, `BLOCKED_MISSING_DISCLAIMER`, `BLOCKED_UNAPPROVED_STATUS`, `BLOCKED_MISSING_EVIDENCE`, `BLOCKED_INVALID_REFERENCE`, `BLOCKED_STALE_REFERENCE_SET`, `BLOCKED_OUTPUT_SCHEMA_ERROR`).
- **Human Reviewer Attestation Schema (`ai_incident_monitor.governance.models.EUReviewerAttestationSchema`)**:
  - Structured, immutable attestation schema enforcing `is_human=True`, confirmed statement, evidence verification, and linter clearance.
  - Enforces Constitutional Rules 12 & 13: automated algorithms and models cannot self-approve or self-attest.
- **Seven-Gate Fail-Closed Output Eligibility (`verify_output_eligibility`)**:
  - Enforces fail-closed evaluation across 7 preconditions: Approved informational status, exact immutable disclaimer v2 (`2024-1689-v2`), minimum 1 primary evidence link, authenticated human reviewer identity and timestamp, valid reviewer attestation with `is_human=True`, active non-stale reference set, and clean output linter report.
- **Append-Only Cryptographic Audit Extensions**:
  - Added `LINTER_EXECUTION` and `OUTPUT_ELIGIBILITY_CHECK` to `GovernanceAuditEventType`.
  - Added `record_linter_audit_event` and `record_output_eligibility_audit_event` in `GovernanceRepository` with SHA-256 state digests and previous-event-hash linkage.
- **Unit Test Suites**:
  - `backend/tests/unit/governance/test_eu_output_linter.py`: 71 comprehensive unit tests verifying clean text, prohibited term detection, casing, punctuation/whitespace bypass resistance, allowlist preservation, and screen traversal.
  - `backend/tests/unit/governance/test_eu_output_eligibility.py`: 25 unit tests isolating all 7 fail-closed gates, reviewer attestation checks, repository transition safeguards, and audit hash chaining.

## [Phase 5 Increment 2C-3A] - 2026-10-23

### Added
- **EU AI Act Conceptual Relevance Engine (`ai_incident_monitor.governance.eu_screen.EURelevanceScreeningEngine`)**:
  - Implemented deterministic, offline, inspectable screening engine orchestrating fact evaluators (`evaluate_eu_fact_context`) and conceptual relevance evaluators (`evaluate_eu_conceptual_context`).
  - Evaluates incident facts against 28 specific conceptual rules mapped to canonical controls in `frameworks/eu-ai-act/eu-ai-act-2024-1689.yaml`.
  - Automatic parent control linkage for `EU-ART-5` (prohibited practices parent), `EU-ART-6` (Annex III parent), and `EU-ART-50` (transparency parent).
  - Safety Rule 2 enforcement: raises `ConstitutionalViolationError` if any rule references an unvalidated or inactive external identifier.
  - Epistemic modesty & Safety Rule 1: zero evidence records unconditionally produce zero affirmative conceptual findings.
  - Orthogonal confidence calculation decoupled from AIG-ISI severity and OECD/NIST confidence.
  - Mandatory `PENDING_REVIEW` routing: all affirmative screens unconditionally enter `PENDING_REVIEW`.
- **Deterministic Conceptual Relevance Rules (`ai_incident_monitor.governance.rules.eu_conceptual_relevance_rules`)**:
  - **Rule Family D1 (Article 5 Prohibited Concepts)**:
    - `RULE-EU-CONC-PROHIB-01` (`EU-ART-5.1.a`): Subliminal and manipulative techniques.
    - `RULE-EU-CONC-PROHIB-02` (`EU-ART-5.1.b`): Vulnerability exploitation.
    - `RULE-EU-CONC-PROHIB-03` (`EU-ART-5.1.c`): Social scoring.
    - `RULE-EU-CONC-PROHIB-04` (`EU-ART-5.1.d`): Predictive policing profiling.
    - `RULE-EU-CONC-PROHIB-05` (`EU-ART-5.1.e`): Untargeted facial image scraping.
    - `RULE-EU-CONC-PROHIB-06` (`EU-ART-5.1.f`): Emotion recognition in workplace and education.
    - `RULE-EU-CONC-PROHIB-07` (`EU-ART-5.1.g`): Sensitive biometric categorization.
    - `RULE-EU-CONC-PROHIB-08` (`EU-ART-5.1.h`): Real-time remote biometric identification in public spaces.
  - **Rule Family D2 (Annex III Regulated Operational Domain Concepts)**:
    - `RULE-EU-CONC-ANNEX3-01` (`EU-ANNEX-III.1`): Biometrics in permitted contexts.
    - `RULE-EU-CONC-ANNEX3-02` (`EU-ANNEX-III.2`): Critical infrastructure safety components.
    - `RULE-EU-CONC-ANNEX3-03` (`EU-ANNEX-III.3`): Education and vocational training.
    - `RULE-EU-CONC-ANNEX3-04` (`EU-ANNEX-III.4`): Employment and worker management.
    - `RULE-EU-CONC-ANNEX3-05` (`EU-ANNEX-III.5`): Essential public and private services.
    - `RULE-EU-CONC-ANNEX3-06` (`EU-ANNEX-III.6`): Law enforcement.
    - `RULE-EU-CONC-ANNEX3-07` (`EU-ANNEX-III.7`): Migration, asylum, and border control.
    - `RULE-EU-CONC-ANNEX3-08` (`EU-ANNEX-III.8`): Administration of justice and democratic processes.
  - **Rule Family D3 (Article 50 Transparency Concepts)**:
    - `RULE-EU-CONC-TRANSP-01` (`EU-ART-50.1`): AI interaction notification.
    - `RULE-EU-CONC-TRANSP-02` (`EU-ART-50.2`): Synthetic media and deepfakes.
    - `RULE-EU-CONC-TRANSP-04` (`EU-ART-50.4`): AI-generated public informational text.
  - **Rule Family D4 (General-Purpose AI Concepts)**:
    - `RULE-EU-CONC-GPAI-01` (`EU-ART-51`): High-compute models with systemic risk.
    - `RULE-EU-CONC-GPAI-02` (`EU-ART-53`): GPAI provider documentation obligations.
  - **Rule Family D5 (Operational Control Concepts)**:
    - `RULE-EU-CONC-OPS-DATA` (`EU-ART-10`): Data and data governance.
    - `RULE-EU-CONC-OPS-LOGS` (`EU-ART-12`): Record-keeping and technical logging.
    - `RULE-EU-CONC-OPS-OVERSIGHT` (`EU-ART-14`): Human oversight.
    - `RULE-EU-CONC-OPS-ROBUST` (`EU-ART-15`): Accuracy, robustness, and cybersecurity.
    - `RULE-EU-CONC-OPS-PMM` (`EU-ART-72`): Post-market monitoring by providers.
    - `RULE-EU-CONC-OPS-REPORTING` (`EU-ART-73`): Reporting of serious incidents.
  - **Rule Family D6 (Serious Incident Thresholds)**:
    - `RULE-EU-CONC-SERIOUS-01` (`EU-ART-3.49`): Serious incident harm thresholds.
- **Controlled Vocabularies & Domain Schemas**:
  - `EUConceptualRelevanceLevel`, `EUConceptType`, `EUEvidenceStrength` in `ai_incident_monitor.governance.enums`.
  - `EUConceptualFinding` and `EUConceptualEvaluationResult` in `ai_incident_monitor.governance.models` with strict non-legal language validation.
- **Testing & Verification**:
  - 40 new unit tests in `backend/tests/unit/governance/test_eu_conceptual_rules.py`.
  - Total test suite: **556 / 556 passed tests** in ~6.1s (0 failures, 0 regressions).
  - Provenance chain verified via `make verify-provenance-chain` (`is_valid: true`, 0 anomalies).
- **Documentation**:
  - Section 7 added to `docs/GOVERNANCE_MAPPING_METHODOLOGY.md`.
  - `docs/REQUIREMENTS_TRACEABILITY.md`, `docs/PROJECT_STATUS.md`, and `docs/NEXT_SESSION.md` updated.

### Hard Boundaries Enforced in Phase 5 Increment 2C-3A
- Phase 5 Increment 2C-3B remains explicitly deferred:
  - Zero output linter (`eu_output_linter.py`) code.
  - Final external-use output eligibility enforcement deferred.
  - Reviewer attestation validation beyond existing 2C-1 mechanics deferred.
- Zero LLMs, generative models, web scrapers, or network dependencies.
- Zero statutory or judicial determinations (`Safety Rule 7`, `LGL-001`).

## [Phase 5 Increment 2C-2] - 2026-10-22

### Added
- **Core Deterministic Fact Evaluators (`ai_incident_monitor.governance.rules.eu_fact_rules`)**:
  - Implemented offline, inspectable, deterministic rule families evaluating core factual predicates under Regulation (EU) 2024/1689:
    - **Rule Family A (Territorial & Market Nexus — Article 2)**:
      - `RULE-EU-NEXUS-01` (`EUEstablishmentNexusRule`): Provider or deployer establishment in an EU Member State (`COND-NEXUS-ESTABLISHMENT` -> `POSSIBLE_EU_NEXUS`).
      - `RULE-EU-NEXUS-02` (`EUMarketPlacementNexusRule`): Commercial availability, distribution, placing on the market, or putting into service in EU territory (`COND-NEXUS-MARKET-PLACEMENT` -> `POSSIBLE_EU_NEXUS`).
      - `RULE-EU-NEXUS-03` (`EUOutputUsedNexusRule`): Third-country AI system outputs utilized in Union or affecting natural persons located in the EU (`COND-NEXUS-OUTPUT-USED-IN-EU` -> `POSSIBLE_EU_NEXUS`).
      - `RULE-EU-NEXUS-04` (`EUNexusAbsenceInsufficiencyRule`): Absence of nexus, foreign deployment, or insufficient information (`OUTSIDE_APPARENT_TERRITORIAL_SCOPE`, `NO_EU_NEXUS_EVIDENCE`, `INSUFFICIENT_NEXUS_INFORMATION`).
    - **Rule Family B (AI-System Technical Context — Article 3(1))**:
      - `RULE-EU-AISYS-01` (`EUAISystemMeetsDefinitionRule`): Machine-based inferencing, adaptiveness, and autonomy generating outputs influencing physical/virtual environments (`COND-AISYS-AUTONOMOUS-INFERENCE` -> `MEETS_DEFINITION`).
      - `RULE-EU-AISYS-02` (`EUAISystemBorderlineRule`): Complex statistical scoring, heuristic expert systems, or ambiguous autonomy (`COND-AISYS-BORDERLINE-AUTONOMY` -> `BORDERLINE_OR_UNCLEAR`).
      - `RULE-EU-AISYS-03` (`EUAISystemOutsideDefinitionRule`): Classical deterministic scripts, static databases, traditional software lacking machine inference (`COND-AISYS-CLASSICAL-SOFTWARE` -> `OUTSIDE_DEFINITION`).
    - **Rule Family C (Actor Role Context — Article 3(2)–(8))**:
      - `RULE-EU-ROLE-01` (`EUActorRoleProviderRule`): Entity developed, trained, branded, or placed AI system on market under own name/trademark (`PROVIDER`).
      - `RULE-EU-ROLE-02` (`EUActorRoleDeployerRule`): Entity utilizing AI system under own authority in operational/professional context (`DEPLOYER`).
      - `RULE-EU-ROLE-03` (`EUActorRoleImporterDistributorRule`): Supply chain intermediaries (`IMPORTER`, `DISTRIBUTOR`).
      - `RULE-EU-ROLE-04` (`EUActorRoleGPAIProviderRule`): Upstream general-purpose AI model development/provision (`GPAI_MODEL_PROVIDER`).
      - Deterministic role confidence resolution: `IDENTIFIED_FROM_EVIDENCE`, `POSSIBLE_FROM_EVIDENCE`, `DISPUTED`, or `UNKNOWN`.
    - **Temporal Alignment Evaluator**:
      - `RULE-EU-TEMPORAL-01` (`EUTemporalAlignmentRule`): Compares incident occurrence date against statutory reference metadata effective dates (`REFERENCE_METADATA_ALIGNS`, `TEMPORAL_CONTEXT_REQUIRES_REVIEW`, `EFFECTIVE_DATE_UNCERTAIN`, `INCIDENT_DATE_UNKNOWN`, `NOT_ASSESSED`).
    - **Rule Family E (Missing Facts & Non-Leading Follow-Up Questions)**:
      - `RULE-EU-QUESTIONS-01` (`EUMissingFactsQuestionsRule`): Systematically identifies factual voids across nexus, technical autonomy, actor roles, and timeline, generating neutral inquiries for human governance investigators.
  - **Screening Context Evaluator (`evaluate_eu_fact_context`)**:
    - Central deterministic coordinator executing all 5 rule families and producing `EUFactEvaluationResult`.
    - Emits fine-grained rule evaluation traces (`EUScreenRuleTraceSchema`) for relational persistence in `eu_screen_rule_traces`.
    - Provides `.to_screen_dict()` and `.to_screen_schema()` helpers for seamless integration with repository and schema models.
  - **Extended `IncidentFactContext`**: Added optional typed `incident_date: Optional[date] = None` supporting temporal evaluations.
- **Testing & Quality Assurance**:
  - 32 new unit tests added in `backend/tests/unit/governance/test_eu_fact_evaluators.py`.
  - Full test suite: **516 / 516 passed tests** in ~5.8s with zero failures, zero warnings, and zero regressions.
  - Full cryptographic provenance chain verified via `make verify-provenance-chain` (`is_valid: true`, 0 anomalies).
- **Architecture & Traceability Documentation**:
  - Ratified ADR-018 (`EU AI Act Core Deterministic Fact Evaluators & Epistemic Void Inquiries`) in `docs/DECISIONS.md`.
  - Updated `docs/GOVERNANCE_MAPPING_METHODOLOGY.md` documenting Section 6 (EU AI Act Fact Evaluators).
  - Updated `docs/REQUIREMENTS_TRACEABILITY.md`, `docs/PROJECT_STATUS.md`, and `docs/NEXT_SESSION.md`.

### Hard Boundaries Enforced in Phase 5 Increment 2C-2
- Phase 5 Increment 2C-3 explicitly deferred and not started:
  - Zero Article 5 (prohibited practices), Annex III (high-risk), Article 50 (transparency), Articles 51–53 (GPAI systemic risk), or operational Articles (10, 12, 14, 15, 72, 73) conceptual relevance rules implemented.
  - `eu_output_linter.py` deferred to 2C-3.
- Zero generative LLMs, Gemini, embeddings, or heuristic guesswork.
- Zero live network retrieval, scraping, or external reference refreshes.
- Zero UI/API endpoints, dashboard exposure, or public publishing components.
- Zero legal determinations, compliance conclusions, statutory applicability findings, or violation language (`Safety Rule 7`, `LGL-001`).

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
