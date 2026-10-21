# PHASE 4 SPECIFICATION: SECURE INGESTION CONNECTORS, CRYPTOGRAPHIC PROVENANCE, & SOURCE CONTAINMENT
**Project:** AI Incident Monitor  
**Organization:** AI Guardians LLC  
**Document Identifier:** SPEC-004  
**Version:** 1.0.0  
**Effective Date:** 2026-10-20  
**Governing Charter:** [Project Constitution](PROJECT_CONSTITUTION.md), [ADR-008](DECISIONS.md#adr-008-secure-ingestion-connectors-cryptographic-provenance-and-ssrf-defense), [SEC-002](CONNECTOR_SECURITY_MODEL.md)  

---

## 1. Executive Summary & Goals

Phase 4 builds a secure, pluggable, read-only source-ingestion foundation that retrieves permitted public structured feeds or documents, preserves cryptographic provenance, defends against SSRF and prompt-injection risks, and stages normalized source material for downstream human review and AI analysis.

### Primary Objectives
1. **SSRF & DNS Rebinding Immunity**: Validated-destination connection pinning, 21 blocked IP ranges, independent redirect hop validation, and 5 MB content bounds.
2. **Pluggable Connectors**: Base connector framework supporting RSS/Atom feeds, arXiv paper metadata, and offline OECD export files.
3. **OECD Adapter Strategy (DEC-P4-001)**: Export/fixture-only architecture with zero scraping of undocumented endpoints.
4. **Staging & Retention Policy (DEC-P4-002)**: Gitignored local staging (`.data/raw_feeds/`) with a 30-day purge TTL. Zero full copyrighted article text in Git or database.
5. **Cryptographic Provenance Chaining (DEC-P4-004)**: Sequential manifest hash chaining linking to `previous_manifest_sha256` from a deterministic genesis zero hash.
6. **Structural Prompt Isolation (SEC-001, Rule 11)**: Structured XML containment (`<untrusted_source_content>`) and template cryptographic integrity checks (`SEC-005`).

---

## 2. Ingestion Connector Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                   INGESTION PIPELINE ARCHITECTURE                      │
└────────────────────────────────────────────────────────────────────────┘

 [ External Source ] (RSS / arXiv / OECD Export)
          │
          ▼
 [ Security Subsystem ]
   - URL Policy & Normalizer (HTTPS, Port 443, strip userinfo)
   - DNS Pre-flight Validator (21 blocked IP ranges, punycode)
   - Connection Pinning Transport (Pin IP, preserve TLS SNI & Host)
   - Redirect Hop Inspector (Max 3 hops, per-hop DNS check)
   - Content Bounds & Decompression Guard (5 MB max, 5:1 ratio)
          │
          ▼
 [ Connector Layer ]
   - RSSConnector (Feedparser, XML/Atom parsing)
   - ArXivConnector (OAI-PMH / atom feed parsing, rate-limiting)
   - OECDAdapter (Offline CSV/JSON/XLSX export parser)
          │
          ▼
 [ Provenance & Staging Subsystem ]
   - Raw Payload Staging (.data/raw_feeds/, 30-day purge TTL)
   - Payload SHA-256 Computation
   - Sequential Ingestion Manifest Hash Chaining
          │
          ▼
 [ Normalization & Containment ]
   - FeedItem -> RawImportRecord
   - Structured XML Containment Wrapper (<untrusted_source_content>)
   - Prompt Digest Verifier (SHA-256 template check)
          │
          ▼
 [ Downstream Persistence ] (Stage transition into dedup & triage)
```

---

## 3. Cryptographic Provenance & Manifest Hash Chaining (DEC-P4-004)

### 3.1 Design Principles
- **Tamper-Evident Sequential Logging**: Manifests provide auditable proof that no ingestion run was inserted, deleted, or altered out of order.
- **Not Distributed Consensus**: This is a cryptographic sequence verification log for auditability, not a blockchain or proof-of-work system.
- **Genesis Anchor**: The first ingestion run links to a deterministic 64-character zero-hash:
  `0000000000000000000000000000000000000000000000000000000000000000`.

### 3.2 Manifest Schema (`IngestionManifest`)
```python
class IngestionManifest(BaseModel):
    manifest_id: str                      # man_ prefixed UUID
    run_timestamp: datetime               # ISO 8601 UTC
    connector_type: str                   # "rss", "arxiv", "oecd_export"
    source_url: str                       # Source feed or file identifier
    item_count: int                       # Number of items ingested
    payload_sha256: str                   # SHA-256 of the raw feed payload
    item_sha256_list: list[str]           # List of individual item hashes
    previous_manifest_sha256: str         # Parent manifest hash (or 64 zeros)
    manifest_sha256: str                  # SHA-256 digest of this canonical manifest
```

---

## 4. Raw Feed Staging & Retention Policy (DEC-P4-002)

1. **Storage Location**: Raw feed payloads are stored on disk in `$REPO_ROOT/.data/raw_feeds/{year}/{month}/{manifest_id}.raw`.
2. **Git Hygiene (Rule 15, ADR-003)**: `.data/` is strictly ignored by Git. No raw news bodies are ever committed.
3. **Database Boundary**: The relational database stores only metadata, canonical URL, structured fields, provenance hash, and short permitted snippets.
4. **Purge Job Specification**:
   - Retention TTL: 30 days.
   - Command: `ai-incident-monitor purge-raw-feeds --retention-days 30` (or `make purge-raw-feeds`).
   - The job deletes files older than 30 days and logs an immutable audit event (`AuditAction.DATA_PURGE`).

---

## 5. Deferred Scheduler Architecture Note

In Phase 4, automated background scheduling (e.g., cron jobs, daemon loops, or celery workers) is explicitly **decoupled and deferred**:
- **Why**: Scheduling introduces long-running process management, clock drift, duplicate execution risk, and complex mocking in automated test suites.
- **Phase 4 Execution**: All connector ingestion, deduplication, and purge operations are exposed as deterministic CLI commands and Makefile targets:
  - `make ingest-feed URL="https://..."`
  - `make ingest-arxiv QUERY="..."`
  - `make purge-raw-feeds`
- **Future Integration (Phase 7)**: Production scheduling will be implemented as an external orchestration layer (e.g., systemd timers, AWS EventBridge, or Kubernetes CronJobs) invoking these idempotent CLI commands.

---

## 6. Phase 4 Acceptance Test Matrix

| Increment | Test Suite | Requirements Covered | Target Assertions & Edge Cases |
| :---: | :--- | :--- | :--- |
| **Inc 1** | `test_security_ssrf.py` | `SEC-004`, `ADR-008` (DEC-P4-003) | - 21 blocked IP ranges rejected<br>- Decimal/octal/hex IP notations rejected<br>- IPv4-mapped IPv6 evasions blocked<br>- DNS rebinding simulation blocked<br>- TLS SNI and cert verification preserved<br>- Max 3 redirect hops, downgrade blocked<br>- 5 MB size limit & decompression ratio guard |
| **Inc 2** | `test_connectors.py` | `SRC-001`, `OPS-002`, `SRC-005` | - RSS connector parses valid RSS 2.0 and Atom feeds<br>- arXiv connector parses API XML metadata<br>- Rate limiting enforces delay between calls<br>- Exponential backoff on 429/503 errors<br>- 10s socket timeout enforced |
| **Inc 3** | `test_oecd_adapter.py`, `test_feed_staging.py` | `SRC-001`, `PRI-002`, `ADR-008` (DEC-P4-001, DEC-P4-002) | - OECD export parser maps fields correctly<br>- Zero live requests made to OECD endpoints<br>- Raw feed staged in `.data/raw_feeds/`<br>- 30-day purge deletes aged files<br>- Audit log records purge action |
| **Inc 4** | `test_provenance_manifest.py` | `SRC-002`, `AUD-004`, `ADR-008` (DEC-P4-004) | - Genesis manifest links to 64 zero-hash<br>- Sequential manifests form unbroken SHA-256 chain<br>- Broken chain / tampering triggers verification failure<br>- Deterministic canonical serialization |
| **Inc 5** | `test_prompt_containment.py`, `test_phase4_integration.py` | `SRC-003`, `SEC-001`, `SEC-002`, `SEC-005` | - Untrusted content wrapped in `<untrusted_source_content>`<br>- Prompt injection vectors neutralized/contained<br>- System prompt SHA-256 digest verified<br>- Full end-to-end feed -> manifest -> staging -> dedup candidate run |
