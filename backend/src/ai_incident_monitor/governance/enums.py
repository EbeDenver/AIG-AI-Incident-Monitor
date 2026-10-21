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


class EUNexus(str, Enum):
    """Territorial and market nexus under Article 2 of Regulation (EU) 2024/1689."""

    EU_ESTABLISHED = "EU_ESTABLISHED"
    EU_PLACED_ON_MARKET = "EU_PLACED_ON_MARKET"
    EU_AFFECTED_PERSONS = "EU_AFFECTED_PERSONS"
    NO_APPARENT_EU_NEXUS = "NO_APPARENT_EU_NEXUS"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"


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


class EURiskClass(str, Enum):
    """Informational risk classification screening under Regulation (EU) 2024/1689."""

    PROHIBITED_PRACTICE = "PROHIBITED_PRACTICE"
    HIGH_RISK_SYSTEM = "HIGH_RISK_SYSTEM"
    TRANSPARENCY_OBLIGATION = "TRANSPARENCY_OBLIGATION"
    GPAI_OBLIGATION = "GPAI_OBLIGATION"
    MINIMAL_OTHER_RISK = "MINIMAL_OTHER_RISK"
    OUTSIDE_APPARENT_SCOPE = "OUTSIDE_APPARENT_SCOPE"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"


class EUSeriousIncident(str, Enum):
    """Correspondence to Article 3(49) serious incident harm thresholds."""

    POTENTIALLY_RELEVANT = "POTENTIALLY_RELEVANT"
    UNLIKELY_RELEVANT = "UNLIKELY_RELEVANT"
    OUTSIDE_SCOPE = "OUTSIDE_SCOPE"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"


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
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class GovernanceAuditEventType(str, Enum):
    """Types of state transitions and lifecycle actions tracked in governance audit trail."""

    CREATE_MAPPING = "CREATE_MAPPING"
    TRANSITION_STATE = "TRANSITION_STATE"
    SUPERSEDE_MAPPING = "SUPERSEDE_MAPPING"
    ADD_EVIDENCE_LINK = "ADD_EVIDENCE_LINK"
    MANUAL_OVERRIDE = "MANUAL_OVERRIDE"
    CREATE_EU_SCREEN = "CREATE_EU_SCREEN"
    SUPERSEDE_EU_SCREEN = "SUPERSEDE_EU_SCREEN"
