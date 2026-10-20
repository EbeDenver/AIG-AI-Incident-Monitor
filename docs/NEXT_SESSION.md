# NEXT SESSION HANDOFF: Phase 4 Execution
**Project:** AI Incident Monitor
**Organization:** AI Guardians LLC
**Document Identifier:** NEXT-001
**Target Milestone:** Phase 4 Increment 4 (Cryptographic Provenance Manifests, XML Containment, & Verification)
**Parent Handoff:** Phase 4 Increments 1, 2, & 3 Verified on `feature/secure-ingestion-connectors`
**Effective Date:** 2026-10-20
**Current Branch:** `feature/secure-ingestion-connectors`

---

## 1. Current State: Increments 1, 2, & 3 Completed

- **Increment 1 (Security Core)**: SSRF defense, 21 blocked IP ranges, DNS resolution, connection pinning transport preserving TLS SNI and cert verification (`DEC-P4-003`), redirect inspector (max 3 hops), and 5 MB content bounds. (85 tests)
- **Increment 2 (Pluggable Connectors)**: `BaseConnector`, per-connector rate limiter with concurrency guard, exponential backoff with jitter on 429/503/transient errors, `RSSConnector` (feedparser byte parsing, defusedxml pre-screening, HTML sanitization, bozo tracking), `ArXivConnector` (export.arxiv.org official API, 1-connection 3-second rate limit, research signal labeling, PDF download blocking). (42 tests)
- **Increment 3 (OECD Adapter, Staging Store, & Purge Job)**: `OECDExportAdapter` (CSV/JSON/XLSX export parsing, formula neutralization, zero web scraping, `DEC-P4-001`), `RawPayloadStagingStore` (atomic write to `.data/raw_feeds/`, permission 0600, path traversal rejection, metadata cataloging, `DEC-P4-002`), `purge_staged_feeds` (30-day retention boundary, dry-run mode, active-run and legal-hold protection, append-only audit trail). (23 tests)
- **Total Passing Tests**: 294 / 294 tests passing with zero regressions.

---

## 2. Incoming Agent Mission: Phase 4 Increment 4 Objectives

In Increment 4, you will implement:
1. **Cryptographic Provenance Manifests (`IngestionManifest`)**:
   - Hash chaining linking ingestion runs in a tamper-evident sequence (`SRC-002`, `AUD-004`).
   - Every ingestion batch generates an immutable manifest with parent manifest SHA-256 hash.
   - Verification utility validating integrity of the manifest chain from genesis to head.
2. **XML Isolation & Containment (`<untrusted_source_content>`)**:
   - Defense against indirect prompt injection (`SRC-003`, `SEC-001`, Rule 11).
   - Strict sanitization of closing tag escapes (`</untrusted_source_content>`).
   - Attribute validation (source_id, timestamp, sha256).
   - Test suite verifying that adversarial instructions embedded in feed content cannot break containment.
3. **End-to-End Ingestion Integration Tests & Final PR Package**:
   - Integration test proving complete flow: fetch/parse -> staging -> deduplication check -> audit log -> manifest creation.
   - PR #3 readiness and validation.

### Targeted Requirements from RTM ([`docs/REQUIREMENTS_TRACEABILITY.md`](REQUIREMENTS_TRACEABILITY.md))
- **`SRC-002`**: Cryptographic SHA-256 digest computation and persistence upon ingestion.
- **`SRC-003`**: Mandatory structured XML containment (`<untrusted_source_content>`) prior to LLM processing.
- **`SEC-001`**: Adversarial prompt-injection defense test suite.
- **`AUD-004`**: Tamper-evident append-only audit trail and manifest chaining.
- **`SEC-005`**: Prompt template cryptographic digest integrity verification.
- **`PRI-003`**: Whistleblower pseudonymization schemas.
- **`OPS-002`**: Rate-limiting and backoff policies for web fetchers.

---

## 2. Startup Verification Checklist

Before writing any code in Phase 4:
1. [ ] Check current branch and git status:
   ```bash
   git status
   git branch --show-current
   ```
2. [ ] Verify `main` commit reflects the merged Phase 3 pull request.
3. [ ] Confirm feature branch `feature/data-foundation-import` remains intact until deletion is authorized.
4. [ ] Review the 17 non-negotiable constitutional rules in [`AGENTS.md`](../AGENTS.md).
5. [ ] Read [`docs/PROJECT_STATUS.md`](PROJECT_STATUS.md) to confirm Phase 3 is green (144/144 tests passing).
6. [ ] Run the complete test suite to verify baseline integrity:
   ```bash
   make test
   # or: .venv/bin/pytest backend/tests
   ```

---

## 3. Targeted Deliverables for Phase 4

You will extend `backend/src/ai_incident_monitor/`:

```
backend/src/ai_incident_monitor/
├── domain/                      # (Completed in Phase 2)
├── db/                          # (Completed in Phase 3)
├── repositories/                # (Completed in Phase 3)
├── importers/                   # (Completed in Phase 3 manual CSV/JSON/XLSX)
├── deduplication/               # (Completed in Phase 3 4-tier engine)
└── ingestion/                   # (Targeted in Phase 4)
    ├── __init__.py
    ├── connectors/
    │   ├── base.py              # BaseConnector abstract class with rate limiter & backoff
    │   ├── rss.py               # Feedparser / RSS news connector with timeout
    │   ├── arxiv.py             # arXiv API metadata connector
    │   └── poller.py            # Poller orchestrator feeding into ImportRepository
    └── security/
        ├── ssrf.py              # SSRF URL filter and IP validator (RFC 1918 blocking)
        ├── isolation.py         # Structured XML wrapper (<untrusted_source_content>)
        └── prompt_digest.py     # Prompt template cryptographic integrity verifier
backend/tests/
├── unit/
│   ├── test_connectors.py       # Mocked connector fetch tests
│   ├── test_ssrf.py             # SSRF blocklist & DNS resolution tests
│   └── test_prompt_isolation.py # XML containment & adversarial escape tests
└── fixtures/
    └── adversarial/             # Injection payload test fixtures (indirect prompt injection)
```

---

## 4. Key Implementation Rules for Phase 4

1. **Copyright Compliance (ADR-003, Rule 16)**: Never write raw external news article bodies into tracked Git files or database columns. Store SHA-256 digests, canonical URLs, and fair-use quote spans only.
2. **SSRF Defense (SEC-004)**: All outbound HTTP requests must resolve target hostnames before sending and explicitly reject:
   - Loopback (`127.0.0.0/8`, `::1`)
   - Private RFC 1918 ranges (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`)
   - Link-local addresses (`169.254.0.0/16`, cloud metadata endpoints like `169.254.169.254`)
   - Non-HTTP/HTTPS schemes (`file://`, `ftp://`, `gopher://`).
3. **Prompt Injection Containment (SEC-001, Rule 11)**: External untrusted text must never be concatenated directly into instruction prompts. Wrap strictly inside `<untrusted_source_content source_id="...">` blocks.
4. **Mocked Offline Tests**: All connector and fetcher tests must run strictly offline against mocked fixtures. Zero live outbound network requests allowed during CI test runs.
5. **Epistemic Traceability**: Ingested records must automatically tag created claims with `EpistemicStatus.UNVERIFIED_ALLEGATION` until human review occurs (Rule 3, Rule 13).
