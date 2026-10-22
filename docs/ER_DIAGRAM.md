# Relational Entity-Relationship (ER) Diagram
**Project:** AI Incident Monitor
**Organization:** AI Guardians LLC
**Document Identifier:** DOC-ERD-001
**Milestone:** Phase 5 Increment 2C-1 (EU AI Act Informational Relevance Screen Foundation)
**Status:** ACTIVE

---

## 1. Relational Database Schema Overview

The AI Incident Monitor persistence foundation comprises 22 relational tables managed via SQLAlchemy 2.0 ORM and Alembic migrations:
- **Core Entities**: `incidents`, `claims`, `evidence_records`, `source_references`, `quote_spans`, `claim_evidence_links`
- **Epistemic & Causal Layer**: `causal_assessments`, `ai_involvement_assessments`, `uncertainty_records`, `disputed_facts`
- **Assessment & Severity Layer**: `severity_assessments`
- **Governance Framework Mapping Layer (Migrations 003, 004, 005)**: `framework_reference_sets`, `framework_controls`, `incident_framework_mappings`, `eu_legal_relevance_screens`, `eu_screen_rule_traces`, `mapping_evidence_links`, `governance_audit_logs`
- **Ingestion & Deduplication Layer**: `raw_import_records`, `dedup_candidates`
- **Governance & Audit Trail**: `human_review_records`, `audit_logs`, `governance_audit_logs`

---

## 2. Mermaid Entity-Relationship Diagram

```mermaid
erDiagram
    incidents ||--o{ claims : "has"
    incidents ||--o{ ai_involvement_assessments : "has"
    incidents ||--o{ uncertainty_records : "has"
    incidents ||--o{ severity_assessments : "evaluated_by"
    incidents ||--o{ dedup_candidates : "matched_in"
    incidents ||--o{ incident_framework_mappings : "mapped_to"
    incidents ||--o{ eu_legal_relevance_screens : "screened_by"

    claims ||--o{ claim_evidence_links : "grounded_by"
    claims ||--o{ causal_assessments : "specifies"
    claims ||--o{ disputed_facts : "subject_to"

    evidence_records ||--o{ claim_evidence_links : "supports"
    evidence_records ||--o{ quote_spans : "contains"
    evidence_records ||--o{ mapping_evidence_links : "corroborates"
    source_references ||--o{ evidence_records : "published_in"

    severity_assessments ||--o{ human_review_records : "governed_by"
    severity_assessments ||--o| severity_assessments : "supersedes"

    framework_reference_sets ||--o{ framework_controls : "contains"
    framework_reference_sets ||--o{ incident_framework_mappings : "defines"
    framework_reference_sets ||--o{ eu_legal_relevance_screens : "defines"
    framework_reference_sets ||--o{ eu_screen_rule_traces : "defines"
    framework_reference_sets ||--o| framework_reference_sets : "supersedes"

    framework_controls ||--o{ incident_framework_mappings : "referenced_by"

    incident_framework_mappings ||--o{ mapping_evidence_links : "grounded_by"
    incident_framework_mappings ||--o| incident_framework_mappings : "supersedes"

    eu_legal_relevance_screens ||--o{ mapping_evidence_links : "grounded_by"
    eu_legal_relevance_screens ||--o{ eu_screen_rule_traces : "evaluated_by"
    eu_legal_relevance_screens ||--o| eu_legal_relevance_screens : "supersedes"

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

    framework_reference_sets {
        string id PK
        string framework_code
        string framework_name
        string version
        string source_url
        string publisher
        datetime retrieved_at
        datetime verified_at
        string verified_by
        string content_hash
        text license_notes
        string status
        string supersedes_reference_set_id FK
        json metadata_json
        datetime created_at
        datetime updated_at
    }

    framework_controls {
        string id PK
        string reference_set_id FK
        string external_identifier
        string parent_identifier
        string title
        text description
        string control_level
        string framework_function
        string category
        string subcategory
        string article_number
        date effective_date
        text applicability_notes
        string source_locator
        string status
        json metadata_json
        datetime created_at
        datetime updated_at
    }

    incident_framework_mappings {
        string id PK
        string incident_id FK
        string framework_code
        string reference_set_id FK
        string framework_control_id FK
        string mapping_level
        string applicability
        string confidence
        string mapping_status
        text rationale
        json known_facts
        json unknowns
        json disputed_facts
        json evidence_ids
        text recommended_control_or_follow_up
        string rule_id
        string rule_version
        string generated_by
        string reviewed_by
        datetime generated_at
        datetime reviewed_at
        string supersedes_mapping_id
        string superseded_by_id
        datetime created_at
        datetime updated_at
    }

    eu_legal_relevance_screens {
        string id PK
        string incident_id FK
        string reference_set_id FK
        string screen_version
        string status
        string relevance_level
        string nexus_assessment
        string territorial_nexus
        string ai_system_context
        string ai_system_relevance
        json actor_roles
        string actor_role_confidence
        string risk_class
        string serious_incident_relevance
        json conceptual_risk_areas
        json potentially_relevant_articles
        json potentially_relevant_reference_ids
        json operational_obligations
        json operational_relevance_areas
        text applicability_date_assessment
        string timing_assessment
        json known_facts
        json unknowns
        json disputed_facts
        json missing_facts
        json follow_up_questions
        text rationale
        string confidence
        string disclaimer_version
        text disclaimer_text
        string generated_by
        string reviewed_by
        datetime generated_at
        datetime reviewed_at
        string supersedes_screen_id
        string superseded_by_id
        json metadata_json
        datetime created_at
        datetime updated_at
    }

    eu_screen_rule_traces {
        string id PK
        string eu_legal_relevance_screen_id FK
        string rule_id
        string rule_version
        string reference_set_id FK
        json matched_condition_ids
        datetime created_at
    }

    mapping_evidence_links {
        string id PK
        string incident_framework_mapping_id FK
        string eu_legal_relevance_screen_id FK
        string evidence_id FK
        string claim_type
        text relevance_note
        datetime created_at
    }

    governance_audit_logs {
        string id PK
        string entity_type
        string entity_id
        string transition_type
        string actor_id
        boolean is_human
        string actor_role
        datetime timestamp_utc
        string before_state_digest
        string after_state_digest
        string event_hash
        string previous_event_hash
        json details_json
        datetime created_at
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
