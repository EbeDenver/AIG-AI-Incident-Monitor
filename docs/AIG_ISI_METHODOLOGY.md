# AI Guardians Incident Severity Index (AIG-ISI) Methodology Specification
**Version:** 1.0.0
**Effective Date:** 2026-10-20
**Author:** AI Guardians LLC
**Document Identifier:** METH-AIG-ISI-001
**Status:** RATIFIED & ACTIVE

---

## 1. Executive Summary & Purpose

The **AI Guardians Incident Severity Index (AIG-ISI)** is a deterministic, multi-dimensional, evidence-grounded framework for quantifying and characterizing the severity of artificial intelligence incidents.

### Foundational Postulates:
1. **Analytical Metric, Not Legal Adjudication**: AIG-ISI is a proprietary technical safety assessment. It does not establish legal liability, regulatory non-compliance, statutory violations, or negligence (`Constitutional Rule 10`, `Rule 11`).
2. **Actual Harm vs Potential Harm Segregation**: Demonstrated, materialized real-world harm is rigorously segregated from hypothetical or counterfactual blast radius (`Constitutional Rule 5`).
3. **Unknown Is Not Zero**: Missing or unverified information evaluates strictly to `UNKNOWN` (`None`). It is never coerced to zero, omitted silently, or treated as absent harm (`Constitutional Rule 2`).
4. **Non-Monetization of Human Dignity**: Harms involving physical injury, loss of life, psychological well-being, civil rights, privacy, or democratic integrity must never be converted into financial dollar amounts (`Constitutional Rule 9`).
5. **Orthogonality of Severity and Confidence**: Severity magnitude and evidentiary confidence are orthogonal dimensions (`Constitutional Rule 6`).
6. **Structural Independence**: AIG-ISI is structurally decoupled from OECD principles, NIST AI RMF profiles, EU AI Act classifications, and media noteworthiness (`Constitutional Rule 8`).

---

## 2. Dimension Architecture & Weight Distribution

AIG-ISI v1.0 evaluates incidents across **eight discrete dimensions** with fixed weights summing to **100 points**:

| Dimension ID | Dimension Name | Weight ($w_i$) | Focus Area |
| :--- | :--- | :---: | :--- |
| `human_impact` | **Human Impact and Dignity** | **25** | Loss of life, bodily injury, psychological trauma, dignity violation. |
| `financial_property` | **Financial and Property Impact** | **15** | Direct, quantifiable economic and property damage (non-human). |
| `trust_reputation` | **Trust and Reputational Impact** | **15** | Institutional erosion, market panic, loss of faith in AI systems. |
| `privacy_confidentiality` | **Privacy and Confidentiality Impact** | **15** | Personal data exfiltration, trade secret leaks, surveillance harms. |
| `rights_fairness` | **Rights, Fairness, and Access Impact** | **10** | Algorithmic bias, civil rights deprivation, discriminatory denial of access. |
| `operational_critical_service`| **Operational & Critical-Service Impact**| **10** | Critical infrastructure downtime, hospital outages, supply-chain disruption. |
| `scale_reach` | **Scale, Reach, and Propagation** | **5** | Velocity, geographic footprint, population blast radius. |
| `societal_environmental` | **Societal and Environmental Impact** | **5** | Macroeconomic externalities, cultural erosion, ecological degradation. |
| **TOTAL** | | **100** | |

---

## 3. Dimension Scoring Anchors (0 to 5)

Each dimension receives an ordinal score $s_i \in \{0, 1, 2, 3, 4, 5\}$ or `null` (`UNKNOWN`):

```
0: None / Negligible ──► 1: Minor ──► 2: Moderate ──► 3: Substantial ──► 4: Severe ──► 5: Catastrophic
```

### 3.1 Human Impact and Dignity (`human_impact`, Weight: 25)
- **0**: Zero physical injury, psychological trauma, or dignity violation.
- **1 (Minor)**: Minor, transient emotional distress; negligible discomfort.
- **2 (Moderate)**: Documented moderate psychological distress; minor injury requiring first aid only.
- **3 (Substantial)**: Significant psychological trauma; reversible physical injury requiring hospitalization or medical treatment.
- **4 (Severe)**: Severe, life-altering physical injury; permanent physical disability; extreme psychological trauma.
- **5 (Catastrophic)**: Loss of life; multiple fatalities; catastrophic bodily devastation.

### 3.2 Financial and Property Impact (`financial_property`, Weight: 15)
- **0**: Zero financial or property loss.
- **1 (Minor)**: Negligible financial loss ($< \$10,000$ USD) or trivial property damage.
- **2 (Moderate)**: Moderate financial loss ($\$10,000 - \$100,000$ USD) or localized property repair.
- **3 (Substantial)**: Substantial economic loss ($\$100,000 - \$1,000,000$ USD) or major equipment destruction.
- **4 (Severe)**: Severe financial loss ($\$1,000,000 - \$10,000,000$ USD) or significant facility damage.
- **5 (Catastrophic)**: Catastrophic financial loss ($> \$10,000,000$ USD) or systemic enterprise bankruptcy.

### 3.3 Trust and Reputational Impact (`trust_reputation`, Weight: 15)
- **0**: Zero measurable erosion of trust or reputational fallout.
- **1 (Minor)**: Localized complaints, individual negative feedback, negligible reach.
- **2 (Moderate)**: Moderate customer dissatisfaction, formal enterprise complaints, regional press coverage.
- **3 (Substantial)**: Substantial reputational fallout, prominent national news coverage, stakeholder backlash.
- **4 (Severe)**: Severe institutional crisis, termination of major partnerships, sustained boycotts.
- **5 (Catastrophic)**: Irreparable collapse of public/institutional trust, formal regulatory sanctions, enterprise failure.

### 3.4 Privacy and Confidentiality Impact (`privacy_confidentiality`, Weight: 15)
- **0**: Zero privacy compromise or unauthorized data disclosure.
- **1 (Minor)**: Inadvertent exposure of non-sensitive public metadata ($< 100$ records).
- **2 (Moderate)**: Exposure of standard PII (names, contact info) affecting $< 1,000$ individuals.
- **3 (Substantial)**: Breach of sensitive PII (financial, medical, login credentials) affecting $1,000 - 50,000$ individuals.
- **4 (Severe)**: Mass breach of sensitive personal data ($> 50,000$ individuals) or confidential corporate trade secrets.
- **5 (Catastrophic)**: Systemic mass exfiltration ($> 1,000,000$ individuals) or national security intelligence breach.

### 3.5 Rights, Fairness, and Access Impact (`rights_fairness`, Weight: 10)
- **0**: Zero algorithmic bias, disparate impact, or civil rights compromise.
- **1 (Minor)**: Isolated, non-systemic unfairness promptly remediated administratively.
- **2 (Moderate)**: Documented algorithmic bias affecting a small cohort with modest service disparity.
- **3 (Substantial)**: Systemic bias resulting in denial of credit, housing, employment, or academic access.
- **4 (Severe)**: Severe civil rights infringement, wrongful arrest, unlawful detention, or systemic discrimination.
- **5 (Catastrophic)**: Deprivation of fundamental constitutional human rights, state surveillance abuse, democratic subversion.

### 3.6 Operational and Critical-Service Impact (`operational_critical_service`, Weight: 10)
- **0**: Zero operational disruption or service degradation.
- **1 (Minor)**: Transient glitch with automated failover and zero user impact.
- **2 (Moderate)**: Minor operational disruption ($< 1$ hour) affecting non-critical business processes.
- **3 (Substantial)**: Extended downtime ($1 - 12$ hours) of mission-critical business or localized municipal services.
- **4 (Severe)**: Prolonged disruption ($> 12$ hours) of vital infrastructure (transport, power grid, hospitals, water).
- **5 (Catastrophic)**: Sustained, nationwide collapse of critical infrastructure or emergency communication networks.

### 3.7 Scale, Reach, and Propagation (`scale_reach`, Weight: 5)
- **0**: Single isolated user or closed test environment.
- **1 (Minor)**: Single team or small workgroup ($< 50$ individuals).
- **2 (Moderate)**: Multi-team or regional customer footprint ($50 - 5,000$ individuals).
- **3 (Substantial)**: Multi-organization or national deployment ($5,000 - 100,000$ individuals).
- **4 (Severe)**: Multi-national enterprise deployment ($100,000 - 1,000,000$ individuals).
- **5 (Catastrophic)**: Global systemic reach impacting $> 1,000,000$ individuals across international borders.

### 3.8 Societal and Environmental Impact (`societal_environmental`, Weight: 5)
- **0**: Zero societal, democratic, or ecological repercussions.
- **1 (Minor)**: Trivial localized resource consumption or isolated misinformation promptly refuted.
- **2 (Moderate)**: Moderate ecological footprint or localized disinformation spillover.
- **3 (Substantial)**: Substantial societal disruption, polluted public information commons, or localized toxic contamination.
- **4 (Severe)**: Major disruption to democratic electoral processes or severe environmental contamination.
- **5 (Catastrophic)**: Irreversible ecological catastrophe or systemic destabilization of civic and democratic institutions.

---

## 4. Mathematical Formulation & Calculation Engine

Let $i \in \{1, \dots, 8\}$ represent the eight dimensions with weights $w_i \in \{25, 15, 15, 15, 10, 10, 5, 5\}$ such that $\sum_{i=1}^8 w_i = 100$.

Let $s_i$ be the score assigned to dimension $i$. The set of evaluated dimensions is $E = \{i \mid s_i \ne \text{null}\}$, and the set of unknown dimensions is $U = \{i \mid s_i = \text{null}\}$.

### 4.1 Dimension Weighted Contribution
For an evaluated dimension $i \in E$:
$$c_i = s_i \times \frac{w_i}{5.0}$$
Each dimension contributes between $0.0$ and $w_i$ points to the total score.

### 4.2 Lower Evidence Bound
The lower bound represents the confirmed floor of severity, treating all unknown dimensions as producing zero additional harm:
$$\text{lower\_bound} = \sum_{i \in E} s_i \times \frac{w_i}{5.0}$$

### 4.3 Upper Uncertainty Bound
The upper bound represents the maximum potential severity, treating all unknown dimensions as worst-case ($s_i = 5$):
$$\text{upper\_bound} = \text{lower\_bound} + \sum_{i \in U} w_i$$

### 4.4 Completeness Score
Completeness measures the percentage of the framework's weight that has been substantiated by evidence:
$$\text{completeness} = \frac{\sum_{i \in E} w_i}{100.0}$$
If all 8 dimensions are evaluated, $\text{completeness} = 1.0$ (100%).

### 4.5 Provisional Normalized Score
The provisional normalized score rescales the observed contributions over the evaluated weight space:
$$\text{provisional\_normalized\_score} = \begin{cases}
\left( \frac{\text{lower\_bound}}{\sum_{i \in E} w_i} \right) \times 100.0 & \text{if } \sum_{i \in E} w_i > 0 \\
\text{null} & \text{if } \sum_{i \in E} w_i = 0
\end{cases}$$

### 4.6 Score Range
The uncertainty interval is formally represented as:
$$\text{score\_range} = [\text{lower\_bound}, \text{upper\_bound}]$$

---

## 5. Severity Tiers

The 0–100 scale maps to five standardized severity tiers:

```
[0.0 ─── 19.999]  Tier 1: Minimal
[20.0 ── 39.999]  Tier 2: Moderate
[40.0 ── 59.999]  Tier 3: Significant
[60.0 ── 79.999]  Tier 4: Severe
[80.0 ── 100.00]  Tier 5: Critical
```

### Special & Status Tiers:
- **`UNSCORED`**: When completeness is $0\%$ (all dimensions unknown) or data is insufficient to compute a provisional score.
- **`DISPUTED`**: When primary factual claims, causal attribution, or impact scores are subject to unresolved disputes.
- **`SUPERSEDED`**: When an assessment record has been superseded by a newer versioned record.

---

## 6. Separate Confidence Levels

Confidence in the evidentiary basis is assessed independently from severity:
- **`HIGH`**: Corroborated by primary direct evidence, official engineering postmortems, or verified telemetry.
- **`MEDIUM`**: Supported by reputable investigative reporting, accredited research, or uncontested court filings.
- **`LOW`**: Single-source reporting, preliminary press accounts, or unverified plaintiff allegations.
- **`INSUFFICIENT`**: Anecdotal claims, anonymous forum posts, or unverified rumors.

---

## 7. Human-Review States & Mandatory Gates

### 7.1 Lifecycle States:
1. `DRAFT`: Automated machine calculation or preliminary analyst draft.
2. `PENDING_REVIEW`: Triggered when review gates are activated, requiring human sign-off.
3. `APPROVED`: Authenticated human reviewer (`is_human=True`) signed off on all dimensions and evidence anchors.
4. `REJECTED`: Rejected by human editor due to ungrounded claims or methodology violation.
5. `SUPERSEDED`: Historical approved assessment replaced by an updated revision.

### 7.2 The 10 Mandatory Human-Review Gates:
An assessment automatically enters `PENDING_REVIEW` if any of the following 10 gates are triggered:

| Gate Identifier | Condition | Description |
| :--- | :--- | :--- |
| `TIER_4_OR_5` | $\text{tier} \in \{\text{SEVERE}, \text{CRITICAL}\}$ | High severity requires mandatory senior editor sign-off. |
| `LOW_CONFIDENCE` | $\text{confidence} \in \{\text{LOW}, \text{INSUFFICIENT}\}$ | Weak evidence requires manual corroboration. |
| `LOW_COMPLETENESS`| $\text{completeness} < 0.70$ | Less than 70% weight evaluated requires human review. |
| `ACTUAL_VS_POTENTIAL_DIVERGENCE` | $|\text{actual} - \text{potential}| \ge 20.0$ or tiers differ | Substantial gap between actual and potential impact. |
| `OVERRIDE_PRESENT` | $\text{len}(\text{overrides}) > 0$ | Any manual score or tier adjustment triggers mandatory review. |
| `SERIOUS_INJURY_OR_DEATH` | $s_{\text{human\_impact}} \ge 4$ | Loss of life or catastrophic bodily injury. |
| `CRITICAL_INFRASTRUCTURE`| $s_{\text{operational}} \ge 4$ | Major disruption to vital services or infrastructure. |
| `SERIOUS_PRIVACY_IMPACT` | $s_{\text{privacy}} \ge 4$ | Massive or highly sensitive personal data exfiltration. |
| `SERIOUS_RIGHTS_IMPACT` | $s_{\text{rights}} \ge 4$ | Severe civil rights violations or unlawful detention. |
| `MATERIALLY_DISPUTED_FACTS` | $\text{has\_disputes} = \text{true}$ | Factual claims or causality contested by parties. |

---

## 8. Explicit, Auditable Overrides

To ensure epistemic honesty while allowing human editorial discretion:
1. **Never Silent**: Overrides cannot silently overwrite calculated values.
2. **Immutable Audit Record**: The system records the original calculated score, the overridden score, the target dimension or composite score, a substantive written justification (minimum 10 characters), the authenticated reviewer ID, and the UTC timestamp.
3. **Mandatory Gate**: The presence of an override permanently locks the assessment into requiring human approval (`OVERRIDE_PRESENT` gate).
