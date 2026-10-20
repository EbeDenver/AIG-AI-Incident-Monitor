# CRYPTOGRAPHIC PROVENANCE MANIFESTS SPECIFICATION
**Project:** AI Incident Monitor  
**Organization:** AI Guardians LLC  
**Document Identifier:** SPEC-006  
**Version:** 1.0.0  
**Effective Date:** 2026-10-20  
**Governing Charter:** [Project Constitution](PROJECT_CONSTITUTION.md) (Rules 1, 4, 11, 14, 15, 16), [ADR-008](DECISIONS.md#adr-008-secure-ingestion-connectors-cryptographic-provenance-and-ssrf-defense), [ADR-010](DECISIONS.md#adr-010-cryptographic-provenance-manifests-and-sequential-hash-chaining)  

---

## 1. Architectural Scope and Purpose

The AI Incident Monitor requires a verifiable, tamper-evident audit record for every source retrieval and parsing execution. The **`IngestionManifest`** serves as the authoritative cryptographic record for each completed, partial, or failed ingestion cycle.

### Constitutional Scope and Epistemic Honesty
- **Application Audit Chain Only**: This mechanism is a tamper-evident application-level audit chain. It is **not** presented as a blockchain, immutable distributed ledger, non-repudiation mechanism, or external RFC 3161 timestamp proof.
- **DBA Threat Model Disclosure**: Database administrators or system users with unrestricted write access to the underlying storage files or database tables can technically rewrite history unless an external cryptographic timestamp anchoring service (e.g. public ledger or HSM key sign-off) is introduced in a future phase.
- **Append-Only Immutability**: Within application code, manifests are strictly append-only and frozen (`frozen=True`). Corrections, reprocessing, or retries create new manifests pointing to the prior finalized manifest; historical rows are never overwritten.

---

## 2. Canonical JSON Serialization & SHA-256 Hashing

To ensure bit-for-bit cryptographic determinism across operating systems and execution runs, manifests undergo canonical JSON serialization before digest calculation:

```
┌─────────────────────────────────┐
│     IngestionManifest Object    │
│  - 28 Typed Provenance Fields   │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│  Canonical Dict Transformation  │
│  - Omit manifest_sha256         │
│  - Sort nested keys & lists     │
│  - Normalize ISO 8601 UTC dates │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│    Canonical JSON Serializer    │
│  - UTF-8 Encoding               │
│  - sort_keys=True               │
│  - separators=(',', ':')        │
│  - ensure_ascii=False           │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│         SHA-256 Digest          │
│  - Hexadecimal representation   │
│  - Sealed into manifest_sha256  │
└─────────────────────────────────┘
```

### Manifest Fields Specification

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `manifest_id` | `str` | Unique manifest identifier (e.g. `man_a1b2c3d4...`) |
| `schema_version` | `str` | Explicit schema version (`"1.0.0"`) |
| `environment` | `str` | Deployment environment (e.g. `development`, `test`, `production`) |
| `chain_scope` | `str` | Audit chain scope identifier (`global_environment_default`) |
| `ingestion_run_id` | `str` | Correlation run ID from the ingestion orchestrator |
| `run_status` | `ManifestRunStatus` | `STARTED`, `COMPLETED`, `PARTIAL`, `FAILED`, `PURGED`, `VERIFIED`, `SUPERSEDED` |
| `connector_id` | `str` | Identifier of connector (e.g. `rss_news_connector`, `arxiv_api`) |
| `connector_version` | `str` | Semantic version of connector code |
| `connector_policy_version` | `str` | Version of active rate-limit and backoff policy |
| `parser_version` | `str` | Semantic version of parser/normalizer |
| `build_identifier` | `str` | Git commit hash or deployment build ID |
| `started_at` | `str` | UTC ISO 8601 timestamp of run commencement |
| `finalized_at` | `str` | UTC ISO 8601 timestamp of manifest sealing |
| `approved_source_host` | `str` | Hostname verified against connector allowlist |
| `source_url` | `str` | Request URL sanitized of credentials and sensitive query parameters |
| `final_url` | `str` | Final URL after redirect hops (credentials stripped) |
| `redirect_chain_summary` | `list[dict]` | Redacted list of redirect hops with status codes |
| `request_method` | `str` | HTTP request method (`GET`, `POST`, `LOCAL_FILE`) |
| `http_status` | `int \| str` | Final HTTP status code or failure category |
| `content_type` | `str` | Response MIME type (e.g. `application/rss+xml`) |
| `response_bytes` | `int` | Exact byte count of retrieved payload |
| `response_sha256` | `str` | SHA-256 digest of raw retrieved bytes |
| `staged_payload_ref` | `dict` | Reference metadata to `.data/raw_feeds/` (never raw content) |
| `parse_status` | `str` | Parsing outcome (`SUCCESS`, `PARTIAL`, `FAILED`, `NOT_MODIFIED`) |
| `parser_warning_codes` | `list[str]` | Safe warning codes (e.g. `MALFORMED_FEED_SYNTAX`) |
| `normalized_record_ids` | `list[str]` | List of generated `SRC-*` IDs |
| `normalized_record_count`| `int` | Count of successfully normalized records |
| `duplicate_summary` | `dict[str, int]`| Tier 1–4 deduplication result breakdown |
| `retry_summary` | `dict` | Attempts count, cumulative wait seconds, retried flag |
| `validation_warning_codes`| `list[str]`| Security/validation warning codes (e.g. `QUARANTINED_INJECTION_SIGNAL`)|
| `previous_manifest_sha256`| `str \| None`| Hash of previous finalized manifest (null for genesis) |
| `manifest_sha256` | `str` | Cryptographic SHA-256 digest of canonical manifest body |

---

## 3. Sequential Hash-Chaining Protocol

All finalized manifests form a strictly ordered sequential hash chain within a designated `chain_scope`:

1. **Genesis Rule**: The first manifest in a chain scope must have `previous_manifest_sha256 = None`.
2. **Sequential Linkage Rule**: For every manifest $M_i$ ($i > 0$), $M_i.\text{previous\_manifest\_sha256} = M_{i-1}.\text{manifest\_sha256}$.
3. **No Self-Links**: Under no circumstances may $M.\text{previous\_manifest\_sha256} == M.\text{manifest\_sha256}$.
4. **Fork Prohibition**: If an incoming manifest claims a previous hash that has already been superseded by another manifest in the same scope, a `ManifestForkError` is raised immediately.
5. **Corrections & Reprocessing**: If an earlier run is disputed or re-analyzed, the original manifest remains intact and immutable. A new corrective manifest is appended with status `SUPERSEDED` or `CORRECTION`, referencing the preceding head manifest.

---

## 4. Verification CLI and Anomaly Detection

Integrity is validated via automated CLI targets:
```bash
make verify-provenance-chain
make verify-provenance-chain-dry-run
```

### Anomaly Types Detected
- `ALTERED_MANIFEST_HASH`: Recomputed canonical SHA-256 does not match stored hash.
- `BROKEN_CHAIN_LINKAGE`: `previous_manifest_sha256` does not match preceding manifest hash.
- `GENESIS_PREVIOUS_HASH_NOT_NULL`: First manifest in chain has a non-null previous hash.
- `SELF_LINK_DETECTED`: Manifest points to its own digest.
- `DUPLICATE_MANIFEST_ID`: Reused `manifest_id` detected in chain.
- `TIMESTAMP_ANOMALY`: `finalized_at` is earlier than `started_at`.
- `SCHEMA_VERSION_MISMATCH`: Manifest uses an unrecognized schema version.

### Safe Redaction Standard
The verification tool emits a structured JSON report that **strictly excludes**:
- Raw payload content or article text.
- API keys, credentials, or bearer tokens.
- Absolute server paths or user directories.
- Internal authorization headers or session cookies.
