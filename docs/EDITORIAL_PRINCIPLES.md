# EDITORIAL PRINCIPLES & SUBSTACK PUBLISHING STANDARDS
**Organization:** AI Guardians LLC  
**Document Identifier:** EDT-001  
**Version:** 1.0.0  
**Effective Date:** 2026-10-07  
**Governing Charter:** [Project Constitution](PROJECT_CONSTITUTION.md) (Rules 1, 2, 3, 4, 8, 9, 10, 11, 14, 15)  

---

## 1. The AI Guardians Editorial Voice

The editorial voice of **AI Guardians LLC** is **forensic, dispassionate, objective, and analytically unassailable**. 

We operate as digital investigators and safety auditors, not sensationalist commentators or tabloid journalists. Our readers—enterprise risk officers, AI researchers, policymakers, and legal counsel—rely on us for signal, not noise.

### Tone & Style Mandates
* **No Sensationalism**: Ban hyperbolic buzzwords (e.g., *"terrifying," "catastrophic nightmare," "AI runs amok," "killer robots," "shocking scandal"*).
* **Forensic Precision**: Use exact technical language (e.g., *"latent adversarial trigger," "unintended instruction leakage," "stochastic distributional shift"*).
* **Epistemic Modesty**: Clearly delineate what is proven from what is suspected, alleged, or unknown.
* **Presumption of Neutrality**: Report corporate admissions, plaintiff allegations, and government statements with balanced, dispassionate neutrality.

---

## 2. The Epistemic Ontology & Controlled Vocabulary

Every sentence written in an AI Guardians incident dossier or newsletter must belong to one of five distinct epistemic categories, each with strict grammatical constraints:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        EPISTEMIC ONTOLOGY MATRIX                       │
├───────────────────────┬──────────────────────┬─────────────────────────┤
│ Category              │ Epistemic Standard   │ Controlled Vocabulary   │
├───────────────────────┼──────────────────────┼─────────────────────────┤
│ 1. Confirmed Fact     │ Corroborated by      │ "Confirmed by..."       │
│                       │ public technical     │ "Records indicate..."   │
│                       │ postmortem or docs   │ "Empirical data shows..."│
├───────────────────────┼──────────────────────┼─────────────────────────┤
│ 2. Unverified         │ Asserted by legal    │ "The complaint alleges.."│
│    Allegation         │ complaint or media;  │ "Reported by [Source],  │
│                       │ not yet adjudicated  │  unverified by postmortem"│
├───────────────────────┼──────────────────────┼─────────────────────────┤
│ 3. Technical Analysis │ Deductive findings   │ "Technical analysis     │
│                       │ from forensic audit  │  indicates..."           │
│                       │ or model telemetry   │ "Observed behavior is   │
│                       │                      │  consistent with..."    │
├───────────────────────┼──────────────────────┼─────────────────────────┤
│ 4. Identified         │ Absence of verified  │ "Currently unknown..."  │
│    Uncertainty        │ data; boundary of    │ "No verified public     │
│                       │ observable evidence  │  record exists..."      │
├───────────────────────┼──────────────────────┼─────────────────────────┤
│ 5. Editorial Opinion  │ Normative policy or  │ "In our view..."        │
│                       │ governance commentary│ "AI Guardians assesses  │
│                       │ by AI Guardians team │  as a governance flaw"  │
└───────────────────────┴──────────────────────┴─────────────────────────┘
```

### Grammatical Separation Rules
1. **Never use indicative verbs for allegations**: Do NOT write *"Company X leaked user passwords"*. You MUST write *"Plaintiffs in Doe v. Company X allege that Company X leaked user passwords"*.
2. **Never treat absence of evidence as evidence of absence**: Do NOT write *"No financial damage occurred"*. You MUST write *"The financial extent of damages remains unknown at the time of publication"*.
3. **Never speculate without an uncertainty tag**: Any extrapolation must explicitly commence with *"Technical analysis suggests..."* or *"Uncertainty remains regarding..."*.

---

## 3. Treatment of Named Entities & Legal Rigor

### Presumption of Innocence & Procedural Fairness
* All companies, developers, and individuals named in incidents are treated under the presumption of procedural fairness.
* When referencing litigation, regulatory inquiries, or law enforcement actions, state the exact legal procedural status (e.g., *"complaint filed," "motion to dismiss pending," "investigation initiated," "consent decree finalized"*).
* Distinguish sharply between **voluntary admissions** in corporate postmortems and **contested claims** in adversary filings.

### Prohibition of Unadjudicated Legal Determinations (Rule 11)
* The system shall **never** state or imply that an entity *"violated"* the EU AI Act, the FTC Act, GDPR, or any criminal statute unless citing an official, final judgment, enforcement order, or consent decree issued by a competent court or regulatory body.
* In the absence of an authoritative ruling, use compliant framing:
  * Compliant: *"The incident implicates transparency obligations outlined in EU AI Act Article 53."*
  * Violation: *"Company X violated the EU AI Act."* (STRICTLY PROHIBITED).

---

## 4. Substack Newsletter Format & Structural Standards

AI Guardians incident intelligence is published to Substack across three primary formats:
1. **Executive Brief**: Rapid, high-signal summary of a major newly detected incident (400–600 words).
2. **Weekly Incident Monitor**: Multi-incident roundup summarizing week-over-week trends, severity distributions, and root causes (1,200–2,000 words).
3. **Forensic Deep Dive Dossier**: Comprehensive case study on a high-severity or landmark failure (2,500+ words).

### Required Document Structure for Substack Dossiers
Every published Substack dossier must contain these standard sections in sequence:

```markdown
# [INCIDENT IDENTIFIER]: [Incident Title]
*Date: YYYY-MM-DD | AI Guardians Incident Severity Index (AIG-ISI): [Score/Level]*

## Executive Summary
[Concise, 2-3 paragraph objective overview of what occurred, systems involved, and outcomes.]

## Timeline of Events
[Chronological bulleted sequence with verified dates and sources.]

## Evidentiary Breakdown
- **Confirmed Facts**: [Bullet points with exact citation links]
- **Unverified Allegations**: [Clearly attributed claims]
- **Identified Uncertainties**: [Explicitly noted unknown variables]

## AIG-ISI Severity Assessment
- **Overall Score**: [e.g. 7.4 / 10 - Level 4: Severe]
- **Harm Dimension**: [Score + Evidence Rationale]
- **Autonomy Dimension**: [Score + Evidence Rationale]
- **Reversibility Dimension**: [Score + Evidence Rationale]
- **Scope Dimension**: [Score + Evidence Rationale]

## Root Cause & Contributing Factors (RCA)
[Multi-factor analysis: model, data, deployment, human oversight.]

## Governance & Regulatory Context
- **OECD AI Principles**: [Mapped principles and alignment gaps]
- **NIST AI RMF Core Functions**: [Govern, Map, Measure, Manage analysis]
- **EU AI Act Screening**: [Conceptual relevance, risk tier, note on applicability]

## Key Takeaways for AI Safety & Risk Leaders
[Actionable engineering, operational, and governance lessons.]

---
### Mandatory Editorial & Legal Disclaimer
*AI Guardians Incident Monitor is a technical and forensic intelligence publication produced by AI Guardians LLC. This analysis is prepared for research, safety monitoring, and risk education purposes only and does not constitute formal legal advice, compliance certification, or investment guidance. Severity assessments represent proprietary AI Guardians methodologies and are independent of regulatory determinations.*
```

---

## 5. Human-in-the-Loop Review: The 10-Point Gatekeeper Protocol

Under Constitutional Rules 14 and 15, **no automated system or LLM can approve its own work or trigger publication**. Every public release requires a human editor to complete and sign the following 10-point checklist:

```
┌────────────────────────────────────────────────────────────────────────┐
│             AI GUARDIANS HUMAN EDITORIAL GATEKEEPER CHECKLIST          │
├────┬───────────────────────────────────────────────────────────────────┤
│ [ ]│ 1. Zero Fabrication Check: Every factual assertion has a valid   │
│    │    evidence citation and verifiable source URI.                  │
│ [ ]│ 2. Unknown Verification: All missing metrics are labeled UNKNOWN, │
│    │    with zero instances of missing data coerced to 0.              │
│ [ ]│ 3. Epistemic Separation: No allegations disguised as facts.      │
│ [ ]│ 4. Verbatim Quote Match: All quoted text matches source payload. │
│ [ ]│ 5. Tone Neutrality: All sensationalism and clickbait adjectives   │
│    │    have been stripped.                                           │
│ [ ]│ 6. Dignity Check: Zero monetization of human life, dignity, or   │
│    │    civil rights.                                                 │
│ [ ]│ 7. Legal Disclaimer: Mandatory legal and safe-harbor disclaimers  │
│    │    are attached.                                                 │
│ [ ]│ 8. Legal Compliance: No unadjudicated claims of statutory guilt. │
│ [ ]│ 9. AIG-ISI Explainability: Every severity factor has an explicit │
│    │    textual rationale.                                            │
│ [ ]│ 10. Privacy & PII Check: All private, non-public individuals are  │
│    │     redacted.                                                    │
└────┴───────────────────────────────────────────────────────────────────┘
```

Only when all 10 items are checked by an authenticated human reviewer may the state machine transition from `PENDING_REVIEW` to `APPROVED_FOR_PUBLICATION`.
