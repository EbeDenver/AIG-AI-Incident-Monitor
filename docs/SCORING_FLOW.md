# AIG-ISI Scoring Flow and Review Gate Architecture
**Project:** AI Incident Monitor  
**Organization:** AI Guardians LLC  
**Document Identifier:** DOC-FLOW-001  
**Milestone:** Phase 5 Increment 1 (AIG-ISI Severity Foundation)  
**Status:** ACTIVE  

---

## 1. End-to-End Scoring Flow

The AIG-ISI deterministic scoring engine processes evaluated dimension scores for both Actual Impact and Potential Impact, evaluates mathematical bounds and completeness, routes through 10 mandatory review gates, and enforces authenticated human sign-off:

```mermaid
flowchart TD
    subgraph Ingestion["1. Evidence Grounding"]
        A["Incident Claims & Evidence Anchors"] --> B["Dimension Inputs (0-5 or UNKNOWN)"]
    end

    subgraph DualEngine["2. Segregated Evaluation"]
        B --> C["Actual Impact Engine"]
        B --> D["Potential Impact Engine"]
        
        C --> C1["Lower Bound (Unknown=0)"]
        C --> C2["Upper Bound (Unknown=5)"]
        C --> C3["Completeness % (Evaluated Weight / 100)"]
        C --> C4["Provisional Normalized Score (0-100)"]
        C --> C5["Assign Actual Tier"]

        D --> D1["Lower Bound (Unknown=0)"]
        D --> D2["Upper Bound (Unknown=5)"]
        D --> D3["Completeness % (Evaluated Weight / 100)"]
        D --> D4["Provisional Normalized Score (0-100)"]
        D --> D5["Assign Potential Tier"]
    end

    subgraph Gates["3. Human Review Gatekeeper"]
        C5 & D5 --> G{"Evaluate 10 Review Gates"}
        
        G -->|Tier 4 or 5| H["TRIGGER: TIER_4_OR_5"]
        G -->|Confidence Low| I["TRIGGER: LOW_CONFIDENCE"]
        G -->|Completeness < 70%| J["TRIGGER: LOW_COMPLETENESS"]
        G -->|Score Diff >= 20| K["TRIGGER: ACTUAL_VS_POTENTIAL_DIVERGENCE"]
        G -->|Manual Override| L["TRIGGER: OVERRIDE_PRESENT"]
        G -->|Human Impact >= 4| M["TRIGGER: SERIOUS_INJURY_OR_DEATH"]
        G -->|Operational >= 4| N["TRIGGER: CRITICAL_INFRASTRUCTURE"]
        G -->|Privacy >= 4| O["TRIGGER: SERIOUS_PRIVACY_IMPACT"]
        G -->|Rights >= 4| P["TRIGGER: SERIOUS_RIGHTS_IMPACT"]
        G -->|Disputed Claims| Q["TRIGGER: MATERIALLY_DISPUTED_FACTS"]
    end

    subgraph Lifecycle["4. Human Sign-Off State Machine"]
        H & I & J & K & L & M & N & O & P & Q --> R["State: PENDING_REVIEW"]
        G -->|Zero Gates Triggered| S["State: DRAFT"]

        R --> T{"Authenticated Human Reviewer (is_human=True)"}
        T -->|Approved with Justification| U["State: APPROVED"]
        T -->|Rejected / Insufficient Evidence| V["State: REJECTED"]
        T -->|Revision Requested| W["State: REVISION_REQUESTED"]

        U --> X["Append-Only Audit Log"]
        V --> X
        W --> X
    end
```
