# OECD EXPORT ADAPTER SPECIFICATION
**Project:** AI Incident Monitor  
**Organization:** AI Guardians LLC  
**Document Identifier:** SPEC-005  
**Version:** 1.0.0  
**Effective Date:** 2026-10-20  
**Governing Charter:** [Project Constitution](PROJECT_CONSTITUTION.md) (Rules 1, 9, 11, 14, 15, 16), [ADR-008](DECISIONS.md#adr-008-secure-ingestion-connectors-cryptographic-provenance-and-ssrf-defense), [ADR-009](DECISIONS.md#adr-009-oecd-export-only-adapter-strategy-and-zero-scraping-mandate)  

---

## 1. Architectural Mandate: Zero Live Scraping (DEC-P4-001)

The AI Incident Monitor strictly maintains DEC-P4-001 without exception:
- **Permitted Data Sources**:
  1. Files exported directly through an official, documented, and permitted OECD download mechanism.
  2. Manual file uploads performed by an authorized system operator.
  3. Sanitized, recorded synthetic test fixtures.
- **Strictly Prohibited Operations**:
  - Live scraping of `oecd.ai` or OECD web pages.
  - Polling undocumented OECD frontend, internal, or private API endpoints.
  - Reverse-engineering dynamic UI calls or token exchanges.
  - Circumventing rate limits, CAPTCHAs, or access controls.
  - Fetching operator-entered arbitrary OECD URLs over the network.
  - Adding scheduled, background, or automated recurring OECD retrieval.

---

## 2. Source Modes

Every OECD ingestion operation must specify an explicit `OECDSourceMode`:

| Mode Enum Value | Meaning | Permitted Operations |
| :--- | :--- | :--- |
| `MANUAL_OFFICIAL_EXPORT` | An official export file downloaded manually by an operator | Ingests from local file path or file stream |
| `RECORDED_TEST_FIXTURE` | Pre-recorded, sanitized synthetic test fixture | Ingests from sanitized test fixture directories |
| `FUTURE_OFFICIAL_API_DISABLED` | Future authorized, officially documented API | Disabled by default; raises `ConnectorDisabledError` if invoked |

---

## 3. Supported File Formats & Mapping Specifications

The adapter processes three structured file formats: **CSV**, **JSON**, and **XLSX**.

### 3.1 Common Preserved Metadata
Every imported OECD record preserves the following immutable provenance attributes:
- `source_system`: `"OECD_AIM"`
- `source_mode`: `OECDSourceMode`
- `original_file_name`: Original name of the imported file
- `file_sha256`: Cryptographic SHA-256 digest of the entire export file
- `import_timestamp`: ISO 8601 UTC timestamp of the import execution
- `operator_id`: Identifier of the operator or import job
- `original_source_record_id`: Raw OECD record identifier (if present)
- `original_source_url`: Raw OECD canonical link or reference URL
- `original_record_title`: Raw OECD incident title
- `original_record_dates`: Raw incident date string and precision
- `normalized_fields`: Mapped fields conforming to AI Incident Monitor domain schemas
- `validation_warnings`: Non-fatal schema or formatting warnings
- `duplicate_resolution_result`: Linkage status from deduplication engine
- `ingestion_manifest_id`: Correlation ID linking to the ingestion run manifest
- `methodology_version`: `"OECD-Adapter-1.0.0"`

### 3.2 CSV Mapping Specification
Expected standard CSV column headers (case-insensitive, whitespace-trimmed):
- `Incident ID` / `ID` $\to$ `original_source_record_id` (e.g. `OECD-1234`)
- `Title` / `Incident Name` $\to$ `title`
- `Date` / `Incident Date` $\to$ `incident_date` (normalized to ISO 8601 or `DateWithPrecision`)
- `URL` / `Link` / `Source URL` $\to$ `canonical_url`
- `Description` / `Summary` $\to$ `summary_snippet` (sanitized to max 500 characters)
- `OECD Principles` / `Classification` $\to$ `metadata["oecd_principles"]`
- `AI System` / `Entity` $\to$ `metadata["ai_system"]`
- `Harm Type` / `Impact` $\to$ `metadata["oecd_harm_category"]`

### 3.3 JSON Mapping Specification
Accepts JSON arrays (`[...]`), root object containers (`{"incidents": [...]}` or `{"data": [...]}`), or newline-delimited JSON (NDJSON).
Expected JSON keys:
- `id` / `incident_id` $\to$ `original_source_record_id`
- `title` / `name` $\to$ `title`
- `date` / `incident_date` $\to$ `incident_date`
- `url` / `source_url` $\to$ `canonical_url`
- `description` / `summary` $\to$ `summary_snippet`
- `classifications` / `tags` $\to$ `metadata["oecd_tags"]`
- `ai_system` $\to$ `metadata["ai_system"]`

### 3.4 XLSX Mapping Specification
- Processes the first worksheet using `openpyxl` with `read_only=True, data_only=True`.
- Extracts cached formula values; does not evaluate active formulas.
- Sanitizes formula triggers (`=`, `+`, `-`, `@`, `\t`, `\r`) per CWE-1236.

---

## 4. Epistemic Separation & Non-Overwriting Rules (Rule 3, Rule 7, Rule 9)

1. **Classifications as Source Metadata**:
   OECD classifications (e.g., OECD AI Principles mapping, sector tags) must be stored strictly as **source metadata** (`metadata["oecd_..."]`). They must **never** be represented as proven factual conclusions, legal findings, or conflated with the proprietary **AIG-ISI (AI Guardians Incident Severity Index)** score.
2. **Original Fields Preserved**:
   The adapter maps records into the normalized incident model without mutating or overwriting the original OECD export row dictionary (`original_record_dict`).
3. **Handling Missing Record Identifiers**:
   If an imported row lacks an explicit OECD record identifier, the adapter **must not invent a synthetic identifier**. The record is flagged with `requires_dedup_review = True` and routed to the deduplication queue for human review.

---

## 5. Sample-Data Policy for Sanitized Test Fixtures

- All OECD test fixtures checked into the repository must contain strictly **synthetic, public-domain, or anonymized incident descriptions**.
- Fixtures must clearly bear the header/disclaimer:  
  `DEMONSTRATION DATA — NOT A REAL INCIDENT — AI GUARDIANS TEST FIXTURE`.
- Never commit private, proprietary, or full-text copyrighted news articles as test fixtures.
