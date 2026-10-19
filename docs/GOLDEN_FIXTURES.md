# GOLDEN FIXTURE REGISTRY & VALIDATION SPECIFICATION
**Project:** AI Incident Monitor
**Organization:** AI Guardians LLC
**Document Identifier:** FIXT-001
**Version:** 1.0.0
**Effective Date:** 2026-10-07
**Status:** ACTIVE SPECIFICATION
**Governing Charter:** [Project Constitution](PROJECT_CONSTITUTION.md)
**Parent Traceability:** [Requirements Traceability Matrix](REQUIREMENTS_TRACEABILITY.md)

---

## 1. Overview and Fixture Hygiene

In strict adherence to **Constitutional Rule 16** (Git Hygiene & Copyright Compliance) and **Requirement PRI-004** (Sanitized Synthetic Fixtures), the test suite does not store raw copyrighted news articles, customer PII, or actual unadjudicated incident documents in Git.

Instead, Phase 2 implements a comprehensive registry of **29 sanitized, synthetic golden test fixtures**:
- **22 Valid Golden Fixtures** (`backend/tests/fixtures/golden/`): Demonstrate every valid state across the domain taxonomy.
- **7 Invalid Negative Fixtures** (`backend/tests/fixtures/invalid/`): Explicitly trigger and verify constitutional validation errors.

### Demonstration Notice Banner
Every single fixture JSON file carries the top-level immutable banner:
```json
"demonstration_notice": "DEMONSTRATION DATA — NOT A REAL INCIDENT"
```
This guarantees that automated scrapers or external readers never confuse test scenarios with real-world incident assessments.

---

## 2. Valid Golden Fixtures Inventory (`tests/fixtures/golden/`)

| # | Fixture File | Target Model | Constitutional Rules Verified | Description & Key Invariants |
| :-: | :--- | :--- | :--- | :--- |
| **01** | `01_confirmed_fact_with_evidence.json` | `ClaimRecord` | Rule 1, 3, 4 | Confirmed empirical finding anchored to valid `evidence_ids`. |
| **02** | `02_single_source_allegation.json` | `ClaimRecord` | Rule 3 | Unverified lawsuit allegation with explicit `asserting_entity`. |
| **03** | `03_primary_and_independent_reporting.json` | `SourceReference` | Rule 4, 16 | Primary source disclosure with verified SHA-256 content hash. |
| **04** | `04_disputed_claim_bilateral_evidence.json` | `ClaimRecord` | Rule 3, 4 | Claim in `DISPUTED` state supported by competing evidentiary sources. |
| **05** | `05_unknown_financial_impact.json` | `MonetaryAmount` | Rule 2 | Explicit `UNKNOWN` monetary impact where `amount` is strictly `null`. |
| **06** | `06_confirmed_zero_financial_impact.json` | `MonetaryAmount` | Rule 2 | `CONFIRMED_ZERO` loss with mandatory affirmative `evidence_id`. |
| **07** | `07_monetary_range_original_currency.json` | `MonetaryAmount` | Rule 2 | Bounded loss range (`range_min`/`range_max`) with ISO 4217 currency. |
| **08** | `08_currency_converted_with_provenance.json` | `MonetaryAmount` | Rule 2 | Converted currency with full `CurrencyConversionRecord` audit trail. |
| **09** | `09_possible_ai_causal_contribution.json` | `CausalAssessment` | Rule 5, 6 | Explicit causal assessment distinguishing actual vs potential harm. |
| **10** | `10_ai_involvement_alleged_unestablished.json` | `AIInvolvementAssessment` | Rule 3, 6 | AI involvement alleged by external party, not established as root cause. |
| **11** | `11_corrected_source_report.json` | `ClaimRecord` | Rule 10, 16 | Corrected claim with explicit `correction_rationale` and lineage. |
| **12** | `12_superseded_claim_reference.json` | `ClaimRecord` | Rule 10, 16 | Superseded claim linking to successor `replaces_claim_id`. |
| **13** | `13_syndicated_reports_shared_origin.json` | `SourceReference` | Rule 4 | Wire-service republication linked back to `original_source_id`. |
| **14** | `14_paywalled_source_reference.json` | `SourceReference` | Rule 4, 16 | Paywalled source marked `is_paywalled=true` with fair-use snippet. |
| **15** | `15_broken_source_with_archive.json` | `SourceReference` | Rule 4 | Dead link preserved with valid Wayback Machine `archive_url`. |
| **16** | `16_approximate_incident_date.json` | `DateWithPrecision` | Rule 2 | Approximate incident timing with year/month and descriptive context. |
| **17** | `17_unknown_incident_date.json` | `DateWithPrecision` | Rule 2 | Completely unknown date where all numeric date fields are strictly `null`. |
| **18** | `18_material_numeric_claim_with_evidence.json` | `ClaimRecord` | Rule 5 | Material quantitative claim supported by empirical evidence linkage. |
| **19** | `19_human_approved_record.json` | `HumanReviewRecord` | Rule 14, 15 | Published review completed by authenticated human (`is_human=true`). |
| **20** | `20_machine_recommended_unapproved.json` | `AuditMetadata` | Rule 14 | Model inference recommendation with `human_approved=false`. |
| **21** | `21_multi_type_uncertainty_record.json` | `UncertaintyRecord` | Rule 2, 3 | Multi-faceted uncertainty record isolating missing from disputed facts. |
| **22** | `22_inert_prompt_injection_content.json` | `EvidenceRecord` | Rule 12 | Malicious adversarial prompt text treated safely as inert quote data. |

---

## 3. Deliberately Invalid Negative Fixtures (`tests/fixtures/invalid/`)

These negative fixtures prove that the Pydantic v2 validators actively defend constitutional boundaries:

| # | Fixture File | Target Model | Intended Failure Trigger | Expected Exception |
| :-: | :--- | :--- | :--- | :--- |
| **01** | `01_numeric_claim_missing_evidence.json` | `ClaimRecord` | Material numeric claim (`FINANCIAL_IMPACT`) with empty `evidence_ids`. | `UngroundedClaimError` (Rule 5 violation) |
| **02** | `02_confirmed_claim_missing_evidence.json` | `ClaimRecord` | Claim marked `CONFIRMED_FACT` with empty `evidence_ids`. | `UngroundedClaimError` (Rule 4 violation) |
| **03** | `03_causal_claim_missing_status.json` | `ClaimRecord` | `CAUSAL_ASSERTION` missing mandatory `causal_assessment` sub-model. | `ValidationError` (Field required) |
| **04** | `04_unknown_money_as_zero.json` | `MonetaryAmount` | Monetary status `UNKNOWN` with `amount = 0.00`. | `InvalidMonetaryStateError` (Rule 2 violation) |
| **05** | `05_llm_confirmed_legal_claim.json` | `ClaimRecord` | Legal finding marked `CONFIRMED_FACT` without human approval. | `ConstitutionalViolationError` (Rule 7/11 violation) |
| **06** | `06_superseded_missing_replacement.json` | `ClaimRecord` | Claim with `superseded_by_claim_id` but missing `supersedes_claim_id` or `replaces_claim_id`. | `ValidationError` (Value error) |
| **07** | `07_syndicated_missing_origin.json` | `SourceReference` | `SYNDICATED_COPY` source missing mandatory `original_source_id`. | `ValidationError` (Value error) |

---

## 4. Test Harness Integration

The fixture suite is verified via `backend/tests/unit/test_fixtures.py`:
- **Positive Test Matrix**: Automatically iterates over all 22 golden fixtures, instantiates their respective domain models, and asserts valid deserialization.
- **Negative Test Matrix**: Executes targeted test cases for all 7 invalid fixtures, confirming that validation exceptions are raised with precise constitutional error messages.
