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

## Scenario 6: Automated Scheduled Ingestion (macOS launchd LaunchAgent)

### Objective
Configure unattended recurring ingestion of configured live incident and research feeds on macOS using a native launchd user LaunchAgent (`com.aiguardians.incident-monitor.ingest`).

### Architecture & Guarantees
- **Interval:** Configurable default of 3600 seconds (60 minutes).
- **Execution Target:** `make ingest-cycle` executing `ai_incident_monitor.ingestion.cycle` via the local `.venv/bin/python`.
- **Concurrency Protection:** Shared advisory file lock at `.data/ingestion.lock`. Prevents concurrent runs between scheduler, CLI, and portal refreshes. If the process terminates abnormally, stale locks are automatically recovered by verifying PID liveness via `os.kill(pid, 0)`.
- **Durable Checkpoints:** `.data/ingestion_checkpoints.json` maintains source ETags, Last-Modified timestamps, and last run records. Invariant: `last_success_utc` is never updated on a failed or erroring source run.
- **Epistemic Separation:** Primary incident feeds populate the `incidents` table directly. Supplementary research contexts (e.g. arXiv preprints) populate context reference records only and never generate unverified primary incidents.
- **Zero Approval Invariant:** Ingested incidents are immediately visible in the incident explorer and ready for optional dossier assembly, artifact preview, and package export without requiring reviewer keys, attestation, or editorial approval.

### Configuration & Plist Generation
Generate the user-specific LaunchAgent plist containing exact absolute paths:
```bash
make generate-launchd-plist
make validate-launchd-plist
```
The generated plist is placed at `config/launchd/com.aiguardians.incident-monitor.ingest.plist`.

### LaunchAgent Installation & Activation (Operator Action)
To install and activate the LaunchAgent for the current macOS user:
```bash
# 1. Copy plist to user LaunchAgents directory
mkdir -p ~/Library/LaunchAgents
cp config/launchd/com.aiguardians.incident-monitor.ingest.plist ~/Library/LaunchAgents/

# 2. Load and start the LaunchAgent
launchctl load ~/Library/LaunchAgents/com.aiguardians.incident-monitor.ingest.plist

# 3. Verify status
launchctl list | grep aiguardians
```

### Log Paths & Monitoring
- **Standard Output:** `.data/logs/ingest.stdout.log`
- **Standard Error:** `.data/logs/ingest.stderr.log`
- **Execution Summary:** `.data/last_ingestion_summary.json`

### Disabling & Removal
```bash
# Unload and disable
launchctl unload ~/Library/LaunchAgents/com.aiguardians.incident-monitor.ingest.plist

# Remove plist
rm ~/Library/LaunchAgents/com.aiguardians.incident-monitor.ingest.plist
```

### Machine Sleep, Restart, and Offline Behavior
- **Sleep:** `launchd` suspends timers during system sleep. If an execution interval elapsed while sleeping, `launchd` triggers the cycle promptly upon system wake.
- **Offline / Network Outage:** If the network is unavailable, outbound connector requests fail gracefully with error isolation. The failing source is marked `FAILED` with its error recorded in checkpoints, while `last_success_utc` remains unchanged. Other healthy/offline sources continue unaffected.
- **System Reboot:** As a user LaunchAgent in `~/Library/LaunchAgents/`, the agent automatically restarts when the operator logs into the desktop session.

---

## Scenario 7: On-Demand Portal & API Ingestion Refresh

### Objective
Allow authenticated operators to trigger an immediate ingestion cycle from the web portal dashboard or via the authenticated JSON API without waiting for the scheduled 60-minute interval.

### Dashboard Action
1. Log into the AI Incident Monitor dashboard (`/login`).
2. Navigate to **Diagnostics** (`/diagnostics`) or **Incidents** (`/incidents`).
3. Click the **"Refresh Incidents Now →"** button in the page header.
4. The web server initiates the ingestion cycle in a background subprocess and returns an immediate status notice:
   - If idle, the cycle starts and runs with lock acquisition.
   - If an ingestion run is already active, the portal displays a conflict notice: `[ACTIVE: <TRIGGER>] Overlapping concurrent executions are prohibited by the concurrency lock`.
5. Once completed, refresh the `/incidents` or `/diagnostics` page to inspect newly ingested records, updated timestamps, and source metrics.

### JSON API Refresh & Status Inspection
Authenticated clients (with valid session cookie and CSRF token) can programmatically trigger and monitor collection:
```bash
# Trigger collection cycle via API
curl -X POST http://127.0.0.1:8000/api/ingestion/refresh \
  -H "Cookie: session_id=<SESSION_ID>" \
  -H "X-CSRF-Token: <CSRF_TOKEN>"

# Check current ingestion lock & execution status
curl http://127.0.0.1:8000/api/ingestion/status \
  -H "Cookie: session_id=<SESSION_ID>"
```

### Live Source Configuration & Gaps
- Configuration is loaded declaratively from `config/sources.json`.
- Current live network sources:
  - `arxiv_research`: `export.arxiv.org` (supplementary research context).
  - `rss_incident_feed`: Primary incident feed adapter. To enable live polling, configure a verified RSS/Atom feed URL in `config/sources.json`.
  - `oecd_export`: Offline manual file export (skipped during unattended network polling).
