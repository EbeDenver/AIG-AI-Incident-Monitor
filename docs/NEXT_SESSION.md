# NEXT SESSION HANDOFF: Phase 3 Kickoff
**Project:** AI Incident Monitor
**Organization:** AI Guardians LLC
**Document Identifier:** NEXT-001
**Target Milestone:** Phase 3 (Ingestion Connectors, Cryptographic Provenance, & Prompt Injection Defense)
**Parent Handoff:** Phase 2 (Core Epistemic Schemas & Golden Fixtures Completed)
**Effective Date:** 2026-10-07

---

## 1. Incoming Agent Mission: Phase 3 Objectives

Welcome to Phase 3 of **AI Incident Monitor**. In this phase, you will implement the source ingestion connectors, cryptographic raw payload provenance engine, and prompt-injection containment defenses that safely ingest untrusted external news, scientific papers, and regulatory filings into the system.

### Targeted Requirements from RTM ([`docs/REQUIREMENTS_TRACEABILITY.md`](REQUIREMENTS_TRACEABILITY.md))
- **`SRC-001`**: Pluggable connectors for RSS feeds, arXiv papers, regulatory dockets, and manual submissions.
- **`SRC-002`**: SHA-256 cryptographic digest computation and persistence upon ingestion.
- **`SRC-003`**: Mandatory structured XML containment (`<untrusted_source_content>`) prior to LLM processing.
- **`SRC-004`**: Multi-source incident deduplication and clustering.
- **`SRC-005`**: Unstable endpoint resilience, timeouts, and failure fallbacks.
- **`SEC-001`**: Adversarial prompt-injection defense test suite.
- **`SEC-002`**: Read-only ingestion and extraction sandboxing.
- **`SEC-004`**: SSRF prevention and URL sanitization.
- **`SEC-005`**: Prompt template cryptographic digest integrity verification.
- **`PRI-003`**: Whistleblower pseudonymization schemas.
- **`OPS-002`**: Rate-limiting and backoff policies for web fetchers.

---

## 2. Startup Verification Checklist

Before writing any code in Phase 3:
1. [ ] Check current branch and git status:
   ```bash
   git status
   git branch --show-current
   ```
2. [ ] Review the 17 non-negotiable constitutional rules in [`AGENTS.md`](../AGENTS.md).
3. [ ] Read [`docs/PROJECT_STATUS.md`](PROJECT_STATUS.md) to confirm Phase 2 is green and verified.
4. [ ] Run the Phase 2 test suite to verify baseline integrity:
   ```bash
   PYTHONPATH=backend/src pytest backend/tests
   ```

---

## 3. Targeted Deliverables for Phase 3

You will build upon the `backend/` package layout:

```
backend/src/ai_incident_monitor/
├── domain/                      # (Completed in Phase 2)
│   └── ...
└── ingestion/                   # (Targeted in Phase 3)
    ├── __init__.py
    ├── connectors/
    │   ├── base.py              # BaseConnector abstract class with rate limiter
    │   ├── rss.py               # Feedparser / RSS news connector
    │   ├── arxiv.py             # arXiv API metadata connector
    │   └── manual.py            # Manual JSON submission connector
    ├── security/
    │   ├── ssrf.py              # SSRF URL filter and IP validator (RFC 1918 blocking)
    │   ├── isolation.py         # Structured XML wrapper (<untrusted_source_content>)
    │   └── sanitizer.py         # Raw payload sanitizer and normalizer
    └── storage/
        ├── cache.py             # Out-of-tree local cache (.data/cache/), ADR-003 compliant
        └── hasher.py            # SHA-256 payload digest generator
backend/tests/
├── unit/
│   ├── test_connectors.py       # Mocked connector fetch tests
│   ├── test_ssrf.py             # SSRF blocklist tests
│   └── test_prompt_isolation.py # XML containment & adversarial escape tests
└── fixtures/
    └── adversarial/             # Injection payload test fixtures
```

---

## 4. Key Implementation Rules for Phase 3

1. **Copyright Compliance (ADR-003)**: Never write raw article payloads to tracked Git directories. All raw cached payloads must reside in `.data/cache/` (which is gitignored).
2. **SSRF Defense (SEC-004)**: All external fetch operations must resolve domain DNS and block loopback (`127.0.0.1`), private RFC 1918 ranges (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), link-local addresses, and non-HTTP schemes.
3. **Prompt Injection Containment (SEC-001, Rule 12)**: Untrusted external text must never be concatenated into raw instruction strings. It must always be wrapped in `<untrusted_source_content>` XML delimiters.
4. **Mocked Offline Tests**: All unit tests must use mocked responses or local fixtures; no live outbound network calls during CI test runs.
