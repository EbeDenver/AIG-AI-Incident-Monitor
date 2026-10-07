# SCHEMA EVOLUTION & VERSIONING POLICY
**Project:** AI Incident Monitor
**Organization:** AI Guardians LLC
**Document Identifier:** VER-001
**Version:** 1.0.0
**Effective Date:** 2026-10-07
**Status:** ACTIVE POLICY
**Governing Charter:** [Project Constitution](PROJECT_CONSTITUTION.md)
**Parent Traceability:** [Requirements Traceability Matrix](REQUIREMENTS_TRACEABILITY.md)

---

## 1. Purpose and Foundational Mandate

In accordance with **Constitutional Rule 16** (Versioned Methodology & Immutability) and **ADR-001**, all architectural, schema, and methodology changes within the **AI Incident Monitor** must be explicitly versioned.

Because the system serves as an auditable historical registry of AI safety incidents, **historical assessments must never be silently overwritten or modified in-place**. When data models or analytical methodologies evolve, historical records must remain readable, valid, and verifiable under the schema version active at the time of their creation.

---

## 2. Semantic Versioning Specification for Schemas

All schemas adhere strictly to **Semantic Versioning 2.0.0** (`MAJOR.MINOR.PATCH`):

```
                       schema_version = "X.Y.Z"
                                         │ │ │
     ┌───────────────────────────────────┘ │ └─── PATCH (Bug fixes, docs, tighter regex)
     │                                     └───── MINOR (Backward-compatible additions)
     └─────────────────────────────────────────── MAJOR (Breaking schema changes)
```

### 2.1 MAJOR Version Bumps (`X.0.0`)
A MAJOR bump is required when a change alters existing schema semantics or breaks backward compatibility:
- Removing an existing field or renaming an attribute.
- Changing the data type of an existing field (e.g. changing an integer to a string).
- Removing an enum member or narrowing an enum's permissible values.
- Introducing a new required field without a default value.
- Changing validation invariants such that previously valid historical records would fail validation.

**Policy**: A MAJOR version upgrade requires a formal Architectural Decision Record (ADR) in [`docs/DECISIONS.md`](DECISIONS.md) and explicit approval from AI Guardians engineering leadership.

### 2.2 MINOR Version Bumps (`X.Y.0`)
A MINOR bump is permitted for backward-compatible additions:
- Adding a new optional field with `default=None` or a safe default value.
- Expanding an enum with new permitted members.
- Adding a new independent domain entity that does not alter existing entity definitions.

**Policy**: Historical records must remain fully deserializable by the new MINOR schema without modification.

### 2.3 PATCH Version Bumps (`X.Y.Z`)
A PATCH bump is reserved for non-functional or tightening modifications:
- Clarifying field docstrings or descriptions.
- Tightening validation regex patterns where existing valid data remains fully compliant.
- Updating schema export metadata (e.g., JSON Schema Draft annotations).

---

## 3. The `SchemaVersioned` Protocol

All first-class domain models inherit from `SchemaVersioned`:

```python
class SchemaVersioned(BaseEntity):
    schema_version: str = Field(
        default="1.0.0",
        description="Semantic version of the domain schema governing this entity.",
    )
```

### Invariants:
1. Every emitted JSON payload contains an explicit `"schema_version"` string.
2. Deserialization validates that the incoming `schema_version` matches the major version supported by the active software release.
3. If an incoming record has an unsupported `schema_version` (e.g. major version mismatch), the system refuses silent coercion and flags the record for migration.

---

## 4. Immutability and Historical Preservation

### 4.1 Append-Only Historical Records
- Incident dossiers, claims, evidence links, and severity assessments are stored as **immutable, append-only entities** (`frozen=True`).
- Rerunning analysis pipelines or applying updated scoring algorithms creates a **new versioned assessment record** linked back to the prior assessment via `supersedes_claim_id` or `replaces_claim_id`.
- Historical assessments are preserved indefinitely for auditability.

### 4.2 Migration Strategy
When a MAJOR schema upgrade occurs:
1. Historical records remain stored under their historical `schema_version`.
2. Schema migration scripts (implemented via declarative transformers) can project historical records into the new schema for unified querying.
3. The original raw cryptographic hashes (`ContentHash`) and provenance records remain unaltered.
