"""Deterministic, evidence-grounded conceptual relevance rules for Regulation (EU) 2024/1689.

Phase 5 Increment 2C-3A Implementation:
Evaluates factual correspondence between verified incident evidence and statutory reference concepts:
- Article 5 concepts (Prohibited AI practice concepts - points 5.1.a through 5.1.h, and parent Art. 5)
- Annex III concepts (High-risk critical areas - points 1 through 8, and parent Art. 6)
- Article 50 concepts (Transparency - points 50.1, 50.2, 50.4, and parent Art. 50)
- General-Purpose AI concepts (Articles 51 and 53)
- Operational control concepts (Articles 10, 12, 14, 15, 72, 73)
- Serious incident conceptual relevance (Article 3(49))

Non-Negotiable Safety Invariants:
- Informational governance screening ONLY; does NOT determine statutory applicability, jurisdiction,
  legal role, legal obligation, compliance, non-compliance, breach, violation, or liability.
- Grounded strictly in verified incident evidence records (zero evidence = zero affirmative findings).
- Avoids negative inference: absent facts are preserved as explicit unknowns.
- All affirmative findings unconditionally route to PENDING_REVIEW.
- Programmatically validated against prohibited legal conclusion terminology (Safety Rule 7).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from ai_incident_monitor.governance.enums import (
    ControlLevel,
    EUConceptType,
    EUConceptualRelevanceLevel,
    EUEvidenceStrength,
    EUScreenStatus,
    EUSeriousIncidentRelevance,
    FrameworkCode,
    GovernanceConfidence,
)
from ai_incident_monitor.governance.models import (
    EUConceptualEvaluationResult,
    EUConceptualFinding,
    EUScreenRuleTraceSchema,
    IncidentFactContext,
    MappingRuleMetadata,
    validate_no_legal_language,
)

# Canonical EU reference set identifier and content hash from frameworks/manifest.json
EU_REFERENCE_SET_ID = "eu-ai-act-2024-1689"
EU_REFERENCE_VERSION = "2024/1689"
EU_REFERENCE_CONTENT_HASH = "c5b25d21a4b4c7ec022f8b8c0b39dae48f1b9a96041f89ad082d5bfaff2b2d11"


class BaseEUConceptualRule(ABC):
    """Abstract base class for EU AI Act deterministic conceptual relevance rules."""

    @property
    @abstractmethod
    def metadata(self) -> MappingRuleMetadata:
        """Rule specification and metadata."""
        ...

    @property
    @abstractmethod
    def concept_type(self) -> EUConceptType:
        """Categorical classification of the concept."""
        ...

    @property
    @abstractmethod
    def target_identifier(self) -> str:
        """Canonical external identifier from the validated reference library."""
        ...

    @property
    @abstractmethod
    def source_locator(self) -> str:
        """Official pinpoint citation in the publication."""
        ...

    @abstractmethod
    def evaluate(self, context: IncidentFactContext) -> Optional[EUConceptualFinding]:
        """Evaluate rule deterministically against incident context.

        Returns EUConceptualFinding if conceptual correspondence is identified or
        if an explicit epistemic gap is evaluated, or None if the concept is unengaged.
        """
        ...


# ==============================================================================
# Helper for Evidence Strength & Confidence Calculation
# ==============================================================================


def _resolve_evidence_strength(context: IncidentFactContext) -> tuple[EUEvidenceStrength, GovernanceConfidence]:
    """Resolve evidence strength and orthogonal confidence for a conceptual finding."""
    if not context.evidence_records:
        return EUEvidenceStrength.INSUFFICIENT, GovernanceConfidence.INSUFFICIENT

    if context.disputed_facts or "disputed" in context.fact_tags:
        return EUEvidenceStrength.DISPUTED, GovernanceConfidence.LOW

    has_corroboration = any(
        ev.get("corroboration_status") == "FULLY_CORROBORATED"
        for ev in context.evidence_records
    ) or len(context.evidence_records) >= 2

    has_primary = any(
        ev.get("directness") in {"PRIMARY_DIRECT", "PRIMARY_OBSERVATIONAL"}
        for ev in context.evidence_records
    )

    if has_corroboration and has_primary:
        return EUEvidenceStrength.CORROBORATED, GovernanceConfidence.HIGH
    elif has_primary:
        return EUEvidenceStrength.DIRECT, GovernanceConfidence.MEDIUM
    else:
        return EUEvidenceStrength.INDICATIVE, GovernanceConfidence.LOW


# ==============================================================================
# Rule Family D1: Article 5 Concepts (Prohibited AI Practices Concepts)
# ==============================================================================


class BaseArticle5ConceptualRule(BaseEUConceptualRule):
    """Base class for Article 5 prohibited practice conceptual screening."""

    @property
    def concept_type(self) -> EUConceptType:
        return EUConceptType.ARTICLE_5_CONCEPT


class EUArticle5SubliminalManipulativeRule(BaseArticle5ConceptualRule):
    """Screens for cognitive manipulation and behavioral distortion concepts under Art. 5(1)(a)."""

    RULE_ID = "RULE-EU-CONC-PROHIB-01"
    RULE_VERSION = "1.0.0"
    TARGET_ID = "EU-ART-5.1.a"
    LOCATOR = "Regulation (EU) 2024/1689, Article 5(1)(a)"

    @property
    def target_identifier(self) -> str:
        return self.TARGET_ID

    @property
    def source_locator(self) -> str:
        return self.LOCATOR

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.EU_AI_ACT,
            target_identifier=self.TARGET_ID,
            target_level=ControlLevel.ARTICLE,
            title="EU Article 5(1)(a) — Subliminal, Manipulative, or Deceptive Techniques",
            description=(
                "Screens for factual evidence describing subliminal techniques or purposeful "
                "manipulative/deceptive distortion of human behavior causing significant physical or psychological harm."
            ),
            prerequisite_fact_keys=[
                "subliminal_technique",
                "behavioral_manipulation",
                "cognitive_distortion",
                "deceptive_interface",
            ],
            applicability=EUConceptualRelevanceLevel.POTENTIALLY_RELEVANT_FOR_QUALIFIED_REVIEW.value,
        )

    def evaluate(self, context: IncidentFactContext) -> Optional[EUConceptualFinding]:
        if not context.evidence_records:
            return None

        tags = {
            "subliminal_technique",
            "behavioral_manipulation",
            "cognitive_distortion",
            "deceptive_interface",
            "manipulative_ai",
            "dark_pattern_distortion",
        }
        matched = tags.intersection(context.fact_tags)
        if not matched and not context.system_context.get("manipulative_techniques"):
            return None

        evidence_ids = [ev.get("id") for ev in context.evidence_records if ev.get("id")]
        strength, confidence = _resolve_evidence_strength(context)

        rationale = (
            "Recorded facts describe system techniques designed to influence human behavior "
            "beyond conscious awareness or through purposeful deception, corresponding conceptually "
            "to Article 5(1)(a) behavioral distortion themes."
        )
        validate_no_legal_language(rationale, field_name="rationale")

        obs = f"Observed factual signals for cognitive manipulation: {', '.join(sorted(matched)) if matched else 'system context flag'}"
        validate_no_legal_language(obs, field_name="known_facts")

        return EUConceptualFinding(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            reference_id=self.TARGET_ID,
            control_title=self.metadata.title,
            source_locator=self.LOCATOR,
            concept_type=self.concept_type,
            relevance_level=EUConceptualRelevanceLevel.POTENTIALLY_RELEVANT_FOR_QUALIFIED_REVIEW,
            evidence_strength=strength,
            evidence_ids=evidence_ids,
            known_facts=[obs],
            unknowns=["Whether documented behavioral impacts reached the statutory significant harm threshold."],
            disputed_facts=list(context.disputed_facts),
            rationale=rationale,
            matched_condition_ids=["COND-CONC-PROHIB-SUBLIMINAL"],
            confidence=confidence,
            review_routing=EUScreenStatus.PENDING_REVIEW,
        )


class EUArticle5VulnerabilityExploitationRule(BaseArticle5ConceptualRule):
    """Screens for vulnerability exploitation concepts under Art. 5(1)(b)."""

    RULE_ID = "RULE-EU-CONC-PROHIB-02"
    RULE_VERSION = "1.0.0"
    TARGET_ID = "EU-ART-5.1.b"
    LOCATOR = "Regulation (EU) 2024/1689, Article 5(1)(b)"

    @property
    def target_identifier(self) -> str:
        return self.TARGET_ID

    @property
    def source_locator(self) -> str:
        return self.LOCATOR

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.EU_AI_ACT,
            target_identifier=self.TARGET_ID,
            target_level=ControlLevel.ARTICLE,
            title="EU Article 5(1)(b) — Exploitation of Vulnerabilities",
            description="Screens for exploitation of age, disability, or socio-economic vulnerabilities.",
            prerequisite_fact_keys=["vulnerability_exploitation", "child_exploitation", "disability_exploitation"],
            applicability=EUConceptualRelevanceLevel.POTENTIALLY_RELEVANT_FOR_QUALIFIED_REVIEW.value,
        )

    def evaluate(self, context: IncidentFactContext) -> Optional[EUConceptualFinding]:
        if not context.evidence_records:
            return None

        tags = {
            "vulnerability_exploitation",
            "child_exploitation",
            "elderly_targeting",
            "disability_exploitation",
            "exploitative_targeting",
            "socioeconomic_exploitation",
        }
        matched = tags.intersection(context.fact_tags)
        if not matched and not context.system_context.get("vulnerability_exploitation"):
            return None

        evidence_ids = [ev.get("id") for ev in context.evidence_records if ev.get("id")]
        strength, confidence = _resolve_evidence_strength(context)

        rationale = (
            "Recorded facts document system interaction exploiting specific vulnerabilities of natural persons "
            "related to age, disability, or socio-economic standing, conceptually engaging Article 5(1)(b)."
        )
        validate_no_legal_language(rationale, field_name="rationale")

        obs = f"Observed factual signals for vulnerability targeting: {', '.join(sorted(matched)) if matched else 'system context flag'}"
        validate_no_legal_language(obs, field_name="known_facts")

        return EUConceptualFinding(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            reference_id=self.TARGET_ID,
            control_title=self.metadata.title,
            source_locator=self.LOCATOR,
            concept_type=self.concept_type,
            relevance_level=EUConceptualRelevanceLevel.POTENTIALLY_RELEVANT_FOR_QUALIFIED_REVIEW,
            evidence_strength=strength,
            evidence_ids=evidence_ids,
            known_facts=[obs],
            unknowns=["Degree of specific vulnerability impairment resulting from system interaction."],
            disputed_facts=list(context.disputed_facts),
            rationale=rationale,
            matched_condition_ids=["COND-CONC-PROHIB-VULNERABILITY"],
            confidence=confidence,
            review_routing=EUScreenStatus.PENDING_REVIEW,
        )


class EUArticle5SocialScoringRule(BaseArticle5ConceptualRule):
    """Screens for social scoring concepts under Art. 5(1)(c)."""

    RULE_ID = "RULE-EU-CONC-PROHIB-03"
    RULE_VERSION = "1.0.0"
    TARGET_ID = "EU-ART-5.1.c"
    LOCATOR = "Regulation (EU) 2024/1689, Article 5(1)(c)"

    @property
    def target_identifier(self) -> str:
        return self.TARGET_ID

    @property
    def source_locator(self) -> str:
        return self.LOCATOR

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.EU_AI_ACT,
            target_identifier=self.TARGET_ID,
            target_level=ControlLevel.ARTICLE,
            title="EU Article 5(1)(c) — Social Scoring",
            description="Screens for evaluation of persons based on social behavior leading to detrimental treatment.",
            prerequisite_fact_keys=["social_scoring", "citizen_scoring", "behavioral_social_credit"],
            applicability=EUConceptualRelevanceLevel.POTENTIALLY_RELEVANT_FOR_QUALIFIED_REVIEW.value,
        )

    def evaluate(self, context: IncidentFactContext) -> Optional[EUConceptualFinding]:
        if not context.evidence_records:
            return None

        tags = {"social_scoring", "citizen_scoring", "behavioral_social_credit", "social_trust_rating"}
        matched = tags.intersection(context.fact_tags)
        if not matched and not context.system_context.get("social_scoring"):
            return None

        evidence_ids = [ev.get("id") for ev in context.evidence_records if ev.get("id")]
        strength, confidence = _resolve_evidence_strength(context)

        rationale = (
            "Recorded facts indicate evaluation or classification of natural persons based on social behavior "
            "or personality traits leading to adverse treatment, corresponding conceptually to Article 5(1)(c)."
        )
        validate_no_legal_language(rationale, field_name="rationale")

        obs = f"Observed factual signals for social scoring: {', '.join(sorted(matched)) if matched else 'system context flag'}"
        validate_no_legal_language(obs, field_name="known_facts")

        return EUConceptualFinding(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            reference_id=self.TARGET_ID,
            control_title=self.metadata.title,
            source_locator=self.LOCATOR,
            concept_type=self.concept_type,
            relevance_level=EUConceptualRelevanceLevel.POTENTIALLY_RELEVANT_FOR_QUALIFIED_REVIEW,
            evidence_strength=strength,
            evidence_ids=evidence_ids,
            known_facts=[obs],
            unknowns=["Whether scoring was enacted by public authorities or under private initiative."],
            disputed_facts=list(context.disputed_facts),
            rationale=rationale,
            matched_condition_ids=["COND-CONC-PROHIB-SOCIAL-SCORING"],
            confidence=confidence,
            review_routing=EUScreenStatus.PENDING_REVIEW,
        )


class EUArticle5PredictivePolicingRule(BaseArticle5ConceptualRule):
    """Screens for predictive policing or criminal risk assessment profiling under Art. 5(1)(d)."""

    RULE_ID = "RULE-EU-CONC-PROHIB-04"
    RULE_VERSION = "1.0.0"
    TARGET_ID = "EU-ART-5.1.d"
    LOCATOR = "Regulation (EU) 2024/1689, Article 5(1)(d)"

    @property
    def target_identifier(self) -> str:
        return self.TARGET_ID

    @property
    def source_locator(self) -> str:
        return self.LOCATOR

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.EU_AI_ACT,
            target_identifier=self.TARGET_ID,
            target_level=ControlLevel.ARTICLE,
            title="EU Article 5(1)(d) — Predictive Policing / Criminal Offence Profiling",
            description="Screens for individual risk assessment predicting criminal offence likelihood based solely on profiling.",
            prerequisite_fact_keys=["predictive_policing", "criminal_risk_assessment_profiling"],
            applicability=EUConceptualRelevanceLevel.POTENTIALLY_RELEVANT_FOR_QUALIFIED_REVIEW.value,
        )

    def evaluate(self, context: IncidentFactContext) -> Optional[EUConceptualFinding]:
        if not context.evidence_records:
            return None

        tags = {
            "predictive_policing",
            "criminal_risk_assessment_profiling",
            "recidivism_profiling",
            "crime_prediction_individual",
        }
        matched = tags.intersection(context.fact_tags)
        if not matched and not context.system_context.get("predictive_policing"):
            return None

        evidence_ids = [ev.get("id") for ev in context.evidence_records if ev.get("id")]
        strength, confidence = _resolve_evidence_strength(context)

        rationale = (
            "Recorded facts describe individual risk assessments or personality profiling predicting "
            "criminal offence likelihood, corresponding conceptually to Article 5(1)(d) profiling themes."
        )
        validate_no_legal_language(rationale, field_name="rationale")

        obs = f"Observed factual signals for predictive policing: {', '.join(sorted(matched)) if matched else 'system context flag'}"
        validate_no_legal_language(obs, field_name="known_facts")

        return EUConceptualFinding(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            reference_id=self.TARGET_ID,
            control_title=self.metadata.title,
            source_locator=self.LOCATOR,
            concept_type=self.concept_type,
            relevance_level=EUConceptualRelevanceLevel.POTENTIALLY_RELEVANT_FOR_QUALIFIED_REVIEW,
            evidence_strength=strength,
            evidence_ids=evidence_ids,
            known_facts=[obs],
            unknowns=["Whether assessment was supported by objective verifiable facts directly linked to criminal activity."],
            disputed_facts=list(context.disputed_facts),
            rationale=rationale,
            matched_condition_ids=["COND-CONC-PROHIB-PREDICTIVE-POLICING"],
            confidence=confidence,
            review_routing=EUScreenStatus.PENDING_REVIEW,
        )


class EUArticle5FacialScrapingRule(BaseArticle5ConceptualRule):
    """Screens for untargeted facial image scraping under Art. 5(1)(e)."""

    RULE_ID = "RULE-EU-CONC-PROHIB-05"
    RULE_VERSION = "1.0.0"
    TARGET_ID = "EU-ART-5.1.e"
    LOCATOR = "Regulation (EU) 2024/1689, Article 5(1)(e)"

    @property
    def target_identifier(self) -> str:
        return self.TARGET_ID

    @property
    def source_locator(self) -> str:
        return self.LOCATOR

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.EU_AI_ACT,
            target_identifier=self.TARGET_ID,
            target_level=ControlLevel.ARTICLE,
            title="EU Article 5(1)(e) — Untargeted Facial Image Scraping",
            description="Screens for untargeted scraping of facial images from the internet or CCTV footage.",
            prerequisite_fact_keys=["untargeted_facial_scraping", "cctv_facial_scraping"],
            applicability=EUConceptualRelevanceLevel.POTENTIALLY_RELEVANT_FOR_QUALIFIED_REVIEW.value,
        )

    def evaluate(self, context: IncidentFactContext) -> Optional[EUConceptualFinding]:
        if not context.evidence_records:
            return None

        tags = {
            "untargeted_facial_scraping",
            "cctv_facial_scraping",
            "internet_facial_harvesting",
            "bulk_face_scraping",
        }
        matched = tags.intersection(context.fact_tags)
        if not matched and not context.system_context.get("facial_scraping"):
            return None

        evidence_ids = [ev.get("id") for ev in context.evidence_records if ev.get("id")]
        strength, confidence = _resolve_evidence_strength(context)

        rationale = (
            "Evidence records indicate untargeted collection or bulk extraction of facial imagery "
            "from online platforms or surveillance streams to populate facial databases (Article 5(1)(e) concept)."
        )
        validate_no_legal_language(rationale, field_name="rationale")

        obs = f"Observed factual signals for bulk facial harvesting: {', '.join(sorted(matched)) if matched else 'system context flag'}"
        validate_no_legal_language(obs, field_name="known_facts")

        return EUConceptualFinding(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            reference_id=self.TARGET_ID,
            control_title=self.metadata.title,
            source_locator=self.LOCATOR,
            concept_type=self.concept_type,
            relevance_level=EUConceptualRelevanceLevel.POTENTIALLY_RELEVANT_FOR_QUALIFIED_REVIEW,
            evidence_strength=strength,
            evidence_ids=evidence_ids,
            known_facts=[obs],
            unknowns=["Specific geographic provenance of scraped imagery."],
            disputed_facts=list(context.disputed_facts),
            rationale=rationale,
            matched_condition_ids=["COND-CONC-PROHIB-FACIAL-SCRAPING"],
            confidence=confidence,
            review_routing=EUScreenStatus.PENDING_REVIEW,
        )


class EUArticle5EmotionRecognitionRule(BaseArticle5ConceptualRule):
    """Screens for workplace or educational emotion recognition under Art. 5(1)(f)."""

    RULE_ID = "RULE-EU-CONC-PROHIB-06"
    RULE_VERSION = "1.0.0"
    TARGET_ID = "EU-ART-5.1.f"
    LOCATOR = "Regulation (EU) 2024/1689, Article 5(1)(f)"

    @property
    def target_identifier(self) -> str:
        return self.TARGET_ID

    @property
    def source_locator(self) -> str:
        return self.LOCATOR

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.EU_AI_ACT,
            target_identifier=self.TARGET_ID,
            target_level=ControlLevel.ARTICLE,
            title="EU Article 5(1)(f) — Emotion Recognition in Workplace and Education",
            description="Screens for emotion recognition systems deployed in employment or educational settings.",
            prerequisite_fact_keys=["workplace_emotion_recognition", "educational_emotion_recognition"],
            applicability=EUConceptualRelevanceLevel.POTENTIALLY_RELEVANT_FOR_QUALIFIED_REVIEW.value,
        )

    def evaluate(self, context: IncidentFactContext) -> Optional[EUConceptualFinding]:
        if not context.evidence_records:
            return None

        tags = {
            "workplace_emotion_recognition",
            "educational_emotion_recognition",
            "workplace_affect_monitoring",
            "student_emotion_tracking",
        }
        matched = tags.intersection(context.fact_tags)
        if not matched and not context.system_context.get("emotion_recognition_workplace_education"):
            return None

        evidence_ids = [ev.get("id") for ev in context.evidence_records if ev.get("id")]
        strength, confidence = _resolve_evidence_strength(context)

        rationale = (
            "Recorded facts describe inferencing of emotional states of workers or students within "
            "employment or educational contexts, corresponding to Article 5(1)(f) themes."
        )
        validate_no_legal_language(rationale, field_name="rationale")

        obs = f"Observed factual signals for emotion inference: {', '.join(sorted(matched)) if matched else 'system context flag'}"
        validate_no_legal_language(obs, field_name="known_facts")

        return EUConceptualFinding(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            reference_id=self.TARGET_ID,
            control_title=self.metadata.title,
            source_locator=self.LOCATOR,
            concept_type=self.concept_type,
            relevance_level=EUConceptualRelevanceLevel.POTENTIALLY_RELEVANT_FOR_QUALIFIED_REVIEW,
            evidence_strength=strength,
            evidence_ids=evidence_ids,
            known_facts=[obs],
            unknowns=["Whether system served medical or safety exception purposes."],
            disputed_facts=list(context.disputed_facts),
            rationale=rationale,
            matched_condition_ids=["COND-CONC-PROHIB-EMOTION-REC"],
            confidence=confidence,
            review_routing=EUScreenStatus.PENDING_REVIEW,
        )


class EUArticle5BiometricCategorizationRule(BaseArticle5ConceptualRule):
    """Screens for sensitive biometric categorization under Art. 5(1)(g)."""

    RULE_ID = "RULE-EU-CONC-PROHIB-07"
    RULE_VERSION = "1.0.0"
    TARGET_ID = "EU-ART-5.1.g"
    LOCATOR = "Regulation (EU) 2024/1689, Article 5(1)(g)"

    @property
    def target_identifier(self) -> str:
        return self.TARGET_ID

    @property
    def source_locator(self) -> str:
        return self.LOCATOR

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.EU_AI_ACT,
            target_identifier=self.TARGET_ID,
            target_level=ControlLevel.ARTICLE,
            title="EU Article 5(1)(g) — Biometric Categorization for Sensitive Traits",
            description="Screens for biometric deduction of race, political opinions, or religious beliefs.",
            prerequisite_fact_keys=["sensitive_biometric_categorization", "race_inference_biometric"],
            applicability=EUConceptualRelevanceLevel.POTENTIALLY_RELEVANT_FOR_QUALIFIED_REVIEW.value,
        )

    def evaluate(self, context: IncidentFactContext) -> Optional[EUConceptualFinding]:
        if not context.evidence_records:
            return None

        tags = {
            "sensitive_biometric_categorization",
            "race_inference_biometric",
            "political_belief_biometric",
            "sexual_orientation_biometric",
        }
        matched = tags.intersection(context.fact_tags)
        if not matched and not context.system_context.get("sensitive_biometric_categorization"):
            return None

        evidence_ids = [ev.get("id") for ev in context.evidence_records if ev.get("id")]
        strength, confidence = _resolve_evidence_strength(context)

        rationale = (
            "Recorded facts indicate biometric analysis deducing protected sensitive attributes "
            "(e.g., race, political beliefs, sexual orientation), corresponding to Article 5(1)(g) concepts."
        )
        validate_no_legal_language(rationale, field_name="rationale")

        obs = f"Observed factual signals for sensitive biometric categorization: {', '.join(sorted(matched)) if matched else 'system context flag'}"
        validate_no_legal_language(obs, field_name="known_facts")

        return EUConceptualFinding(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            reference_id=self.TARGET_ID,
            control_title=self.metadata.title,
            source_locator=self.LOCATOR,
            concept_type=self.concept_type,
            relevance_level=EUConceptualRelevanceLevel.POTENTIALLY_RELEVANT_FOR_QUALIFIED_REVIEW,
            evidence_strength=strength,
            evidence_ids=evidence_ids,
            known_facts=[obs],
            unknowns=["Whether categorization occurred in lawful law enforcement filtering contexts."],
            disputed_facts=list(context.disputed_facts),
            rationale=rationale,
            matched_condition_ids=["COND-CONC-PROHIB-BIOMETRIC-CAT"],
            confidence=confidence,
            review_routing=EUScreenStatus.PENDING_REVIEW,
        )


# ==============================================================================
class EUArticle5RealTimeBiometricRule(BaseArticle5ConceptualRule):
    """Screens for real-time remote biometric identification in publicly accessible spaces under Art. 5(1)(h)."""

    RULE_ID = "RULE-EU-CONC-PROHIB-08"
    RULE_VERSION = "1.0.0"
    TARGET_ID = "EU-ART-5.1.h"
    LOCATOR = "Regulation (EU) 2024/1689, Article 5(1)(h)"

    @property
    def target_identifier(self) -> str:
        return self.TARGET_ID

    @property
    def source_locator(self) -> str:
        return self.LOCATOR

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.EU_AI_ACT,
            target_identifier=self.TARGET_ID,
            target_level=ControlLevel.ARTICLE,
            title="EU Article 5(1)(h) — Real-Time Remote Biometric Identification in Public Spaces",
            description="Screens for live remote biometric identification across publicly accessible spaces.",
            prerequisite_fact_keys=["real_time_biometric_id", "public_space_facial_recognition"],
            applicability=EUConceptualRelevanceLevel.POTENTIALLY_RELEVANT_FOR_QUALIFIED_REVIEW.value,
        )

    def evaluate(self, context: IncidentFactContext) -> Optional[EUConceptualFinding]:
        if not context.evidence_records:
            return None

        tags = {
            "real_time_biometric_id",
            "public_space_facial_recognition",
            "live_crowd_surveillance",
            "public_space_cctv_biometrics",
        }
        matched = tags.intersection(context.fact_tags)
        if not matched and not context.system_context.get("real_time_biometrics"):
            return None

        evidence_ids = [ev.get("id") for ev in context.evidence_records if ev.get("id")]
        strength, confidence = _resolve_evidence_strength(context)

        rationale = (
            "Recorded facts describe live remote biometric identification deployed across publicly accessible "
            "spaces, corresponding conceptually to Article 5(1)(h) surveillance parameters."
        )
        validate_no_legal_language(rationale, field_name="rationale")

        obs = f"Observed factual signals for real-time public biometrics: {', '.join(sorted(matched)) if matched else 'system context flag'}"
        validate_no_legal_language(obs, field_name="known_facts")

        return EUConceptualFinding(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            reference_id=self.TARGET_ID,
            control_title=self.metadata.title,
            source_locator=self.LOCATOR,
            concept_type=self.concept_type,
            relevance_level=EUConceptualRelevanceLevel.POTENTIALLY_RELEVANT_FOR_QUALIFIED_REVIEW,
            evidence_strength=strength,
            evidence_ids=evidence_ids,
            known_facts=[obs],
            unknowns=["Whether deployment was conducted under statutory law enforcement exceptions or prior judicial authorization."],
            disputed_facts=list(context.disputed_facts),
            rationale=rationale,
            matched_condition_ids=["COND-CONC-PROHIB-REALTIME-BIOMETRIC"],
            confidence=confidence,
            review_routing=EUScreenStatus.PENDING_REVIEW,
        )


# ==============================================================================
# Rule Family D2: Annex III Concepts (Regulated Operational Domains)
# ==============================================================================


class BaseAnnexIIIConceptualRule(BaseEUConceptualRule):
    """Base class for Annex III domain-specific conceptual screening."""

    @property
    def concept_type(self) -> EUConceptType:
        return EUConceptType.ANNEX_III_CONCEPT


class EUAnnex3BiometricsRule(BaseAnnexIIIConceptualRule):
    """Screens for remote biometric identification and categorization in permitted contexts (Annex III Point 1)."""

    RULE_ID = "RULE-EU-CONC-ANNEX3-01"
    RULE_VERSION = "1.0.0"
    TARGET_ID = "EU-ANNEX-III.1"
    LOCATOR = "Regulation (EU) 2024/1689, Annex III, Point 1"

    @property
    def target_identifier(self) -> str:
        return self.TARGET_ID

    @property
    def source_locator(self) -> str:
        return self.LOCATOR

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.EU_AI_ACT,
            target_identifier=self.TARGET_ID,
            target_level=ControlLevel.ANNEX,
            title="EU Annex III Point 1 — Biometrics",
            description="Screens for remote biometric identification, biometric categorization, or emotion recognition outside prohibited contexts.",
            prerequisite_fact_keys=["remote_biometric_identification", "biometric_verification"],
            applicability=EUConceptualRelevanceLevel.CONCEPTUALLY_RELEVANT.value,
        )

    def evaluate(self, context: IncidentFactContext) -> Optional[EUConceptualFinding]:
        if not context.evidence_records:
            return None

        tags = {
            "remote_biometric_identification",
            "biometric_verification",
            "emotion_recognition_system",
            "biometric_categorization",
        }
        matched = tags.intersection(context.fact_tags)
        if not matched and not any(sd.value == "BIOMETRICS" for sd in context.sensitive_domains):
            return None

        evidence_ids = [ev.get("id") for ev in context.evidence_records if ev.get("id")]
        strength, confidence = _resolve_evidence_strength(context)

        rationale = (
            "Recorded facts indicate deployment of remote biometric identification or categorization "
            "outside prohibited domains, corresponding conceptually to Annex III Point 1 areas."
        )
        validate_no_legal_language(rationale, field_name="rationale")

        obs = f"Observed factual signals for biometric processing: {', '.join(sorted(matched)) if matched else 'sensitive domain tag'}"
        validate_no_legal_language(obs, field_name="known_facts")

        return EUConceptualFinding(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            reference_id=self.TARGET_ID,
            control_title=self.metadata.title,
            source_locator=self.LOCATOR,
            concept_type=self.concept_type,
            relevance_level=EUConceptualRelevanceLevel.CONCEPTUALLY_RELEVANT,
            evidence_strength=strength,
            evidence_ids=evidence_ids,
            known_facts=[obs],
            unknowns=["Whether system was used solely for biometric verification or authentication of individual identity."],
            disputed_facts=list(context.disputed_facts),
            rationale=rationale,
            matched_condition_ids=["COND-CONC-ANNEX3-BIOMETRICS"],
            confidence=confidence,
            review_routing=EUScreenStatus.PENDING_REVIEW,
        )


class EUAnnex3CriticalInfrastructureRule(BaseAnnexIIIConceptualRule):
    """Screens for critical digital/physical infrastructure safety components (Annex III Point 2)."""

    RULE_ID = "RULE-EU-CONC-ANNEX3-02"
    RULE_VERSION = "1.0.0"
    TARGET_ID = "EU-ANNEX-III.2"
    LOCATOR = "Regulation (EU) 2024/1689, Annex III, Point 2"

    @property
    def target_identifier(self) -> str:
        return self.TARGET_ID

    @property
    def source_locator(self) -> str:
        return self.LOCATOR

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.EU_AI_ACT,
            target_identifier=self.TARGET_ID,
            target_level=ControlLevel.ANNEX,
            title="EU Annex III Point 2 — Critical Infrastructure",
            description="Screens for AI safety components in digital infrastructure, road traffic, utilities.",
            prerequisite_fact_keys=["critical_infrastructure_safety", "traffic_management_system"],
            applicability=EUConceptualRelevanceLevel.CONCEPTUALLY_RELEVANT.value,
        )

    def evaluate(self, context: IncidentFactContext) -> Optional[EUConceptualFinding]:
        if not context.evidence_records:
            return None

        tags = {
            "critical_infrastructure_safety",
            "power_grid_management",
            "water_supply_system",
            "traffic_management_system",
            "telecommunications_backbone",
        }
        matched = tags.intersection(context.fact_tags)
        if not matched and not any(sd.value == "CRITICAL_INFRASTRUCTURE" for sd in context.sensitive_domains):
            return None

        evidence_ids = [ev.get("id") for ev in context.evidence_records if ev.get("id")]
        strength, confidence = _resolve_evidence_strength(context)

        rationale = (
            "Recorded facts indicate deployment within critical utility, transport, or digital infrastructure "
            "where system outputs influence physical safety or supply continuity (Annex III Point 2 concept)."
        )
        validate_no_legal_language(rationale, field_name="rationale")

        obs = f"Observed factual signals for critical infrastructure operation: {', '.join(sorted(matched)) if matched else 'sensitive domain tag'}"
        validate_no_legal_language(obs, field_name="known_facts")

        return EUConceptualFinding(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            reference_id=self.TARGET_ID,
            control_title=self.metadata.title,
            source_locator=self.LOCATOR,
            concept_type=self.concept_type,
            relevance_level=EUConceptualRelevanceLevel.CONCEPTUALLY_RELEVANT,
            evidence_strength=strength,
            evidence_ids=evidence_ids,
            known_facts=[obs],
            unknowns=["Whether the system constituted a safety component under relevant product legislation."],
            disputed_facts=list(context.disputed_facts),
            rationale=rationale,
            matched_condition_ids=["COND-CONC-ANNEX3-INFRASTRUCTURE"],
            confidence=confidence,
            review_routing=EUScreenStatus.PENDING_REVIEW,
        )


class EUAnnex3EducationRule(BaseAnnexIIIConceptualRule):
    """Screens for educational admissions, student evaluation, and proctoring (Annex III Point 3)."""

    RULE_ID = "RULE-EU-CONC-ANNEX3-03"
    RULE_VERSION = "1.0.0"
    TARGET_ID = "EU-ANNEX-III.3"
    LOCATOR = "Regulation (EU) 2024/1689, Annex III, Point 3"

    @property
    def target_identifier(self) -> str:
        return self.TARGET_ID

    @property
    def source_locator(self) -> str:
        return self.LOCATOR

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.EU_AI_ACT,
            target_identifier=self.TARGET_ID,
            target_level=ControlLevel.ANNEX,
            title="EU Annex III Point 3 — Education and Vocational Training",
            description="Screens for AI systems used in student admissions, grading, assignment, or proctoring.",
            prerequisite_fact_keys=["educational_admissions", "student_evaluation_system"],
            applicability=EUConceptualRelevanceLevel.CONCEPTUALLY_RELEVANT.value,
        )

    def evaluate(self, context: IncidentFactContext) -> Optional[EUConceptualFinding]:
        if not context.evidence_records:
            return None

        tags = {
            "educational_admissions",
            "student_evaluation_system",
            "automated_proctoring",
            "vocational_placement",
        }
        matched = tags.intersection(context.fact_tags)
        if not matched and not any(sd.value == "EDUCATION" for sd in context.sensitive_domains):
            return None

        evidence_ids = [ev.get("id") for ev in context.evidence_records if ev.get("id")]
        strength, confidence = _resolve_evidence_strength(context)

        rationale = (
            "Recorded facts indicate deployment in educational admissions, student grading, or exam monitoring, "
            "corresponding conceptually to Annex III Point 3 areas."
        )
        validate_no_legal_language(rationale, field_name="rationale")

        obs = f"Observed factual signals for educational evaluation: {', '.join(sorted(matched)) if matched else 'sensitive domain tag'}"
        validate_no_legal_language(obs, field_name="known_facts")

        return EUConceptualFinding(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            reference_id=self.TARGET_ID,
            control_title=self.metadata.title,
            source_locator=self.LOCATOR,
            concept_type=self.concept_type,
            relevance_level=EUConceptualRelevanceLevel.CONCEPTUALLY_RELEVANT,
            evidence_strength=strength,
            evidence_ids=evidence_ids,
            known_facts=[obs],
            unknowns=["Whether system outputs directly determined educational access or course grading."],
            disputed_facts=list(context.disputed_facts),
            rationale=rationale,
            matched_condition_ids=["COND-CONC-ANNEX3-EDUCATION"],
            confidence=confidence,
            review_routing=EUScreenStatus.PENDING_REVIEW,
        )


class EUAnnex3EmploymentRule(BaseAnnexIIIConceptualRule):
    """Screens for recruitment, screening, task allocation, and worker management (Annex III Point 4)."""

    RULE_ID = "RULE-EU-CONC-ANNEX3-04"
    RULE_VERSION = "1.0.0"
    TARGET_ID = "EU-ANNEX-III.4"
    LOCATOR = "Regulation (EU) 2024/1689, Annex III, Point 4"

    @property
    def target_identifier(self) -> str:
        return self.TARGET_ID

    @property
    def source_locator(self) -> str:
        return self.LOCATOR

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.EU_AI_ACT,
            target_identifier=self.TARGET_ID,
            target_level=ControlLevel.ANNEX,
            title="EU Annex III Point 4 — Employment and Worker Management",
            description="Screens for AI recruitment screening, job advertising, task allocation, or performance tracking.",
            prerequisite_fact_keys=["recruitment_screening", "worker_performance_monitoring"],
            applicability=EUConceptualRelevanceLevel.CONCEPTUALLY_RELEVANT.value,
        )

    def evaluate(self, context: IncidentFactContext) -> Optional[EUConceptualFinding]:
        if not context.evidence_records:
            return None

        tags = {
            "recruitment_screening",
            "workforce_task_allocation",
            "worker_performance_monitoring",
            "automated_dismissal",
            "resume_filtering",
        }
        matched = tags.intersection(context.fact_tags)
        if not matched and not any(sd.value == "EMPLOYMENT" for sd in context.sensitive_domains):
            return None

        evidence_ids = [ev.get("id") for ev in context.evidence_records if ev.get("id")]
        strength, confidence = _resolve_evidence_strength(context)

        rationale = (
            "Recorded facts describe AI utilization in hiring, resume filtering, task allocation, or worker evaluation, "
            "corresponding conceptually to Annex III Point 4 employment management themes."
        )
        validate_no_legal_language(rationale, field_name="rationale")

        obs = f"Observed factual signals for employment screening: {', '.join(sorted(matched)) if matched else 'sensitive domain tag'}"
        validate_no_legal_language(obs, field_name="known_facts")

        return EUConceptualFinding(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            reference_id=self.TARGET_ID,
            control_title=self.metadata.title,
            source_locator=self.LOCATOR,
            concept_type=self.concept_type,
            relevance_level=EUConceptualRelevanceLevel.CONCEPTUALLY_RELEVANT,
            evidence_strength=strength,
            evidence_ids=evidence_ids,
            known_facts=[obs],
            unknowns=["Degree of human discretion retained in employment decisions."],
            disputed_facts=list(context.disputed_facts),
            rationale=rationale,
            matched_condition_ids=["COND-CONC-ANNEX3-EMPLOYMENT"],
            confidence=confidence,
            review_routing=EUScreenStatus.PENDING_REVIEW,
        )


class EUAnnex3EssentialServicesRule(BaseAnnexIIIConceptualRule):
    """Screens for credit scoring, insurance risk pricing, and emergency dispatch (Annex III Point 5)."""

    RULE_ID = "RULE-EU-CONC-ANNEX3-05"
    RULE_VERSION = "1.0.0"
    TARGET_ID = "EU-ANNEX-III.5"
    LOCATOR = "Regulation (EU) 2024/1689, Annex III, Point 5"

    @property
    def target_identifier(self) -> str:
        return self.TARGET_ID

    @property
    def source_locator(self) -> str:
        return self.LOCATOR

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.EU_AI_ACT,
            target_identifier=self.TARGET_ID,
            target_level=ControlLevel.ANNEX,
            title="EU Annex III Point 5 — Essential Public and Private Services",
            description="Screens for credit scoring, life/health insurance risk assessment, public benefit eligibility, and emergency dispatch.",
            prerequisite_fact_keys=["creditworthiness_evaluation", "emergency_call_dispatch"],
            applicability=EUConceptualRelevanceLevel.CONCEPTUALLY_RELEVANT.value,
        )

    def evaluate(self, context: IncidentFactContext) -> Optional[EUConceptualFinding]:
        if not context.evidence_records:
            return None

        tags = {
            "creditworthiness_evaluation",
            "health_insurance_risk_pricing",
            "public_benefit_eligibility",
            "emergency_call_dispatch",
            "credit_underwriting",
        }
        matched = tags.intersection(context.fact_tags)
        if not matched and not any(sd.value in {"CREDIT", "HEALTH_SAFETY"} for sd in context.sensitive_domains):
            return None

        evidence_ids = [ev.get("id") for ev in context.evidence_records if ev.get("id")]
        strength, confidence = _resolve_evidence_strength(context)

        rationale = (
            "Recorded facts document system application in evaluating creditworthiness, access to public benefits, "
            "insurance risk categorization, or emergency response triage (Annex III Point 5 concepts)."
        )
        validate_no_legal_language(rationale, field_name="rationale")

        obs = f"Observed factual signals for essential service access: {', '.join(sorted(matched)) if matched else 'sensitive domain tag'}"
        validate_no_legal_language(obs, field_name="known_facts")

        return EUConceptualFinding(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            reference_id=self.TARGET_ID,
            control_title=self.metadata.title,
            source_locator=self.LOCATOR,
            concept_type=self.concept_type,
            relevance_level=EUConceptualRelevanceLevel.CONCEPTUALLY_RELEVANT,
            evidence_strength=strength,
            evidence_ids=evidence_ids,
            known_facts=[obs],
            unknowns=["Whether system operated in standalone mode or as an advisory input to human adjudicators."],
            disputed_facts=list(context.disputed_facts),
            rationale=rationale,
            matched_condition_ids=["COND-CONC-ANNEX3-ESSENTIAL-SERVICES"],
            confidence=confidence,
            review_routing=EUScreenStatus.PENDING_REVIEW,
        )


# ==============================================================================
class EUAnnex3LawEnforcementRule(BaseAnnexIIIConceptualRule):
    """Screens for law enforcement risk assessment, polygraph, and evidence evaluation (Annex III Point 6)."""

    RULE_ID = "RULE-EU-CONC-ANNEX3-06"
    RULE_VERSION = "1.0.0"
    TARGET_ID = "EU-ANNEX-III.6"
    LOCATOR = "Regulation (EU) 2024/1689, Annex III, Point 6"

    @property
    def target_identifier(self) -> str:
        return self.TARGET_ID

    @property
    def source_locator(self) -> str:
        return self.LOCATOR

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.EU_AI_ACT,
            target_identifier=self.TARGET_ID,
            target_level=ControlLevel.ANNEX,
            title="EU Annex III Point 6 — Law Enforcement",
            description="Screens for AI deployment by or for law enforcement authorities for risk assessment, evidence evaluation, or profiling.",
            prerequisite_fact_keys=["law_enforcement_ai", "police_risk_assessment"],
            applicability=EUConceptualRelevanceLevel.CONCEPTUALLY_RELEVANT.value,
        )

    def evaluate(self, context: IncidentFactContext) -> Optional[EUConceptualFinding]:
        if not context.evidence_records:
            return None

        tags = {
            "law_enforcement_ai",
            "police_risk_assessment",
            "evidence_reliability_evaluation",
            "criminal_profiling",
            "polygraph_ai",
        }
        matched = tags.intersection(context.fact_tags)
        if not matched and not any(sd.value == "LAW_ENFORCEMENT" for sd in context.sensitive_domains):
            return None

        evidence_ids = [ev.get("id") for ev in context.evidence_records if ev.get("id")]
        strength, confidence = _resolve_evidence_strength(context)

        rationale = (
            "Recorded facts describe AI deployment in law enforcement operations for risk assessment, "
            "evidence evaluation, or individual profiling (Annex III Point 6 concept)."
        )
        validate_no_legal_language(rationale, field_name="rationale")

        obs = f"Observed factual signals for law enforcement AI usage: {', '.join(sorted(matched)) if matched else 'sensitive domain tag'}"
        validate_no_legal_language(obs, field_name="known_facts")

        return EUConceptualFinding(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            reference_id=self.TARGET_ID,
            control_title=self.metadata.title,
            source_locator=self.LOCATOR,
            concept_type=self.concept_type,
            relevance_level=EUConceptualRelevanceLevel.CONCEPTUALLY_RELEVANT,
            evidence_strength=strength,
            evidence_ids=evidence_ids,
            known_facts=[obs],
            unknowns=["Specific law enforcement operational context and evidentiary procedures."],
            disputed_facts=list(context.disputed_facts),
            rationale=rationale,
            matched_condition_ids=["COND-CONC-ANNEX3-LAW-ENFORCEMENT"],
            confidence=confidence,
            review_routing=EUScreenStatus.PENDING_REVIEW,
        )


class EUAnnex3MigrationBorderRule(BaseAnnexIIIConceptualRule):
    """Screens for migration, asylum, and border control management (Annex III Point 7)."""

    RULE_ID = "RULE-EU-CONC-ANNEX3-07"
    RULE_VERSION = "1.0.0"
    TARGET_ID = "EU-ANNEX-III.7"
    LOCATOR = "Regulation (EU) 2024/1689, Annex III, Point 7"

    @property
    def target_identifier(self) -> str:
        return self.TARGET_ID

    @property
    def source_locator(self) -> str:
        return self.LOCATOR

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.EU_AI_ACT,
            target_identifier=self.TARGET_ID,
            target_level=ControlLevel.ANNEX,
            title="EU Annex III Point 7 — Migration, Asylum, and Border Control",
            description="Screens for AI systems used in border control, examining asylum or visa applications, or traveller risk assessment.",
            prerequisite_fact_keys=["border_control_ai", "asylum_application_screening"],
            applicability=EUConceptualRelevanceLevel.CONCEPTUALLY_RELEVANT.value,
        )

    def evaluate(self, context: IncidentFactContext) -> Optional[EUConceptualFinding]:
        if not context.evidence_records:
            return None

        tags = {
            "border_control_ai",
            "asylum_application_screening",
            "visa_adjudication_ai",
            "entry_risk_assessment",
            "traveller_verification_ai",
        }
        matched = tags.intersection(context.fact_tags)
        if not matched and not any(sd.value == "MIGRATION" for sd in context.sensitive_domains):
            return None

        evidence_ids = [ev.get("id") for ev in context.evidence_records if ev.get("id")]
        strength, confidence = _resolve_evidence_strength(context)

        rationale = (
            "Recorded facts describe AI usage in border management, visa processing, or asylum "
            "determination, corresponding conceptually to Annex III Point 7 criteria."
        )
        validate_no_legal_language(rationale, field_name="rationale")

        obs = f"Observed factual signals for migration/border management: {', '.join(sorted(matched)) if matched else 'sensitive domain tag'}"
        validate_no_legal_language(obs, field_name="known_facts")

        return EUConceptualFinding(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            reference_id=self.TARGET_ID,
            control_title=self.metadata.title,
            source_locator=self.LOCATOR,
            concept_type=self.concept_type,
            relevance_level=EUConceptualRelevanceLevel.CONCEPTUALLY_RELEVANT,
            evidence_strength=strength,
            evidence_ids=evidence_ids,
            known_facts=[obs],
            unknowns=["Whether decisions were subject to mandatory human officer review prior to border actions."],
            disputed_facts=list(context.disputed_facts),
            rationale=rationale,
            matched_condition_ids=["COND-CONC-ANNEX3-MIGRATION"],
            confidence=confidence,
            review_routing=EUScreenStatus.PENDING_REVIEW,
        )


class EUAnnex3JusticeDemocracyRule(BaseAnnexIIIConceptualRule):
    """Screens for judicial assistance, dispute resolution, and democratic processes (Annex III Point 8)."""

    RULE_ID = "RULE-EU-CONC-ANNEX3-08"
    RULE_VERSION = "1.0.0"
    TARGET_ID = "EU-ANNEX-III.8"
    LOCATOR = "Regulation (EU) 2024/1689, Annex III, Point 8"

    @property
    def target_identifier(self) -> str:
        return self.TARGET_ID

    @property
    def source_locator(self) -> str:
        return self.LOCATOR

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.EU_AI_ACT,
            target_identifier=self.TARGET_ID,
            target_level=ControlLevel.ANNEX,
            title="EU Annex III Point 8 — Administration of Justice and Democratic Processes",
            description="Screens for AI systems used in judicial research, dispute resolution, or influencing democratic/electoral processes.",
            prerequisite_fact_keys=["judicial_assistance_ai", "election_process_ai"],
            applicability=EUConceptualRelevanceLevel.CONCEPTUALLY_RELEVANT.value,
        )

    def evaluate(self, context: IncidentFactContext) -> Optional[EUConceptualFinding]:
        if not context.evidence_records:
            return None

        tags = {
            "judicial_assistance_ai",
            "legal_interpretation_ai",
            "alternative_dispute_resolution_ai",
            "election_monitoring_ai",
            "voter_influence_ai",
        }
        matched = tags.intersection(context.fact_tags)
        if not matched and not any(sd.value == "JUSTICE" for sd in context.sensitive_domains):
            return None

        evidence_ids = [ev.get("id") for ev in context.evidence_records if ev.get("id")]
        strength, confidence = _resolve_evidence_strength(context)

        rationale = (
            "Recorded facts describe AI application in judicial research, dispute resolution, or "
            "democratic processes, corresponding conceptually to Annex III Point 8 areas."
        )
        validate_no_legal_language(rationale, field_name="rationale")

        obs = f"Observed factual signals for justice/democratic processes: {', '.join(sorted(matched)) if matched else 'sensitive domain tag'}"
        validate_no_legal_language(obs, field_name="known_facts")

        return EUConceptualFinding(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            reference_id=self.TARGET_ID,
            control_title=self.metadata.title,
            source_locator=self.LOCATOR,
            concept_type=self.concept_type,
            relevance_level=EUConceptualRelevanceLevel.CONCEPTUALLY_RELEVANT,
            evidence_strength=strength,
            evidence_ids=evidence_ids,
            known_facts=[obs],
            unknowns=["Advisory versus determinative role of AI outputs in judicial or electoral administration."],
            disputed_facts=list(context.disputed_facts),
            rationale=rationale,
            matched_condition_ids=["COND-CONC-ANNEX3-JUSTICE"],
            confidence=confidence,
            review_routing=EUScreenStatus.PENDING_REVIEW,
        )


# ==============================================================================
# Rule Family D3: Article 50 Concepts (Transparency Concepts)
# ==============================================================================


class BaseArticle50ConceptualRule(BaseEUConceptualRule):
    """Base class for Article 50 transparency conceptual screening."""

    @property
    def concept_type(self) -> EUConceptType:
        return EUConceptType.ARTICLE_50_CONCEPT


class EUArticle50InteractionNotificationRule(BaseArticle50ConceptualRule):
    """Screens for direct AI-to-human interaction disclosure under Art. 50(1)."""

    RULE_ID = "RULE-EU-CONC-TRANSP-01"
    RULE_VERSION = "1.0.0"
    TARGET_ID = "EU-ART-50.1"
    LOCATOR = "Regulation (EU) 2024/1689, Article 50(1)"

    @property
    def target_identifier(self) -> str:
        return self.TARGET_ID

    @property
    def source_locator(self) -> str:
        return self.LOCATOR

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.EU_AI_ACT,
            target_identifier=self.TARGET_ID,
            target_level=ControlLevel.ARTICLE,
            title="EU Article 50(1) — Notification of AI Interaction",
            description="Screens for AI systems interacting directly with natural persons without clear disclosure.",
            prerequisite_fact_keys=["conversational_agent", "human_interaction_ai"],
            applicability=EUConceptualRelevanceLevel.CONCEPTUALLY_RELEVANT.value,
        )

    def evaluate(self, context: IncidentFactContext) -> Optional[EUConceptualFinding]:
        if not context.evidence_records:
            return None

        tags = {
            "conversational_agent",
            "human_interaction_ai",
            "customer_service_chatbot",
            "voice_assistant_interaction",
        }
        matched = tags.intersection(context.fact_tags)
        if not matched and not context.system_context.get("conversational_interaction"):
            return None

        evidence_ids = [ev.get("id") for ev in context.evidence_records if ev.get("id")]
        strength, confidence = _resolve_evidence_strength(context)

        rationale = (
            "Recorded facts describe AI systems directly interacting with natural persons without obvious "
            "mechanical disclosure, corresponding conceptually to Article 50(1) notification themes."
        )
        validate_no_legal_language(rationale, field_name="rationale")

        obs = f"Observed factual signals for human-AI interaction: {', '.join(sorted(matched)) if matched else 'system context flag'}"
        validate_no_legal_language(obs, field_name="known_facts")

        return EUConceptualFinding(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            reference_id=self.TARGET_ID,
            control_title=self.metadata.title,
            source_locator=self.LOCATOR,
            concept_type=self.concept_type,
            relevance_level=EUConceptualRelevanceLevel.CONCEPTUALLY_RELEVANT,
            evidence_strength=strength,
            evidence_ids=evidence_ids,
            known_facts=[obs],
            unknowns=["Whether user disclosure was presented at initial interaction onset."],
            disputed_facts=list(context.disputed_facts),
            rationale=rationale,
            matched_condition_ids=["COND-CONC-TRANSP-INTERACTION"],
            confidence=confidence,
            review_routing=EUScreenStatus.PENDING_REVIEW,
        )


class EUArticle50SyntheticMediaRule(BaseArticle50ConceptualRule):
    """Screens for synthetic media, deepfake, or voice cloning context under Art. 50(2)."""

    RULE_ID = "RULE-EU-CONC-TRANSP-02"
    RULE_VERSION = "1.0.0"
    TARGET_ID = "EU-ART-50.2"
    LOCATOR = "Regulation (EU) 2024/1689, Article 50(2)"

    @property
    def target_identifier(self) -> str:
        return self.TARGET_ID

    @property
    def source_locator(self) -> str:
        return self.LOCATOR

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.EU_AI_ACT,
            target_identifier=self.TARGET_ID,
            target_level=ControlLevel.ARTICLE,
            title="EU Article 50(2) — Labeling of Synthetic Media and Deepfakes",
            description="Screens for synthetic audio, image, video, or deepfake generation context.",
            prerequisite_fact_keys=["synthetic_media_labeling", "deepfake_content"],
            applicability=EUConceptualRelevanceLevel.CONCEPTUALLY_RELEVANT.value,
        )

    def evaluate(self, context: IncidentFactContext) -> Optional[EUConceptualFinding]:
        if not context.evidence_records:
            return None

        tags = {
            "synthetic_media_labeling",
            "deepfake_content",
            "voice_cloning_replication",
            "generated_image_labeling",
            "synthetic_video_generation",
        }
        matched = tags.intersection(context.fact_tags)
        if not matched and not context.system_context.get("synthetic_media"):
            return None

        evidence_ids = [ev.get("id") for ev in context.evidence_records if ev.get("id")]
        strength, confidence = _resolve_evidence_strength(context)

        rationale = (
            "Recorded facts document generation of synthetic media, likeness manipulation, or deepfake content, "
            "corresponding conceptually to Article 50(2) synthetic content identification themes."
        )
        validate_no_legal_language(rationale, field_name="rationale")

        obs = f"Observed factual signals for synthetic media generation: {', '.join(sorted(matched)) if matched else 'system context flag'}"
        validate_no_legal_language(obs, field_name="known_facts")

        return EUConceptualFinding(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            reference_id=self.TARGET_ID,
            control_title=self.metadata.title,
            source_locator=self.LOCATOR,
            concept_type=self.concept_type,
            relevance_level=EUConceptualRelevanceLevel.CONCEPTUALLY_RELEVANT,
            evidence_strength=strength,
            evidence_ids=evidence_ids,
            known_facts=[obs],
            unknowns=["Whether technical watermarking or visible disclosure markers were embedded in outputs."],
            disputed_facts=list(context.disputed_facts),
            rationale=rationale,
            matched_condition_ids=["COND-CONC-TRANSP-SYNTHETIC-MEDIA"],
            confidence=confidence,
            review_routing=EUScreenStatus.PENDING_REVIEW,
        )


# ==============================================================================
class EUArticle50TextDisclosureRule(BaseArticle50ConceptualRule):
    """Screens for AI-generated text informing the public on matters of public interest under Art. 50(4)."""

    RULE_ID = "RULE-EU-CONC-TRANSP-04"
    RULE_VERSION = "1.0.0"
    TARGET_ID = "EU-ART-50.4"
    LOCATOR = "Regulation (EU) 2024/1689, Article 50(4)"

    @property
    def target_identifier(self) -> str:
        return self.TARGET_ID

    @property
    def source_locator(self) -> str:
        return self.LOCATOR

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.EU_AI_ACT,
            target_identifier=self.TARGET_ID,
            target_level=ControlLevel.ARTICLE,
            title="EU Article 50(4) — Disclosure of AI-Generated Public Text",
            description="Screens for AI-generated or manipulated text published to inform the public on matters of public interest.",
            prerequisite_fact_keys=["ai_generated_public_text", "automated_news_generation"],
            applicability=EUConceptualRelevanceLevel.CONCEPTUALLY_RELEVANT.value,
        )

    def evaluate(self, context: IncidentFactContext) -> Optional[EUConceptualFinding]:
        if not context.evidence_records:
            return None

        tags = {
            "ai_generated_public_text",
            "automated_news_generation",
            "public_information_synthesis",
            "synthetic_article_publication",
        }
        matched = tags.intersection(context.fact_tags)
        if not matched and not context.system_context.get("public_text_generation"):
            return None

        evidence_ids = [ev.get("id") for ev in context.evidence_records if ev.get("id")]
        strength, confidence = _resolve_evidence_strength(context)

        rationale = (
            "Recorded facts indicate publication of AI-generated or manipulated text intended to inform the "
            "public on matters of public interest, corresponding conceptually to Article 50(4) disclosure parameters."
        )
        validate_no_legal_language(rationale, field_name="rationale")

        obs = f"Observed factual signals for AI-generated public text: {', '.join(sorted(matched)) if matched else 'system context flag'}"
        validate_no_legal_language(obs, field_name="known_facts")

        return EUConceptualFinding(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            reference_id=self.TARGET_ID,
            control_title=self.metadata.title,
            source_locator=self.LOCATOR,
            concept_type=self.concept_type,
            relevance_level=EUConceptualRelevanceLevel.CONCEPTUALLY_RELEVANT,
            evidence_strength=strength,
            evidence_ids=evidence_ids,
            known_facts=[obs],
            unknowns=["Whether editorial review and human responsibility were retained prior to public distribution."],
            disputed_facts=list(context.disputed_facts),
            rationale=rationale,
            matched_condition_ids=["COND-CONC-TRANSP-PUBLIC-TEXT"],
            confidence=confidence,
            review_routing=EUScreenStatus.PENDING_REVIEW,
        )


# ==============================================================================
# Rule Family D4: General-Purpose AI Concepts (Articles 51 & 53)
# ==============================================================================


class BaseGPAIConceptualRule(BaseEUConceptualRule):
    """Base class for General-Purpose AI model conceptual screening."""

    @property
    def concept_type(self) -> EUConceptType:
        return EUConceptType.GPAI_CONCEPT


class EUGPAISystemicRiskRule(BaseGPAIConceptualRule):
    """Screens for systemic risk criteria in high-compute general-purpose foundation models (Art. 51)."""

    RULE_ID = "RULE-EU-CONC-GPAI-01"
    RULE_VERSION = "1.0.0"
    TARGET_ID = "EU-ART-51"
    LOCATOR = "Regulation (EU) 2024/1689, Article 51"

    @property
    def target_identifier(self) -> str:
        return self.TARGET_ID

    @property
    def source_locator(self) -> str:
        return self.LOCATOR

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.EU_AI_ACT,
            target_identifier=self.TARGET_ID,
            target_level=ControlLevel.ARTICLE,
            title="EU Article 51 — General-Purpose AI Models with Systemic Risk",
            description="Screens for high-compute foundation model context (>10^25 FLOPs) or wide systemic impact surface.",
            prerequisite_fact_keys=["gpai_systemic_risk", "high_compute_foundation_model"],
            applicability=EUConceptualRelevanceLevel.CONCEPTUALLY_RELEVANT.value,
        )

    def evaluate(self, context: IncidentFactContext) -> Optional[EUConceptualFinding]:
        if not context.evidence_records:
            return None

        tags = {
            "gpai_systemic_risk",
            "high_compute_foundation_model",
            "frontier_model_capabilities",
            "catastrophic_risk_surface",
        }
        matched = tags.intersection(context.fact_tags)
        if not matched and not context.system_context.get("systemic_risk_gpai"):
            return None

        evidence_ids = [ev.get("id") for ev in context.evidence_records if ev.get("id")]
        strength, confidence = _resolve_evidence_strength(context)

        rationale = (
            "Recorded facts indicate involvement of a general-purpose AI model with substantial training compute "
            "or wide cross-sectoral downstream surface, corresponding conceptually to Article 51 systemic risk parameters."
        )
        validate_no_legal_language(rationale, field_name="rationale")

        obs = f"Observed factual signals for foundation model systemic risk: {', '.join(sorted(matched)) if matched else 'system context flag'}"
        validate_no_legal_language(obs, field_name="known_facts")

        return EUConceptualFinding(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            reference_id=self.TARGET_ID,
            control_title=self.metadata.title,
            source_locator=self.LOCATOR,
            concept_type=self.concept_type,
            relevance_level=EUConceptualRelevanceLevel.CONCEPTUALLY_RELEVANT,
            evidence_strength=strength,
            evidence_ids=evidence_ids,
            known_facts=[obs],
            unknowns=["Exact cumulative floating-point operations (FLOPs) used in model pre-training."],
            disputed_facts=list(context.disputed_facts),
            rationale=rationale,
            matched_condition_ids=["COND-CONC-GPAI-SYSTEMIC"],
            confidence=confidence,
            review_routing=EUScreenStatus.PENDING_REVIEW,
        )


# ==============================================================================
class EUGPAIProviderObligationsRule(BaseGPAIConceptualRule):
    """Screens for documentation, copyright policy, and model card transparency under Art. 53."""

    RULE_ID = "RULE-EU-CONC-GPAI-02"
    RULE_VERSION = "1.0.0"
    TARGET_ID = "EU-ART-53"
    LOCATOR = "Regulation (EU) 2024/1689, Article 53"

    @property
    def target_identifier(self) -> str:
        return self.TARGET_ID

    @property
    def source_locator(self) -> str:
        return self.LOCATOR

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.EU_AI_ACT,
            target_identifier=self.TARGET_ID,
            target_level=ControlLevel.ARTICLE,
            title="EU Article 53 — Obligations for Providers of General-Purpose AI Models",
            description="Screens for technical documentation, training data summary transparency, or copyright policy gaps.",
            prerequisite_fact_keys=["gpai_provider_documentation", "model_training_summary"],
            applicability=EUConceptualRelevanceLevel.CONCEPTUALLY_RELEVANT.value,
        )

    def evaluate(self, context: IncidentFactContext) -> Optional[EUConceptualFinding]:
        if not context.evidence_records:
            return None

        tags = {
            "gpai_provider_documentation",
            "model_training_summary",
            "copyright_compliance_policy",
            "downstream_integration_docs",
        }
        matched = tags.intersection(context.fact_tags)
        if not matched and not context.system_context.get("gpai_documentation_gap"):
            return None

        evidence_ids = [ev.get("id") for ev in context.evidence_records if ev.get("id")]
        strength, confidence = _resolve_evidence_strength(context)

        rationale = (
            "Recorded facts describe technical documentation, training data transparency, or copyright "
            "policy issues for general-purpose AI models, corresponding conceptually to Article 53 parameters."
        )
        validate_no_legal_language(rationale, field_name="rationale")

        obs = f"Observed factual signals for GPAI model documentation: {', '.join(sorted(matched)) if matched else 'system context flag'}"
        validate_no_legal_language(obs, field_name="known_facts")

        return EUConceptualFinding(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            reference_id=self.TARGET_ID,
            control_title=self.metadata.title,
            source_locator=self.LOCATOR,
            concept_type=self.concept_type,
            relevance_level=EUConceptualRelevanceLevel.CONCEPTUALLY_RELEVANT,
            evidence_strength=strength,
            evidence_ids=evidence_ids,
            known_facts=[obs],
            unknowns=["Completeness of publicly available model cards and training data documentation."],
            disputed_facts=list(context.disputed_facts),
            rationale=rationale,
            matched_condition_ids=["COND-CONC-GPAI-DOCS"],
            confidence=confidence,
            review_routing=EUScreenStatus.PENDING_REVIEW,
        )


# ==============================================================================
# Rule Family D5: Operational Control Concepts
# ==============================================================================


class BaseOperationalControlConceptualRule(BaseEUConceptualRule):
    """Base class for operational control conceptual screening."""

    @property
    def concept_type(self) -> EUConceptType:
        return EUConceptType.OPERATIONAL_CONTROL_CONCEPT


class EUArticle10DataGovernanceRule(BaseOperationalControlConceptualRule):
    """Screens for data quality, bias mitigation, and governance gaps under Art. 10."""

    RULE_ID = "RULE-EU-CONC-OPS-DATA"
    RULE_VERSION = "1.0.0"
    TARGET_ID = "EU-ART-10"
    LOCATOR = "Regulation (EU) 2024/1689, Article 10"

    @property
    def target_identifier(self) -> str:
        return self.TARGET_ID

    @property
    def source_locator(self) -> str:
        return self.LOCATOR

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.EU_AI_ACT,
            target_identifier=self.TARGET_ID,
            target_level=ControlLevel.ARTICLE,
            title="EU Article 10 — Data and Data Governance",
            description="Screens for training/testing dataset quality, demographic representation, or data curation gaps.",
            prerequisite_fact_keys=["training_data_governance", "data_quality_deficiency"],
            applicability=EUConceptualRelevanceLevel.CONCEPTUALLY_RELEVANT.value,
        )

    def evaluate(self, context: IncidentFactContext) -> Optional[EUConceptualFinding]:
        if not context.evidence_records:
            return None

        tags = {
            "training_data_governance",
            "data_quality_deficiency",
            "dataset_bias",
            "demographic_unrepresentativeness",
            "data_contamination",
        }
        matched = tags.intersection(context.fact_tags)
        if not matched and not context.system_context.get("data_governance_gap"):
            return None

        evidence_ids = [ev.get("id") for ev in context.evidence_records if ev.get("id")]
        strength, confidence = _resolve_evidence_strength(context)

        rationale = (
            "Recorded facts document anomalies in training dataset curation, demographic representation, "
            "or data quality management, corresponding conceptually to Article 10 data governance themes."
        )
        validate_no_legal_language(rationale, field_name="rationale")

        obs = f"Observed factual signals for data governance: {', '.join(sorted(matched)) if matched else 'system context flag'}"
        validate_no_legal_language(obs, field_name="known_facts")

        return EUConceptualFinding(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            reference_id=self.TARGET_ID,
            control_title=self.metadata.title,
            source_locator=self.LOCATOR,
            concept_type=self.concept_type,
            relevance_level=EUConceptualRelevanceLevel.CONCEPTUALLY_RELEVANT,
            evidence_strength=strength,
            evidence_ids=evidence_ids,
            known_facts=[obs],
            unknowns=["Data governance protocols enacted prior to system deployment."],
            disputed_facts=list(context.disputed_facts),
            rationale=rationale,
            matched_condition_ids=["COND-CONC-OPS-DATA"],
            confidence=confidence,
            review_routing=EUScreenStatus.PENDING_REVIEW,
        )


class EUArticle12LoggingRule(BaseOperationalControlConceptualRule):
    """Screens for automatic recording of events and technical logging gaps under Art. 12."""

    RULE_ID = "RULE-EU-CONC-OPS-LOGS"
    RULE_VERSION = "1.0.0"
    TARGET_ID = "EU-ART-12"
    LOCATOR = "Regulation (EU) 2024/1689, Article 12"

    @property
    def target_identifier(self) -> str:
        return self.TARGET_ID

    @property
    def source_locator(self) -> str:
        return self.LOCATOR

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.EU_AI_ACT,
            target_identifier=self.TARGET_ID,
            target_level=ControlLevel.ARTICLE,
            title="EU Article 12 — Record-Keeping and Technical Logging",
            description="Screens for deficiencies in automatic event recording, logging duration, or traceability.",
            prerequisite_fact_keys=["audit_logging_deficiency", "event_recording_gap"],
            applicability=EUConceptualRelevanceLevel.CONCEPTUALLY_RELEVANT.value,
        )

    def evaluate(self, context: IncidentFactContext) -> Optional[EUConceptualFinding]:
        if not context.evidence_records:
            return None

        tags = {
            "audit_logging_deficiency",
            "event_recording_gap",
            "telemetry_failure",
            "traceability_gap",
        }
        matched = tags.intersection(context.fact_tags)
        if not matched and not context.system_context.get("logging_gap"):
            return None

        evidence_ids = [ev.get("id") for ev in context.evidence_records if ev.get("id")]
        strength, confidence = _resolve_evidence_strength(context)

        rationale = (
            "Recorded facts document deficiencies in system event logging, audit trails, or operational "
            "traceability, corresponding conceptually to Article 12 record-keeping themes."
        )
        validate_no_legal_language(rationale, field_name="rationale")

        obs = f"Observed factual signals for logging/record-keeping: {', '.join(sorted(matched)) if matched else 'system context flag'}"
        validate_no_legal_language(obs, field_name="known_facts")

        return EUConceptualFinding(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            reference_id=self.TARGET_ID,
            control_title=self.metadata.title,
            source_locator=self.LOCATOR,
            concept_type=self.concept_type,
            relevance_level=EUConceptualRelevanceLevel.CONCEPTUALLY_RELEVANT,
            evidence_strength=strength,
            evidence_ids=evidence_ids,
            known_facts=[obs],
            unknowns=["Retention windows and cryptographic protections of operational audit logs."],
            disputed_facts=list(context.disputed_facts),
            rationale=rationale,
            matched_condition_ids=["COND-CONC-OPS-LOGS"],
            confidence=confidence,
            review_routing=EUScreenStatus.PENDING_REVIEW,
        )


class EUArticle14HumanOversightRule(BaseOperationalControlConceptualRule):
    """Screens for human oversight, automation bias, and intervention gaps under Art. 14."""

    RULE_ID = "RULE-EU-CONC-OPS-OVERSIGHT"
    RULE_VERSION = "1.0.0"
    TARGET_ID = "EU-ART-14"
    LOCATOR = "Regulation (EU) 2024/1689, Article 14"

    @property
    def target_identifier(self) -> str:
        return self.TARGET_ID

    @property
    def source_locator(self) -> str:
        return self.LOCATOR

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.EU_AI_ACT,
            target_identifier=self.TARGET_ID,
            target_level=ControlLevel.ARTICLE,
            title="EU Article 14 — Human Oversight",
            description="Screens for failures in human-in-the-loop intervention, stop buttons, or automation bias.",
            prerequisite_fact_keys=["human_oversight_failure", "automation_bias"],
            applicability=EUConceptualRelevanceLevel.CONCEPTUALLY_RELEVANT.value,
        )

    def evaluate(self, context: IncidentFactContext) -> Optional[EUConceptualFinding]:
        if not context.evidence_records:
            return None

        tags = {
            "human_oversight_failure",
            "automation_bias",
            "missing_override_mechanism",
            "inadequate_human_intervention",
            "lack_of_operator_control",
        }
        matched = tags.intersection(context.fact_tags)
        if not matched and not context.system_context.get("oversight_gap"):
            return None

        evidence_ids = [ev.get("id") for ev in context.evidence_records if ev.get("id")]
        strength, confidence = _resolve_evidence_strength(context)

        rationale = (
            "Recorded facts indicate that human operators were unable to oversee, intercept, or stop automated "
            "system actions in a timely manner, corresponding conceptually to Article 14 human oversight themes."
        )
        validate_no_legal_language(rationale, field_name="rationale")

        obs = f"Observed factual signals for human oversight: {', '.join(sorted(matched)) if matched else 'system context flag'}"
        validate_no_legal_language(obs, field_name="known_facts")

        return EUConceptualFinding(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            reference_id=self.TARGET_ID,
            control_title=self.metadata.title,
            source_locator=self.LOCATOR,
            concept_type=self.concept_type,
            relevance_level=EUConceptualRelevanceLevel.CONCEPTUALLY_RELEVANT,
            evidence_strength=strength,
            evidence_ids=evidence_ids,
            known_facts=[obs],
            unknowns=["Operational training and technical tools available to human operators during deployment."],
            disputed_facts=list(context.disputed_facts),
            rationale=rationale,
            matched_condition_ids=["COND-CONC-OPS-OVERSIGHT"],
            confidence=confidence,
            review_routing=EUScreenStatus.PENDING_REVIEW,
        )


class EUArticle15RobustnessCybersecurityRule(BaseOperationalControlConceptualRule):
    """Screens for accuracy degradation, adversarial vulnerability, and cybersecurity incidents under Art. 15."""

    RULE_ID = "RULE-EU-CONC-OPS-ROBUST"
    RULE_VERSION = "1.0.0"
    TARGET_ID = "EU-ART-15"
    LOCATOR = "Regulation (EU) 2024/1689, Article 15"

    @property
    def target_identifier(self) -> str:
        return self.TARGET_ID

    @property
    def source_locator(self) -> str:
        return self.LOCATOR

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.EU_AI_ACT,
            target_identifier=self.TARGET_ID,
            target_level=ControlLevel.ARTICLE,
            title="EU Article 15 — Accuracy, Robustness, and Cybersecurity",
            description="Screens for adversarial vulnerabilities, prompt injection susceptibility, or technical instability.",
            prerequisite_fact_keys=["adversarial_vulnerability", "prompt_injection_susceptibility"],
            applicability=EUConceptualRelevanceLevel.CONCEPTUALLY_RELEVANT.value,
        )

    def evaluate(self, context: IncidentFactContext) -> Optional[EUConceptualFinding]:
        if not context.evidence_records:
            return None

        tags = {
            "adversarial_vulnerability",
            "prompt_injection_susceptibility",
            "accuracy_degradation",
            "cybersecurity_incident",
            "jailbreak_exploit",
            "model_evasion",
        }
        matched = tags.intersection(context.fact_tags)
        if not matched and not context.system_context.get("robustness_gap"):
            return None

        evidence_ids = [ev.get("id") for ev in context.evidence_records if ev.get("id")]
        strength, confidence = _resolve_evidence_strength(context)

        rationale = (
            "Recorded facts describe technical vulnerabilities to adversarial manipulation, prompt injection, "
            "or significant performance degradation under anomalous inputs (Article 15 concepts)."
        )
        validate_no_legal_language(rationale, field_name="rationale")

        obs = f"Observed factual signals for robustness/security: {', '.join(sorted(matched)) if matched else 'system context flag'}"
        validate_no_legal_language(obs, field_name="known_facts")

        return EUConceptualFinding(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            reference_id=self.TARGET_ID,
            control_title=self.metadata.title,
            source_locator=self.LOCATOR,
            concept_type=self.concept_type,
            relevance_level=EUConceptualRelevanceLevel.CONCEPTUALLY_RELEVANT,
            evidence_strength=strength,
            evidence_ids=evidence_ids,
            known_facts=[obs],
            unknowns=["Pre-deployment adversarial testing protocols applied to the system."],
            disputed_facts=list(context.disputed_facts),
            rationale=rationale,
            matched_condition_ids=["COND-CONC-OPS-ROBUST"],
            confidence=confidence,
            review_routing=EUScreenStatus.PENDING_REVIEW,
        )


# ==============================================================================
class EUArticle72PostMarketMonitoringRule(BaseOperationalControlConceptualRule):
    """Screens for provider post-market monitoring and field telemetry gaps under Art. 72."""

    RULE_ID = "RULE-EU-CONC-OPS-PMM"
    RULE_VERSION = "1.0.0"
    TARGET_ID = "EU-ART-72"
    LOCATOR = "Regulation (EU) 2024/1689, Article 72"

    @property
    def target_identifier(self) -> str:
        return self.TARGET_ID

    @property
    def source_locator(self) -> str:
        return self.LOCATOR

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.EU_AI_ACT,
            target_identifier=self.TARGET_ID,
            target_level=ControlLevel.ARTICLE,
            title="EU Article 72 — Post-Market Monitoring by Providers",
            description="Screens for post-deployment performance surveillance, telemetry collection, or field drift analysis.",
            prerequisite_fact_keys=["post_market_monitoring_deficiency", "field_telemetry_gap"],
            applicability=EUConceptualRelevanceLevel.CONCEPTUALLY_RELEVANT.value,
        )

    def evaluate(self, context: IncidentFactContext) -> Optional[EUConceptualFinding]:
        if not context.evidence_records:
            return None

        tags = {
            "post_market_monitoring_deficiency",
            "field_telemetry_gap",
            "unmonitored_drift",
            "post_deployment_surveillance_gap",
        }
        matched = tags.intersection(context.fact_tags)
        if not matched and not context.system_context.get("post_market_monitoring_gap"):
            return None

        evidence_ids = [ev.get("id") for ev in context.evidence_records if ev.get("id")]
        strength, confidence = _resolve_evidence_strength(context)

        rationale = (
            "Recorded facts describe absence or inadequacy of active post-market monitoring or field "
            "performance surveillance, corresponding conceptually to Article 72 monitoring themes."
        )
        validate_no_legal_language(rationale, field_name="rationale")

        obs = f"Observed factual signals for post-market monitoring: {', '.join(sorted(matched)) if matched else 'system context flag'}"
        validate_no_legal_language(obs, field_name="known_facts")

        return EUConceptualFinding(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            reference_id=self.TARGET_ID,
            control_title=self.metadata.title,
            source_locator=self.LOCATOR,
            concept_type=self.concept_type,
            relevance_level=EUConceptualRelevanceLevel.CONCEPTUALLY_RELEVANT,
            evidence_strength=strength,
            evidence_ids=evidence_ids,
            known_facts=[obs],
            unknowns=["Pre-existing post-market monitoring plans filed with organizational oversight bodies."],
            disputed_facts=list(context.disputed_facts),
            rationale=rationale,
            matched_condition_ids=["COND-CONC-OPS-PMM"],
            confidence=confidence,
            review_routing=EUScreenStatus.PENDING_REVIEW,
        )


class EUArticle73SeriousIncidentReportingRule(BaseOperationalControlConceptualRule):
    """Screens for incident escalation and authority reporting protocols under Art. 73."""

    RULE_ID = "RULE-EU-CONC-OPS-REPORTING"
    RULE_VERSION = "1.0.0"
    TARGET_ID = "EU-ART-73"
    LOCATOR = "Regulation (EU) 2024/1689, Article 73"

    @property
    def target_identifier(self) -> str:
        return self.TARGET_ID

    @property
    def source_locator(self) -> str:
        return self.LOCATOR

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.EU_AI_ACT,
            target_identifier=self.TARGET_ID,
            target_level=ControlLevel.ARTICLE,
            title="EU Article 73 — Reporting of Serious Incidents",
            description="Screens for escalation protocols or notification timelines following severe malfunctions.",
            prerequisite_fact_keys=["incident_reporting_protocol", "authority_notification_delay"],
            applicability=EUConceptualRelevanceLevel.CONCEPTUALLY_RELEVANT.value,
        )

    def evaluate(self, context: IncidentFactContext) -> Optional[EUConceptualFinding]:
        if not context.evidence_records:
            return None

        tags = {
            "incident_reporting_protocol",
            "authority_notification_delay",
            "market_surveillance_notification",
            "failure_to_notify",
        }
        matched = tags.intersection(context.fact_tags)
        if not matched and not context.system_context.get("reporting_protocol_gap"):
            return None

        evidence_ids = [ev.get("id") for ev in context.evidence_records if ev.get("id")]
        strength, confidence = _resolve_evidence_strength(context)

        rationale = (
            "Recorded facts document delays or omissions in notifying relevant public authorities or "
            "market surveillance bodies following a severe system malfunction (Article 73 concept)."
        )
        validate_no_legal_language(rationale, field_name="rationale")

        obs = f"Observed factual signals for incident reporting: {', '.join(sorted(matched)) if matched else 'system context flag'}"
        validate_no_legal_language(obs, field_name="known_facts")

        return EUConceptualFinding(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            reference_id=self.TARGET_ID,
            control_title=self.metadata.title,
            source_locator=self.LOCATOR,
            concept_type=self.concept_type,
            relevance_level=EUConceptualRelevanceLevel.CONCEPTUALLY_RELEVANT,
            evidence_strength=strength,
            evidence_ids=evidence_ids,
            known_facts=[obs],
            unknowns=["Internal incident escalation timelines and formal notification records to supervisory authorities."],
            disputed_facts=list(context.disputed_facts),
            rationale=rationale,
            matched_condition_ids=["COND-CONC-OPS-REPORTING"],
            confidence=confidence,
            review_routing=EUScreenStatus.PENDING_REVIEW,
        )


# ==============================================================================
# Rule Family D6: Serious Incident Conceptual Relevance (Article 3(49))
# ==============================================================================


class EUArticle349SeriousIncidentRule(BaseEUConceptualRule):
    """Screens for conceptual correspondence to Article 3(49) serious incident harm thresholds."""

    RULE_ID = "RULE-EU-CONC-SERIOUS-01"
    RULE_VERSION = "1.0.0"
    TARGET_ID = "EU-ART-3.49"
    LOCATOR = "Regulation (EU) 2024/1689, Article 3(49)"

    @property
    def target_identifier(self) -> str:
        return self.TARGET_ID

    @property
    def source_locator(self) -> str:
        return self.LOCATOR

    @property
    def concept_type(self) -> EUConceptType:
        return EUConceptType.SERIOUS_INCIDENT_CONCEPT

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.EU_AI_ACT,
            target_identifier=self.TARGET_ID,
            target_level=ControlLevel.ARTICLE,
            title="EU Article 3(49) — Serious Incident Definition",
            description=(
                "Screens whether documented harm corresponds conceptually to Article 3(49) thresholds "
                "(death, serious health injury, critical infrastructure disruption, fundamental rights impact, property/environment harm)."
            ),
            prerequisite_fact_keys=["death_or_serious_health_injury", "critical_infrastructure_disruption"],
            applicability=EUSeriousIncidentRelevance.POTENTIALLY_RELEVANT_FOR_REVIEW.value,
        )

    def evaluate(self, context: IncidentFactContext) -> Optional[EUConceptualFinding]:
        if not context.evidence_records:
            return None

        serious_tags = {
            "death_or_serious_health_injury",
            "critical_infrastructure_disruption",
            "fundamental_rights_infringement",
            "serious_property_environmental_damage",
            "irreversible_harm",
        }
        matched = serious_tags.intersection(context.fact_tags)
        if not matched and not context.system_context.get("serious_harm_observed"):
            return None

        evidence_ids = [ev.get("id") for ev in context.evidence_records if ev.get("id")]
        strength, confidence = _resolve_evidence_strength(context)

        rationale = (
            "Recorded facts document consequences touching upon death, severe health injury, critical infrastructure "
            "disruption, or fundamental rights impairment, conceptually corresponding to Article 3(49) harm criteria."
        )
        validate_no_legal_language(rationale, field_name="rationale")

        obs = f"Observed factual signals for serious incident thresholds: {', '.join(sorted(matched)) if matched else 'system context flag'}"
        validate_no_legal_language(obs, field_name="known_facts")

        return EUConceptualFinding(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            reference_id=self.TARGET_ID,
            control_title=self.metadata.title,
            source_locator=self.LOCATOR,
            concept_type=self.concept_type,
            relevance_level=EUConceptualRelevanceLevel.POTENTIALLY_RELEVANT_FOR_QUALIFIED_REVIEW,
            evidence_strength=strength,
            evidence_ids=evidence_ids,
            known_facts=[obs],
            unknowns=["Direct causal attribution between the AI malfunction and the reported harm."],
            disputed_facts=list(context.disputed_facts),
            rationale=rationale,
            matched_condition_ids=["COND-CONC-SERIOUS-INCIDENT"],
            confidence=confidence,
            review_routing=EUScreenStatus.PENDING_REVIEW,
        )


# ==============================================================================
# Rule Registries
# ==============================================================================

ALL_EU_CONCEPTUAL_RULES: tuple[BaseEUConceptualRule, ...] = (
    # Article 5
    EUArticle5SubliminalManipulativeRule(),
    EUArticle5VulnerabilityExploitationRule(),
    EUArticle5SocialScoringRule(),
    EUArticle5PredictivePolicingRule(),
    EUArticle5FacialScrapingRule(),
    EUArticle5EmotionRecognitionRule(),
    EUArticle5BiometricCategorizationRule(),
    EUArticle5RealTimeBiometricRule(),
    # Annex III
    EUAnnex3BiometricsRule(),
    EUAnnex3CriticalInfrastructureRule(),
    EUAnnex3EducationRule(),
    EUAnnex3EmploymentRule(),
    EUAnnex3EssentialServicesRule(),
    EUAnnex3LawEnforcementRule(),
    EUAnnex3MigrationBorderRule(),
    EUAnnex3JusticeDemocracyRule(),
    # Article 50
    EUArticle50InteractionNotificationRule(),
    EUArticle50SyntheticMediaRule(),
    EUArticle50TextDisclosureRule(),
    # GPAI
    EUGPAISystemicRiskRule(),
    EUGPAIProviderObligationsRule(),
    # Operational Controls
    EUArticle10DataGovernanceRule(),
    EUArticle12LoggingRule(),
    EUArticle14HumanOversightRule(),
    EUArticle15RobustnessCybersecurityRule(),
    EUArticle72PostMarketMonitoringRule(),
    EUArticle73SeriousIncidentReportingRule(),
    # Serious Incident
    EUArticle349SeriousIncidentRule(),
)


# ==============================================================================
# Evaluation Coordinator Function
# ==============================================================================


def evaluate_eu_conceptual_context(
    context: IncidentFactContext,
    reference_set_id: str = EU_REFERENCE_SET_ID,
    custom_rules: Optional[tuple[BaseEUConceptualRule, ...]] = None,
) -> EUConceptualEvaluationResult:
    """Coordinate deterministic evaluation across all EU AI Act conceptual rules.

    Enforces mandatory safety rules:
    - Zero evidence records = zero affirmative findings.
    - Findings are strictly informational governance observations.
    - Status unconditionally routes to PENDING_REVIEW if any finding is matched.
    - All text output passes validate_no_legal_language.

    Args:
        context: Validated IncidentFactContext.
        reference_set_id: Target canonical reference set ID.
        custom_rules: Optional override tuple of conceptual rules; defaults to ALL_EU_CONCEPTUAL_RULES.

    Returns:
        Structured EUConceptualEvaluationResult containing findings and rule traces.
    """
    rules_to_run = custom_rules if custom_rules is not None else ALL_EU_CONCEPTUAL_RULES

    # Safety Rule 1: Zero evidence records = Zero affirmative findings
    if not context.evidence_records:
        return EUConceptualEvaluationResult(
            incident_id=context.incident_id,
            reference_set_id=reference_set_id,
            findings=[],
            rule_traces=[],
            conceptual_risk_areas=[],
            potentially_relevant_reference_ids=[],
            operational_relevance_areas=[],
            serious_incident_relevance=EUSeriousIncidentRelevance.INSUFFICIENT_INFORMATION,
            status=EUScreenStatus.PENDING_REVIEW,
            rationale="No affirmative conceptual findings generated due to absence of verified evidence records.",
        )

    findings: list[EUConceptualFinding] = []
    rule_traces: list[EUScreenRuleTraceSchema] = []
    conceptual_risk_areas: list[str] = []
    potentially_relevant_reference_ids: list[str] = []
    operational_relevance_areas: list[str] = []
    serious_incident_relevance = EUSeriousIncidentRelevance.NOT_APPARENTLY_RELEVANT

    for rule in rules_to_run:
        finding = rule.evaluate(context)
        if finding is not None:
            findings.append(finding)
            potentially_relevant_reference_ids.append(finding.reference_id)

            rule_traces.append(
                EUScreenRuleTraceSchema(
                    rule_id=finding.rule_id,
                    rule_version=finding.rule_version,
                    reference_set_id=reference_set_id,
                    matched_condition_ids=finding.matched_condition_ids,
                )
            )

            # Categorize into risk / operational / serious incident buckets
            if finding.concept_type in {EUConceptType.ARTICLE_5_CONCEPT, EUConceptType.ANNEX_III_CONCEPT}:
                if finding.reference_id not in conceptual_risk_areas:
                    conceptual_risk_areas.append(finding.reference_id)
            elif finding.concept_type == EUConceptType.OPERATIONAL_CONTROL_CONCEPT:
                if finding.reference_id not in operational_relevance_areas:
                    operational_relevance_areas.append(finding.reference_id)
            elif finding.concept_type == EUConceptType.SERIOUS_INCIDENT_CONCEPT:
                serious_incident_relevance = EUSeriousIncidentRelevance.POTENTIALLY_RELEVANT_FOR_REVIEW

    # Synthesize neutral, non-legal composite rationale
    if findings:
        composite_rationale = (
            f"Evaluated {len(findings)} informational conceptual findings across "
            f"{len(set(f.concept_type for f in findings))} statutory concept areas. "
            f"Findings touch upon references: [{', '.join(sorted(potentially_relevant_reference_ids))}]. "
            "All findings are informational relevance observations routed to PENDING_REVIEW."
        )
    else:
        composite_rationale = (
            "Recorded facts were evaluated across Article 5, Annex III, Article 50, GPAI, and operational "
            "control concepts; no direct factual engagement was identified in currently available evidence."
        )

    validate_no_legal_language(composite_rationale, field_name="composite_rationale")

    return EUConceptualEvaluationResult(
        incident_id=context.incident_id,
        reference_set_id=reference_set_id,
        findings=findings,
        rule_traces=rule_traces,
        conceptual_risk_areas=conceptual_risk_areas,
        potentially_relevant_reference_ids=potentially_relevant_reference_ids,
        operational_relevance_areas=operational_relevance_areas,
        serious_incident_relevance=serious_incident_relevance,
        status=EUScreenStatus.PENDING_REVIEW,
        rationale=composite_rationale,
    )
