# LOCAL OPERATOR RUNBOOK: INGESTION & DATA RETENTION
**Project:** AI Incident Monitor  
**Organization:** AI Guardians LLC  
**Document Identifier:** OPS-003  
**Version:** 1.0.0  
**Effective Date:** 2026-10-20  
**Governing Charter:** [Project Constitution](PROJECT_CONSTITUTION.md), [ADR-008](DECISIONS.md#adr-008-secure-ingestion-connectors-cryptographic-provenance-and-ssrf-defense), [ADR-009](DECISIONS.md#adr-009-oecd-export-only-adapter-strategy-and-zero-scraping-mandate)  

---

## 1. Overview & Authorized Workflows

This runbook guides authorized operators and local administrators through routine source ingestion, raw payload staging, and retention maintenance procedures.

```
┌────────────────────────────────────────────────────────────────────────┐
│                      OPERATIONAL WORKFLOW MATRIX                       │
├─────────────────────────┬──────────────────────────────────────────────┤
│ Scenario                │ Command / Procedure                          │
├─────────────────────────┼──────────────────────────────────────────────┤
│ 1. Manual OECD Export   │ make import-oecd FILE=/path/to/export.csv    │
│    Upload               │ (or .json / .xlsx)                           │
├─────────────────────────┼──────────────────────────────────────────────┤
│ 2. RSS / Atom Feed      │ make ingest-feed URL="https://safe-news.org" │
│    Ingestion            │                                              │
├─────────────────────────┼──────────────────────────────────────────────┤
│ 3. Raw Staging          │ Authorized admin inspects metadata catalog:  │
│    Inspection           │ .data/raw_feeds/staging_catalog.json         │
├─────────────────────────┼──────────────────────────────────────────────┤
│ 4. Manual Purge Dry Run │ make purge-raw-feeds-dry-run                 │
├─────────────────────────┼──────────────────────────────────────────────┤
│ 5. Manual Purge Execute │ make purge-raw-feeds                         │
├─────────────────────────┼──────────────────────────────────────────────┤
│ 6. Future Scheduling    │ DECOUPLED & DISABLED (Explicitly deferred)   │
└─────────────────────────┴──────────────────────────────────────────────┘
```

---

## Scenario 1: Manual OECD Export Upload

### Objective
Ingest an official, operator-downloaded OECD export file (CSV, JSON, or XLSX) into the normalized incident database.

### Preconditions
- The export file was downloaded through an authorized, documented OECD download interface.
- Operator has confirmed the file is authentic and uncorrupted.

### Execution
```bash
# Ingest OECD CSV export
python -m ai_incident_monitor.ingestion.oecd_adapter --file path/to/oecd_export.csv --mode MANUAL_OFFICIAL_EXPORT

# Or via Makefile target
make import-oecd FILE=path/to/oecd_export.csv
```

### Verification
- Output reports total parsed rows, valid mapped items, and any warnings.
- Records without stable OECD IDs are marked for deduplication review.
- Original fields are preserved in `original_record_dict`.

---

## Scenario 2: RSS / Atom Feed Ingestion

### Objective
Retrieve and parse an approved RSS or Atom feed through the hardened `SecureHTTPClient`.

### Preconditions
- Target host must be present in the connector's approved allowlist.
- Network connection must satisfy SSRF constraints (HTTPS, 443, no private IP).

### Execution
```bash
python -m ai_incident_monitor.ingestion.connectors.rss --url "https://safe-news.org/feed.xml"
```

### Verification
- Verify response status is `SUCCESS` or `NOT_MODIFIED` (HTTP 304).
- Raw feed payload is automatically staged in `.data/raw_feeds/` (if staging enabled).
- Snippets are sanitized and limited to 500 characters.

---

## Scenario 3: Raw Staging Inspection (Authorized Admin Only)

### Objective
Verify staged feed payloads and check storage consumption.

### Constraints & Security
- **Confidentiality Notice**: Raw staged feeds may contain third-party text. They are strictly stored on local disk in `.data/raw_feeds/` with restrictive POSIX permissions (`0600`).
- Raw payloads must **never** be copied into Git, committed, exposed via public endpoints, or pasted into bug trackers.

### Procedure
```bash
# Check raw feed directory contents (Admin only)
ls -la .data/raw_feeds/

# Inspect staging metadata catalog
cat .data/raw_feeds/staging_catalog.json | grep -E "staging_record_id|retrieval_time|purge_status"
```

---

## Scenario 4: Manual Purge Dry Run

### Objective
Preview aged raw feed payloads eligible for deletion without deleting any files.

### Execution
```bash
# Run purge in dry-run mode (default: 30 days retention)
make purge-raw-feeds-dry-run

# Or with custom retention threshold
python -m ai_incident_monitor.ingestion.purge --retention-days 30 --dry-run
```

### Expected Output
- Lists candidate files older than 30 days.
- Reports skipped items (e.g. active runs, legal holds).
- Zero files are removed from disk.

---

## Scenario 5: Manual Purge Execution

### Objective
Permanently delete raw feed payloads that have exceeded the 30-day retention TTL.

### Execution
```bash
# Execute purge
make purge-raw-feeds

# Or with custom retention
python -m ai_incident_monitor.ingestion.purge --retention-days 30
```

### Verification
- Candidate raw files are unlinked from `.data/raw_feeds/`.
- Staging metadata records are updated to `PURGED`.
- Staging records where files were previously deleted are updated to `MISSING`.
- An immutable audit record is logged for each item.
- File metadata, canonical URL, and SHA-256 remain preserved in the metadata store.

---

## Scenario 6: Future Automated Scheduling (Explicitly Deferred)

### Current Architecture Status
- In Phase 4, **all automated recurring schedulers (cron, daemons, Cloudflare triggers) are explicitly decoupled and disabled**.
- All operations must be executed manually or triggered via explicit script invocation.

### Future Implementation Roadmap (Phase 7)
- Scheduled background polling and periodic purge runs will be orchestrated via external systemd timers or container orchestration cron jobs calling the idempotent CLI commands documented in Scenarios 1–5.
