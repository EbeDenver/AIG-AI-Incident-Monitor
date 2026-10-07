# AI Incident Monitor

> **Rigorous, forensic, and epistemically unassailable intelligence on artificial intelligence incidents and harms.**  
> Developed by **AI Guardians LLC**.

---

## 1. Mission and Executive Overview

The **AI Incident Monitor** is a specialized intelligence and governance platform designed by **AI Guardians LLC** to detect, evaluate, analyze, and report on real-world artificial intelligence failures, safety incidents, and systemic harms.

In an era crowded with breathless sensationalism and unverified claims, AI Incident Monitor provides an objective, evidentiary anchor for AI risk analysts, legal auditors, safety researchers, and enterprise leadership. We apply uncompromising standards of forensic investigation, mathematical rigor, and epistemic honesty to every tracked event.

---

## 2. Core Differentiators & Principles

1. **Absolute Epistemic Integrity**:
   - Zero fabrication of facts, quotes, causal chains, financial metrics, or citations.
   - Strict categorical segregation of **Confirmed Facts**, **Unverified Allegations**, **Technical Analysis**, **Identified Uncertainty**, and **Editorial Opinion**.
   - **Unknown is not Zero**: Missing or unverified data remains explicitly unknown; it is never coerced to zero, assumed false, or ignored during quantitative analysis.
2. **AI Guardians Incident Severity Index (AIG-ISI)**:
   - A proprietary, multi-dimensional, and fully explainable severity metric based on empirical harm, autonomy level, reversibility, and system scope.
   - **Strict Decoupling**: AIG-ISI is an AI Guardians methodology—it is never conflated with media noteworthiness, political sensitivity, or external regulatory classifications.
3. **Incommensurable Harm Protection**:
   - Explicit prohibition on converting human life, physical safety, dignity, privacy, civil rights, or public trust into financial damage approximations. Non-monetary harms are tracked in their native human and societal dimensions.
4. **Independent Governance Framework Mappings**:
   - Methodical alignment with the **OECD AI Principles**, the **NIST AI Risk Management Framework (RMF)**, and the **EU AI Act**.
   - Clear distinction between *conceptual framework relevance* and *statutory legal applicability*. The platform never asserts an EU AI Act violation without a cited, authoritative judicial or regulatory ruling.
5. **Defense-in-Depth Security**:
   - Ingested external content is treated as untrusted data, defended against indirect prompt injection and data poisoning.
   - LLMs are strictly barred from approving their own outputs.
6. **Mandatory Human-in-the-Loop Review**:
   - High-severity classifications and public editorial releases (such as Substack newsletters) strictly require human expert sign-off.

---

## 3. Repository Architecture & Documentation Map

This repository is governed by an interlocking documentation suite that dictates all architectural, security, and editorial decisions:

```
.
├── AGENTS.md                          # Mandatory agent charter, session protocols, and Git hygiene
├── README.md                          # Project overview, architecture, and onboarding (this file)
└── docs/
    ├── PROJECT_CONSTITUTION.md        # The 17 non-negotiable ethical, legal, and operational rules
    ├── PRODUCT_REQUIREMENTS.md        # Product specifications, user personas, system boundaries
    ├── REQUIREMENTS_TRACEABILITY.md   # Master 15-category matrix mapping all requirements across phases
    ├── EDITORIAL_PRINCIPLES.md        # Epistemic reporting vocabulary, Substack formatting, HITL review gate
    ├── SECURITY_PRINCIPLES.md         # Threat model, indirect prompt-injection defenses, secret/PII controls
    ├── DATA_GOVERNANCE.md             # Provenance data models, copyright fair-use rules, synthetic fixtures
    ├── DECISIONS.md                   # Architectural Decision Records (ADRs ADR-001 through ADR-005)
    ├── PROJECT_STATUS.md              # Real-time maturity dashboard, phase progress, blocker register
    └── NEXT_SESSION.md                # Phase 2 handoff contract, prerequisites, and target schema deliverables
```

---

## 4. Development Environment & Portability

The project is built for seamless cross-workstation development across macOS environments (Darwin/arm64) and CI/CD pipelines.

### Prerequisites
- macOS Sonoma (14.x) or higher / Darwin arm64
- Git 2.40+
- Python 3.11+ (planned for Phase 2 implementation)

### Repository Hygiene
- **Zero Secrets**: Secrets, private credentials, and API keys are strictly forbidden from Git commits.
- **Zero Mutable DBs**: Local SQLite/PostgreSQL files are excluded via `.gitignore`.
- **Zero Copyright Infringement**: Raw crawled external news articles are never stored in the repository. The repo stores only cryptographic hashes (SHA-256), URLs, timestamps, and minimal fair-use direct citation spans.

---

## 5. Project Roadmap & Lifecycle

| Phase | Description | Status |
| :---: | :--- | :---: |
| **Phase 1** | **Foundational Governing Documentation & Architecture** | **In Progress (Active)** |
| **Phase 2** | Core Schemas, Epistemic Types, Data Models & Golden Fixtures | Planned |
| **Phase 3** | Ingestion Engine, Connector Isolation & Injection Defense | Planned |
| **Phase 4** | AIG-ISI Scoring Engine, Root Cause Analysis & Governance Mapping | Planned |
| **Phase 5** | Editorial Pipeline, Substack Generator & Human Review CLI | Planned |
| **Phase 6** | End-to-End Orchestration, Multi-Mac Harness & Observability | Planned |

---

## 6. Ethics and License

Copyright © 2026 AI Guardians LLC. All rights reserved.  
All analytical methodologies, prompts, documentation, and source code are maintained under strict adherence to the [Project Constitution](docs/PROJECT_CONSTITUTION.md).
