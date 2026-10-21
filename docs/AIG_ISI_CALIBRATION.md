# AI Guardians Incident Severity Index (AIG-ISI) Calibration & Baseline Guide
**Version:** 1.0.0  
**Effective Date:** 2026-10-20  
**Author:** AI Guardians LLC  
**Document Identifier:** CAL-AIG-ISI-001  
**Status:** RATIFIED & ACTIVE  

---

## 1. Purpose of Calibration

The **AIG-ISI Calibration Suite** establishes a set of deterministic benchmark incident archetypes spanning all five severity tiers (Minimal, Moderate, Significant, Severe, Critical) as well as edge cases (incomplete evidence, extreme divergence between actual and potential harm, overrides, and disputed claims).

The calibration suite serves two purposes:
1. **Mathematical Repeatability**: Automated regression tests execute against these benchmark profiles to guarantee that engine calculations never drift.
2. **Analyst Consistency**: Provides human evaluators and future prompt templates with explicit, referenceable standards for what constitutes each tier.

---

## 2. Benchmark Incident Archetypes

### Case 1: Trivial Output Glitch (Tier 1 — Minimal)
- **Profile**: Internal customer support chatbot outputs minor gibberish for 5 minutes during routine update. Automated retry caught it; no customer complaints or data leak.
- **Dimension Scores**:
  - `human_impact`: 0
  - `financial_property`: 0
  - `trust_reputation`: 0
  - `privacy_confidentiality`: 0
  - `rights_fairness`: 0
  - `operational_critical_service`: 1 (Glitch with immediate failover, 0 user impact)
  - `scale_reach`: 0 (Internal test)
  - `societal_environmental`: 0
- **Actual Impact Calculations**:
  - Lower Bound: $0 + 0 + 0 + 0 + 0 + 1 \times (10 / 5) + 0 + 0 = 2.0$
  - Upper Bound: $2.0$ (all dimensions evaluated, unknown weight = 0)
  - Completeness: $100\%$ ($1.0$)
  - Normalized Score: $2.0$
  - Tier: **MINIMAL** ($[0.0, 19.999]$)
  - Review Gates: None triggered.

---

### Case 2: Regional E-Commerce Recommendation Outage (Tier 2 — Moderate)
- **Profile**: Recommendation model crash leads to \$45,000 in lost regional checkout conversions over 45 minutes before rollback.
- **Dimension Scores**:
  - `human_impact`: 0
  - `financial_property`: 2 (\$45k loss, moderate range \$10k–\$100k)
  - `trust_reputation`: 2 (Formal merchant complaints, regional coverage)
  - `privacy_confidentiality`: 0
  - `rights_fairness`: 0
  - `operational_critical_service`: 2 (Non-critical operational disruption < 1 hr)
  - `scale_reach`: 2 (Regional customer base)
  - `societal_environmental`: 0
- **Actual Impact Calculations**:
  - $c_{\text{financial}} = 2 \times (15 / 5) = 6.0$
  - $c_{\text{trust}} = 2 \times (15 / 5) = 6.0$
  - $c_{\text{operational}} = 2 \times (10 / 5) = 4.0$
  - $c_{\text{scale}} = 2 \times (5 / 5) = 2.0$
  - Lower Bound: $6.0 + 6.0 + 4.0 + 2.0 = 18.0$
  - Upper Bound: $18.0$ (completeness 100%)
  - Completeness: $100\%$
  - Normalized Score: $18.0 \rightarrow$ Minimal / borderline Moderate.
  - Potential Impact (had rollback taken 6 hours):
    - Financial: 3 ($9.0$), Operational: 3 ($6.0$), Trust: 3 ($9.0$), Scale: 3 ($3.0$) $\rightarrow 27.0$ (**MODERATE**).
  - Review Gates: Divergence gate evaluated.

---

### Case 3: Algorithmic Tenant Screening Disparate Impact (Tier 3 — Significant)
- **Profile**: Third-party tenant-screening AI erroneously applied automated eviction flags against 12,000 low-income applicants across 3 states due to flawed training data merge.
- **Dimension Scores**:
  - `human_impact`: 2 (Moderate psychological distress, housing uncertainty)
  - `financial_property`: 2 (Application fees and temporary lodging costs)
  - `trust_reputation`: 3 (National press coverage, civil rights inquiry)
  - `privacy_confidentiality`: 1 (Inadvertent exposure of applicant status)
  - `rights_fairness`: 3 (Systemic denial of housing access)
  - `operational_critical_service`: 0 (No municipal grid disruption)
  - `scale_reach`: 3 (Multi-state, 12,000 individuals)
  - `societal_environmental`: 2 (Societal discourse on algorithmic bias)
- **Actual Impact Calculations**:
  - $c_{\text{human}} = 2 \times (25 / 5) = 10.0$
  - $c_{\text{financial}} = 2 \times (15 / 5) = 6.0$
  - $c_{\text{trust}} = 3 \times (15 / 5) = 9.0$
  - $c_{\text{privacy}} = 1 \times (15 / 5) = 3.0$
  - $c_{\text{rights}} = 3 \times (10 / 5) = 6.0$
  - $c_{\text{operational}} = 0.0$
  - $c_{\text{scale}} = 3 \times (5 / 5) = 3.0$
  - $c_{\text{societal}} = 2 \times (5 / 5) = 2.0$
  - Lower Bound: $10.0 + 6.0 + 9.0 + 3.0 + 6.0 + 0 + 3.0 + 2.0 = 39.0$
  - Normalized Score: $39.0$
  - Tier: **MODERATE / SIGNIFICANT** (Borderline Tier 2/3).
  - Review Gates: None or Rights impact review.

---

### Case 4: Deepfake Bank Wire Fraud & Executive Impersonation (Tier 4 — Severe)
- **Profile**: Real-time generative voice clone deceived a multi-national engineering firm's finance desk into transferring \$25,000,000 across multiple international shell accounts.
- **Dimension Scores**:
  - `human_impact`: 1 (Emotional distress of defrauded staff)
  - `financial_property`: 5 (> \$10M loss: \$25M stolen)
  - `trust_reputation`: 4 (Executive crisis, stock plunge, termination of key supplier accounts)
  - `privacy_confidentiality`: 3 (Exfiltration of internal executive communications)
  - `rights_fairness`: 0
  - `operational_critical_service`: 2 (Short-term freeze on company accounts)
  - `scale_reach`: 3 (International supplier network)
  - `societal_environmental`: 2 (Erosion of enterprise voice authentication trust)
- **Actual Impact Calculations**:
  - $c_{\text{human}} = 1 \times 5.0 = 5.0$
  - $c_{\text{financial}} = 5 \times 3.0 = 15.0$
  - $c_{\text{trust}} = 4 \times 3.0 = 12.0$
  - $c_{\text{privacy}} = 3 \times 3.0 = 9.0$
  - $c_{\text{rights}} = 0.0$
  - $c_{\text{operational}} = 2 \times 2.0 = 4.0$
  - $c_{\text{scale}} = 3 \times 1.0 = 3.0$
  - $c_{\text{societal}} = 2 \times 1.0 = 2.0$
  - Lower Bound: $5.0 + 15.0 + 12.0 + 9.0 + 0 + 4.0 + 3.0 + 2.0 = 50.0$
  - Normalized Score: $50.0$ (Significant tier by weight; however, financial was 5).
  - Review Gates: Triggered by Tier or Financial/Trust impacts.

---

### Case 5: Autonomous Clinical Triage Failure (Tier 5 — Critical)
- **Profile**: Hospital network deployed an autonomous clinical scheduling agent. A software logic bug caused acute cardiac emergency alerts to be misrouted as low-priority elective visits for 48 hours, resulting in 4 patient fatalities and 11 permanent injuries.
- **Dimension Scores**:
  - `human_impact`: 5 (Multiple fatalities; catastrophic physical devastation)
  - `financial_property`: 3 (Estimated direct hospital remediation > \$500k)
  - `trust_reputation`: 5 (Total collapse of hospital trust, health authority shutdown)
  - `privacy_confidentiality`: 2 (Accidental disclosure of patient triage tickets)
  - `rights_fairness`: 4 (Systemic deprivation of access to emergency healthcare)
  - `operational_critical_service`: 5 (Prolonged catastrophic failure of emergency hospital network)
  - `scale_reach`: 3 (Multi-hospital regional network, > 5,000 patients affected)
  - `societal_environmental`: 4 (Severe public panic, loss of faith in healthcare automation)
- **Actual Impact Calculations**:
  - $c_{\text{human}} = 5 \times (25 / 5) = 25.0$
  - $c_{\text{financial}} = 3 \times (15 / 5) = 9.0$
  - $c_{\text{trust}} = 5 \times (15 / 5) = 15.0$
  - $c_{\text{privacy}} = 2 \times (15 / 5) = 6.0$
  - $c_{\text{rights}} = 4 \times (10 / 5) = 8.0$
  - $c_{\text{operational}} = 5 \times (10 / 5) = 10.0$
  - $c_{\text{scale}} = 3 \times (5 / 5) = 3.0$
  - $c_{\text{societal}} = 4 \times (5 / 5) = 4.0$
  - Lower Bound: $25.0 + 9.0 + 15.0 + 6.0 + 8.0 + 10.0 + 3.0 + 4.0 = 80.0$
  - Normalized Score: $80.0$
  - Tier: **CRITICAL** (Tier 5: $[80.0, 100.0]$)
  - Review Gates Triggered:
    - `TIER_4_OR_5` (Score is 80.0)
    - `SERIOUS_INJURY_OR_DEATH` (Human impact is 5)
    - `CRITICAL_INFRASTRUCTURE` (Operational impact is 5)
    - `SERIOUS_RIGHTS_IMPACT` (Rights impact is 4)
  - Mandatory Outcome: Automatic hold state (`PENDING_REVIEW`) requiring dual-reviewer sign-off before publication.

---

### Case 6: Unconfirmed Single-Source Whistleblower Report (Incomplete / Low Confidence)
- **Profile**: Leaked document alleges that a defense contractor's computer vision system misclassified target assets. No details on financial losses, privacy, or societal impacts.
- **Dimension Scores**:
  - `human_impact`: 3 (Allegation of physical injury during military exercise)
  - `financial_property`: `null` (Unknown)
  - `trust_reputation`: 2 (Internal whistleblower discontent)
  - `privacy_confidentiality`: `null` (Unknown)
  - `rights_fairness`: `null` (Unknown)
  - `operational_critical_service`: 3 (Significant operational disruption)
  - `scale_reach`: 1 (Single contractor test site)
  - `societal_environmental`: `null` (Unknown)
- **Calculations**:
  - Evaluated Weights: $w_{\text{human}}(25) + w_{\text{trust}}(15) + w_{\text{operational}}(10) + w_{\text{scale}}(5) = 55.0$
  - Unknown Weights: $w_{\text{financial}}(15) + w_{\text{privacy}}(15) + w_{\text{rights}}(10) + w_{\text{societal}}(5) = 45.0$
  - Completeness: $55.0 / 100.0 = 55.0\%$ ($0.55$)
  - $c_{\text{human}} = 3 \times 5.0 = 15.0$
  - $c_{\text{trust}} = 2 \times 3.0 = 6.0$
  - $c_{\text{operational}} = 3 \times 2.0 = 6.0$
  - $c_{\text{scale}} = 1 \times 1.0 = 1.0$
  - Lower Bound: $15.0 + 6.0 + 6.0 + 1.0 = 28.0$
  - Upper Bound: $28.0 + 45.0 = 73.0$
  - Score Range: $[28.0, 73.0]$
  - Provisional Normalized Score: $(28.0 / 55.0) \times 100.0 = 50.91$
  - Confidence: `LOW`
  - Review Gates Triggered:
    - `LOW_COMPLETENESS` ($55\% < 70\%$)
    - `LOW_CONFIDENCE` (`LOW`)
    - `TIER_4_OR_5` (Upper bound 73.0 reaches Severe tier)

---

## 3. Calibration Test Invariants

All automated tests and evaluation pipelines must enforce:
1. **Mathematical Invariant 1**: $\text{Lower Bound} \le \text{Normalized Score} \le \text{Upper Bound}$ (when normalized score is defined).
2. **Mathematical Invariant 2**: $\text{Upper Bound} - \text{Lower Bound} = \sum_{i \in U} w_i = 100 \times (1 - \text{Completeness})$.
3. **Epistemic Invariant 3**: If all dimensions are `null`, Lower Bound is $0.0$, Upper Bound is $100.0$, Completeness is $0.0\%$, Normalized Score is `null`, and Tier is `UNSCORED`.
4. **Epistemic Invariant 4**: `UNKNOWN` is never coerced to zero.
