# NEXT SESSION HANDOFF: Phase 2 Kickoff
**Project:** AI Incident Monitor  
**Organization:** AI Guardians LLC  
**Document Identifier:** NEXT-001  
**Target Milestone:** Phase 2 (Core Epistemic Schemas, Data Models, & Golden Fixtures)  
**Parent Handoff:** Phase 1 (Governing Documentation Suite Completed)  

---

## 1. Incoming Agent Mission: Phase 2 Objectives

Welcome to Phase 2 of **AI Incident Monitor**. In this phase, you will implement the core epistemic typing system and foundational Pydantic v2 data models that enforce the 17 non-negotiable constitutional rules directly at the software and schema level.

### Targeted Requirements
During Phase 2, the following requirements from [`docs/REQUIREMENTS_TRACEABILITY.md`](REQUIREMENTS_TRACEABILITY.md) will be transitioned to implementation and verification:
- **`EVD-001`**: Zero fabrication guarantees.
- **`EVD-002`**: Epistemic tri-state modeling (`UNKNOWN` is not equivalent to zero).
- **`EVD-003`**: Claim categorical classification (Fact, Allegation, Analysis, Uncertainty, Opinion).
- **`EVD-004`**: Mandatory evidence linkage with URI, timestamp, and quotation offsets.
- **`EVD-005`**: Verbatim direct quotation validation.
- **`EVD-006`**: Orthogonal separation of Incident Severity and Evidence Confidence.
- **`SEV-004`**: Strict segregation of Actual Harm vs Potential Harm.
- **`SEV-005`**: Non-monetization constraint for human dignity and physical harm.
- **`AUD-003`**: Append-only, immutable assessment record schemas.
- **`PRI-004`**: Sanitized, non-infringing synthetic test fixtures.
- **`TST-001`, `TST-003`, `TST-004`**: Automated unit and property test suites.

---

## 2. Startup Verification Checklist

Before writing any code:
1. [ ] Run `git status` — verify you are on branch `main` and working tree is clean.
2. [ ] Read [`AGENTS.md`](../AGENTS.md) — re-verify all 17 non-negotiable constitutional rules and session protocols.
3. [ ] Read [`docs/PROJECT_STATUS.md`](PROJECT_STATUS.md) — verify Phase 1 baseline is completed.
4. [ ] Verify Python environment (Python 3.11+):
   ```bash
   python3 --version
   ```

---

## 3. Targeted Deliverables for Phase 2

You will create the following package layout and implementation files:

```
src/
└── aig_monitor/
    ├── __init__.py
    ├── core/
    │   ├── __init__.py
    │   ├── epistemic.py         # EpistemicValue[T], EpistemicCertainty enum (Rule 2)
    │   └── exceptions.py        # ConstitutionalViolationError, UngroundedClaimError
    └── models/
        ├── __init__.py
        ├── source.py            # SourceProvenance, SHA256 digest models (Rule 4, Rule 16)
        ├── evidence.py          # EvidenceClaim, QuoteSpan, Fact/Allegation tags (Rule 3)
        ├── severity.py          # AIG-ISI dimensional models (Harm, Autonomy, Scope) (Rule 7, 8)
        ├── governance.py        # OECD, NIST, EU AI Act mapping models (Rule 8, 10, 11)
        └── incident.py          # Master IncidentDossier model unifying all layers
tests/
├── __init__.py
├── conftest.py
├── fixtures/
│   └── synthetic_incidents.json # Sanitized, non-copyrighted golden test fixtures
├── test_epistemic_models.py     # Property tests verifying unknown != 0
├── test_validation_rules.py     # Negative tests verifying rejection of ungrounded data
└── test_immutability.py         # Verification that historical records are append-only
pyproject.toml                   # Project metadata, dependencies (pydantic>=2.7, pytest)
```

---

## 4. Key Implementation Rules for Phase 2

1. **Constitutional Primacy**: Every validator in `src/aig_monitor/` must directly raise a descriptive `ConstitutionalViolationError` if an ungrounded assertion, unhedged allegation, or coerced zero is detected.
2. **Type-Level Unknown Handling**: Ensure `EpistemicValue[T]` cannot be accidentally evaluated as falsy or coerced into `0` during numerical operations.
3. **No External Network Calls**: Phase 2 is strictly local schemas, validation rules, and offline test fixtures. Do not introduce network dependencies or scrapers yet (deferred to Phase 3).
4. **macOS Cross-Workstation Portability**: Ensure all paths in tests use `pathlib.Path` relative to the repository root.

---

## 5. Phase 2 Closeout Commands

When Phase 2 implementation is complete:
```bash
# 1. Run unit test suite
pytest -v

# 2. Type check
mypy src/ tests/

# 3. Synchronize status docs
# Update docs/PROJECT_STATUS.md (mark Phase 2 VERIFIED)
# Update docs/NEXT_SESSION.md (specify Phase 3 Ingestion deliverables)
```
