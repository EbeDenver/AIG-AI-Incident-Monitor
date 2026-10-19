# PHASE 2 DOMAIN SCHEMA SPECIFICATION
**Project:** AI Incident Monitor
**Organization:** AI Guardians LLC
**Document Identifier:** SPEC-001
**Version:** 1.0.0
**Effective Date:** 2026-10-07
**Status:** RATIFIED & IMPLEMENTED
**Governing Charter:** [Project Constitution](PROJECT_CONSTITUTION.md)
**Parent Traceability:** [Requirements Traceability Matrix](REQUIREMENTS_TRACEABILITY.md)

---

## 1. Overview and Architectural Scope

This document provides the formal technical specification for the core epistemic domain models, value objects, and deterministic validation rules implemented in **Phase 2: Core Epistemic Schemas, Pydantic v2 Domain Models, and Golden Fixtures**.

The schemas defined herein establish the software-level enforcement of the **17 Non-Negotiable Rules** set forth in [`docs/PROJECT_CONSTITUTION.md`](PROJECT_CONSTITUTION.md). All models are implemented in Python 3.11+ using **Pydantic v2.7+** and provide strict JSON Schema Draft 2020-12 generation.

### 1.1 Invariant Architecture
All domain models strictly adhere to four foundational constraints:
1. **Immutability**: Every entity is configured with `frozen = True` (`model_config = ConfigDict(frozen=True, extra="forbid")`), preventing in-place state mutation.
2. **Strict Attribute Admission**: `extra = "forbid"` prohibits unmodeled attributes, preventing schema drift or accidental payload injection.
3. **Semantic Schema Versioning**: Every major entity inherits from `SchemaVersioned` carrying an immutable `schema_version = "1.0.0"`.
4. **Epistemic Tri-State Integrity**: Missing or unverified data remains explicitly `None` or an explicit `UNKNOWN` enum state; coercion to `0` or false defaults is mathematically barred.

---

## 2. Core Entities and Value Objects

```
┌────────────────────────────────────────────────────────┐
│                   BaseEntity                           │
│  - frozen=True, extra="forbid"                         │
│  - demonstration_notice: Optional[str]                 │
└──────────────────────────┬─────────────────────────────┘
                           │
             ┌─────────────┴─────────────┐
             ▼                           ▼
   SchemaVersioned (1.0.0)         Value Objects
   - SourceReference               - ContentHash (SHA-256)
   - EvidenceRecord                - QuoteSpan (char offsets)
   - ClaimRecord                   - ReviewerIdentity (is_human=True)
   - CausalAssessment              - MonetaryAmount
   - AIInvolvementAssessment       - DateWithPrecision
   - UncertaintyRecord             - DateRange
   - HumanReviewRecord             - ModelInferenceMetadata
   - AuditMetadata                 - CurrencyConversionRecord
```

---

### 2.1 Identifiers (`domain/identifiers.py`)
Strongly typed, prefixed UUID-backed identifiers prevent cross-entity reference confusion:

| Identifier Type | Prefix Format | Example | Description |
| :--- | :--- | :--- | :--- |
| `SourceId` | `src-[0-9a-f]{8}` | `src-a1b2c3d4` | External source reference identifier |
| `EvidenceId` | `evd-[0-9a-f]{8}` | `evd-b2c3d4e5` | Verifiable evidentiary artifact identifier |
| `ClaimId` | `clm-[0-9a-f]{8}` | `clm-c3d4e5f6` | Discrete factual, analytical, or legal assertion identifier |
| `IncidentId` | `inc-[0-9a-f]{8}` | `inc-d4e5f6a7` | Root incident dossier identifier |
| `ReviewId` | `rev-[0-9a-f]{8}` | `rev-e5f6a7b8` | Human review sign-off record identifier |
| `UncertaintyId` | `unc-[0-9a-f]{8}` | `unc-f6a7b8c9` | Discrete uncertainty or disputed fact record identifier |

---

### 2.2 Controlled Vocabularies (`domain/vocabularies.py`)
All domain states are governed by 22 explicit, string-backed enumeration types:

1. **`EpistemicStatus`**: `CONFIRMED_FACT`, `UNVERIFIED_ALLEGATION`, `TECHNICAL_ANALYSIS`, `STATED_UNCERTAINTY`, `EDITORIAL_OPINION`, `DISPUTED`.
2. **`ClaimType`**: `FACTUAL_EVENT`, `CAUSAL_ASSERTION`, `FINANCIAL_IMPACT`, `TECHNICAL_FAILURE`, `LEGAL_FINDING`, `SAFETY_IMPACT`, `GOVERNANCE_SCREENING`.
3. **`SourceAuthority`**: `REGULATORY_AGENCY`, `JUDICIAL_RECORD`, `PEER_REVIEWED_RESEARCH`, `PRIMARY_DISCLOSURE`, `INVESTIGATIVE_JOURNALISM`, `REPUTABLE_NEWS`, `CORPORATE_STATEMENT`, `INDUSTRY_ANALYSIS`, `SOCIAL_MEDIA`, `UNVERIFIED_SUBMISSION`.
4. **`HarmType`**: `PHYSICAL_INJURY`, `LOSS_OF_LIFE`, `PSYCHOLOGICAL_HARM`, `DISCRIMINATION_CIVIL_RIGHTS`, `PRIVACY_VIOLATION`, `FINANCIAL_LOSS`, `INFRASTRUCTURE_DISRUPTION`, `DEMOCRATIC_DISRUPTION`, `REPUTATIONAL_DAMAGE`, `NO_DEMONSTRATED_HARM`, `UNKNOWN_HARM`.
5. **`MonetaryAmountStatus`**: `UNKNOWN`, `CONFIRMED_ZERO`, `EXACT_KNOWN`, `RANGE_KNOWN`.
6. **`DatePrecision`**: `EXACT_DAY`, `MONTH`, `YEAR`, `RANGE`, `APPROXIMATE`, `UNKNOWN`.
7. **`ReviewStatus`**: `APPROVED_FOR_PUBLICATION`, `REJECTED`, `REVISION_REQUIRED`, `HOLD_PENDING_INVESTIGATION`.
8. **`SyndicationType`**: `ORIGINAL_REPORTING`, `SYNDICATED_COPY`, `AGGREGATOR_SUMMARY`, `PARAPHRASED_REFERENCE`.
9. **`UncertaintyType`**: `MISSING_INFORMATION`, `CONFLICTING_REPORTS`, `UNVERIFIED_ATTRIBUTION`, `PRELIMINARY_FINDING`, `UNCONFIRMED_CASUALTIES`.

---

### 2.3 Source Reference (`domain/sources.py`)
Governed by Constitutional Rule 4 (Mandatory Evidence Linkage) and Rule 16 (Copyright Compliance).

```python
class SourceReference(SchemaVersioned):
    source_id: SourceId
    canonical_url: HttpUrl
    archive_url: Optional[HttpUrl] = None
    title: str
    author: Optional[str] = None
    publisher: str
    publication_date: DateWithPrecision
    authority: SourceAuthority
    is_paywalled: bool = False
    content_hash: ContentHash
    syndication_type: SyndicationType = SyndicationType.ORIGINAL_REPORTING
    original_source_id: Optional[SourceId] = None
    copyright_restriction: CopyrightRestriction = CopyrightRestriction.FAIR_USE_SNIPPET_ONLY
```

**Validation Invariants**:
- `canonical_url` must use `http` or `https` schemes.
- If `syndication_type` is `SYNDICATED_COPY`, `original_source_id` is mandatory to trace back to primary reporting.
- `content_hash` requires a valid 64-character lowercase hex string (`^[a-f0-9]{64}$`).
- Raw article bodies are excluded from the schema, ensuring compliance with [`docs/DATA_GOVERNANCE.md`](DATA_GOVERNANCE.md).

---

### 2.4 Evidence Record and Quote Span (`domain/evidence.py`)
Governed by Constitutional Rule 1 (Zero Fabrication) and Rule 4 (Mandatory Evidence Linkage).

```python
class QuoteSpan(BaseEntity):
    exact_text: str
    start_char_offset: int
    end_char_offset: int
```

**Validation Invariants**:
- `start_char_offset >= 0` and `end_char_offset > start_char_offset`.
- `len(exact_text) == (end_char_offset - start_char_offset)`.
- Direct quotes cannot be zero-length or fabricated.

```python
class EvidenceRecord(SchemaVersioned):
    evidence_id: EvidenceId
    source_id: SourceId
    quote_spans: list[QuoteSpan] = Field(default_factory=list)
    summary: str
    confidence: EvidenceConfidence
    provenance: ProvenanceRecord
```

---

### 2.5 Claim Record (`domain/claims.py`)
Governed by Constitutional Rules 1, 3, 4, 5, 7, 10, 11, and 16.

```python
class ClaimRecord(SchemaVersioned):
    claim_id: ClaimId
    claim_text: str
    claim_type: ClaimType
    epistemic_status: EpistemicStatus
    evidence_ids: list[EvidenceId] = Field(default_factory=list)
    asserting_entity: Optional[str] = None
    causal_assessment: Optional[CausalAssessment] = None
    human_approved: bool = False
    human_review_id: Optional[ReviewId] = None
    supersedes_claim_id: Optional[ClaimId] = None
    superseded_by_claim_id: Optional[ClaimId] = None
    replaces_claim_id: Optional[ClaimId] = None
    correction_rationale: Optional[str] = None
```

**Validation Invariants**:
- **Rule 4 Enforcement**: If `epistemic_status == CONFIRMED_FACT`, `evidence_ids` cannot be empty.
- **Rule 5 Enforcement**: If `claim_type == FINANCIAL_IMPACT`, `evidence_ids` cannot be empty.
- **Rule 6 Enforcement**: If `claim_type == CAUSAL_ASSERTION`, `causal_assessment` is required.
- **Rule 7 & 11 Enforcement**: If `claim_type == LEGAL_FINDING` and `epistemic_status == CONFIRMED_FACT`, `human_approved` must be `True` with valid `human_review_id`. Automated agents cannot declare confirmed legal violations without judicial citation and human review.
- **Rule 10 Enforcement**: If `superseded_by_claim_id` is provided, `supersedes_claim_id` or `replaces_claim_id` tracks evolution; corrected claims require a `correction_rationale`.

---

### 2.6 Monetary Amount (`domain/money.py`)
Governed by Constitutional Rule 2 (Unknown Is Not Zero) and Rule 9 (Prohibition on Monetizing Dignity).

```python
class MonetaryAmount(BaseEntity):
    status: MonetaryAmountStatus
    amount: Optional[Decimal] = None
    range_min: Optional[Decimal] = None
    range_max: Optional[Decimal] = None
    currency: Optional[CurrencyCode] = None
    evidence_id: Optional[EvidenceId] = None
    conversion_record: Optional[CurrencyConversionRecord] = None
```

**Validation Invariants**:
- **Rule 2**: If `status == UNKNOWN`, `amount`, `range_min`, and `range_max` must be `None`. Coercing unknown financial damage to `0.00` raises `InvalidMonetaryStateError`.
- **Zero Proof**: If `status == CONFIRMED_ZERO`, `amount` must be `0.00` AND `evidence_id` must be present. A zero damage finding is invalid without an affirmative source proving zero losses.
- If `status == EXACT_KNOWN`, `amount` is required, `amount > 0`, and `currency` is mandatory.
- If `status == RANGE_KNOWN`, `range_min <= range_max`, and `currency` is mandatory.

---

### 2.7 Date Representation (`domain/dates.py`)
Governed by Constitutional Rule 2 (Unknown Is Not Zero).

```python
class DateWithPrecision(BaseEntity):
    precision: DatePrecision
    exact_date: Optional[date] = None
    year: Optional[int] = None
    month: Optional[int] = None
    range_start: Optional[date] = None
    range_end: Optional[date] = None
    approximate_description: Optional[str] = None
```

**Validation Invariants**:
- If `precision == UNKNOWN`, all numeric date attributes must be `None`.
- If `precision == EXACT_DAY`, `exact_date` is mandatory.
- If `precision == RANGE`, `range_start <= range_end`.

---

### 2.8 Human Review and Reviewer Identity (`domain/reviews.py`)
Governed by Constitutional Rule 14 (LLM Shall Not Approve Itself) and Rule 15 (Human-in-the-Loop Sign-off).

```python
class ReviewerIdentity(BaseEntity):
    reviewer_id: str
    full_name: str
    email: EmailStr
    role: str
    is_human: bool = True
```

**Validation Invariants**:
- `is_human` must be strictly `True`. Attempting to register an automated agent (`is_human=False`) raises `ReviewerNotHumanError`.

```python
class HumanReviewRecord(SchemaVersioned):
    review_id: ReviewId
    reviewer: ReviewerIdentity
    reviewed_at: datetime
    status: ReviewStatus
    reviewed_claim_ids: list[ClaimId] = Field(default_factory=list)
    review_notes: str
    checklist_verified: bool = True
```

**Validation Invariants**:
- Review cannot be in an unfinalized draft state; must be an explicit final status (`APPROVED_FOR_PUBLICATION`, `REJECTED`, etc.).

---

### 2.9 Machine Recommendations and Audit Metadata (`domain/audit.py`)
Governed by Gate 4 (Separation of Machine Recommendations from Human Approvals).

```python
class ModelInferenceMetadata(BaseEntity):
    model_name: str
    model_family: str
    temperature: float
    prompt_digest: str
    execution_timestamp: datetime
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    latency_ms: Optional[float] = None
```

```python
class AuditMetadata(BaseEntity):
    incident_id: IncidentId
    current_stage: PipelineStage
    stages_completed: list[PipelineStage] = Field(default_factory=list)
    machine_recommended_status: Optional[str] = None
    machine_confidence: Optional[float] = None
    machine_recommendation_timestamp: Optional[datetime] = None
    inference_metadata: Optional[ModelInferenceMetadata] = None
    human_approved: bool = False
    human_review_id: Optional[ReviewId] = None
```

**Validation Invariants**:
- `machine_recommended_status` and `human_approved` are completely separate fields.
- A machine recommendation never implies or sets human approval.
- Full inference provenance (`model_name`, `prompt_digest`, `temperature`) is captured.

---

## 3. JSON Schema Generation

The export utility `export_schemas.py` provides programmatic export of JSON Schemas for all domain models:
- Target Standard: **JSON Schema Draft 2020-12** (`model_json_schema()`).
- All enums emit string value constraints.
- Field descriptions, regex patterns, and nested definitions are completely preserved.

---

## 4. Verification and Compliance Matrix

| Requirement | Schema Model | Validation Rule | Test Module |
| :--- | :--- | :--- | :--- |
| **EVD-001** (Zero Fabrication) | `EvidenceRecord`, `QuoteSpan` | Verbatim text offset matching | `test_evidence.py` |
| **EVD-002** (Unknown Is Not Zero) | `MonetaryAmount`, `DateWithPrecision` | Rejection of 0 for unknown | `test_money.py`, `test_dates.py` |
| **EVD-003** (Claim Classification) | `ClaimRecord` | 5-way epistemic typing | `test_claims.py` |
| **EVD-004** (Evidence Linkage) | `ClaimRecord` | Mandatory evidence for facts | `test_claims.py` |
| **SEV-004** (Actual vs Potential) | `CausalAssessment` | Distinct harm type categorization | `test_causality.py` |
| **SEV-005** (Non-Monetization) | `MonetaryAmount` | Monetary damages isolated to economic loss | `test_money.py` |
| **AUD-001** (No LLM Self-Approval) | `ReviewerIdentity` | Strict `is_human=True` check | `test_reviews.py` |
| **PRI-002** (No Raw Scraped Git) | `SourceReference` | Raw body excluded; SHA-256 only | `test_sources.py` |
