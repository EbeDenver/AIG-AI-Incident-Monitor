"""Two-stage EU AI Act Compliance Assessor.

Specification: AI-incident-AU-Act-Compliance-assessor.pdf
("EU AI Act Compliance Intelligence — LLM API Design", Pages 1-9)

Orchestration:
Stage 1: Deterministic Applicability Pre-Screen (Article 2 territorial nexus and exclusions).
Stage 2: Structured Regulatory Inference (Articles 5, 6, 50, 53/55, 73).
Stage 3: November 2026 Phased Timeline Enforcement Alignment.
"""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Optional

from ai_incident_monitor.compliance.schemas import (
    ComplianceGapFinding,
    ComplianceGapStatus,
    EnforcementTimelineStatus,
    EUAIActComplianceAssessment,
    HighRiskClassificationFinding,
    JurisdictionScope,
    ProhibitedPracticeFinding,
    SeriousIncidentDetermination,
    SeriousIncidentFinding,
    SystemClassification,
    TerritorialScopeAssessment,
    TransparencyObligationFinding,
)
from ai_incident_monitor.compliance.timeline import (
    BASELINE_EVALUATION_DATE,
    adjust_gap_status_for_timeline,
    get_timeline_status_for_article,
)

# Textual indicators for jurisdiction and exclusions
EU_GEO_KEYWORDS = re.compile(
    r"\b(european union|eu\b|europe|germany|france|italy|spain|netherlands|belgium|poland|sweden|austria|ireland|denmark|finland|portugal|greece|czech|brussels|bulgaria|sofia)\b",
    re.IGNORECASE,
)
MILITARY_KEYWORDS = re.compile(
    r"\b(military|defense|armed forces|pentagon|warfare|combat|battlefield|weapon|missile)\b",
    re.IGNORECASE,
)
RESEARCH_KEYWORDS = re.compile(
    r"\b(purely scientific|academic research|laboratory experiment|arxiv preprint|benchmarking study)\b",
    re.IGNORECASE,
)

# High-Risk domain indicators (Regulation (EU) 2024/1689 Annex I & Annex III)
HEALTHCARE_KEYWORDS = re.compile(
    r"\b(medical|clinical|diagnostic|radiology|hospital|patient|surgery|surgical|pathology|therapeutic|gene therapy)\b",
    re.IGNORECASE,
)
ROBOTICS_MACHINERY_KEYWORDS = re.compile(
    r"\b(robot|robotic|machinery|autonomous vehicle|drone|freight|locomotive|industrial equipment)\b",
    re.IGNORECASE,
)
CREDIT_INSURANCE_KEYWORDS = re.compile(
    r"\b(credit score|creditworthiness|loan underwriting|mortgage approval|health insurance risk|life insurance pricing)\b",
    re.IGNORECASE,
)
CRITICAL_INFRA_KEYWORDS = re.compile(
    r"\b(power grid|electricity|water supply|gas supply|telecom network|critical infrastructure|traffic management|load-shedding)\b",
    re.IGNORECASE,
)
BIOMETRIC_KEYWORDS = re.compile(
    r"\b(biometric|facial recognition|remote identification|emotion recognition|iris scan)\b",
    re.IGNORECASE,
)

# Article 5 indicators
PROHIBITION_SUBLIMINAL = re.compile(r"\b(subliminal|manipulative technique|deceptive design|covert distortion)\b", re.IGNORECASE)
PROHIBITION_SOCIAL_SCORING = re.compile(r"\b(social credit|social scoring|citizen score|trustworthiness evaluation)\b", re.IGNORECASE)
PROHIBITION_BIOMETRIC_CAT = re.compile(r"\b(biometric categorization|deduce sexual orientation|deduce political opinion|deduce religious belief)\b", re.IGNORECASE)
PROHIBITION_FACIAL_SCRAPING = re.compile(r"\b(untargeted scraping|cctv scraping|scraping facial images|facial recognition database)\b", re.IGNORECASE)

# Article 50 indicators
SYNTHETIC_MEDIA_KEYWORDS = re.compile(r"\b(deepfake|synthetic media|cloned voice|ai-generated audio|ai-generated video|altered image)\b", re.IGNORECASE)
CHATBOT_KEYWORDS = re.compile(r"\b(conversational agent|chatbot|customer service bot|synthetic persona)\b", re.IGNORECASE)


class EUAIActAssessor:
    """Evaluates incidents against the EU AI Act with deterministic safeguards and timeline alignment."""

    def evaluate_incident(
        self,
        incident_id: str,
        title: str,
        summary: str,
        category: str,
        claims: Optional[list[str]] = None,
        observed_harms: Optional[list[str]] = None,
        evidence_ids: Optional[list[str]] = None,
    ) -> EUAIActComplianceAssessment:
        """Execute two-stage compliance evaluation aligned to the November 2026 baseline."""
        text_corpus = f"{title} {summary} {' '.join(claims or [])} {' '.join(observed_harms or [])}"
        ev_ids = evidence_ids or ["E001"]

        # =========================================================================
        # Stage 1: Deterministic Applicability & Jurisdiction Pre-Screen (Article 2)
        # =========================================================================
        has_eu_nexus = bool(EU_GEO_KEYWORDS.search(text_corpus))
        is_military = bool(MILITARY_KEYWORDS.search(text_corpus))
        is_research = bool(RESEARCH_KEYWORDS.search(text_corpus))

        if is_military:
            jurisdiction = JurisdictionScope.NOT_APPLICABLE
            jurisdiction_rationale = (
                "Excluded from statutory scope under Article 2(3): System developed or used exclusively for military/defense."
            )
        elif is_research:
            jurisdiction = JurisdictionScope.NOT_APPLICABLE
            jurisdiction_rationale = (
                "Excluded from statutory scope under Article 2(6): System developed or used exclusively for scientific research."
            )
        elif has_eu_nexus:
            jurisdiction = JurisdictionScope.APPLICABLE
            jurisdiction_rationale = (
                "Applicable under Article 2: Territorial nexus established through Union market placement, "
                "Union deployment, or output affecting natural persons within the Union."
            )
        else:
            jurisdiction = JurisdictionScope.UNDETERMINED
            jurisdiction_rationale = (
                "Undetermined under Article 2: Available source reporting does not definitively confirm EU market placement, "
                "deployer location, or EU user impact. Evaluated conditionally for European cross-border risk."
            )

        territorial_scope = TerritorialScopeAssessment(
            jurisdiction=jurisdiction,
            placed_on_union_market=has_eu_nexus,
            deployer_in_union=has_eu_nexus,
            output_used_in_union=has_eu_nexus,
            military_defense_exclusion=is_military,
            scientific_research_exclusion=is_research,
            rationale=jurisdiction_rationale,
        )

        # =========================================================================
        # Stage 2: Structured Regulatory Inference
        # =========================================================================

        # A. Article 5 Prohibited Practices
        is_prohibited = False
        proh_type = None
        proh_analysis = "No Article 5 prohibited practices indicated by available evidence."

        if PROHIBITION_SOCIAL_SCORING.search(text_corpus):
            is_prohibited = True
            proh_type = "Article 5(1)(c) — Social Scoring"
            proh_analysis = "Incident evidence indicates evaluation or classification of natural persons based on social behavior."
        elif PROHIBITION_FACIAL_SCRAPING.search(text_corpus):
            is_prohibited = True
            proh_type = "Article 5(1)(e) — Untargeted Facial Image Scraping"
            proh_analysis = "Incident evidence indicates untargeted scraping of facial images from the internet or CCTV footage."
        elif PROHIBITION_BIOMETRIC_CAT.search(text_corpus):
            is_prohibited = True
            proh_type = "Article 5(1)(g) — Biometric Categorization for Sensitive Attributes"
            proh_analysis = "Incident evidence indicates biometric categorization deducing political, religious, or philosophical beliefs."

        prohibited_finding = ProhibitedPracticeFinding(
            is_prohibited=is_prohibited,
            prohibition_type=proh_type,
            analysis=proh_analysis,
        )

        # B. Article 6 / Annex I / Annex III High-Risk Systems
        # Audit strictly against Regulation (EU) 2024/1689:
        # - Critical Infrastructure falls under Annex III Point 2 (management of digital & physical infrastructure)
        # - Financial essential services fall under Annex III Point 5 (credit scoring & financial risk evaluation)
        # - Medical devices & clinical diagnostic AI fall under Annex I (Item 11, MDR (EU) 2017/745)
        # - Robotics & industrial machinery fall under Annex I (Item 1, Machinery Reg (EU) 2023/1230)
        # - Biometrics & remote ID falls under Annex III Point 1
        is_high_risk = False
        annex_type = None
        annex_point = None
        high_risk_analysis = "System use-case does not fall under mandatory high-risk annexes based on available reporting."

        cat_upper = category.upper()
        if "CYBERSECURITY" in cat_upper or "INFRASTRUCTURE" in cat_upper or CRITICAL_INFRA_KEYWORDS.search(text_corpus):
            is_high_risk = True
            annex_type = "ANNEX_III"
            annex_point = "Annex III, point 2 — Critical Infrastructure (Management & Safety of Digital Infrastructure)"
            high_risk_analysis = "AI system is utilized as a safety or security component in the management of critical digital infrastructure."
        elif "FINANCIAL" in cat_upper or "ECONOMIC" in cat_upper or CREDIT_INSURANCE_KEYWORDS.search(text_corpus):
            is_high_risk = True
            annex_type = "ANNEX_III"
            annex_point = "Annex III, point 5 — Essential Services (Creditworthiness & Financial Risk Evaluation)"
            high_risk_analysis = "AI system evaluates creditworthiness, allocates essential financial resources, or models financial risk."
        elif HEALTHCARE_KEYWORDS.search(text_corpus) and ("HEALTH" in cat_upper or "SAFETY" in cat_upper or "MEDICAL" in cat_upper):
            is_high_risk = True
            annex_type = "ANNEX_I"
            annex_point = "Annex I, Section A (Item 11) — Medical Devices Regulation (EU) 2017/745"
            high_risk_analysis = (
                "AI system operates as clinical decision-support software or medical device safety component "
                "governed by Union harmonization legislation (Regulation (EU) 2017/745)."
            )
        elif ROBOTICS_MACHINERY_KEYWORDS.search(text_corpus) and ("ROBOT" in cat_upper or "SAFETY" in cat_upper or "AUTONOMY" in cat_upper):
            is_high_risk = True
            annex_type = "ANNEX_I"
            annex_point = "Annex I, Section A (Item 1) — Machinery Regulation (EU) 2023/1230"
            high_risk_analysis = (
                "AI system operates as an autonomous safety component in industrial machinery, vehicles, or robotics "
                "under Union harmonization legislation (Regulation (EU) 2023/1230)."
            )
        elif BIOMETRIC_KEYWORDS.search(text_corpus) or "RIGHTS" in cat_upper:
            is_high_risk = True
            annex_type = "ANNEX_III"
            annex_point = "Annex III, point 1 — Biometrics and Remote Biometric Identification"
            high_risk_analysis = "AI system operates in biometric identification, categorization, or remote verification."
        elif "SAFETY" in cat_upper:
            is_high_risk = True
            annex_type = "ANNEX_I"
            annex_point = "Annex I, Section A — Safety Component of Union Harmonization Product"
            high_risk_analysis = "AI system operates as an autonomous safety component under Union harmonization product safety legislation."

        high_risk_finding = HighRiskClassificationFinding(
            is_high_risk=is_high_risk,
            annex_type=annex_type,
            annex_point=annex_point,
            analysis=high_risk_analysis,
        )

        # C. Article 50 Transparency Obligations
        applies_transparency = False
        transparency_obs: list[str] = []
        transparency_analysis = "No specific Article 50 transparency duties triggered by available incident evidence."

        if SYNTHETIC_MEDIA_KEYWORDS.search(text_corpus):
            applies_transparency = True
            transparency_obs.append("Article 50(2) — Mandatory marking of synthetic audio, image, video, or deepfake content.")
            transparency_analysis = "AI system generated synthetic media without machine-detectable provenance watermark."
        elif CHATBOT_KEYWORDS.search(text_corpus):
            applies_transparency = True
            transparency_obs.append("Article 50(1) — Mandatory disclosure that natural person is interacting with an AI system.")
            transparency_analysis = "Natural persons interacted with AI system without clear and timely notification."

        transparency_finding = TransparencyObligationFinding(
            applies=applies_transparency,
            obligations=transparency_obs,
            analysis=transparency_analysis,
        )

        # D. System Classification
        if is_military or is_research:
            system_class = SystemClassification.EXCLUDED
        elif is_prohibited:
            system_class = SystemClassification.PROHIBITED_PRACTICE
        elif is_high_risk and annex_type == "ANNEX_I":
            system_class = SystemClassification.HIGH_RISK_ANNEX_I
        elif is_high_risk and annex_type == "ANNEX_III":
            system_class = SystemClassification.HIGH_RISK_ANNEX_III
        elif applies_transparency:
            system_class = SystemClassification.TRANSPARENCY_ONLY
        else:
            system_class = SystemClassification.GENERAL_AI_SYSTEM

        # E. Article 73 Serious Incident Reporting
        harms_text = " ".join(observed_harms or [])
        serious_criteria: list[str] = []
        is_serious = False
        det = SeriousIncidentDetermination.NON_SERIOUS

        if re.search(r"\b(death|fatal|kill|permanent injury|severe bodily harm)\b", text_corpus, re.IGNORECASE):
            is_serious = True
            serious_criteria.append("Article 73(a) — Death of a person or serious harm to a person's health.")
            det = SeriousIncidentDetermination.SERIOUS_INCIDENT
        elif re.search(r"\b(critical infrastructure|grid failure|blackout|outage.*emergency|hospital)\b", text_corpus, re.IGNORECASE):
            is_serious = True
            serious_criteria.append("Article 73(b) — Serious and irreversible disruption of the management or operation of critical infrastructure.")
            det = SeriousIncidentDetermination.SERIOUS_INCIDENT
        elif re.search(r"\b(fundamental rights|discrimination|civil rights|unlawful detention|liberty)\b", text_corpus, re.IGNORECASE):
            is_serious = True
            serious_criteria.append("Article 73(c) — Infringement of obligations under Union law intended to protect fundamental rights.")
            det = SeriousIncidentDetermination.POTENTIAL_SERIOUS_INCIDENT
        elif re.search(r"\b(property damage|financial collapse|severe pollution|catastrophic loss)\b", text_corpus, re.IGNORECASE):
            is_serious = True
            serious_criteria.append("Article 73(d) — Serious harm to property or the environment.")
            det = SeriousIncidentDetermination.POTENTIAL_SERIOUS_INCIDENT

        serious_finding = SeriousIncidentFinding(
            determination=det,
            criteria_met=serious_criteria,
            rationale=(
                f"Evaluated against Article 73 statutory thresholds. Identified criteria: "
                f"{'; '.join(serious_criteria) if serious_criteria else 'None demonstrated by current evidence.'}"
            ),
        )

        # F. Compliance Gaps & Timeline Adjustment
        gaps: list[ComplianceGapFinding] = []

        if is_prohibited:
            gaps.append(
                ComplianceGapFinding(
                    article="Article 5 (Prohibited AI Practices)",
                    requirement_summary="Strict prohibition against unacceptable-risk AI practices.",
                    gap_status=ComplianceGapStatus.DOCUMENTED_GAP,
                    finding=f"Incident demonstrates deployment matching prohibited practice criteria: {proh_type}.",
                    evidence_ids=ev_ids,
                    timeline_status=EnforcementTimelineStatus.ACTIVE_LAW,
                )
            )

        if is_high_risk:
            # Article 14 Human Oversight
            art14_tl, art14_note = get_timeline_status_for_article("Article 14")
            raw_gap = ComplianceGapStatus.POTENTIAL_GAP
            adjusted_gap = adjust_gap_status_for_timeline(raw_gap, art14_tl)
            gaps.append(
                ComplianceGapFinding(
                    article="Article 14 (Human Oversight)",
                    requirement_summary="High-risk AI systems must be designed to enable effective human oversight, intervention, and emergency stop.",
                    gap_status=adjusted_gap,
                    finding="Evidence indicates human oversight was unable to interrupt autonomous execution cascade in real time.",
                    evidence_ids=ev_ids,
                    timeline_status=art14_tl,
                )
            )

            # Article 9 Risk Management System
            art9_tl, _ = get_timeline_status_for_article("Article 9")
            gaps.append(
                ComplianceGapFinding(
                    article="Article 9 (Risk Management System)",
                    requirement_summary="Continuous, iterative risk management system identifying foreseeable post-deployment failure modes.",
                    gap_status=adjust_gap_status_for_timeline(ComplianceGapStatus.POTENTIAL_GAP, art9_tl),
                    finding="Risk management procedures did not anticipate autonomous failure condition manifested during the incident.",
                    evidence_ids=ev_ids,
                    timeline_status=art9_tl,
                )
            )

            # Article 15 Accuracy, Robustness, and Cybersecurity
            art15_tl, _ = get_timeline_status_for_article("Article 15")
            gaps.append(
                ComplianceGapFinding(
                    article="Article 15 (Accuracy, Robustness, and Cybersecurity)",
                    requirement_summary="Resilience against errors, faults, and adversarial exploitation.",
                    gap_status=adjust_gap_status_for_timeline(ComplianceGapStatus.POTENTIAL_GAP, art15_tl),
                    finding="System exhibited vulnerability to adversarial input or unhandled environment edge case.",
                    evidence_ids=ev_ids,
                    timeline_status=art15_tl,
                )
            )

        if applies_transparency:
            art50_tl, _ = get_timeline_status_for_article("Article 50")
            gaps.append(
                ComplianceGapFinding(
                    article="Article 50 (Transparency Obligations)",
                    requirement_summary="Mandatory disclosure of AI interaction and synthetic media watermarking.",
                    gap_status=ComplianceGapStatus.DOCUMENTED_GAP,
                    finding="Deployer failed to provide clear disclosure or synthetic provenance markers required by Article 50.",
                    evidence_ids=ev_ids,
                    timeline_status=art50_tl,
                )
            )

        # G. Overall Timeline & Notes
        if is_prohibited or applies_transparency:
            overall_timeline = EnforcementTimelineStatus.ACTIVE_LAW
            notes = (
                "Statutory obligations governing this incident (Article 5 prohibitions and/or Article 50 transparency) "
                "are currently in full legal force under the November 2026 baseline."
            )
        elif is_high_risk:
            overall_timeline = EnforcementTimelineStatus.NOT_YET_APPLICABLE
            notes = (
                "High-risk obligations under Annex III become legally enforceable on December 2, 2027. "
                "Current findings provide compliance gap analysis and organizational preparedness guidance."
            )
        else:
            overall_timeline = EnforcementTimelineStatus.ACTIVE_LAW
            notes = "Evaluated under standard governance baseline as of November 2026."

        return EUAIActComplianceAssessment(
            incident_id=incident_id,
            assessed_at=datetime.now(timezone.utc).isoformat(),
            baseline_date=str(BASELINE_EVALUATION_DATE),
            territorial_scope=territorial_scope,
            system_classification=system_class,
            prohibited_practice=prohibited_finding,
            high_risk=high_risk_finding,
            transparency=transparency_finding,
            serious_incident=serious_finding,
            compliance_gaps=gaps,
            overall_enforcement_status=overall_timeline,
            timeline_notes=notes,
        )
