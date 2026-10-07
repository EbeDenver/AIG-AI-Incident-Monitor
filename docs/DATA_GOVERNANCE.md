# DATA GOVERNANCE, PROVENANCE, & COPYRIGHT COMPLIANCE
**Project:** AI Incident Monitor  
**Organization:** AI Guardians LLC  
**Document Identifier:** DAT-001  
**Version:** 1.0.0  
**Effective Date:** 2026-10-07  
**Governing Charter:** [Project Constitution](PROJECT_CONSTITUTION.md) (Rules 2, 4, 9, 16, 17)  
**Architectural Decisions:** [DECISIONS.md](DECISIONS.md) (ADR-003, ADR-004)  

---

## 1. Copyright & Fair-Use Policy (Constitutional Rule 16)

To respect intellectual property rights, comply with copyright law, and prevent repository bloat, **raw full-text copyrighted news articles and scraped external web pages must NEVER be committed to Git**.

### What Git Stores vs What Stays Out-of-Tree

```
┌───────────────────────────────────────┬───────────────────────────────────────┐
│     COMMITTED TO GIT REPOSITORY       │       STRICTLY EXCLUDED FROM GIT      │
│          (Source of Truth)            │       (Out-of-tree / Gitignored)      │
├───────────────────────────────────────┼───────────────────────────────────────┤
│ • Cryptographic SHA-256 digests       │ • Raw scraped HTML pages              │
│ • Canonical Source URLs               │ • Downloaded full-text PDF articles   │
│ • Publication metadata (date, author) │ • Full 5,000-word copyrighted text    │
│ • Ingestion timestamps                │ • Local SQLite/PostgreSQL databases   │
│ • Minimal fair-use quotation spans    │ • Local scraper caches (.data/cache/) │
│ • Character/byte offset anchors       │ • Developer session cookies & secrets │
│ • Sanitized, synthetic test fixtures  │ • Temporary runtime cache files       │
└───────────────────────────────────────┴───────────────────────────────────────┘
```

### Fair-Use Quotation Standards
* Direct quotes extracted from copyrighted sources must be minimal (strictly necessary to substantiate the specific factual assertion).
* Every quote must be explicitly attributed with the source URL, publication date, and character offsets.
* Quotations must never reproduce the substantive creative expression of the original article.

---

## 2. Epistemic Data Modeling: Unknown Is Not Zero (Constitutional Rule 2)

A core failure mode of automated databases is coercing `NULL` or missing records to default zeros during computation or serialization. In AI safety analytics, **a missing harm figure does not mean zero harm occurred**.

### Schema-Level Tri-State Architecture
In Phase 2 Pydantic schemas and database models, every numerical and boolean attribute that can be unobserved must be wrapped in an explicit tri-state epistemic type:

```python
# Conceptual Pydantic Model Pattern for Phase 2
from enum import Enum
from typing import Generic, Optional, TypeVar
from pydantic import BaseModel

T = TypeVar("T")

class EpistemicCertainty(str, Enum):
    CONFIRMED_FACT = "CONFIRMED_FACT"
    UNVERIFIED_ALLEGATION = "UNVERIFIED_ALLEGATION"
    TECHNICAL_ANALYSIS = "TECHNICAL_ANALYSIS"
    UNKNOWN = "UNKNOWN"

class EpistemicValue(BaseModel, Generic[T]):
    value: Optional[T] = None
    status: EpistemicCertainty = EpistemicCertainty.UNKNOWN
    evidence_ids: list[str] = []

    def is_known(self) -> bool:
        return self.status != EpistemicCertainty.UNKNOWN and self.value is not None
```

### Aggregation Rules
* **No `COALESCE(val, 0)`**: Database queries computing averages, sums, or distributions must never default `NULL` to 0.
* **Dual-Metric Reporting**: Any aggregated metric (e.g., average financial impact, average model latency) must report:
  1. The aggregate computed strictly across known samples (`known_sample_count`).
  2. The total count of unknown records (`unknown_count`).
  3. The confidence interval or uncertainty bounds.

---

## 3. Provenance Architecture & Cryptographic Integrity

Every incident entity in the system is rooted in an unforgeable provenance record:

```
┌────────────────────────────────────────────────────────┐
│                   PROVENANCE ENTITY                    │
├─────────────────────────┬──────────────────────────────┤
│ Field                   │ Description                  │
├─────────────────────────┼──────────────────────────────┤
│ source_id               │ Unique UUIDv5 deterministic   │
│ canonical_url           │ Normalized source URL        │
│ archive_url             │ Wayback / Archive.today snapshot│
│ sha256_hash             │ SHA-256 digest of raw payload │
│ fetched_at              │ UTC ISO-8601 timestamp       │
│ publisher_domain        │ Domain name for reputation   │
│ license_category        │ Fair Use / CC / Public Domain│
└─────────────────────────┴──────────────────────────────┘
```

Whenever an extraction is contested or audited, the system can verify that the raw payload hashed to the recorded `sha256_hash`, proving that evidence was not tampered with post-ingestion.

---

## 4. Schema Evolution & Historical Immutability (Rule 17)

1. **Append-Only Assessment History**:
   - Re-evaluating an incident with a newer model, altered prompt, or updated AIG-ISI rubric creates a **new assessment revision**.
   - Historical assessments are immutable and preserved with their original execution metadata (`created_at`, `model_id`, `version`).
2. **Forward-Compatible Migrations**:
   - Database schema changes must be versioned via declarative migrations (e.g. Alembic/SQLAlchemy in Phase 2+).
   - Destructive migrations (`DROP COLUMN`, type truncation) are prohibited in production branches.

---

## 5. Synthetic Fixture Creation Standards

To enable thorough automated testing (`TST-001` through `TST-005`) without violating copyright or privacy:
- All test fixtures checked into `tests/fixtures/` must be **100% synthetic, public-domain, or anonymized**.
- Synthetic fixtures must cover realistic edge cases: multi-lingual text, extreme token lengths, embedded prompt-injection vectors, and incomplete records with extensive `UNKNOWN` parameters.
