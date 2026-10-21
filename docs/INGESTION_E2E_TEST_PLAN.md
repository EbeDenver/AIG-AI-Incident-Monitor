# END-TO-END INGESTION TEST PLAN & VERIFICATION MATRIX
**Project:** AI Incident Monitor  
**Organization:** AI Guardians LLC  
**Document Identifier:** TST-003  
**Version:** 1.0.0  
**Effective Date:** 2026-10-20  
**Governing Charter:** [Project Constitution](PROJECT_CONSTITUTION.md), [ADR-008](DECISIONS.md#adr-008), [ADR-010](DECISIONS.md#adr-010), [ADR-011](DECISIONS.md#adr-011)  

---

## 1. Test Strategy Overview

The Phase 4 integration test suite exercises the complete source-ingestion lifecycle:
$$\text{Approved Host} \longrightarrow \text{SecureHTTPClient} \longrightarrow \text{Staging Store} \longrightarrow \text{Parser} \longrightarrow \text{Envelope} \longrightarrow \text{Deduplication} \longrightarrow \text{Manifest Chaining} \longrightarrow \text{Audit Log}$$

All integration tests are executed **strictly offline** using local in-memory fixtures or controlled mock responses. Zero live network calls occur in CI test runs.

---

## 2. 21-Point Verification Matrix

| # | Test Identifier | Subsystem Exercised | Status | Result / Evidence |
| :---: | :--- | :--- | :---: | :--- |
| **01** | `test_01_happy_path_valid_rss_feed_ingestion` | Full Pipeline | **PASSED** | Valid RSS 2.0 ingested, staged, enveloped, chained (genesis manifest). |
| **02** | `test_02_atom_feed_ingestion` | Full Pipeline | **PASSED** | Valid Atom 1.0 XML parsed and enveloped cleanly. |
| **03** | `test_03_malformed_feed_with_safe_failure_partial_run_state` | Resilient Parsing | **PASSED** | Incomplete XML logged with `MALFORMED_FEED_SYNTAX`, chain intact. |
| **04** | `test_04_oversized_compressed_and_decompressed_payload_rejection` | Content Limits | **PASSED** | Payload > 5MB rejected via `PayloadTooLargeError`. |
| **05** | `test_05_redirect_to_disallowed_host_or_private_ip_rejection` | Redirect Inspector | **PASSED** | Redirect to metadata IP (`169.254.169.254`) blocked via `BlockedIPError`. |
| **06** | `test_06_dns_rebinding_and_connection_pinning_regression` | Security Core | **PASSED** | IP change between DNS check and connect blocked via pinning. |
| **07** | `test_07_etag_and_last_modified_conditional_retrieval` | Connector Policy | **PASSED** | HTTP 304 produces 0-byte manifest with status `COMPLETED`. |
| **08** | `test_08_429_retry_after_behavior` | Rate Limiter | **PASSED** | `Retry-After: 5` honored; backoff delay adjusted to 5.0s. |
| **09** | `test_09_503_timeout_retry_behavior_and_retry_cap` | Backoff Policy | **PASSED** | Retries 3 times on 503, halts at retry cap without hanging. |
| **10** | `test_10_duplicate_and_near_duplicate_incident_routing` | Deduplication | **PASSED** | Identical title routed to Tier 3 candidate review queue. |
| **11** | `test_11_rss_item_with_unsafe_html_scripts_iframes_and_formula_content` | Sanitization | **PASSED** | `<script>`/`<iframe>` stripped; `=CMD(...)` neutralized to `'=CMD(...)`. |
| **12** | `test_12_xml_entity_dtd_xinclude_excessive_nesting_huge_attribute_and_malicious_unicode` | XML Containment | **PASSED** | DTD entity bomb blocked via `FORBIDDEN_ENTITY_OR_DTD`. |
| **13** | `test_13_direct_and_indirect_prompt_injection_source_text` | Injection Detector | **PASSED** | "Ignore instructions" triggers `INJ-OVERRIDE-INSTRUCTION` & quarantine. |
| **14** | `test_14_demonstration_that_prompt_labels_do_not_authorize_actions` | LLM Contract | **PASSED** | `[SYSTEM]` text blocked from executing privileged actions. |
| **15** | `test_15_raw_stage_enabled_and_raw_stage_disabled_modes` | Staging Store | **PASSED** | Staging disabled writes no file; staging enabled writes `.raw`. |
| **16** | `test_16_raw_payload_expiration_and_manual_purge_dry_run` | Retention Purge | **PASSED** | Payloads > 30 days flagged as candidates; dry run preserves files. |
| **17** | `test_17_manifest_generation_and_hash_chain_verification` | Provenance Chain | **PASSED** | Sequential run builds valid 2-node chain verified by `verify_provenance_chain`. |
| **18** | `test_18_tampered_manifest_detection` | Verification CLI | **PASSED** | Mutating response size triggers `ALTERED_MANIFEST_HASH`. |
| **19** | `test_19_missing_manifest_altered_previous_hash_self_reference_and_fork_detection` | Verification CLI | **PASSED** | Gaps in sequence trigger `BROKEN_CHAIN_LINKAGE`. |
| **20** | `test_20_proof_no_full_article_bodies_raw_payloads_secrets_in_logs_or_db` | Git / DB Hygiene | **PASSED** | Manifests, database models, and logs confirmed free of raw bodies & secrets. |
| **21** | `test_21_repeatability_deterministic_normalized_output_and_canonical_manifest` | Determinism | **PASSED** | Same fixture produces identical normalized items & SHA-256 digests. |

---

## 3. Test Execution Summary

```bash
.venv/bin/pytest backend/tests/integration/test_ingestion_e2e_pipeline.py -v
============================== 21 passed in 3.76s ==============================
```
All 21 test scenarios pass with zero failures and zero network calls.
