# NEXT SESSION HANDOFF: Phase 4 Execution
**Project:** AI Incident Monitor
**Organization:** AI Guardians LLC
**Document Identifier:** NEXT-001
**Target Milestone:** Phase 4 Increment 3 (OECD Export Adapter, Raw Feed Staging Store, & 30-Day Purge TTL Job)
**Parent Handoff:** Phase 4 Increments 1 & 2 Verified on `feature/secure-ingestion-connectors`
**Effective Date:** 2026-10-20
**Current Branch:** `feature/secure-ingestion-connectors`

---

## 1. Current State: Increments 1 & 2 Completed

- **Increment 1 (Security Core)**: SSRF defense, 21 blocked IP ranges, DNS resolution, connection pinning transport preserving TLS SNI and cert verification (`DEC-P4-003`), redirect inspector (max 3 hops), and 5 MB content bounds. (85 tests)
- **Increment 2 (Pluggable Connectors)**: `BaseConnector`, per-connector rate limiter with concurrency guard, exponential backoff with jitter on 429/503/transient errors, `RSSConnector` (feedparser byte parsing, defusedxml pre-screening, HTML sanitization, bozo tracking), `ArXivConnector` (export.arxiv.org official API, 1-connection 3-second rate limit, research signal labeling, PDF download blocking). (42 tests)
- **Total Passing Tests**: 271 / 271 tests passing with zero regressions.

---

## 2. Incoming Agent Mission: Phase 4 Increment 3 Objectives

In Increment 3, you will implement:
1. **OECD Export Adapter (`OECDAdapter`)**:
   - Implements offline structured export and fixture-only parsing (`DEC-P4-001`, Option A).
   - Zero live scraping or polling of undocumented OECD web/UI API endpoints.
   - Standardized adapter interface so an authorized future API or bulk export can be plugged in seamlessly.
2. **Raw Feed Payload Staging Store (`.data/raw_feeds/`)**:
   - Stages raw retrieved feed payloads in `.data/raw_feeds/{year}/{month}/{manifest_id}.raw` (`DEC-P4-002`, Option A).
   - Strictly gitignored to uphold copyright fair-use rules and prevent repository bloat (ADR-003, Rule 15).
3. **30-Day Purge TTL Job**:
   - Automated purge routine deleting staged raw payloads older than 30 days (`DEC-P4-002`).
   - CLI / Makefile trigger (`make purge-raw-feeds`).
   - Appends immutable audit record to `audit_logs` documenting each purge run.
4. **Unit and Integration Tests**:
   - Test OECD export parser against sanitized OECD exports.
   - Test staging file writes and retrieval.
   - Test 30-day purge TTL job logic and audit record creation.

### Targeted Requirements from RTM ([`docs/REQUIREMENTS_TRACEABILITY.md`](REQUIREMENTS_TRACEABILITY.md))
- **`SRC-001`**: Pluggable connectors for RSS news feeds, arXiv papers, regulatory dockets, and scheduled polling.
- **`SRC-003`**: Mandatory structured XML containment (`<untrusted_source_content>`) prior to LLM processing.
- **`SRC-005`**: Unstable endpoint resilience, timeouts, and failure fallbacks.
- **`SEC-001`**: Adversarial prompt-injection defense test suite.
- **`SEC-002`**: Read-only ingestion and extraction sandboxing.
- **`SEC-004`**: SSRF prevention and URL sanitization (RFC 1918 blocking, loopback defense).
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
