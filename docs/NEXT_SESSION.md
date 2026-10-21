# NEXT SESSION HANDOFF: Phase 5 Increment 2
**Project:** AI Incident Monitor
**Organization:** AI Guardians LLC
**Document Identifier:** NEXT-001
**Target Milestone:** Phase 5, Increment 2 (Governance Framework Mappings: OECD, NIST AI RMF, EU AI Act Screening) — PLANNING ONLY UNTIL SEPARATELY AUTHORIZED
**Parent Handoff:** Phase 5, Increment 1 (AIG-ISI Multi-Dimensional Scoring Core) Merged into `main` via PR #4 (`19db6c35fc1ad854d40b0386f4508f04af571c63`)
**Effective Date:** 2026-10-20
**Current Branch:** `main` (synchronized with `origin/main` at `19db6c35fc1ad854d40b0386f4508f04af571c63`)
**Feature Branch Status:** `feature/aig-isi-scoring-engine` preserved intact

---

## 1. Current State: Phase 5 Increment 1 Merged into Main

Phase 5 Increment 1 (AIG-ISI Multi-Dimensional Scoring Core) has been reviewed, approved, and merged into `main`:
- **Merged PR**: [#4](https://github.com/EbeDenver/AIG-AI-Incident-Monitor/pull/4) (`feat: Phase 5 Increment 1 AIG-ISI multi-dimensional scoring core`)
- **Merge Commit SHA**: `19db6c35fc1ad854d40b0386f4508f04af571c63` (short: `19db6c3`)
- **Main Branch Status**: Fully synchronized with `origin/main`
- **Post-Merge Test Suite Status**: **382 passed tests** (341 Phase 4 regression + 41 new scoring tests) in ~10s with zero failures and zero regressions.
- **Alembic Migrations**: Migration `002_aig_isi_severity_foundation.py` verified through complete upgrade/downgrade/upgrade cycle.
- **Provenance Integrity**: Verified via `make verify-provenance-chain` (`is_valid: true`).

### Deliverables Landed on Main in Increment 1:
1. **Deterministic Scoring Engine (`ai_incident_monitor.scoring`)**:
   - Eight approved dimensions and weights totaling exactly 100: Human Impact and Dignity (25), Financial and Property Impact (15), Trust and Reputation (15), Privacy and Confidentiality (15), Rights and Fairness (10), Operational and Critical-Service (10), Scale and Reach (5), Societal and Environmental (5).
   - Strict segregation of Actual Impact and Potential Impact into independent assessments.
   - Discrete 0–5 scores or `null`/`UNKNOWN`. `UNKNOWN` is never coerced to zero.
   - Exact mathematical formulation for lower bounds, upper bounds, score ranges, completeness, and provisional normalized scores.
   - Five core severity tiers (Minimal, Moderate, Significant, Severe, Critical) and special status tiers (Unscored, Disputed, Superseded).
   - Ten automated human-review workflow gates routing to `PENDING_REVIEW`.
   - Explicit, auditable manual overrides with mandatory rationale, reviewer ID, and timestamp.
2. **Relational Persistence**:
   - `SeverityAssessmentModel` with foreign key to `incidents.id` (`ondelete="CASCADE"`).
   - Typed `SeverityRepository` integrated with append-only `AuditRepository`.
   - Alembic migration `002_aig_isi_severity_foundation.py`.
3. **Methodology & Documentation Artifacts**:
   - `frameworks/ai-guardians/aig-isi-1.0.yaml` (machine-readable spec).
   - `docs/AIG_ISI_METHODOLOGY.md` (comprehensive methodology).
   - `docs/AIG_ISI_CALIBRATION.md` and `frameworks/ai-guardians/calibration_fixtures.json` (6 canonical benchmarks).
   - `docs/ER_DIAGRAM.md` (relational ER diagram).
   - `docs/SCORING_FLOW.md` (scoring flow diagram).
   - Ratified ADRs: `ADR-012` through `ADR-015` in `docs/DECISIONS.md`.

---

## 2. Hard Boundaries & Scope Safeguards

The following boundaries must be strictly maintained:
- **Phase 5 Increment 2 is PLANNING ONLY until separately authorized by the user.**
- Do not create a branch, write code, modify schemas, or install packages for Increment 2 without explicit user approval.
- Zero Gemini, LLM, or generative-AI calls.
- Zero live or scheduled external retrieval.
- Zero web scraping or undocumented API polling.
- Zero dashboard or public UI.
- Zero Substack, email, webhook, or publishing features.
- Zero Cloudflare deployment or domain configuration.
- Zero automated legal or regulatory noncompliance determinations.
- The feature branch `feature/aig-isi-scoring-engine` is preserved intact.

---

## 3. Scope for Future Increment 2 (Governance Framework Mappings)

When authorized, Increment 2 will implement:
1. **OECD AI Principles Mapper (`GOV-001`)**:
   - Mapping incidents against OECD Principles: P1.1 (Inclusive Growth), P1.2 (Human-Centered Values & Fairness), P1.3 (Transparency & Explainability), P1.4 (Robustness, Security, Safety), P1.5 (Accountability).
2. **NIST AI RMF Core Functions Mapper (`GOV-002`)**:
   - Categorization across NIST AI 100-1 functions: `GOVERN`, `MAP`, `MEASURE`, `MANAGE`.
3. **EU AI Act Screening Classifier (`GOV-003`, `GOV-004`, `Rule 10`, `Rule 11`)**:
   - Screening for Prohibited Practices (Article 5), High-Risk AI Systems (Annex III), and General Purpose AI (Article 53).
   - Strict jurisdictional nexus evaluation (`EU_ESTABLISHED`, `EU_DEPLOYED`, `AFFECTS_EU_PERSONS`, `NO_EU_NEXUS`, `UNKNOWN`).
   - Absolute prohibition against unadjudicated violation claims without judicial dockets (`LGL-001`).
4. **Orthogonality Preservation (`GOV-005`, `Rule 8`)**:
   - Ensuring governance mappings remain completely decoupled metadata tags that do not alter AIG-ISI severity scores.

---

## 4. Mac Mini Resume Instructions

To synchronize and verify this state on another workstation (e.g. Mac mini):

```bash
cd /path/to/AIG-AI-Incident-Monitor
git switch main
git pull --ff-only origin main
git status --short
.venv/bin/pytest backend/tests
make verify-provenance-chain
```
