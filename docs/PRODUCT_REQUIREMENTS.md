# PRODUCT REQUIREMENTS DOCUMENT: AI Incident Monitor
**Organization:** AI Guardians LLC  
**Document Identifier:** PRD-001  
**Version:** 1.0.0  
**Effective Date:** 2026-10-07  
**Governing Charter:** [Project Constitution](PROJECT_CONSTITUTION.md)  
**Traceability Registry:** [Requirements Traceability Matrix](REQUIREMENTS_TRACEABILITY.md)  

---

## 1. System Vision & Boundaries

### 1.1 Vision
The **AI Incident Monitor** is an enterprise-grade intelligence platform that continuously ingests, evaluates, tracks, and reports on artificial intelligence incidents, failures, safety breaches, and emerging harms worldwide. 

The system automates the labor-intensive stages of incident tracking (ingestion, sanitization, evidence extraction, initial scoring, and draft synthesis) while enforcing an unbreakable chain of epistemic custody, mathematical rigor, and mandatory human authorization.

### 1.2 System Scope
* **In Scope**:
  - Ingestion from public news, RSS feeds, safety databases (e.g. OECD AI Incidents, CVE, arXiv), regulatory filings, and user submissions.
  - Hardened isolation and indirect prompt-injection sanitization of all ingested payloads.
  - Epistemic evidence extraction (fact vs allegation vs analysis, verbatim quotations with byte offsets).
  - Multi-dimensional, explainable severity calculation using the proprietary **AI Guardians Incident Severity Index (AIG-ISI)**.
  - Orthogonal mapping to global governance frameworks: OECD AI Principles, NIST AI Risk Management Framework, and EU AI Act relevance screening.
  - Multi-factor root cause analysis (data, model, system, human, governance) and standardized industry sector tagging.
  - Substack newsletter generation and executive brief synthesis.
  - Human-in-the-loop audit and review workflow prior to public dissemination.
  - Git-based source of truth, versioned ADRs, and cross-Mac operational portability.
* **Strictly Out of Scope**:
  - Autonomous publishing to live feeds or social channels without explicit human approval.
  - Direct scraping or storing of full-text copyrighted news articles in the Git repository.
  - Issuing definitive legal conclusions or alleging unadjudicated regulatory violations.
  - Converting human injuries, fatalities, dignity, or civil rights into financial dollar figures.
  - Speculative extrapolation of unconfirmed rumors into verified facts.

---

## 2. User Personas

| Persona | Role & Objectives | Key Interactions |
| :--- | :--- | :--- |
| **1. AI Safety Analyst** | Investigates technical AI failures, deep-fakes, model hallucinations, and autonomous agent escapes. Seeks granular evidence, root-cause tags, and system vulnerability patterns. | Evaluates evidence spans, reviews causal decomposition (`RCA`), inspects model architecture metadata, reviews technical briefings. |
| **2. Legal & Compliance Auditor** | Assesses organizational liability, regulatory exposure, and framework alignment. Requires strict jurisdictional precision, unassailable evidence provenance, and defensible audit trails. | Audits regulatory mapping (`GOV`), verifies legal disclaimers (`LGL`), inspects jurisdictional applicability vs conceptual relevance. |
| **3. Substack Newsletter Editor** | Authors forensic, authoritative public newsletters and industry briefs for AI Guardians LLC subscribers. Demands crisp, objective prose with zero sensationalism. | Reviews draft dossiers (`EDT`), verifies epistemic tags, conducts mandatory human-in-the-loop gate check, exports to Substack. |
| **4. Executive Risk Officer (CAIO / CRO)** | Needs executive-level threat intelligence, cross-sector industry benchmarks (`IND`), and trend analytics to brief boards and steer AI governance. | Consumes high-level AIG-ISI severity distributions, industry harm breakdowns, and quarterly incident trends. |

---

## 3. End-to-End System Pipeline

```
                                  INGESTION & SANITIZATION
┌─────────────────────────┐      ┌─────────────────────────┐      ┌─────────────────────────┐
│ External Sources (RSS,  │ ───► │ Ingestion Sandbox       │ ───► │ Cryptographic Hashing   │
│ arXiv, Dockets, Feeds)  │      │ - Strip scripts/macros  │      │ - SHA-256 generation    │
│ [SRC-xxx]               │      │ - XML wrapper isolation │      │ - URL & timestamp anchor│
└─────────────────────────┘      └─────────────────────────┘      └────────────┬────────────┘
                                                                               │
                                  ANALYSIS & EVALUATION                        ▼
┌─────────────────────────┐      ┌─────────────────────────┐      ┌─────────────────────────┐
│ Governance & Legal Map  │ ◄─── │ AIG-ISI Severity Engine │ ◄─── │ Epistemic Extraction    │
│ - OECD Principles       │      │ - Harm, Autonomy,       │      │ - Facts vs Allegations  │
│ - NIST AI RMF           │      │   Reversibility, Scope  │      │ - Byte-offset quotes    │
│ - EU AI Act Screening   │      │ - Factor rationales     │      │ - Unknown != 0 handling │
│ [GOV-xxx, LGL-xxx]      │      │ [SEV-xxx]               │      │ [EVD-xxx]               │
└────────────┬────────────┘      └─────────────────────────┘      └─────────────────────────┘
             │
             ▼                    SYNTHESIS & EDITORIAL
┌─────────────────────────┐      ┌─────────────────────────┐      ┌─────────────────────────┐
│ Root Cause & Industry   │ ───► │ Privacy & PII Scrubbing │ ───► │ Editorial Synthesis     │
│ - Causal taxonomy [RCA] │      │ - Entity anonymization  │      │ - Substack newsletter   │
│ - Sector taxonomy [IND] │      │ - Safe harbor [PRI-xxx] │      │ - Executive brief [EDT] │
└─────────────────────────┘      └─────────────────────────┘      └────────────┬────────────┘
                                                                               │
                                  HUMAN REVIEW & PUBLICATION                   ▼
┌─────────────────────────┐      ┌─────────────────────────┐      ┌─────────────────────────┐
│ Substack / Public Feed  │ ◄─── │ Cryptographic Audit Log │ ◄─── │ Human-in-the-Loop Review│
│ (Markdown / HTML export)│      │ - Append-only record    │      │ - Editor sign-off gate  │
│ [EDT-xxx]               │      │ - Versioning [AUD-xxx]  │      │ - No LLM self-approval  │
└─────────────────────────┘      └─────────────────────────┘      └─────────────────────────┘
```

---

## 4. Functional Requirements Overview (By Domain)

Detailed requirements, stable IDs, verification methods, and lifecycle states are registered in [`docs/REQUIREMENTS_TRACEABILITY.md`](REQUIREMENTS_TRACEABILITY.md). Below is the functional architecture:

### 4.1 Source Ingestion & Connectors (`SRC`)
* Multi-source connector architecture supporting RSS, arXiv, judicial/regulatory databases, and direct analyst submissions.
* Automatic deduplication of multi-source coverage referencing the same primary incident.
* Mandatory cryptographic hashing (SHA-256) of every ingested payload at moment of receipt.
* Untrusted payload containment: raw external text is quarantined in XML isolation blocks before LLM processing.

### 4.2 Evidence, Claims, & Citations (`EVD`)
* Granular extraction of factual claims with mandatory bidirectional linkage to source URI and character offsets.
* Categorical classification of every claim into: Confirmed Fact, Allegation, Analysis, Uncertainty, Opinion.
* Strict preservation of missing data: unknown parameters must never be set to 0.
* Exact verbatim quotation validation: quotes must match source text verbatim.

### 4.3 AIG-ISI Severity Assessment (`SEV`)
* Multi-dimensional scoring across:
  1. **Harm Dimension**: Physical/safety, psychological, civil rights/bias, financial, critical infrastructure.
  2. **Autonomy Dimension**: Fully autonomous execution vs human-in-the-loop vs advisory.
  3. **Reversibility Dimension**: Irreversible/fatal vs costly remediation vs instantly recoverable.
  4. **System Scope Dimension**: Global/systemic vs enterprise-wide vs isolated single user.
* Transparent factor-by-factor explainability output alongside composite score.
* Absolute segregation of actual materialized harm from hypothetical potential harm.
* Strict separation between severity score and evidence confidence score.

### 4.4 Governance & Regulatory Mapping (`GOV`)
* **OECD AI Principles**: Independent tagging against OECD values-based principles (inclusive growth, human rights, transparency, robustness, accountability).
* **NIST AI Risk Management Framework**: Mapping to Govern, Map, Measure, and Manage functions.
* **EU AI Act Screening**: Categorization against Prohibited AI practices (Article 5), High-Risk AI systems (Annex III), and General Purpose AI transparency obligations.

### 4.5 Legal-Reference Controls & Disclaimers (`LGL`)
* Mandatory distinction between statutory legal applicability and conceptual framework alignment.
* Strict ban on asserting statutory violations without an authoritative legal ruling.
* Automated injection of legal safe-harbor and forensic analysis disclaimers in all exports.

### 4.6 Root Cause & Industry Classification (`RCA`, `IND`)
* Root cause taxonomy covering: Data Poisoning, Training Deficiency, Distributional Shift, Alignment Failure, Integration Defect, Prompt Injection / Jailbreak, Human Oversight Lapse, and Malicious Intent.
* Industry classification aligned with standardized economic sectors (Healthcare, Financial Services, Defense/Aerospace, Energy/Utilities, Autonomous Transportation, Consumer Technology, Legal/Gov).

### 4.7 Editorial & Substack Generation (`EDT`)
* Structured generation of publication-ready incident dossiers, executive takeaways, and Substack newsletter editions.
* Enforcement of the AI Guardians editorial voice: objective, dispassionate, forensic, non-sensational.
* Markdown formatting compliant with Substack rendering standards.

### 4.8 Security & Prompt Injection Defense (`SEC`)
* Protection against indirect prompt injection embedded in external incident text.
* Zero execution privileges: the ingestion and analysis LLMs have no terminal, network, or modifying tool access.
* Pre-commit git hooks and CI scanning to prevent secret or private credential leaks.

### 4.9 Privacy & Data Governance (`PRI`)
* Automated PII redaction of non-public individuals mentioned in incident reports.
* Copyright compliance: raw scraped news articles are never committed to Git; only URLs, hashes, and fair-use quotations are stored.

### 4.10 Auditability, Quality, & Operations (`AUD`, `GIT`, `OPS`, `UIX`, `TST`)
* Immutable historical incident assessments (append-only versioning; rerunning a model generates a new snapshot).
* Absolute prohibition against LLMs approving their own outputs.
* Interactive human review CLI for editor sign-off prior to publishing.
* Git repository as single source of truth across macOS workstations; zero local machine state dependencies.
* Comprehensive automated test harness including property tests, golden-file comparisons, and negative injection test suites.

---

## 5. Non-Functional Requirements (NFRs)

| NFR ID | Attribute | Specification |
| :--- | :--- | :--- |
| **NFR-001** | **Epistemic Determinism** | Severity scoring rules and classification logic must be deterministic given identical inputs and model parameters. |
| **NFR-002** | **Cross-Mac Portability** | All scripts, tooling, and test suites must execute identically across any macOS (arm64/Darwin) environment without user-specific path dependencies. |
| **NFR-003** | **Git Hygiene** | The repository must contain zero secrets, zero mutable databases (`.sqlite`), and zero full-text copyrighted files. Maximum repository bloat is strictly controlled. |
| **NFR-004** | **Auditability** | 100% of published incident dossiers must contain a cryptographic audit trail identifying the human reviewer, model version, and source hashes. |
| **NFR-005** | **Security Resilience** | The system must withstand 100% of indirect prompt injection test vectors in the golden security test suite without altering system instructions. |

---

## 6. Acceptance & Sign-Off Criteria

A release or milestone meets product acceptance only when:
1. All planned requirements for the phase in [`docs/REQUIREMENTS_TRACEABILITY.md`](REQUIREMENTS_TRACEABILITY.md) have their verification methods satisfied and status marked `VERIFIED`.
2. All 17 constitutional non-negotiable rules are confirmed honored by automated tests and manual inspection.
3. Documentation-level acceptance criteria are verified across the entire governing document suite.
4. [`docs/PROJECT_STATUS.md`](PROJECT_STATUS.md) and [`docs/NEXT_SESSION.md`](NEXT_SESSION.md) are updated and synchronized.
