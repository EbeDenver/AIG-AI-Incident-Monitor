# ARCHITECTURAL DECISION RECORDS (ADRs)
**Project:** AI Incident Monitor  
**Organization:** AI Guardians LLC  
**Document Identifier:** ADR-000  
**Status:** ACTIVE REGISTRY  

---

## Architecture Decision Record Template

```markdown
### ADR-XXX: [Short Title]
* **Date**: YYYY-MM-DD
* **Status**: PROPOSED | RATIFIED | SUPERSEDED
* **Deciders**: AI Guardians LLC Leadership / Engineering
* **Context**: What problem or architectural constraint prompted this decision?
* **Decision**: What specific architecture, pattern, or constraint was adopted?
* **Consequences**:
  - Positive impacts and capabilities enabled
  - Negative impacts, trade-offs, or additional engineering overhead
```

---

## Ratified Architectural Decisions

### ADR-001: Adoption of Foundational Project Constitution and 17 Non-Negotiable Rules
* **Date**: 2026-10-07
* **Status**: RATIFIED
* **Deciders**: AI Guardians LLC Leadership, Antigravity AI
* **Context**: Building an automated AI incident monitoring system carries extreme risks of hallucination, sensationalism, legal liability, and false reporting. Standard LLM agents tend to extrapolate missing data, fabricate quotes, and flatten nuanced legal distinctions.
* **Decision**: Ratified [`docs/PROJECT_CONSTITUTION.md`](PROJECT_CONSTITUTION.md) establishing 17 non-negotiable rules with absolute primacy over all code, agent prompts, and workflows.
* **Consequences**:
  - Ensures unassailable epistemic integrity and defensibility.
  - Requires automated pre-commit and CI validators to enforce rule adherence.
  - Strictly bans LLM self-approval and mandates human review before publishing.

---

### ADR-002: Architectural Decoupling of AIG-ISI from Regulatory Frameworks
* **Date**: 2026-10-07
* **Status**: RATIFIED
* **Deciders**: AI Guardians LLC Methodology Team
* **Context**: Public AI incident databases frequently conflate regulatory classifications (e.g. EU AI Act High-Risk), safety severity, and media virality. This introduces severe jurisdictional bias and skews technical severity analysis.
* **Decision**: Architect the AI Guardians Incident Severity Index (AIG-ISI) as a completely autonomous, orthogonal methodology. AIG-ISI is calculated based on empirical dimensions (Harm, Autonomy, Reversibility, Scope), completely decoupled from OECD principles, NIST AI RMF, EU AI Act categorization, or media click volume. Regulatory mappings are preserved as parallel, non-interfering metadata layers.
* **Consequences**:
  - AIG-ISI scores remain globally valid regardless of legal jurisdiction.
  - Changes in EU regulations do not retroactively alter empirical safety severity scores.
  - Schema requires separate data structures: `SeverityAssessment` vs `GovernanceMapping`.

---

### ADR-003: Copyright Compliance and Zero Raw Ingestion Storage in Git
* **Date**: 2026-10-07
* **Status**: RATIFIED
* **Deciders**: Legal & Engineering
* **Context**: Scraping full-text news articles and committing them to a Git repository violates copyright law, risks DMCA takedowns, and bloats the git repository history with megabytes of ephemeral HTML.
* **Decision**: Git shall store only metadata, canonical URLs, archive timestamps, SHA-256 cryptographic digests, and minimal fair-use direct quote spans anchored by byte offsets. Raw scraped payloads are held strictly in an out-of-tree, gitignored local cache directory (`.data/cache/`) or private storage, never in Git.
* **Consequences**:
  - Full copyright compliance under fair-use doctrine.
  - Lightweight, auditable Git repository.
  - Requires SHA-256 provenance verification to prove extracted quotes match source payloads.

---

### ADR-004: Explicit Tri-State Epistemic Modeling (Unknown Is Not Zero)
* **Date**: 2026-10-07
* **Status**: RATIFIED
* **Deciders**: AI Safety & Data Architecture
* **Context**: Standard relational databases and data pipelines frequently default missing or nullable numerical attributes to `0`. In AI incident tracking, if financial damage or casualty counts are unreported, treating them as `0` yields catastrophic analytical falsehoods.
* **Decision**: Codify explicit tri-state/Option epistemic types across all data models (`EpistemicValue[T]`). Missing data is preserved as `UNKNOWN`. Database queries and analytical functions are barred from using `COALESCE(field, 0)` and must report unknown tallies alongside known averages.
* **Consequences**:
  - Prevents erroneous conclusions that an incident caused zero damage when damage was merely unquantified.
  - Requires custom Pydantic validators and query abstractions in Phase 2.

---

### ADR-005: Multi-Mac Development Parity and Git as Single Source of Truth
* **Date**: 2026-10-07
* **Status**: RATIFIED
* **Deciders**: Engineering & Operations
* **Context**: Development occurs across multiple macOS workstations (Darwin/arm64) and automated agent sessions. Machine-specific paths, hidden local dependencies, and untracked configs lead to brittle execution failures across sessions.
* **Decision**: Establish the GitHub repository as the single source of truth for all code, documentation, prompts, migrations, tests, and synthetic fixtures. All tooling and file paths must be strictly path-agnostic and cross-Mac compatible.
* **Consequences**:
  - Seamless agent session transitions across machines.
  - Zero local environment drift or machine lock-in.
  - Mandates strict session startup and closeout synchronization protocols in `AGENTS.md`.

---

### ADR-006: Core Epistemic Schemas, Pydantic v2 Domain Models, and Golden Fixtures
* **Date**: 2026-10-07
* **Status**: RATIFIED
* **Deciders**: AI Guardians LLC Engineering, Antigravity AI
* **Context**: Enforcing the 17 Non-Negotiable Rules in the Project Constitution requires software-level mathematical invariants rather than relying solely on LLM prompt instructions. Without immutable typing and deterministic validators, systems inevitably succumb to prompt drift, null-coercion to zero, fabricated citations, and self-approval.
* **Decision**: Implement core domain entities as immutable Pydantic v2 models (`frozen=True`, `extra="forbid"`):
  1. Strongly typed prefixed UUIDs (`SourceId`, `EvidenceId`, `ClaimId`, `IncidentId`, `ReviewId`, `UncertaintyId`).
  2. Controlled vocabularies via 22 string enums (`EpistemicStatus`, `ClaimType`, `SourceAuthority`, `HarmType`, etc.).
  3. Epistemic tri-state modeling in `MonetaryAmount` and `DateWithPrecision`, guaranteeing `UNKNOWN` is never coerced to zero.
  4. Mandatory evidence linkage for facts, numeric claims, and root causes; human approval mandatory for legal claims.
  5. Cryptographic source provenance (`ContentHash` SHA-256) and strict character-offset quote spans (`QuoteSpan`).
  6. Human review models strictly requiring `is_human=True` (`ReviewerIdentity`), structurally preventing LLM self-approval.
  7. Strict separation of `machine_recommended_status` and `human_approved` in `AuditMetadata`.
  8. 29 sanitized demonstration fixtures (22 valid golden, 7 invalid negative) labeled `DEMONSTRATION DATA — NOT A REAL INCIDENT`.
* **Consequences**:
  - Constitutional rules are enforced as hard Python validation errors (`ConstitutionalViolationError`, `UngroundedClaimError`, `InvalidMonetaryStateError`).
  - Zero database, ORM, network, or external LLM dependencies in the core domain layer.
  - Comprehensive automated test suite (89 unit tests) guarantees zero regressions.
