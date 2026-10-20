# NEXT SESSION HANDOFF: Phase 5 Execution
**Project:** AI Incident Monitor  
**Organization:** AI Guardians LLC  
**Document Identifier:** NEXT-001  
**Target Milestone:** Phase 5 (AIG-ISI Severity Scoring Engine & Governance Mappings)  
**Parent Handoff:** Phase 4 Secure Ingestion Completed on `feature/secure-ingestion-connectors` (PR #3)  
**Effective Date:** 2026-10-20  
**Current Branch:** `feature/secure-ingestion-connectors`  

---

## 1. Current State: Phase 4 Completed

All four increments of Phase 4 have been implemented and verified with 341 passing tests:
- **Increment 1 (Security Core)**: SSRF defense, 21 blocked IP ranges, DNS resolution, connection pinning transport preserving TLS SNI and cert verification (`DEC-P4-003`), redirect inspector (max 3 hops), and 5 MB content bounds. (85 tests)
- **Increment 2 (Pluggable Connectors)**: `BaseConnector`, per-connector rate limiter with concurrency guard, exponential backoff with jitter on 429/503/transient errors, `RSSConnector` (feedparser byte parsing, defusedxml pre-screening, HTML sanitization, bozo tracking), `ArXivConnector` (export.arxiv.org official API, 1-connection 3-second rate limit, research signal labeling, PDF download blocking). (42 tests)
- **Increment 3 (OECD Adapter, Staging Store, & Purge Job)**: `OECDExportAdapter` (CSV/JSON/XLSX export parsing, formula neutralization, zero web scraping, `DEC-P4-001`, `ADR-009`), `RawPayloadStagingStore` (atomic write to `.data/raw_feeds/`, permission 0600, path traversal rejection, metadata cataloging, `DEC-P4-002`), `purge_staged_feeds` (30-day retention boundary, dry-run mode, active-run and legal-hold protection, append-only audit trail). (23 tests)
- **Increment 4 (Manifests, Untrusted Content Envelope, & E2E Pipeline)**: `IngestionManifest` with sequential hash chaining (`ADR-010`), canonical JSON serialization, `make verify-provenance-chain`, `UntrustedSourceContentEnvelope` with escaped XML prompt serialization (`ADR-011`), HTML/CSS stripping, Unicode NFKC, CWE-1236 formula defense, prompt injection triage signals (`detect_prompt_injection_signals`), future LLM boundary contract, and 21 end-to-end integration tests. (47 tests)
- **Total Passing Tests**: 341 / 341 tests passing with zero regressions.

---

## 2. Incoming Agent Mission: Phase 5 Objectives

In Phase 5, you will implement:
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

## 3. Startup Verification Checklist for Phase 5

1. [ ] Check current branch and git status:
   ```bash
   git status
   git branch --show-current
   ```
2. [ ] Verify PR #3 has been merged to `main` and branch is switched to `main` (or new feature branch `feature/aig-isi-scoring-engine`).
3. [ ] Review the 17 non-negotiable constitutional rules in [`AGENTS.md`](../AGENTS.md).
4. [ ] Run full test suite:
   ```bash
   .venv/bin/pytest backend/tests
   ```
5. [ ] Verify provenance chain integrity:
   ```bash
   make verify-provenance-chain
   ```
