# Phase 3 Implementation Plan: Data Foundation and Manual Import

**Project:** AI Incident Monitor  
**Organization:** AI Guardians LLC  
**Milestone:** Phase 3 (Data Foundation and Manual Import)  
**Target Branch:** `feature/data-foundation-import`  
**Governing Documents:** [Project Constitution](file:///Users/eberolston/Downloads/AIG-AI-Incident-Monitor/docs/PROJECT_CONSTITUTION.md), [RTM](file:///Users/eberolston/Downloads/AIG-AI-Incident-Monitor/docs/REQUIREMENTS_TRACEABILITY.md), [ADR-001..006](file:///Users/eberolston/Downloads/AIG-AI-Incident-Monitor/docs/DECISIONS.md)  
**Status:** APPROVED FOR IMPLEMENTATION  

---

## 1. Approved Decisions & Accepted Defaults

The following architectural defaults govern the Phase 3 implementation, incorporating all user review decisions:

| Decision ID | Domain | Approved Selection | Refined Specification |
| :--- | :--- | :--- | :--- |
| **`DEC-P3-001`** | **Local Database Default** | **Option C: PostgreSQL in Docker Default, SQLite for Offline Tests** | Primary development targets local PostgreSQL 16 (`postgres:16-alpine` via Docker Compose); SQLite 3 is retained as a zero-dependency fallback for rapid, offline unit test runs on macOS. |
| **`DEC-P3-002`** | **Raw Import Retention** | **Option C: Hybrid Epistemic Ingestion** | Store file metadata, SHA-256 content digest, and raw row JSON snapshots in `raw_import_records.raw_payload` in the database. Uploaded raw files are staged in `$REPO_ROOT/.data/raw_imports/` (located **inside the repository workspace, strictly gitignored via `.data/`, and excluded from commits**). This keeps local development self-contained without machine-specific global paths, while a 30-day purge TTL bounds storage. No full-text copyrighted news articles are stored in Git or the database (ADR-003, Rule 16). |
| **`DEC-P3-003`** | **Deduplication Strategy** | **Option B: Conservative Matching + Human Review Queue** | Exact Source ID (Tier 1) and exact normalized Canonical URL (Tier 2) auto-link to existing incidents. Near-duplicate matches (Tier 3: title similarity > 0.90 + event date within $\pm 2$ days) are routed to an explicit `POTENTIAL_DUPLICATE` human review queue. Zero automated merges of separate incident dossiers (Rule 14). |
| **`DEC-P3-004`** | **Migration Policy** | **Option B Refined: PostgreSQL-Native Primary, Selective SQLite Batching** | Standard PostgreSQL-native migration behavior is the default primary path. SQLite batch table recreation (`batch_alter_table(recreate="always")`) is used selectively only when required by SQLite limitations, wrapped with `PRAGMA foreign_keys = OFF;`, table recreation, `PRAGMA foreign_keys = ON;`, and mandatory `PRAGMA foreign_key_check;`. SQLite-specific recreation is explicitly documented and tested in migration test suites. |
| **`XLSX Clarification`** | **Import Parser** | **Cached-Value Strategy** | `openpyxl` with `data_only=True` returns the last cached spreadsheet value for a formula cell (it does not calculate formulas). If a formula cell has no cached value, it is treated strictly as missing/unknown (`None` / `UNKNOWN`), never defaulted to zero. |
| **`Deployment Decoupling`** | **Future Ingress** | **Cloudflare Subdomain Ingress** | The service is architected as an independent container attached to `incidents.aiguardiansllc.us` behind Cloudflare DNS/WAF, entirely decoupled from the main corporate website at `aiguardiansllc.us`. |

---

## 2. Package & Module Architecture

Phase 3 implements the persistence and ingestion modules within `backend/`:

```
backend/
├── pyproject.toml               # Updated with sqlalchemy, alembic, openpyxl, defusedxml
├── docker-compose.yml           # Local PostgreSQL 16 container service for dev
├── Makefile                     # Developer ergonomics: make migrate, make seed, make test-db
├── alembic.ini                  # Alembic configuration
├── alembic/
│   ├── env.py                   # Migration environment with dual PostgreSQL/SQLite batching
│   ├── script.py.mako           # Migration script template
│   └── versions/
│       └── 001_initial_data_foundation.py
└── src/
    └── ai_incident_monitor/
        ├── domain/              # Phase 2 Pydantic domain models (untouched)
        ├── db/                  # Database connectivity & SQLAlchemy 2.0 ORM models
        │   ├── base.py          # DeclarativeBase with explicit naming conventions
        │   ├── session.py       # Engine factory (PostgreSQL / SQLite) & sessionmaker
        │   └── models/          # Relational entities matching domain schemas
        │       ├── common.py    # TimestampMixin, UUID types, BaseEntityTable
        │       ├── incident.py  # IncidentTable
        │       ├── source.py    # SourceTable (SHA-256, URL, publisher)
        │       ├── evidence.py  # EvidenceTable, QuoteSpanTable, ClaimEvidenceLinkTable
        │       ├── claim.py     # ClaimTable (epistemic status, asserting entity, lineage)
        │       ├── causality.py # CausalAssessmentTable, AIInvolvementTable
        │       ├── uncertainty.py # UncertaintyTable, DisputedFactTable
        │       ├── review.py    # HumanReviewTable (is_human=True constraint)
        │       ├── audit.py     # AuditLogTable (append-only)
        │       └── import_record.py # RawImportRecordTable (raw payload + hash)
        ├── repositories/        # Strongly typed data access layer
        │   ├── base.py          # BaseRepository with transaction management
        │   ├── incident_repo.py # Incident & claim queries
        │   ├── claim_repo.py    # Claim lineage, supersession & evidence linking
        │   ├── source_repo.py   # Canonical URL lookup & hash checking
        │   ├── audit_repo.py    # Immutable audit logging (INSERT-only)
        │   └── import_repo.py   # Raw payload persistence & batch provenance
        ├── importers/           # Manual file ingestion & sanitization
        │   ├── base.py          # BaseImporter protocol, upload size/row limits
        │   ├── sanitizers.py    # Formula injection defense (prepending ') & HTML stripper
        │   ├── csv_importer.py  # Streaming DictReader parser
        │   ├── json_importer.py # Streaming JSON parser
        │   ├── xlsx_importer.py # OpenPyXL read_only, data_only parser (cached values)
        │   └── oecd_mapper.py   # OECD AIM export column mapper (missing column tolerance)
        └── deduplication/       # Multi-tier deduplication engine
            ├── normalizer.py    # URL cleaner (strip UTM) & title stemmer
            └── engine.py        # 4-stage waterfall deduplication engine
```

---

## 3. Implementation Increments (Small, Reviewable Steps)

Implementation proceeds in five strictly bounded increments:

### Increment 1: Project Configuration, Dependencies, and Database Core
- Update `backend/pyproject.toml` with `sqlalchemy>=2.0.30`, `alembic>=1.13.0`, `openpyxl>=3.1.0`, `defusedxml>=0.7.0`, `psycopg[binary]>=3.1.0`.
- Create `backend/docker-compose.yml` defining the local development PostgreSQL service.
- Implement `db/base.py` with SQLAlchemy `DeclarativeBase` and explicit naming conventions (`pk_`, `fk_`, `uq_`, `ck_`, `ix_`).
- Implement `db/session.py` with multi-dialect engine resolution (PostgreSQL `DATABASE_URL` with SQLite fallback).

### Increment 2: SQLAlchemy 2.0 ORM Models & Alembic Migration Baseline
- Implement relational models in `db/models/` mirroring the Phase 2 domain entities.
- Configure `alembic.ini` and `alembic/env.py` supporting PostgreSQL-native migrations by default, with selective SQLite batch mode and foreign-key integrity checks.
- Generate and verify initial migration `001_initial_data_foundation.py`.
- Create `tests/integration/test_migrations.py` validating upgrade/downgrade cycles.

### Increment 3: Typed Repository Layer & Append-Only Audit Logging
- Implement `repositories/base.py`, `incident_repo.py`, `claim_repo.py`, `source_repo.py`, `audit_repo.py`, and `import_repo.py`.
- Enforce append-only invariants on `audit_log` (INSERT-only, zero UPDATE/DELETE).
- Create `tests/unit/test_repositories.py` verifying transactional operations and entity mapping.

### Increment 4: Import Sanitization, OECD Field Mapping & Multi-Format Parsers
- Implement `importers/sanitizers.py` neutralizing formula injection triggers (`=`, `+`, `-`, `@`, `\t`, `\r`) by prepending `'`.
- Implement `importers/csv_importer.py`, `json_importer.py`, and `xlsx_importer.py` (with `data_only=True` cached value handling).
- Implement `importers/oecd_mapper.py` with missing-column tolerance and unverified claim typing.
- Create sanitized test fixtures in `backend/tests/fixtures/imports/`.
- Create `tests/unit/test_formula_sanitizer.py` and `tests/unit/test_importers.py`.

### Increment 5: Deterministic Deduplication Engine & End-to-End Integration
- Implement `deduplication/normalizer.py` and `deduplication/engine.py` (Tiers 1–4 waterfall).
- Wire deduplication into the import pipeline, populating `dedup_candidates` for Tier 3 matches.
- Implement `tests/unit/test_deduplication.py` and `tests/integration/test_manual_import_flow.py`.
- Update `Makefile`, documentation, and status files.

---

## 4. Explicit File Allowlist and Denylist

### 4.1 Permitted Files (Allowlist)
- `backend/pyproject.toml`
- `backend/docker-compose.yml`
- `backend/alembic.ini`
- `backend/alembic/**`
- `backend/src/ai_incident_monitor/db/**`
- `backend/src/ai_incident_monitor/repositories/**`
- `backend/src/ai_incident_monitor/importers/**`
- `backend/src/ai_incident_monitor/deduplication/**`
- `backend/tests/fixtures/imports/**`
- `backend/tests/unit/test_db_*.py`
- `backend/tests/unit/test_repositories.py`
- `backend/tests/unit/test_importers.py`
- `backend/tests/unit/test_formula_sanitizer.py`
- `backend/tests/unit/test_deduplication.py`
- `backend/tests/integration/test_migrations.py`
- `backend/tests/integration/test_manual_import_flow.py`
- `Makefile`
- `docs/PHASE_3_DATA_FOUNDATION_SPEC.md`
- `docs/DECISIONS.md`
- `docs/PROJECT_STATUS.md`
- `docs/NEXT_SESSION.md`
- `docs/REQUIREMENTS_TRACEABILITY.md`

### 4.2 Prohibited Files (Denylist)
- ❌ Live scraping or network connectors: `connectors/live_*`, `scrapers/`, `feedparser*`, `requests*`, `httpx*`
- ❌ LLM clients: `google/genai*`, `openai*`, `anthropic*`, `langchain*`
- ❌ Web API routes: `fastapi*`, `starlette*`, `routes/`, `endpoints/`
- ❌ Frontend files: `frontend/`, `components/`, `pages/`, `*.tsx`, `*.jsx`
- ❌ Scoring engine: `scoring/`, `calculator/`, `aig_isi/`
- ❌ Schedulers: `celery*`, `cron*`, `tasks/`
- ❌ Unsanitized files: `*.pfx`, `*.pem`, `*.env`, real copyrighted news dumps

---

## 5. Phase 3 Gates (Modeled on Phase 2)

| Gate | Requirement | Verification Method |
| :--- | :--- | :--- |
| **Gate 1: Scope Limitation** | Code contains only SQLAlchemy models, Alembic migrations, repositories, importers, deduplication, and tests. | Directory & file audit |
| **Gate 2: Subsystem Bar** | Zero live scrapers, zero LLM calls, zero FastAPI routes, zero frontend code, zero schedulers. | Automated regex/import scan |
| **Gate 3: Unknown Is Not Zero** | Unreported metrics stay `NULL` or `UNKNOWN`. Database columns have no default `0` for financial loss or injury counts. | Model inspection & test assertions |
| **Gate 4: Machine Rec vs Human Approval** | Imported OECD records are marked as unverified claims; machine recommendations remain separate from human review fields. | Model attribute verification |
| **Gate 5: Formula Injection Defense** | All formula triggers (`=`, `+`, `-`, `@`, `\t`, `\r`) are neutralized. Tests confirm execution prevention. | Formula injection unit tests |
| **Gate 6: XLSX Cached Values** | OpenPyXL parses in `data_only=True` mode; cells without cached values are treated as `None`/`UNKNOWN`. | XLSX importer unit tests |
| **Gate 7: Dual Migration Parity** | PostgreSQL migrations run native DDL; SQLite migrations use batch mode with foreign-key isolation and integrity checks. | Migration integration test suite |
| **Gate 8: Branch Discipline** | Implemented on `feature/data-foundation-import`. Zero commits directly to `main`. | Git status & log audit |
| **Gate 9: Fixture Hygiene** | All imported test files carry `DEMONSTRATION DATA — NOT A REAL INCIDENT` notices. | Fixture content audit |
| **Gate 10: Test Gate Strategy** | All relevant new tests must pass before checkpoint commits; the full required test suite (Phase 2 core + Phase 3 persistence and import) must pass before merge/review completion. | Targeted pytest runner per increment; full pytest test runner before final merge |
