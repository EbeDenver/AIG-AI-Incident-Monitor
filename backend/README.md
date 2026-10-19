# AI Incident Monitor — Backend Domain Layer

**Organization:** AI Guardians LLC
**Milestone:** Phase 2 (Core Epistemic Schemas, Pydantic v2 Domain Models, and Golden Fixtures)
**Parent Charter:** [`docs/PROJECT_CONSTITUTION.md`](../docs/PROJECT_CONSTITUTION.md)

---

## Overview

The `backend` package houses the core domain models and epistemic foundations of the AI Incident Monitor. These models mathematically and logically encode the 17 non-negotiable constitutional rules governing the representation of facts, allegations, claims, evidence, sources, uncertainty, causality, reviews, and audit trails.

## Package Architecture

```
src/
└── ai_incident_monitor/
    ├── __init__.py
    └── domain/
        ├── __init__.py            # Clean exports of domain entities and vocabularies
        ├── common.py              # BaseEntity, SchemaVersioned, LifecycleMetadata, Exceptions
        ├── identifiers.py         # Strongly typed IDs (SourceId, EvidenceId, ClaimId, IncidentId)
        ├── vocabularies.py        # The 18 Controlled Vocabularies (Enums)
        ├── dates.py               # DateWithPrecision (Exact, Month, Year, Approximate, Range, Unknown)
        ├── money.py               # MonetaryAmount (Unknown is null, Confirmed Zero requires evidence)
        ├── sources.py             # SourceReference, ContentHash, CopyrightRestrictions
        ├── evidence.py            # EvidenceRecord, QuoteSpan, ProvenanceRecord
        ├── claims.py              # ClaimRecord (Materiality, Epistemic status, Causal & Numeric indicators)
        ├── uncertainty.py         # UncertaintyRecord, DisputedFact
        ├── causality.py           # CausalAssessment, AIInvolvementAssessment
        ├── reviews.py             # HumanReviewRecord, ReviewerIdentity
        ├── audit.py               # AuditMetadata, ModelInferenceMetadata
        └── export_schemas.py      # JSON Schema export utility (Draft 2020-12)
```

## Running Tests

From the `backend` directory:

```bash
pytest -v
```
