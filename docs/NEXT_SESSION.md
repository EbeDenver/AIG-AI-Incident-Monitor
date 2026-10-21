# NEXT SESSION HANDOFF: Phase 5 Planning
**Project:** AI Incident Monitor  
**Organization:** AI Guardians LLC  
**Document Identifier:** NEXT-001  
**Target Milestone:** Phase 5 (AIG-ISI Severity Scoring Engine & Governance Mappings) — **PLANNING ONLY**  
**Parent Handoff:** Phase 4 Secure Ingestion Merged to `main` via PR #3 (Merge Commit `d2e9362133c968616ae21da25ba85b05c22fcfcf`)  
**Effective Date:** 2026-10-20  
**Current Branch:** `main`  

---

> [!IMPORTANT]
> **PHASE 5 EXECUTION POLICY: PLANNING-ONLY UNTIL SEPARATELY APPROVED**  
> No code implementation, schema modification, or feature branch creation for Phase 5 may begin until the user has reviewed and explicitly approved the Phase 5 architecture, planning package, and ADRs.

---

## 1. Current State: Phase 4 Merged to `main`

Phase 4 has been completed, peer-reviewed, and merged into `main`:
- **Pull Request**: [#3](https://github.com/EbeDenver/AIG-AI-Incident-Monitor/pull/3) (`feat: Phase 4 secure ingestion connectors and provenance`)
- **Merge Commit SHA**: `d2e9362133c968616ae21da25ba85b05c22fcfcf` (short: `d2e9362`)
- **Test Results**: 341 passed tests (320 unit, 21 integration) with 0 failures and 0 regressions.
- **Cryptographic Provenance**: Verified via `make verify-provenance-chain`.

### Phase 4 Completed Deliverables:
- **Increment 1 (Security Core)**: SSRF defense, 21 blocked IP ranges, DNS resolution pre-flight, connection pinning transport preserving TLS SNI and cert verification (`DEC-P4-003`, `ADR-008`), redirect inspector (max 3 hops), and 5 MB content bounds. (85 tests)
- **Increment 2 (Pluggable Connectors)**: `BaseConnector`, per-connector rate limiter with concurrency guard, exponential backoff with jitter on 429/503/transient errors, `RSSConnector` (feedparser byte parsing, defusedxml pre-screening, HTML sanitization, bozo tracking), `ArXivConnector` (export.arxiv.org official API, 1-connection 3-second rate limit, research signal labeling, PDF download blocking). (42 tests)
- **Increment 3 (OECD Adapter, Staging Store, & Purge Job)**: `OECDExportAdapter` (CSV/JSON/XLSX export parsing, formula neutralization, zero web scraping, `DEC-P4-001`, `ADR-009`), `RawPayloadStagingStore` (atomic write to `.data/raw_feeds/`, permission 0600, path traversal rejection, metadata cataloging, `DEC-P4-002`), `purge_staged_feeds` (30-day retention boundary, dry-run mode, active-run and legal-hold protection, append-only audit trail). (23 tests)
- **Increment 4 (Manifests, Untrusted Content Envelope, & E2E Pipeline)**: `IngestionManifest` with sequential hash chaining (`ADR-010`), canonical JSON serialization, `make verify-provenance-chain`, `UntrustedSourceContentEnvelope` with escaped XML prompt serialization (`ADR-011`), HTML/CSS stripping, Unicode NFKC, CWE-1236 formula defense, prompt injection triage signals (`detect_prompt_injection_signals`), future LLM boundary contract, and 21 end-to-end integration tests. (47 tests)

### Phase 4 Hard Boundaries Enforced:
1. **No Live Production Scheduling**: All connectors and pipelines execute strictly on-demand (CLI or test invocations); no cron jobs, Celery, or background daemon processes exist.
2. **No Web Scraping or Undocumented Polling**: OECD adapter strictly requires export files or fixtures (`DEC-P4-001`); zero dynamic UI scraping or undocumented endpoint reverse-engineering.
3. **No LLM Execution or Tool Dispatch**: Untrusted external content is strictly wrapped in `<untrusted_source_content>` envelopes with prompt-injection triage flags; no LLM calls, agents, or scoring engines are invoked.
4. **No Full Article Storage or Copyright Infringement**: Raw articles and payloads are excluded from Git; stored only in Gitignored staging (`.data/raw_feeds/`) with 30-day purge TTL; domain models store only short, fair-use quotation spans with cryptographic offsets (`PRI-002`, `ADR-003`).
5. **No Bypassing SecureHTTPClient**: Direct use of raw `requests`, `urllib`, or `httpx` is prohibited; all connectors must route through `SecureHTTPClient`.
6. **Application-Level Manifest Chain**: Ingestion manifests provide cryptographic provenance hash chaining across runs without requiring external ledger infrastructure.

---

## 2. Incoming Agent Mission: Phase 5 Objectives (Planning Only)

When authorized, Phase 5 will implement:
1. **AIG-ISI Multi-Dimensional Severity Engine**:
   - Deterministic, explainable scoring across Harm, Autonomy, Reversibility, and Scope (`SEV-001`, `SEV-002`).
   - Structural isolation from external regulatory classifications (OECD, NIST, EU) and media noteworthiness (`SEV-003`, `Rule 7`).
   - Segregation of demonstrated Actual Harm vs potential counterfactual harm (`SEV-004`, `Rule 5`).
   - Non-monetization of human dignity and physical harm (`SEV-005`, `Rule 8`).
   - Mandatory human sign-off triggers for high-severity ratings (`SEV-006`, `Rule 13`).
2. **Governance Framework Mappings**:
   - OECD AI Principles mapper (`GOV-001`).
   - NIST AI Risk Management Framework core functions mapper (`GOV-002`).
   - EU AI Act screening classifier (Prohibited, High-Risk, GPAI) with strict jurisdictional distinction vs conceptual relevance (`GOV-003`, `GOV-004`, `Rule 9`, `Rule 10`).
   - Preserving governance mappings as orthogonal tag layers (`GOV-005`, `Rule 7`).
3. **Root Cause Analysis (RCA) Taxonomies**:
   - Multi-tier taxonomy (Data, Model Architecture, Alignment/Safety, System Integration, Human Oversight, Malicious Exploitation) (`RCA-001`).
   - Direct evidentiary linkage requirement (`RCA-002`, `Rule 4`).
   - Epistemic flagging when technical postmortems are absent (`RCA-004`, `Rule 2`).

### Targeted Requirements from RTM ([`docs/REQUIREMENTS_TRACEABILITY.md`](REQUIREMENTS_TRACEABILITY.md))
- **`SEV-001`**: AIG-ISI multi-dimensional scoring engine.
- **`SEV-002`**: Human-readable evidentiary rationales per dimension.
- **`SEV-003`**: Structural isolation of severity from governance frameworks.
- **`SEV-006`**: High-severity human review triggers.
- **`GOV-001`**: OECD AI Principles mapping.
- **`GOV-002`**: NIST AI RMF core function mapping.
- **`GOV-003`**: EU AI Act categorization screening.
- **`GOV-004`**: Enforceable statutory applicability vs conceptual relevance.
- **`GOV-005`**: Orthogonality of governance tags.
- **`RCA-001`**: Multi-tier causal factor taxonomy.
- **`RCA-002`**: Evidentiary anchoring for root-cause findings.
- **`RCA-004`**: Epistemic labeling for unverified causal findings.

---

## 3. Startup Verification Checklist for Next Agent

1. [ ] Check current branch and git status:
   ```bash
   git status
   git branch --show-current
   ```
2. [ ] Confirm repository is on `main` and clean (merge commit `d2e9362` present).
3. [ ] Review the 17 non-negotiable constitutional rules in [`AGENTS.md`](../AGENTS.md).
4. [ ] Run full test suite:
   ```bash
   .venv/bin/pytest backend/tests
   ```
5. [ ] Verify provenance chain integrity:
   ```bash
   make verify-provenance-chain
   ```
6. [ ] **Wait for explicit user approval before writing Phase 5 code or creating feature branches.**
