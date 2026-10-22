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

---

### ADR-010: Cryptographic Provenance Manifests and Sequential Hash-Chaining
* **Date**: 2026-10-20
* **Status**: RATIFIED
* **Deciders**: AI Guardians LLC Leadership, Antigravity AI
* **Context**: Ingestion runs require auditability and tamper evidence to prove that incident records, fair-use snippets, and diagnostic outcomes have not been secretly modified after ingestion.
* **Decision**:
  1. Implement `IngestionManifest` capturing 28 typed provenance attributes per ingestion run.
  2. Use deterministic canonical JSON serialization (UTF-8, `sort_keys=True`, `separators=(',', ':')`, `ensure_ascii=False`) prior to computing the `manifest_sha256` digest.
  3. Link manifests sequentially via `previous_manifest_sha256` within a designated `chain_scope` (default: `global_environment_default`). Genesis manifests have `previous_manifest_sha256 = None`.
  4. Disallow self-links and forked chains.
  5. Corrections or reprocessing append a new `SUPERSEDED` or `CORRECTION` manifest, preserving the historical trail.
  6. Provide `verify_provenance_chain` CLI tool with diagnostic-only default mode and zero silent repair.
  7. Formally document that this is an application-level audit chain, not a blockchain or non-repudiation ledger; privileged DBAs could rewrite history without external anchoring.
* **Consequences**:
  - Tamper-evident integrity across all ingestion runs.
  - Clean separation of chain scopes across environments.
  - Fully auditable lineage from source URL to normalized record ID.

---

### ADR-011: Untrusted Content Envelope and Prompt Injection Isolation Boundary
* **Date**: 2026-10-20
* **Status**: RATIFIED
* **Deciders**: AI Guardians LLC Leadership, Antigravity AI
* **Context**: All external web and feed content contains untrusted data that could attempt indirect prompt injection, script execution, or formula injection.
* **Decision**:
  1. Wrap all external parsed text in a typed `UntrustedSourceContentEnvelope` marked with `trust_level="UNTRUSTED_EXTERNAL"`.
  2. The prompt serialization marker `<untrusted_source_content>` is an envelope for formatting and provenance only; internal XML entities and closing tags are strictly escaped to prevent delimiter breakout.
  3. Enforce deterministic text normalization: HTML stripping, Unicode NFKC, removal of BiDi overrides and zero-width spaces, and CWE-1236 formula neutralization.
  4. Deploy `detect_prompt_injection_signals` to triage active imperative override directives from objective reporting on prompt injection incidents, quarantining high-risk records.
  5. Prohibit external source content from altering system prompts, tool definitions, permissions, connector policies, severity scores, publication state, or execution destinations.
  6. Require explicit human-in-the-loop sign-off before any quarantined content can be evaluated by future LLM components.
* **Consequences**:
  - Full mitigation of indirect prompt injection delimiter escapes.
  - Zero possibility of external content executing tools or overriding instructions.
  - Robust display and export safety across spreadsheets, logs, and UI components.

---

### ADR-012: Deterministic AIG-ISI Multi-Dimensional Scoring Engine Architecture
* **Date**: 2026-10-20
* **Status**: RATIFIED
* **Deciders**: AI Guardians LLC Leadership, Antigravity AI
* **Context**: Scoring incident severity via unstructured LLM generation yields non-deterministic, drifting metrics that obscure evidentiary justification, monetize human life, and conflate actual materialized harm with counterfactual potential.
* **Decision**:
  1. Codify AIG-ISI v1.0.0 as a deterministic multi-dimensional scoring engine across eight approved dimensions totaling 100 weight: Human Impact (25), Financial and Property (15), Trust and Reputation (15), Privacy and Confidentiality (15), Rights and Fairness (10), Operational and Critical-Service (10), Scale and Reach (5), Societal and Environmental (5).
  2. Separate Actual Impact Severity from Potential Impact Severity into independent assessment records.
  3. Dimension scores are discrete integers $0..5$ or explicit `null` (`UNKNOWN`). `UNKNOWN` is never coerced to zero.
  4. Implement exact mathematical formulations for lower evidence bound, upper uncertainty bound, completeness, and provisional normalized score.
  5. Codify five core severity tiers (Minimal 0–19, Moderate 20–39, Significant 40–59, Severe 60–79, Critical 80–100) and three special status tiers (Unscored, Disputed, Superseded).
  6. Confidence levels (HIGH, MEDIUM, LOW, INSUFFICIENT) remain strictly orthogonal to severity.
* **Consequences**:
  - Mathematical repeatability across all environments.
  - Transparent factor-by-factor evidentiary rationales.
  - Zero monetization of human life or dignity.

---

### ADR-013: Orthogonal Governance Mappings and Jurisdictional Isolation
* **Date**: 2026-10-20
* **Status**: RATIFIED
* **Deciders**: AI Guardians LLC Leadership, Antigravity AI
* **Context**: AI governance frameworks (OECD, NIST AI RMF, EU AI Act) serve fundamentally different legal and policy roles. Public trackers conflate voluntary ethical guidelines with enforceable statutory obligations.
* **Decision**:
  1. Preserved as orthogonal metadata layers that do not feed into or alter AIG-ISI severity scores (`Rule 8`, `GOV-005`).
  2. Differentiate between statutory jurisdictional applicability and conceptual relevance (`Rule 10`, `GOV-004`).
  3. Strictly ban unadjudicated claims of statutory violations without an authoritative judicial or regulatory docket citation (`Rule 11`, `LGL-001`).
* **Consequences**:
  - Clear separation of technical safety severity from regulatory compliance.
  - Zero legal exposure from unwarranted statutory violation claims.

---

### ADR-014: Human-in-the-Loop Review State Machine & High-Severity Gatekeeper
* **Date**: 2026-10-20
* **Status**: RATIFIED
* **Deciders**: AI Guardians LLC Leadership, Antigravity AI
* **Context**: Constitutional Rules 12 and 13 strictly ban automated models from approving their own outputs or authorizing publication. High-severity assessments require enhanced scrutiny.
* **Decision**:
  1. Enforce five lifecycle review states: `DRAFT`, `PENDING_REVIEW`, `APPROVED`, `REJECTED`, `SUPERSEDED`.
  2. Implement 10 automated review gates routing assessments to mandatory human sign-off (`TIER_4_OR_5`, `LOW_CONFIDENCE`, `LOW_COMPLETENESS`, `ACTUAL_VS_POTENTIAL_DIVERGENCE`, `OVERRIDE_PRESENT`, `SERIOUS_INJURY_OR_DEATH`, `CRITICAL_INFRASTRUCTURE`, `SERIOUS_PRIVACY_IMPACT`, `SERIOUS_RIGHTS_IMPACT`, `MATERIALLY_DISPUTED_FACTS`).
  3. Support explicit, auditable manual overrides with mandatory justification and reviewer ID. Overrides cannot be silent and permanently require human approval.
* **Consequences**:
  - Strict human primacy in the loop (`is_human=True`).
  - Total prevention of autonomous self-publishing.

---

### ADR-015: Append-Only Assessment Versioning and Golden Calibration Suite
* **Date**: 2026-10-20
* **Status**: RATIFIED
* **Deciders**: AI Guardians LLC Leadership, Antigravity AI
* **Context**: Assessment methodology evolutions or new factual disclosures must not silently overwrite historical assessments.
* **Decision**:
  1. Assessment records are strictly immutable (`frozen=True`) with explicit version headers (`AIG-ISI-1.0.0`).
  2. Re-scoring an incident creates an append-only new record referencing `supersedes_assessment_id`.
  3. Maintain a golden calibration benchmark suite of synthetic incidents spanning all tiers and gate conditions to verify engine stability.
* **Consequences**:
  - Full auditability and historical reconstruction.
  - Zero regression risk across methodology updates.

---

### ADR-016: Deterministic OECD and NIST AI RMF Governance Mapping Engine
* **Date**: 2026-10-21
* **Status**: RATIFIED
* **Deciders**: AI Guardians LLC Leadership, Antigravity AI
* **Context**: Governance mappings must be deterministic, reproducible, evidence-grounded, and strictly orthogonal to AIG-ISI severity scoring. Heuristics or LLM inference risk hallucinated control associations, unverified compliance claims, and legal liability.
* **Decision**:
  1. **Strict Reference Grounding**: The engine maps only against validated, versioned reference sets registered in `frameworks/manifest.json` (OECD AI Principles 2024, NIST AI RMF 1.0). Target identifiers outside the active reference library raise `ConstitutionalViolationError` (`Safety Rule 2`).
  2. **Evidence-First Mandate**: Every mapping candidate must link to one or more verified incident evidence IDs; zero evidence produces zero mappings (`Safety Rule 1`).
  3. **Strict NIST Hierarchy & Specificity Gate**: NIST mappings follow Function -> Category -> Subcategory. Subcategories require `HIGHLY_SPECIFIC` primary evidence and validated parent category/function references (`Safety Rule 2`).
  4. **Multi-Factor Confidence & Review State Machine**: Independent confidence scoring (directness, corroboration, specificity, minus penalties for unknowns and disputed facts) routes candidates to `PENDING_REVIEW` upon triggering gates for sensitive domains, disputed facts, low confidence, or subcategory granularity. Automated algorithms cannot approve mappings (`Rule 12/13`).
  5. **Non-Legal Terminology**: Mapping rationales, facts, and follow-ups programmatically forbid legal conclusion language (`violation`, `breach`, `illegal`, `unlawful`, `compliant`, `noncompliant`, `statutory duty`) (`Safety Rule 7`, `LGL-001`).
  6. **Relational Provenance (Migration 004)**: Add `rule_id` and `rule_version` columns to `incident_framework_mappings`. Approved records are strictly immutable; edits create append-only superseding records with cryptographic audit chaining.
* **Consequences**:
  - 100% deterministic, audit-traceable governance mappings.
  - Total elimination of LLM hallucination and legal conclusion exposure.
  - Complete decoupling from AIG-ISI technical incident severity (`GOV-005`).

---

### ADR-017: EU AI Act Informational Relevance Screen Foundation & Output Eligibility Guard
* **Date**: 2026-10-22
* **Status**: RATIFIED
* **Deciders**: AI Guardians LLC Leadership, Antigravity AI
* **Context**: Screening incident records against Regulation (EU) 2024/1689 (EU AI Act) concepts requires strict non-judicial boundaries, explicit distinction between statutory applicability and non-binding informational relevance (`LGL-001`, `LGL-002`, `LGL-003`), mandatory immutable disclaimer versioning, human-in-the-loop review gating, fine-grained rule provenance, and an output-eligibility guard that unconditionally blocks unapproved, unverified, or ungrounded screens from external release.
* **Decision**:
  1. **Relational Schema Foundation (Migration 005)**: Extend `eu_legal_relevance_screens` with 16 epistemic and audit columns (`screen_version`, `status`, `relevance_level`, `nexus_assessment`, `ai_system_context`, `actor_role_confidence`, `conceptual_risk_areas`, `potentially_relevant_reference_ids`, `operational_relevance_areas`, `timing_assessment`, `known_facts`, `unknowns`, `disputed_facts`, `follow_up_questions`, `rationale`, `disclaimer_version`, `metadata_json`) and create table `eu_screen_rule_traces` for rule evaluation provenance.
  2. **Non-Judicial Controlled Vocabularies**: Implement strictly non-legal enumerations (`EURelevanceLevel`, `EUScreenStatus`, `EUNexusAssessment`, `EUActorRoleConfidence`, `EUTimingAssessment`, `EUSeriousIncidentRelevance`). Prohibit legal conclusion terminology (`violation`, `breach`, `illegal`, `statutory duty`) in schemas and models (`Safety Rule 7`, `LGL-001`).
  3. **Mandatory Versioned Disclaimer**: Enforce disclaimer version `"2024-1689-v2"` with exact approved text. Any disclaimer tampering or mismatch raises `ValueError` on validation.
  4. **State Machine & Human Review Primacy**: Enforce review states (`DRAFT`, `CANDIDATE`, `PENDING_REVIEW`, `APPROVED_INFORMATIONAL`, `REJECTED`, `SUPERSEDED`). Setting `APPROVED_INFORMATIONAL` strictly requires authenticated human reviewer identity (`is_human=True`); automated algorithms/LLMs cannot approve themselves (`Rule 12/13`). In-place mutation of approved screens raises `ImmutabilityViolationError`; edits must create append-only superseding records.
  5. **Output-Eligibility Guard**: Implement `verify_output_eligibility` blocking external release or reporting unless a screen is in `APPROVED_INFORMATIONAL` status, contains the exact versioned disclaimer, has at least one primary evidence link, and has authenticated human review.
* **Consequences**:
  - Epistemically unassailable and legally hedged foundation for EU AI Act governance screening.
  - Zero risk of unreviewed, automated, or ungrounded legal assertions escaping to external reports.
  - Clean separation of foundation (2C-1) from deterministic rule evaluators (2C-2) and conceptual scoping/linter (2C-3).

---

### ADR-018: EU AI Act Core Deterministic Fact Evaluators & Epistemic Void Inquiries
* **Date**: 2026-10-22
* **Status**: RATIFIED
* **Deciders**: AI Guardians LLC Leadership, Antigravity AI
* **Context**: Following foundation delivery in Phase 5 Increment 2C-1, informational screening requires inspectable, deterministic, offline evaluators to analyze core factual predicates under Regulation (EU) 2024/1689: territorial nexus (Art. 2), AI system technical characteristics (Art. 3(1)), operator role attribution (Art. 3(2)–(8)), timeline alignment against statutory effective dates, and systematic identification of factual voids. All evaluations must strictly preserve epistemic modesty, generate non-leading follow-up questions, and remain entirely free of legal or compliance conclusion language (`Safety Rule 7`, `LGL-001`, `Constitutional Rule 10`).
* **Decision**:
  1. **Rule Family A (Territorial & Market Nexus — Art. 2)**:
     Implement deterministic rules (`RULE-EU-NEXUS-01`..`04`) identifying positive establishment in an EU Member State, placing on the market or putting into service in the EU, or third-country outputs utilized in the Union (`POSSIBLE_EU_NEXUS`), while explicitly distinguishing positive evidence of exclusively foreign deployment (`OUTSIDE_APPARENT_TERRITORIAL_SCOPE`), absence of EU evidence (`NO_EU_NEXUS_EVIDENCE`), and factual voids (`INSUFFICIENT_NEXUS_INFORMATION`).
  2. **Rule Family B (AI-System Context — Art. 3(1))**:
     Implement deterministic rules (`RULE-EU-AISYS-01`..`03`) evaluating machine-based inferencing and varying autonomy (`MEETS_DEFINITION`), identifying complex statistical or heuristic architectures with ambiguous autonomy (`BORDERLINE_OR_UNCLEAR`), and classifying classical procedural scripts or static databases lacking inferencing as outside scope (`OUTSIDE_DEFINITION`).
  3. **Rule Family C (Actor Role Context — Art. 3(2)–(8))**:
     Implement deterministic operator attribution rules (`RULE-EU-ROLE-01`..`04`) for `PROVIDER`, `DEPLOYER`, `IMPORTER`, `DISTRIBUTOR`, and `GPAI_MODEL_PROVIDER`. Enforce an orthogonal epistemic confidence model: `IDENTIFIED_FROM_EVIDENCE` (corroborated primary records), `POSSIBLE_FROM_EVIDENCE` (single source), `DISPUTED` (contested roles in evidence or tags), or `UNKNOWN`.
  4. **Temporal Alignment Evaluator**:
     Implement `RULE-EU-TEMPORAL-01` comparing incident occurrence date against statutory effective dates recorded in reference metadata (`2026-08-02`, `2025-02-02`, etc.). Explicitly emit `TEMPORAL_CONTEXT_REQUIRES_REVIEW` if an incident predates statutory application, preventing retroactive distortion.
  5. **Rule Family E (Missing Facts & Non-Leading Questions)**:
     Implement `RULE-EU-QUESTIONS-01` analyzing evaluated factual gaps and generating neutral, non-leading inquiries and missing fact statements across nexus, autonomy, operator relationships, and timeline.
  6. **Deterministic Rule Provenance Tracing**:
     Every evaluation emits fine-grained `EUScreenRuleTraceSchema` records capturing `rule_id`, `rule_version`, `reference_set_id`, and `matched_condition_ids` for relational persistence in `eu_screen_rule_traces`.
  7. **Strict Non-Judicial Phrasing**:
     Every generated observation, question, missing fact statement, and composite rationale is programmatically validated against `validate_no_legal_language`, ensuring zero presence of prohibited terms (`violation`, `breach`, `illegal`, `unlawful`, `compliant`, `noncompliant`, `statutory duty`).
* **Consequences**:
  - Purely deterministic, inspectable, reproducible factual screening decoupled from generative LLMs.
  - Transparent epistemic void tracking and neutral investigator inquiry generation.
  - Complete compliance with Safety Rule 7 and Constitutional Rules 10 & 11.
  - Strict preservation of the boundary separating 2C-2 (core fact evaluators) from 2C-3 (conceptual scoping, Article 5, Annex III, GPAI obligations, and output linter).
