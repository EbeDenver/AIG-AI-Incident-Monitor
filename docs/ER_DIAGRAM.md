# Relational Entity-Relationship (ER) Diagram
**Project:** AI Incident Monitor
**Organization:** AI Guardians LLC
**Document Identifier:** DOC-ERD-001
**Milestone:** Phase 5 Increment 1 (AIG-ISI Severity Foundation)
**Status:** ACTIVE

---

## 1. Relational Database Schema Overview

The AI Incident Monitor persistence foundation comprises 15 relational tables managed via SQLAlchemy 2.0 ORM and Alembic migrations:
- **Core Entities**: `incidents`, `claims`, `evidence_records`, `source_references`, `quote_spans`, `claim_evidence_links`
- **Epistemic & Causal Layer**: `causal_assessments`, `ai_involvement_assessments`, `uncertainty_records`, `disputed_facts`
- **Assessment & Severity Layer**: `severity_assessments`
- **Ingestion & Deduplication Layer**: `raw_import_records`, `dedup_candidates`
- **Governance & Audit Trail**: `human_review_records`, `audit_logs`

---

## 2. Mermaid Entity-Relationship Diagram

```mermaid
erDiagram
    incidents ||--o{ claims : "has"
    incidents ||--o{ ai_involvement_assessments : "has"
    incidents ||--o{ uncertainty_records : "has"
    incidents ||--o{ severity_assessments : "evaluated_by"
    incidents ||--o{ dedup_candidates : "matched_in"

    claims ||--o{ claim_evidence_links : "grounded_by"
    claims ||--o{ causal_assessments : "specifies"
    claims ||--o{ disputed_facts : "subject_to"

    evidence_records ||--o{ claim_evidence_links : "supports"
    evidence_records ||--o{ quote_spans : "contains"
    source_references ||--o{ evidence_records : "published_in"

    severity_assessments ||--o{ human_review_records : "governed_by"
    severity_assessments ||--o| severity_assessments : "supersedes"

    raw_import_records ||--o{ incidents : "ingested_into"

    incidents {
        string id PK
        string title
        text summary
        string status
        string incident_date_precision
        date incident_exact_date
        datetime created_at
        datetime updated_at
    }

    severity_assessments {
        string id PK
        string incident_id FK
        string methodology_version
        float actual_normalized_score
        float actual_lower_bound
        float actual_upper_bound
        float actual_completeness_pct
        string actual_tier
        string actual_confidence
        float potential_normalized_score
        float potential_lower_bound
        float potential_upper_bound
        float potential_completeness_pct
        string potential_tier
        string potential_confidence
        json dimension_scores
        string review_state
        json review_gates_triggered
        boolean is_pending_review
        boolean has_disputed_facts
        json overrides
        string supersedes_assessment_id
        string superseded_by_id
        datetime created_at
        datetime updated_at
    }

    claims {
        string id PK
        string incident_id FK
        string claim_text
        string claim_type
        string epistemic_status
        datetime created_at
    }

    evidence_records {
        string id PK
        string source_id FK
        string evidence_type
        string confidence_level
        datetime created_at
    }

    source_references {
        string id PK
        string canonical_url
        string source_type
        string source_authority
        string content_sha256
        datetime created_at
    }

    audit_logs {
        int id PK
        string entity_type
        string entity_id
        string action
        string actor_id
        boolean is_model_generated
        json payload_before
        json payload_after
        datetime recorded_at
    }
```
