# EPISTEMIC FOUNDATIONS & CATEGORY MODEL
**Project:** AI Incident Monitor
**Organization:** AI Guardians LLC
**Document Identifier:** EPIS-001
**Version:** 1.0.0
**Effective Date:** 2026-10-07
**Status:** ACTIVE GOVERNANCE
**Governing Charter:** [Project Constitution](PROJECT_CONSTITUTION.md)
**Parent Traceability:** [Requirements Traceability Matrix](REQUIREMENTS_TRACEABILITY.md)

---

## 1. The Epistemic Crisis in AI Safety Reporting

Public reporting on artificial intelligence failures, safety incidents, and algorithmic harms suffers from pervasive epistemic contamination:
1. **Sensationalized Conflation**: An unproven lawsuit allegation is reported as an established technological fact.
2. **The "Missing as Zero" Fallacy**: Incident databases routinely coerce unquantified damages, unknown casualty counts, or unverified outage durations to zero, creating distorted safety benchmarks.
3. **Speculative Causality**: External correlations are reported as direct algorithmic root causes without technical postmortem evidence.
4. **Premature Legal Adjudication**: Journalistic pieces claim an AI system "violated the EU AI Act" or "broke copyright law" long before any court of competent jurisdiction has adjudicated the matter.
5. **Harm Inflation**: Potential, counterfactual worst-case scenarios are conflated with demonstrated, materialized real-world harms.

The **AI Incident Monitor** exists to provide an unassailable, forensically grounded alternative. This document establishes the theoretical epistemic model implemented in the Phase 2 domain schemas.

---

## 2. The Five Epistemic Tiers (`EpistemicStatus`)

Every assertion, finding, and claim tracked by the monitor must be explicitly categorized into one of five strictly segregated tiers:

```
┌────────────────────────────────────────────────────────┐
│                   EPISTEMIC SPECTRUM                   │
├───────────────────┬────────────────────────────────────┤
│ 1. CONFIRMED FACT │ Grounded in authoritative evidence │
├───────────────────┼────────────────────────────────────┤
│ 2. ALLEGATION     │ Attributed to asserting party      │
├───────────────────┼────────────────────────────────────┤
│ 3. TECH ANALYSIS  │ Forensic inference with rationale  │
├───────────────────┼────────────────────────────────────┤
│ 4. UNCERTAINTY    │ Explicitly unknown or conflicting  │
├───────────────────┼────────────────────────────────────┤
│ 5. OPINION        │ Editorial/subjective commentary    │
└───────────────────┴────────────────────────────────────┘
```

### Tier 1: Confirmed Fact (`CONFIRMED_FACT`)
- **Definition**: An empirical event, technical property, or outcome that has been independently verified by authoritative primary disclosures (e.g. engineering postmortems, regulatory investigation findings, sworn judicial filings, or bilateral corroborating investigative reporting).
- **Schema Invariant**: Must anchor to at least one valid `EvidenceRecord` containing character-offset direct quote spans from primary sources. Cannot exist without evidence linkages.
- **Example**: *"The flight control model experienced an out-of-distribution input on sensor #2 at 14:02:11 UTC, causing pitch-trim autopilot disengagement."*

### Tier 2: Unverified Allegation (`UNVERIFIED_ALLEGATION`)
- **Definition**: A claim made by an external entity (e.g., a plaintiff in a complaint, a competitor, a social media whistleblower, or an anonymous source) that has not been independently verified or judicially confirmed.
- **Schema Invariant**: Must explicitly record the `asserting_entity`. The text must be framed neutrally (e.g. *"Plaintiff alleges..."*, *"According to the complaint filed by X..."*).
- **Prohibition**: Never described as an established fact or system truth.

### Tier 3: Technical Analysis (`TECHNICAL_ANALYSIS`)
- **Definition**: Forensic engineering deduction, architectural risk modeling, or causal inference performed by AI Guardians analysts or accredited third-party researchers.
- **Schema Invariant**: Must be accompanied by explicit evidentiary rationale and methodology notes. If causal, must link to a `CausalAssessment` specifying primary vs contributing factors.

### Tier 4: Stated Uncertainty (`STATED_UNCERTAINTY`)
- **Definition**: Crucial dimensions of the incident that are unverified, partially missing, conflicting between sources, or pending preliminary disclosures.
- **Schema Invariant**: Modeled via `UncertaintyRecord` with explicit categorization (`MISSING_INFORMATION`, `CONFLICTING_REPORTS`, `UNVERIFIED_ATTRIBUTION`).
- **Core Rule**: An absence of information must be recorded as an affirmative uncertainty rather than left empty or assumed to be nonexistent.

### Tier 5: Editorial Opinion (`EDITORIAL_OPINION`)
- **Definition**: Normative commentary, policy recommendations, governance evaluations, or industry context authored by analysts.
- **Schema Invariant**: Strictly quarantined from factual narrative blocks. Explicitly labeled so subscribers understand the boundary between empirical findings and policy opinions.

---

## 3. Constitutional Axiom: "Unknown Is Not Zero"

### 3.1 The Mathematical Hazard of False Zeros
In naive relational schemas, fields like `financial_damage_usd` or `injuries_count` default to `0` or `NULL` (which downstream SQL queries routinely coerce via `COALESCE(damage, 0)`).

When applied to AI incident metrics, this produces disastrous statistical distortion:
$$\text{Average Reported Harm} = \frac{\sum (\text{Known} + \text{Coerced Zeros})}{N}$$
If 80 out of 100 incidents have unreported financial loss, coercing missing loss to \$0 artificially suppresses the true mean impact by a factor of 5, leading corporate boards and regulators to false conclusions about AI system safety.

### 3.2 The Epistemic Tri-State Solution
Our schema introduces explicit tri-state handling via `MonetaryAmount` and `DateWithPrecision`:

```
                    ┌───────────────────────────┐
                    │     Monetary Damage       │
                    └─────────────┬─────────────┘
                                  │
         ┌────────────────────────┼────────────────────────┐
         ▼                        ▼                        ▼
     UNKNOWN                CONFIRMED_ZERO            EXACT_KNOWN
  - amount is None         - amount == 0.00         - amount > 0.00
  - never coerced to 0     - requires EvidenceId    - requires Currency
```

1. **`UNKNOWN`**: The impact has not been measured or disclosed. The value is strictly `None`. Downstream analytical engines must report: *"Known average: \$X across Y incidents (Z incidents with unknown loss)"*.
2. **`CONFIRMED_ZERO`**: An authoritative investigation affirmatively verified that zero financial loss occurred (e.g., a fail-safe engaged before unauthorized transactions cleared). Requires direct `EvidenceId` linkage.
3. **`EXACT_KNOWN` / `RANGE_KNOWN`**: The loss is bounded or exact, with explicit ISO 4217 currency.

---

## 4. Orthogonal Epistemic Dimensions

To prevent bias and jurisdictional contamination, four critical dimensions are kept strictly orthogonal:

```
┌─────────────────────────────────┐       ┌─────────────────────────────────┐
│       Incident Severity         │       │       Evidence Confidence       │
│           (AIG-ISI)             │  ───  │      (LOW / MEDIUM / HIGH)      │
│  Empirical Harm & System Scope  │       │   Source Reliability & Depth    │
└─────────────────────────────────┘       └─────────────────────────────────┘
                 │                                         │
                 │              DECOUPLED                  │
                 ▼                                         ▼
┌─────────────────────────────────┐       ┌─────────────────────────────────┐
│       Actual vs Potential       │       │      Regulatory Governance      │
│  Demonstrated vs Counterfactual │  ───  │   OECD / NIST / EU Relevance    │
└─────────────────────────────────┘       └─────────────────────────────────┘
```

1. **Severity vs Confidence**: A catastrophic hospital power outage caused by an AI scheduling bug is of **Critical Severity**, even if only reported by a single local news dispatch (**Low Confidence**). Conversely, an AI chatbot generating a nonsensical poem is **Low Severity**, even if confirmed by 50 tech journals (**High Confidence**). Conflating them destroys analytical fidelity.
2. **Actual Harm vs Potential Harm**: Actual harm requires physical, psychological, or economic damage that has already materialized. Potential harm models what *could* have occurred if human intervention had failed. They are stored in non-overlapping schema attributes (`HarmType`).
3. **Safety Severity vs Regulatory Screening**: A system classified as "High-Risk" under EU AI Act Annex III is a regulatory designation; it does not dictate its empirical AIG-ISI severity.
4. **Dignity vs Financial Loss**: Human casualties, bodily injury, and civil rights violations cannot be converted into cash metrics. Non-economic harms are evaluated purely in their dedicated ethical dimensions.

---

## 5. Epistemic Evolution & Immutability

Incidents evolve over time as initial press reports are corrected by forensic postmortems. To prevent revisionist overwriting while preserving transparency:

1. **Immutable Records**: Historical records are never modified in place (`frozen=True`).
2. **Explicit Lineage**:
   - `supersedes_claim_id`: Points to prior claims that are now obsolete.
   - `replaces_claim_id`: Points to erroneous claims being formally replaced.
   - `correction_rationale`: Documents why the update occurred.
3. **Disputed Facts**: When two authoritative sources publish irreconcilable accounts, the system instantiates a `DisputedFact` record linking both claims and their respective evidence bases, presenting the divergence transparently.
