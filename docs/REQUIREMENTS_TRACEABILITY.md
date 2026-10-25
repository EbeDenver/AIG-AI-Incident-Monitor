# REQUIREMENTS TRACEABILITY MATRIX: AI Incident Monitor
**Organization:** AI Guardians LLC  
**Document Identifier:** RTM-001  
**Version:** 1.0.0  
**Effective Date:** 2026-10-07  
**Governing Charter:** [Project Constitution](PROJECT_CONSTITUTION.md)  
**Parent Specification:** [Product Requirements Document](PRODUCT_REQUIREMENTS.md)  

---

## 1. Traceability Methodology & Schema

The **Requirements Traceability Matrix (RTM)** is the master registry linking business and safety mandates to technical requirements, governing constitutional rules, implementation phases, verification methods, and operational statuses.

### Standardized 9-Field Schema
Every requirement entry strictly complies with the following schema:
1. **Requirement ID**: Unique, immutable identifier composed of the 3-letter domain prefix and a 3-digit sequence (e.g., `SEV-001`).
2. **Requirement Statement**: Formal normative specification using `shall` or `must`.
3. **Source**: Originating charter principle, founder directive, regulatory framework, or security standard.
4. **Priority**: `P0 (Critical)`, `P1 (High)`, or `P2 (Medium)`.
5. **Governing Document**: Link to the specific document and section defining the constraint.
6. **Planned Phase**: Targeted implementation milestone (`Phase 1` through `Phase 6`).
7. **Verification Method**: Method used to validate compliance (`Automated Unit Test`, `Property-Based Test`, `Golden Fixture Test`, `Static Analysis`, `Manual Audit`).
8. **Status**: `PLANNED`, `IN_PROGRESS`, or `VERIFIED`.
9. **Notes / Unresolved Questions**: Caveats, dependencies, edge cases, or open design decisions.

---

## 2. Requirement Index by Taxonomy Category

| Prefix | Domain | Total Req Count | P0 Count | P1 Count |
| :---: | :--- | :---: | :---: | :---: |
| **`SRC`** | Source Ingestion and Connectors | 5 | 3 | 2 |
| **`EVD`** | Evidence, Claims, and Citations | 6 | 4 | 2 |
| **`SEV`** | AIG-ISI Severity Assessment | 6 | 5 | 1 |
| **`GOV`** | Governance Mappings (OECD, NIST, EU) | 5 | 3 | 2 |
| **`RCA`** | Root Cause and Contributing Factors | 4 | 2 | 2 |
| **`IND`** | Industry Classification | 3 | 1 | 2 |
| **`EDT`** | Editorial and Substack Generation | 5 | 3 | 2 |
| **`SEC`** | Security and Prompt-Injection Defense | 5 | 4 | 1 |
| **`PRI`** | Privacy and Data Governance | 4 | 3 | 1 |
| **`GIT`** | GitHub and Cross-Device Continuity | 5 | 4 | 1 |
| **`OPS`** | Scheduling, Operations, and Observability | 4 | 2 | 2 |
| **`UIX`** | Interface and Accessibility | 3 | 1 | 2 |
| **`TST`** | Testing and Quality Assurance | 5 | 4 | 1 |
| **`AUD`** | Auditability and Human Review | 5 | 5 | 0 |
| **`LGL`** | Legal-Reference Controls and Disclaimers | 4 | 3 | 1 |
| **TOTAL** | **Comprehensive System Scope** | **69** | **47** | **22** |

---

## 3. Master Traceability Tables

### 3.1 `SRC`: Source Ingestion and Connectors
Governing Document: [`docs/DATA_GOVERNANCE.md`](DATA_GOVERNANCE.md) & [`docs/SECURITY_PRINCIPLES.md`](SECURITY_PRINCIPLES.md)

| Req ID | Requirement Statement | Source | Priority | Governing Document | Planned Phase | Verification Method | Status | Notes / Unresolved Questions |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **SRC-001** | The system shall support pluggable connectors for RSS news feeds, arXiv papers, regulatory dockets, and manual incident submissions. | PRD §4.1 | P1 | [DATA_GOVERNANCE.md](DATA_GOVERNANCE.md)#3 | Phase 4 | Automated Unit Test | VERIFIED | Enforced via BaseConnector, RSSConnector, ArXivConnector, and OECDExportAdapter. |
| **SRC-002** | The system shall compute and persist a cryptographic SHA-256 digest of every ingested raw payload upon receipt. | Const. Rule 4 | P0 | [PROJECT_CONSTITUTION.md](PROJECT_CONSTITUTION.md)#rule-4 | Phase 3 | Automated Unit Test | VERIFIED | Enforced via compute_file_sha256 and raw_import_records.content_hash. |
| **SRC-003** | The system shall isolate and wrap all raw ingested source text inside structured XML delimiter blocks (`<untrusted_source>`) prior to any LLM processing. | Const. Rule 12 | P0 | [SECURITY_PRINCIPLES.md](SECURITY_PRINCIPLES.md)#2 | Phase 4 | Security Injection Test | VERIFIED | Enforced via UntrustedSourceContentEnvelope and to_xml_prompt_block entity escaping (ADR-011). |
| **SRC-004** | The system shall automatically detect and deduplicate multi-source reports covering the same primary incident. | PRD §4.1 | P1 | [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md)#4.1 | Phase 3 | Integration Test | VERIFIED | Enforced via 4-tier DeduplicationEngine and DedupCandidateModel review queue. |
| **SRC-005** | The system shall treat any undocumented public or scraped endpoint as an unstable dependency, implementing mandatory timeout and failure fallbacks. | Const. Rule 13 | P0 | [PROJECT_CONSTITUTION.md](PROJECT_CONSTITUTION.md)#rule-13 | Phase 4 | Resilience Fault Test | VERIFIED | Enforced via DEC-P4-001 (zero scraping of undocumented OECD endpoints) and BaseConnector retry/backoff policy. |

---

### 3.2 `EVD`: Evidence, Claims, and Citations
Governing Document: [`docs/EDITORIAL_PRINCIPLES.md`](EDITORIAL_PRINCIPLES.md) & [`docs/PROJECT_CONSTITUTION.md`](PROJECT_CONSTITUTION.md)

| Req ID | Requirement Statement | Source | Priority | Governing Document | Planned Phase | Verification Method | Status | Notes / Unresolved Questions |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **EVD-001** | The system shall strictly forbid fabrication of facts, sources, causal chains, financial figures, quotes, or citations. | Const. Rule 1 | P0 | [PROJECT_CONSTITUTION.md](PROJECT_CONSTITUTION.md)#rule-1 | Phase 2 | Automated Citation Validator | VERIFIED | Enforced via QuoteSpan and ClaimRecord validators. |
| **EVD-002** | The system shall maintain missing or unverified data as explicit `UNKNOWN` values and shall never coerce `UNKNOWN` to zero. | Const. Rule 2 | P0 | [DATA_GOVERNANCE.md](DATA_GOVERNANCE.md)#2 | Phase 2 | Type-System Property Test | VERIFIED | Enforced via MonetaryAmount and DateWithPrecision models. |
| **EVD-003** | The system shall categorically classify every extracted claim into: Confirmed Fact, Unverified Allegation, Technical Analysis, Uncertainty, or Opinion. | Const. Rule 3 | P0 | [EDITORIAL_PRINCIPLES.md](EDITORIAL_PRINCIPLES.md)#2 | Phase 2 | Schema Validation Test | VERIFIED | Enforced via EpistemicStatus and ClaimType enums. |
| **EVD-004** | The system shall anchor every material factual assertion to verifiable evidence containing source URI, timestamp, and quotation byte offsets. | Const. Rule 4 | P0 | [PROJECT_CONSTITUTION.md](PROJECT_CONSTITUTION.md)#rule-4 | Phase 2 | Schema Linkage Test | VERIFIED | Enforced via ClaimRecord evidence_ids validation. |
| **EVD-005** | The system shall verify that all extracted direct quotations match the ingested source text verbatim. | Const. Rule 1 | P1 | [EDITORIAL_PRINCIPLES.md](EDITORIAL_PRINCIPLES.md)#4 | Phase 2 | String Matching Unit Test | VERIFIED | Enforced via QuoteSpan character offset validation. |
| **EVD-006** | The system shall maintain orthogonal attributes for Incident Severity and Evidence Confidence. | Const. Rule 6 | P1 | [PROJECT_CONSTITUTION.md](PROJECT_CONSTITUTION.md)#rule-6 | Phase 2 | Model Schema Test | VERIFIED | Enforced via EvidenceConfidence decoupling from severity. |

---

### 3.3 `SEV`: AIG-ISI Severity Assessment
Governing Document: [`docs/PROJECT_CONSTITUTION.md`](PROJECT_CONSTITUTION.md) & [`docs/PRODUCT_REQUIREMENTS.md`](PRODUCT_REQUIREMENTS.md)

| Req ID | Requirement Statement | Source | Priority | Governing Document | Planned Phase | Verification Method | Status | Notes / Unresolved Questions |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **SEV-001** | The system shall compute AIG-ISI as a deterministic, explainable multi-dimensional score across Harm, Autonomy, Reversibility, and Scope. | Const. Rule 7 | P0 | [PROJECT_CONSTITUTION.md](PROJECT_CONSTITUTION.md)#rule-7 | Phase 5 | Determinism Property Test | VERIFIED | Enforced via AIGISIScoringEngine across 8 dimensions (ADR-012). |
| **SEV-002** | The system shall emit explicit, human-readable evidentiary rationales for each AIG-ISI dimension alongside the composite score. | Const. Rule 7 | P0 | [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md)#4.3 | Phase 5 | Output Schema Test | VERIFIED | Enforced via DimensionScore.rationale and ScoreOverride.rationale. |
| **SEV-003** | The system shall structurally isolate AIG-ISI from external regulatory classifications (OECD, NIST, EU) and media noteworthiness. | Const. Rule 8 | P0 | [DECISIONS.md](DECISIONS.md)#ADR-002 | Phase 5 | Orthogonality Unit Test | VERIFIED | Enforced by pure mathematical calculation engine decoupled from governance tags (ADR-012). |
| **SEV-004** | The system shall maintain distinct, non-overlapping fields for demonstrated Actual Harm versus counterfactual Potential Harm. | Const. Rule 5 | P0 | [PROJECT_CONSTITUTION.md](PROJECT_CONSTITUTION.md)#rule-5 | Phase 2 | Schema Validation Test | VERIFIED | Enforced via HarmType, CausalAssessment attributes, and separate actual/potential assessments. |
| **SEV-005** | The system shall strictly prohibit converting human life, physical integrity, dignity, privacy, civil rights, or public trust into financial dollars. | Const. Rule 9 | P0 | [PROJECT_CONSTITUTION.md](PROJECT_CONSTITUTION.md)#rule-9 | Phase 2 | Schema Constraint Test | VERIFIED | Enforced via MonetaryAmount economic isolation. |
| **SEV-006** | The system shall flag any assessment exceeding predefined high-severity thresholds as requiring mandatory human sign-off. | Const. Rule 15 | P1 | [EDITORIAL_PRINCIPLES.md](EDITORIAL_PRINCIPLES.md)#5 | Phase 5 | Workflow State Test | VERIFIED | Enforced via ReviewGate.TIER_4_OR_5 routing to PENDING_REVIEW (ADR-014). |

---

### 3.4 `GOV`: Governance Mappings (OECD, NIST, EU)
Governing Document: [`docs/PRODUCT_REQUIREMENTS.md`](PRODUCT_REQUIREMENTS.md) & [`docs/PROJECT_CONSTITUTION.md`](PROJECT_CONSTITUTION.md)

| Req ID | Requirement Statement | Source | Priority | Governing Document | Planned Phase | Verification Method | Status | Notes / Unresolved Questions |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **GOV-001** | The system shall map incidents against the OECD AI Principles (Inclusive Growth, Human-Centered Values, Transparency, Robustness, Accountability). | PRD §4.4 | P1 | [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md)#4.4 | Phase 5 | Classification Unit Test | VERIFIED | Enforced via GovernanceMappingEngine, ALL_OECD_RULES (Principles 1.1–1.5), and test_oecd_nist_mapping_engine.py in Phase 5 Inc 2B. |
| **GOV-002** | The system shall map incidents to the NIST AI Risk Management Framework core functions (Govern, Map, Measure, Manage). | PRD §4.4 | P1 | [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md)#4.4 | Phase 5 | Classification Unit Test | VERIFIED | Enforced via GovernanceMappingEngine, ALL_NIST_RULES (Functions, Categories, Subcategories with parent hierarchy), and test_oecd_nist_mapping_engine.py in Phase 5 Inc 2B. |
| **GOV-003** | The system shall screen incidents for EU AI Act categorization (Prohibited Practices under Art. 5, High-Risk under Annex III, GPAI transparency under Art. 53). | PRD §4.4 | P0 | [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md)#4.4 | Phase 5 | Categorization Test | VERIFIED | Delivered across Phase 5 Increments 2C-1, 2C-2, 2C-3A, and 2C-3B: Migration 005 relational schema, rule traces, review state machine, deterministic fact evaluators (Nexus Art. 2, AI system Art. 3(1), Roles Art. 3(2)–(8), Temporal alignment, missing facts), conceptual relevance screening engine with 28 canonical rules (Art. 5, Annex III, 50, 51–53, 10–15, 72–73, 3(49)), EUOutputLinter with prohibited legal-conclusion term detection and narrow allowlist, EUReviewerAttestationSchema, and 7-gate fail-closed verify_output_eligibility enforcement. Verified by 96 unit tests in test_eu_output_linter.py and test_eu_output_eligibility.py. |
| **GOV-004** | The system shall explicitly differentiate between statutory jurisdictional applicability and non-binding conceptual relevance. | Const. Rule 10 | P0 | [PROJECT_CONSTITUTION.md](PROJECT_CONSTITUTION.md)#rule-10 | Phase 5 | Schema Attribute Test | VERIFIED | Enforced via EURelevanceLevel, EUNexusAssessment, EU_AI_ACT_DISCLAIMER_V2, and verify_output_eligibility in Phase 5 Inc 2C-1. |
| **GOV-005** | The system shall preserve governance mappings as an orthogonal tag layer that does not influence AIG-ISI severity calculation. | Const. Rule 8 | P0 | [DECISIONS.md](DECISIONS.md)#ADR-002 | Phase 5 | Pipeline Isolation Test | VERIFIED | Enforced via mathematical isolation in GovernanceMappingEngine and verified by test_aig_isi_severity_score_does_not_affect_mapping in Phase 5 Inc 2B. |

---

### 3.5 `RCA`: Root Cause and Contributing Factors
Governing Document: [`docs/PRODUCT_REQUIREMENTS.md`](PRODUCT_REQUIREMENTS.md)

| Req ID | Requirement Statement | Source | Priority | Governing Document | Planned Phase | Verification Method | Status | Notes / Unresolved Questions |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **RCA-001** | The system shall categorize incident causal factors into a multi-tier taxonomy (Data, Model Architecture, Alignment/Safety, System Integration, Human Oversight, Malicious Exploitation). | PRD §4.6 | P0 | [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md)#4.6 | Phase 4 | Taxonomy Validation Test | PLANNED | Allows primary and secondary contributing causes. |
| **RCA-002** | The system shall require direct evidentiary linkage for any asserted root-cause finding. | Const. Rule 4 | P0 | [PROJECT_CONSTITUTION.md](PROJECT_CONSTITUTION.md)#rule-4 | Phase 4 | Evidence Linkage Test | PLANNED | Speculative causes must be tagged as Analysis/Uncertainty. |
| **RCA-003** | The system shall capture contributing external factors including lack of human oversight, interface confusion, or adversarial prompt injection. | PRD §4.6 | P1 | [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md)#4.6 | Phase 4 | Schema Coverage Test | PLANNED | Distinguishes intrinsic flaws from operational misuse. |
| **RCA-004** | The system shall flag when a technical root cause is unknown or unverified by technical postmortem. | Const. Rule 2 | P1 | [DATA_GOVERNANCE.md](DATA_GOVERNANCE.md)#2 | Phase 4 | Epistemic Integrity Test | PLANNED | Avoids premature blame without technical report. |

---

### 3.6 `IND`: Industry Classification
Governing Document: [`docs/PRODUCT_REQUIREMENTS.md`](PRODUCT_REQUIREMENTS.md)

| Req ID | Requirement Statement | Source | Priority | Governing Document | Planned Phase | Verification Method | Status | Notes / Unresolved Questions |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **IND-001** | The system shall tag incidents with standardized economic sector classifications aligned with NAICS/GICS categories. | PRD §4.6 | P1 | [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md)#4.6 | Phase 4 | Sector Lookup Test | PLANNED | Healthcare, Finance, Defense, Energy, Transportation, etc. |
| **IND-002** | The system shall explicitly identify and flag incidents impacting Critical Infrastructure as defined by CISA/EU NIS2 frameworks. | PRD §4.6 | P0 | [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md)#4.6 | Phase 4 | Criticality Tag Test | PLANNED | Triggers elevated monitoring alerts. |
| **IND-003** | The system shall support multi-sector impact tagging when an incident propagates across supply chains. | PRD §4.6 | P1 | [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md)#4.6 | Phase 4 | Multi-Tag Schema Test | PLANNED | Tracks cascading cross-industry harms. |

---

### 3.7 `EDT`: Editorial and Substack Generation
Governing Document: [`docs/EDITORIAL_PRINCIPLES.md`](EDITORIAL_PRINCIPLES.md)

| Req ID | Requirement Statement | Source | Priority | Governing Document | Planned Phase | Verification Method | Status | Notes / Unresolved Questions |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **EDT-001** | The system shall generate structured publication-ready drafts formatted for Substack rendering, including executive summary, evidence review, and technical analysis. | PRD §4.7 | P0 | [EDITORIAL_PRINCIPLES.md](EDITORIAL_PRINCIPLES.md)#4 | Phase 6 | Markdown Lint & Render Test | VERIFIED | Formatted Markdown & JSON renderers, presentation profiles (DEEP_DIVE_DOSSIER, EXECUTIVE_BRIEF, RAPID_ALERT), provenance manifest, and export CLI verified in Phase 6B. |
| **EDT-002** | The system shall strictly maintain an objective, forensic, dispassionate tone of voice, devoid of sensationalism, moralizing, or hyperbole. | Const. Rule 3 | P0 | [EDITORIAL_PRINCIPLES.md](EDITORIAL_PRINCIPLES.md)#1 | Phase 6 | Tone & Sentiment Linter | VERIFIED | Enforced via EditorialValidator prohibited legal/culpability patterns and dispassionate assembly. |
| **EDT-003** | The system shall automatically append mandatory legal disclaimers and methodology safe-harbor notices to all editorial outputs. | Const. Rule 10 | P0 | [EDITORIAL_PRINCIPLES.md](EDITORIAL_PRINCIPLES.md)#4 | Phase 6 | Disclaimer Presence Test | VERIFIED | Enforced via mandatory versioned disclaimer (EDITORIAL_DISCLAIMER_TEXT, 'editorial-v1') and validation guards. |
| **EDT-004** | The system shall enforce the presumption of innocence and neutral framing for all named corporate entities and individuals. | Const. Rule 3 | P1 | [EDITORIAL_PRINCIPLES.md](EDITORIAL_PRINCIPLES.md)#3 | Phase 6 | Entity Framing Audit | VERIFIED | Strict epistemic separation of allegations from facts; prohibits assertions of unadjudicated legal guilt. |
| **EDT-005** | The system shall support tiered drafting: Executive Summary (Brief), Technical Deep Dive (Full Dossier), and Rapid Alert (Flash). | PRD §4.7 | P1 | [EDITORIAL_PRINCIPLES.md](EDITORIAL_PRINCIPLES.md)#4 | Phase 6 | Template Generation Test | VERIFIED | Supported via EditorialPresentationProfile (DEEP_DIVE_DOSSIER, EXECUTIVE_BRIEF, RAPID_ALERT) and EditorialScopeType. |

---

### 3.8 `SEC`: Security and Prompt-Injection Defense
Governing Document: [`docs/SECURITY_PRINCIPLES.md`](SECURITY_PRINCIPLES.md)

| Req ID | Requirement Statement | Source | Priority | Governing Document | Planned Phase | Verification Method | Status | Notes / Unresolved Questions |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **SEC-001** | The system shall treat all ingested external content as untrusted data, preventing adversarial payload instructions from altering system execution. | Const. Rule 12 | P0 | [SECURITY_PRINCIPLES.md](SECURITY_PRINCIPLES.md)#2 | Phase 4 | Adversarial Injection Test Suite | VERIFIED | Enforced via detect_prompt_injection_signals triage, quarantine hold, and test_ingestion_e2e_pipeline.py. |
| **SEC-002** | The system shall deny LLM ingestion and analysis components any write, execution, tool-calling, or network access permissions. | Const. Rule 12 | P0 | [SECURITY_PRINCIPLES.md](SECURITY_PRINCIPLES.md)#2 | Phase 4 | Tool Sandboxing Verification | VERIFIED | Enforced via llm_contract asserting non-delegable authority and blocking privileged automated actions. |
| **SEC-003** | The system shall enforce a zero-secret policy across the Git repository, banning API keys, tokens, and credentials via automated scanning. | Const. Rule 16 | P0 | [SECURITY_PRINCIPLES.md](SECURITY_PRINCIPLES.md)#3 | Phase 1 | Git Secret Linter / Hooks | VERIFIED | Enforced via .gitignore and CI pre-commit. |
| **SEC-004** | The system shall sanitize and validate all incoming URLs against SSRF (Server-Side Request Forgery) attacks before fetching. | PRD §5 | P1 | [SECURITY_PRINCIPLES.md](SECURITY_PRINCIPLES.md)#2 | Phase 4 | SSRF Filter Unit Test | VERIFIED | Enforced via SecureHTTPClient, 21 blocked IP ranges, DNS resolution, and connection pinning (DEC-P4-003). |
| **SEC-005** | The system shall cryptographically verify integrity of all stored prompt templates and configuration files. | PRD §5 | P0 | [SECURITY_PRINCIPLES.md](SECURITY_PRINCIPLES.md)#4 | Phase 3 | Digest Verification Test | PLANNED | Detects unauthorized prompt tampering. |

---

### 3.9 `PRI`: Privacy and Data Governance
Governing Document: [`docs/DATA_GOVERNANCE.md`](DATA_GOVERNANCE.md)

| Req ID | Requirement Statement | Source | Priority | Governing Document | Planned Phase | Verification Method | Status | Notes / Unresolved Questions |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **PRI-001** | The system shall automatically detect and redact non-public Personally Identifiable Information (PII) from incident dossiers and reports. | Const. Rule 16 | P0 | [DATA_GOVERNANCE.md](DATA_GOVERNANCE.md)#4 | Phase 5 | PII Redaction Unit Test | PLANNED | Protects victims and unconsenting third parties. |
| **PRI-002** | The system shall comply with copyright fair-use boundaries by never committing raw full-text news articles to the Git repository. | Const. Rule 16 | P0 | [DATA_GOVERNANCE.md](DATA_GOVERNANCE.md)#1 | Phase 1 | Git Content Audit | VERIFIED | Only stores SHA-256, URL, and fair-use quote spans. |
| **PRI-003** | The system shall support confidential whistleblower source tagging with cryptographic pseudonymization. | PRD §4.9 | P1 | [DATA_GOVERNANCE.md](DATA_GOVERNANCE.md)#3 | Phase 3 | Pseudonymization Test | PLANNED | Protects source identities when requested. |
| **PRI-004** | The system shall generate and maintain sanitized, synthetic test fixtures for development and automated CI testing. | Const. Rule 16 | P0 | [DATA_GOVERNANCE.md](DATA_GOVERNANCE.md)#5 | Phase 2 | Fixture Hygiene Inspection | VERIFIED | 22 golden + 7 invalid synthetic fixtures with demonstration banners. |

---

### 3.10 `GIT`: GitHub and Cross-Device Continuity
Governing Document: [`AGENTS.md`](../AGENTS.md) & [`README.md`](../README.md)

| Req ID | Requirement Statement | Source | Priority | Governing Document | Planned Phase | Verification Method | Status | Notes / Unresolved Questions |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **GIT-001** | The GitHub repository shall serve as the exclusive source of truth for code, documentation, prompts, migrations, tests, and sanitized fixtures. | Const. Rule 16 | P0 | [PROJECT_CONSTITUTION.md](PROJECT_CONSTITUTION.md)#rule-16 | Phase 1 | Repository Inspection | VERIFIED | Centralized authority. |
| **GIT-002** | All scripts, tooling, and file paths shall be cross-Mac portable (macOS arm64/Darwin), containing zero hardcoded machine-specific paths. | PRD §5 | P0 | [AGENTS.md](../AGENTS.md)#3 | Phase 1 | Path Linter Check | VERIFIED | Portable across development laptops. |
| **GIT-003** | The repository shall permanently exclude mutable local databases (`*.sqlite`, `*.db`) and local raw caches via `.gitignore`. | Const. Rule 16 | P0 | [AGENTS.md](../AGENTS.md)#2 | Phase 1 | Gitignore Verification Test | VERIFIED | Prevents binary drift and dirty commits. |
| **GIT-004** | Every architectural, schema, or methodological shift shall be recorded as a versioned ADR in `docs/DECISIONS.md`. | Const. Rule 17 | P0 | [DECISIONS.md](DECISIONS.md) | Phase 1 | ADR Audit Check | VERIFIED | ADR-001 through ADR-005 ratified. |
| **GIT-005** | Every engineering session and completed phase shall update `docs/PROJECT_STATUS.md` and `docs/NEXT_SESSION.md`. | Const. Rule 17 | P1 | [AGENTS.md](../AGENTS.md)#3 | Phase 1 | Session Protocol Inspection | VERIFIED | Guarantees multi-agent handoff continuity. |

---

### 3.11 `OPS`: Scheduling, Operations, and Observability
Governing Document: [`docs/PRODUCT_REQUIREMENTS.md`](PRODUCT_REQUIREMENTS.md)

| Req ID | Requirement Statement | Source | Priority | Governing Document | Planned Phase | Verification Method | Status | Notes / Unresolved Questions |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **OPS-001** | The system shall log all pipeline operations, connector runs, and evaluation cycles with structured JSON logging. | PRD §4.10 | P1 | [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md)#4.10 | Phase 6 | Structured Log Audit | PLANNED | Enables pipeline debugging and metrics. |
| **OPS-002** | The system shall enforce rate limits and backoff policies for all external API and web scrapers to prevent IP throttling or blocks. | PRD §4.10 | P0 | [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md)#4.10 | Phase 4 | Rate Limiter Unit Test | VERIFIED | Enforced via ConnectorRateLimiter, per-connector token buckets, Retry-After honoring, and concurrency control. |
| **OPS-003** | The system shall emit automated alerts upon encountering upstream schema breakage or connector failure. | PRD §4.10 | P1 | [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md)#4.10 | Phase 6 | Alert Trigger Test | PLANNED | Notifies on-call engineer. |
| **OPS-004** | The system shall track execution latency, token consumption, and model inference costs per incident evaluation. | PRD §4.10 | P2 | [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md)#4.10 | Phase 6 | Telemetry Unit Test | PLANNED | Cost and performance monitoring. |

---

### 3.12 `UIX`: Interface and Accessibility
Governing Document: [`docs/PRODUCT_REQUIREMENTS.md`](PRODUCT_REQUIREMENTS.md)

| Req ID | Requirement Statement | Source | Priority | Governing Document | Planned Phase | Verification Method | Status | Notes / Unresolved Questions |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **UIX-001** | The system shall provide a clean, ergonomic CLI interface for managing ingestion, scoring, and editorial review. | PRD §2 | P0 | [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md)#2 | Phase 6 | CLI Usability Test | VERIFIED | Implemented via ai_incident_monitor.editorial.cli managing source selection, assembly, validation, review, and supersession. |
| **UIX-002** | The CLI shall support both human-friendly formatted terminal output (with accessible color coding) and machine-readable JSON output. | PRD §2 | P1 | [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md)#2 | Phase 6 | Output Format Test | VERIFIED | All editorial CLI subcommands support formatted human-readable terminal output and --json flag. |
| **UIX-003** | Terminal diagnostics and error messages shall provide actionable remediation instructions and constitutional rule references. | PRD §2 | P1 | [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md)#2 | Phase 5 | Error Message Inspection | PLANNED | Clear feedback on rule violations. |

---

### 3.13 `TST`: Testing and Quality Assurance
Governing Document: [`docs/PRODUCT_REQUIREMENTS.md`](PRODUCT_REQUIREMENTS.md)

| Req ID | Requirement Statement | Source | Priority | Governing Document | Planned Phase | Verification Method | Status | Notes / Unresolved Questions |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TST-001** | The system shall maintain an automated unit, integration, and property-based test suite with zero test failures allowed in `main`. | PRD §5 | P0 | [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md)#5 | Phase 2 | CI Test Runner | VERIFIED | 144 unit and integration tests pass in 3.50s with zero failures. |
| **TST-002** | The system shall maintain a deterministic golden-fixture test suite validating AIG-ISI severity scoring repeatability across model versions. | PRD §5 | P0 | [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md)#5 | Phase 5 | Golden File Regression Test | VERIFIED | Enforced via calibration_fixtures.json and test_calibration_benchmarks.py across 6 canonical archetypes. |
| **TST-003** | The system shall maintain a negative testing suite validating rejection of fabricated citations, ungrounded assertions, and unhedged legal claims. | Const. Rule 1 | P0 | [PROJECT_CONSTITUTION.md](PROJECT_CONSTITUTION.md)#rule-1 | Phase 2 | Negative Test Suite | VERIFIED | 7 negative fixtures verify rejection of invalid data. |
| **TST-004** | The system shall execute property-based tests verifying that `UNKNOWN` values are never coerced to zero under aggregation. | Const. Rule 2 | P0 | [DATA_GOVERNANCE.md](DATA_GOVERNANCE.md)#2 | Phase 2 | Hypothesis Property Test | VERIFIED | Unit and invariant tests in test_money.py and test_dates.py. |
| **TST-005** | The system shall maintain prompt regression test suites ensuring changes to prompt templates preserve extraction fidelity. | PRD §5 | P1 | [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md)#5 | Phase 3 | Prompt Regression Test | PLANNED | Detects prompt drift. |

---

### 3.14 `AUD`: Auditability and Human Review
Governing Document: [`docs/PROJECT_CONSTITUTION.md`](PROJECT_CONSTITUTION.md) & [`docs/EDITORIAL_PRINCIPLES.md`](EDITORIAL_PRINCIPLES.md)

| Req ID | Requirement Statement | Source | Priority | Governing Document | Planned Phase | Verification Method | Status | Notes / Unresolved Questions |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **AUD-001** | The system shall strictly prohibit any LLM, agent, or automated process from authorizing publication or approving its own outputs. | Const. Rule 14 | P0 | [PROJECT_CONSTITUTION.md](PROJECT_CONSTITUTION.md)#rule-14 | Phase 5 | State Machine Invariant Test | VERIFIED | Automated self-approval is forbidden via is_human=True checks in transition_mapping_status, transition_eu_screen_status, and verify_output_eligibility. |
| **AUD-002** | The system shall require cryptographically verified or authenticated human sign-off prior to publishing any incident dossier or newsletter. | Const. Rule 15 | P0 | [EDITORIAL_PRINCIPLES.md](EDITORIAL_PRINCIPLES.md)#5 | Phase 5 | HITL Gate Enforcement Test | VERIFIED | Enforced via reviewed_by / reviewed_at in verify_output_eligibility and cryptographic audit hash chaining in GovernanceRepository. |
| **AUD-003** | Historical incident assessments shall be immutable and append-only; model reruns shall create new versioned assessment records. | Const. Rule 17 | P0 | [DATA_GOVERNANCE.md](DATA_GOVERNANCE.md)#4 | Phase 2 | Immutability Schema Test | VERIFIED | Enforced via frozen=True, supersedes_claim_id, and replaces_claim_id. |
| **AUD-004** | The system shall record a tamper-evident audit log for every stage transition (Ingested -> Extracted -> Scored -> Reviewed -> Published). | PRD §5 | P0 | [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md)#5 | Phase 3 | Audit Trail Log Test | VERIFIED | Enforced via AuditRepository, AuditLogModel, and append-only immutability guards. |
| **AUD-005** | The system shall record the model family, version, temperature, prompt digest, and execution timestamp for every generative inference call. | PRD §5 | P0 | [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md)#5 | Phase 3 | Metadata Schema Test | PLANNED | Scientific reproducibility. |

---

### 3.15 `LGL`: Legal-Reference Controls and Disclaimers
Governing Document: [`docs/PROJECT_CONSTITUTION.md`](PROJECT_CONSTITUTION.md) & [`docs/EDITORIAL_PRINCIPLES.md`](EDITORIAL_PRINCIPLES.md)

| Req ID | Requirement Statement | Source | Priority | Governing Document | Planned Phase | Verification Method | Status | Notes / Unresolved Questions |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **LGL-001** | The system shall never assert that an incident constitutes a violation of the EU AI Act or any statute without citing an authoritative judicial or regulatory ruling. | Const. Rule 11 | P0 | [PROJECT_CONSTITUTION.md](PROJECT_CONSTITUTION.md)#rule-11 | Phase 5 | Legal Compliance Regex/Linter | VERIFIED | Forbids unadjudicated guilt assertions via validate_no_legal_language across all narrative fields in EULegalRelevanceScreenSchema and MappingCandidate. |
| **LGL-002** | The system shall append standard legal disclaimers stating that incident reports represent technical research, not formal legal advice. | Const. Rule 10 | P0 | [EDITORIAL_PRINCIPLES.md](EDITORIAL_PRINCIPLES.md)#4 | Phase 5 | Disclaimer Validator | VERIFIED | AI Guardians legal liability shield via mandatory versioned disclaimer (EU_AI_ACT_DISCLAIMER_V2, '2024-1689-v2') validated by verify_output_eligibility. |
| **LGL-003** | The system shall maintain an explicit distinction between statutory applicability and non-binding conceptual relevance across all reports. | Const. Rule 10 | P0 | [PROJECT_CONSTITUTION.md](PROJECT_CONSTITUTION.md)#rule-10 | Phase 4 | Schema Attribute Inspection | VERIFIED | Prevents jurisdictional overreach via EURelevanceLevel, EUNexusAssessment, and verify_output_eligibility in Phase 5 Inc 2C-1. |
| **LGL-004** | The system shall record right-of-response status, noting whether targeted entities were contacted or provided public commentary. | PRD §4.5 | P1 | [EDITORIAL_PRINCIPLES.md](EDITORIAL_PRINCIPLES.md)#3 | Phase 5 | Editorial Field Check | PLANNED | Standard journalistic fairness protocol. |
