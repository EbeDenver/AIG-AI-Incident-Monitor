"""Controlled vocabularies and enumerations for the governance framework mapping engine.

Implements official definitions for OECD AI Principles, NIST AI RMF 1.0, and
Regulation (EU) 2024/1689 (EU AI Act).
"""

from enum import Enum


class FrameworkCode(str, Enum):
    """Supported governance and regulatory frameworks."""

    OECD_AI_PRINCIPLES = "OECD_AI_PRINCIPLES"
    NIST_AI_RMF = "NIST_AI_RMF"
    EU_AI_ACT = "EU_AI_ACT"


class FrameworkStatus(str, Enum):
    """Lifecycle status of a framework reference set or control."""

    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    SUPERSEDED = "SUPERSEDED"
    DRAFT = "DRAFT"


class ControlLevel(str, Enum):
    """Structural granularity level of a framework node."""

    FRAMEWORK = "FRAMEWORK"
    PRINCIPLE = "PRINCIPLE"
    FUNCTION = "FUNCTION"
    CATEGORY = "CATEGORY"
    SUBCATEGORY = "SUBCATEGORY"
    ARTICLE = "ARTICLE"
    ANNEX = "ANNEX"


class OECDApplicability(str, Enum):
    """Applicability categorization for OECD AI Principles."""

    DIRECTLY_IMPLICATED = "DIRECTLY_IMPLICATED"
    BROADER_GOVERNANCE_LESSON = "BROADER_GOVERNANCE_LESSON"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class NISTApplicability(str, Enum):
    """Applicability categorization for NIST AI RMF functions and controls."""

    OBSERVED_CONTROL_GAP = "OBSERVED_CONTROL_GAP"
    POTENTIAL_RISK_MANAGEMENT_LESSON = "POTENTIAL_RISK_MANAGEMENT_LESSON"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class EURelevanceLevel(str, Enum):
    """Informational relevance classification under Regulation (EU) 2024/1689.

    Non-judicial categorization observing correspondence between incident evidence
    and EU AI Act statutory concepts. Does NOT represent legal applicability or violation.
    """

    DIRECT_RELEVANCE = "DIRECT_RELEVANCE"
    POSSIBLE_RELEVANCE = "POSSIBLE_RELEVANCE"
    CONCEPTUAL_RELEVANCE = "CONCEPTUAL_RELEVANCE"
    UNLIKELY_RELEVANCE = "UNLIKELY_RELEVANCE"
    OUTSIDE_APPARENT_SCOPE = "OUTSIDE_APPARENT_SCOPE"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"


class EUScreenStatus(str, Enum):
    """Lifecycle workflow state for an EU AI Act informational relevance screen."""

    DRAFT = "DRAFT"
    CANDIDATE = "CANDIDATE"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED_INFORMATIONAL = "APPROVED_INFORMATIONAL"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class EUNexus(str, Enum):
    """Territorial and market nexus under Article 2 of Regulation (EU) 2024/1689."""

    EU_ESTABLISHED = "EU_ESTABLISHED"
    EU_PLACED_ON_MARKET = "EU_PLACED_ON_MARKET"
    EU_AFFECTED_PERSONS = "EU_AFFECTED_PERSONS"
    NO_APPARENT_EU_NEXUS = "NO_APPARENT_EU_NEXUS"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"


class EUNexusAssessment(str, Enum):
    """Controlled nexus assessment under Article 2 of Regulation (EU) 2024/1689."""

    POSSIBLE_EU_NEXUS = "POSSIBLE_EU_NEXUS"
    NO_EU_NEXUS_EVIDENCE = "NO_EU_NEXUS_EVIDENCE"
    INSUFFICIENT_NEXUS_INFORMATION = "INSUFFICIENT_NEXUS_INFORMATION"
    OUTSIDE_APPARENT_TERRITORIAL_SCOPE = "OUTSIDE_APPARENT_TERRITORIAL_SCOPE"


class EUAISystemRelevance(str, Enum):
    """Technology classification under Article 3(1) definition of AI system."""

    MEETS_DEFINITION = "MEETS_DEFINITION"
    BORDERLINE_OR_UNCLEAR = "BORDERLINE_OR_UNCLEAR"
    OUTSIDE_DEFINITION = "OUTSIDE_DEFINITION"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"


class EUActorRole(str, Enum):
    """Regulated operator role under Regulation (EU) 2024/1689."""

    PROVIDER = "PROVIDER"
    DEPLOYER = "DEPLOYER"
    IMPORTER = "IMPORTER"
    DISTRIBUTOR = "DISTRIBUTOR"
    AUTHORIZED_REPRESENTATIVE = "AUTHORIZED_REPRESENTATIVE"
    PRODUCT_MANUFACTURER = "PRODUCT_MANUFACTURER"
    GPAI_MODEL_PROVIDER = "GPAI_MODEL_PROVIDER"
    UNKNOWN = "UNKNOWN"


class EUActorRoleConfidence(str, Enum):
    """Epistemic certainty of actor role attribution in incident evidence."""

    IDENTIFIED_FROM_EVIDENCE = "IDENTIFIED_FROM_EVIDENCE"
    POSSIBLE_FROM_EVIDENCE = "POSSIBLE_FROM_EVIDENCE"
    UNKNOWN = "UNKNOWN"
    DISPUTED = "DISPUTED"


class EURiskClass(str, Enum):
    """Informational risk classification screening under Regulation (EU) 2024/1689."""

    PROHIBITED_PRACTICE = "PROHIBITED_PRACTICE"
    HIGH_RISK_SYSTEM = "HIGH_RISK_SYSTEM"
    TRANSPARENCY_OBLIGATION = "TRANSPARENCY_OBLIGATION"
    GPAI_OBLIGATION = "GPAI_OBLIGATION"
    MINIMAL_OTHER_RISK = "MINIMAL_OTHER_RISK"
    OUTSIDE_APPARENT_SCOPE = "OUTSIDE_APPARENT_SCOPE"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"


class EUTimingAssessment(str, Enum):
    """Temporal correspondence against statutory effective dates in reference metadata."""

    REFERENCE_METADATA_ALIGNS = "REFERENCE_METADATA_ALIGNS"
    INCIDENT_DATE_UNKNOWN = "INCIDENT_DATE_UNKNOWN"
    EFFECTIVE_DATE_UNCERTAIN = "EFFECTIVE_DATE_UNCERTAIN"
    TEMPORAL_CONTEXT_REQUIRES_REVIEW = "TEMPORAL_CONTEXT_REQUIRES_REVIEW"
    NOT_ASSESSED = "NOT_ASSESSED"


class EUSeriousIncident(str, Enum):
    """Correspondence to Article 3(49) serious incident harm thresholds."""

    POTENTIALLY_RELEVANT = "POTENTIALLY_RELEVANT"
    UNLIKELY_RELEVANT = "UNLIKELY_RELEVANT"
    OUTSIDE_SCOPE = "OUTSIDE_SCOPE"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"


class EUSeriousIncidentRelevance(str, Enum):
    """Controlled vocabulary for serious incident conceptual relevance screening."""

    POTENTIALLY_RELEVANT_FOR_REVIEW = "POTENTIALLY_RELEVANT_FOR_REVIEW"
    CONCEPTUALLY_RELEVANT = "CONCEPTUALLY_RELEVANT"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"
    NOT_APPARENTLY_RELEVANT = "NOT_APPARENTLY_RELEVANT"


class EUOperationalObligation(str, Enum):
    """Key operational obligations screened under Regulation (EU) 2024/1689."""

    LOGGING = "LOGGING"
    HUMAN_OVERSIGHT = "HUMAN_OVERSIGHT"
    TRANSPARENCY = "TRANSPARENCY"
    DATA_GOVERNANCE = "DATA_GOVERNANCE"
    ACCURACY_ROBUSTNESS_CYBERSECURITY = "ACCURACY_ROBUSTNESS_CYBERSECURITY"
    POST_MARKET_MONITORING = "POST_MARKET_MONITORING"
    INCIDENT_REPORTING = "INCIDENT_REPORTING"


class GovernanceConfidence(str, Enum):
    """Orthogonal evidentiary confidence for governance mappings."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INSUFFICIENT = "INSUFFICIENT"


class MappingStatus(str, Enum):
    """Lifecycle state of an incident-framework mapping in the review state machine."""

    DRAFT = "DRAFT"
    CANDIDATE = "CANDIDATE"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    APPROVED_INFORMATIONAL = "APPROVED_INFORMATIONAL"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class SensitiveDomain(str, Enum):
    """Domains triggering mandatory PENDING_REVIEW governance review gates."""

    DISCRIMINATION = "DISCRIMINATION"
    PRIVACY = "PRIVACY"
    FUNDAMENTAL_RIGHTS = "FUNDAMENTAL_RIGHTS"
    HEALTH_SAFETY = "HEALTH_SAFETY"
    CHILDREN = "CHILDREN"
    BIOMETRICS = "BIOMETRICS"
    EMPLOYMENT = "EMPLOYMENT"
    CREDIT = "CREDIT"
    EDUCATION = "EDUCATION"
    LAW_ENFORCEMENT = "LAW_ENFORCEMENT"
    MIGRATION = "MIGRATION"
    CRITICAL_INFRASTRUCTURE = "CRITICAL_INFRASTRUCTURE"
    DEMOCRATIC_PROCESS = "DEMOCRATIC_PROCESS"


class GovernanceAuditEventType(str, Enum):
    """Types of state transitions and lifecycle actions tracked in governance audit trail."""

    CREATE_MAPPING = "CREATE_MAPPING"
    TRANSITION_STATE = "TRANSITION_STATE"
    SUPERSEDE_MAPPING = "SUPERSEDE_MAPPING"
    ADD_EVIDENCE_LINK = "ADD_EVIDENCE_LINK"
    MANUAL_OVERRIDE = "MANUAL_OVERRIDE"
    CREATE_EU_SCREEN = "CREATE_EU_SCREEN"
    SUPERSEDE_EU_SCREEN = "SUPERSEDE_EU_SCREEN"
    LINTER_EXECUTION = "LINTER_EXECUTION"
    OUTPUT_ELIGIBILITY_CHECK = "OUTPUT_ELIGIBILITY_CHECK"


class EUConceptualRelevanceLevel(str, Enum):
    """Controlled informational relevance rating for an EU AI Act concept.

    Non-judicial categorization indicating the degree of correspondence between verified
    incident facts and statutory reference concepts. Does NOT represent legal applicability.
    """

    POTENTIALLY_RELEVANT_FOR_QUALIFIED_REVIEW = "POTENTIALLY_RELEVANT_FOR_QUALIFIED_REVIEW"
    CONCEPTUALLY_RELEVANT = "CONCEPTUALLY_RELEVANT"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"
    NOT_APPARENTLY_RELEVANT = "NOT_APPARENTLY_RELEVANT"
    NOT_APPLICABLE_TO_RECORDED_CONTEXT = "NOT_APPLICABLE_TO_RECORDED_CONTEXT"


class EUConceptType(str, Enum):
    """Categorical classification of EU AI Act statutory concepts."""

    ARTICLE_5_CONCEPT = "ARTICLE_5_CONCEPT"
    ANNEX_III_CONCEPT = "ANNEX_III_CONCEPT"
    ARTICLE_50_CONCEPT = "ARTICLE_50_CONCEPT"
    GPAI_CONCEPT = "GPAI_CONCEPT"
    OPERATIONAL_CONTROL_CONCEPT = "OPERATIONAL_CONTROL_CONCEPT"
    SERIOUS_INCIDENT_CONCEPT = "SERIOUS_INCIDENT_CONCEPT"


class EUEvidenceStrength(str, Enum):
    """Degree of factual evidence substantiating a conceptual observation."""

    DIRECT = "DIRECT"
    CORROBORATED = "CORROBORATED"
    INDICATIVE = "INDICATIVE"
    DISPUTED = "DISPUTED"
    INSUFFICIENT = "INSUFFICIENT"

