"""Normative Pydantic schemas for the EU AI Act Compliance Intelligence engine.

Specification Source: AI-incident-AU-Act-Compliance-assessor.pdf
("EU AI Act Compliance Intelligence — LLM API Design", Pages 1–9)

Core Principles:
1. Two-Stage Assessment:
   - Stage 1: Deterministic Applicability & Jurisdiction Pre-Screen (Article 2).
   - Stage 2: Structured Regulatory Inference (Articles 5, 6, 50, 53/55, 73).
2. Phased Enforcement Timeline (November 2026 Baseline):
   - Active Law: Feb 2, 2025 (Art 5 Prohibitions), Aug 2, 2025 (GPAI), Aug 2, 2026 (Transparency).
   - Pending: Dec 2, 2026 (Additional biometric prohibitions).
   - Not Yet Enforceable: Dec 2, 2027 (Annex III High-Risk), Aug 2, 2028 (Annex I Products).
3. Statutory Non-Advice Guarantee:
   - Mandatory disclaimer metadata stating output is technical compliance analysis,
     not formal legal counsel or EU conformity certification.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class JurisdictionScope(str, Enum):
    """Territorial and material jurisdiction under Article 2."""

    APPLICABLE = "APPLICABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNDETERMINED = "UNDETERMINED"


class SystemClassification(str, Enum):
    """Categorical classification of the AI system under Regulation (EU) 2024/1689."""

    PROHIBITED_PRACTICE = "PROHIBITED_PRACTICE"
    HIGH_RISK_ANNEX_I = "HIGH_RISK_ANNEX_I"
    HIGH_RISK_ANNEX_III = "HIGH_RISK_ANNEX_III"
    TRANSPARENCY_ONLY = "TRANSPARENCY_ONLY"
    GPAI_MODEL = "GPAI_MODEL"
    GENERAL_AI_SYSTEM = "GENERAL_AI_SYSTEM"
    EXCLUDED = "EXCLUDED"
    UNKNOWN = "UNKNOWN"


class ComplianceGapStatus(str, Enum):
    """Evidence tier of compliance findings."""

    DOCUMENTED_GAP = "DOCUMENTED_GAP"
    POTENTIAL_GAP = "POTENTIAL_GAP"
    NO_GAP_DEMONSTRATED = "NO_GAP_DEMONSTRATED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_YET_APPLICABLE = "NOT_YET_APPLICABLE"


class SeriousIncidentDetermination(str, Enum):
    """Article 73 serious incident classification."""

    SERIOUS_INCIDENT = "SERIOUS_INCIDENT"
    POTENTIAL_SERIOUS_INCIDENT = "POTENTIAL_SERIOUS_INCIDENT"
    NON_SERIOUS = "NON_SERIOUS"
    NOT_ASSESSABLE = "NOT_ASSESSABLE"


class EnforcementTimelineStatus(str, Enum):
    """Enforcement timeline status relative to November 2026 baseline."""

    ACTIVE_LAW = "ACTIVE_LAW"
    PENDING = "PENDING"
    NOT_YET_APPLICABLE = "NOT_YET_APPLICABLE"


class TerritorialScopeAssessment(BaseModel):
    """Analysis of EU territorial nexus and statutory exclusions under Article 2."""

    jurisdiction: JurisdictionScope = Field(
        ...,
        description="Overall jurisdictional determination: APPLICABLE, NOT_APPLICABLE, or UNDETERMINED.",
    )
    placed_on_union_market: bool = Field(
        default=False,
        description="Whether system was placed on the market or put into service in the EU (Art 2(1)(a)).",
    )
    deployer_in_union: bool = Field(
        default=False,
        description="Whether deployer is established or located within the EU (Art 2(1)(b)).",
    )
    output_used_in_union: bool = Field(
        default=False,
        description="Whether system output is used within the EU by third-country providers/deployers (Art 2(1)(c)).",
    )
    military_defense_exclusion: bool = Field(
        default=False,
        description="Whether system was developed or used exclusively for military/defense purposes (Art 2(3)).",
    )
    scientific_research_exclusion: bool = Field(
        default=False,
        description="Whether system was developed/used exclusively for scientific research and development (Art 2(6)).",
    )
    rationale: str = Field(
        ...,
        description="Factual analysis substantiating the jurisdictional determination.",
    )


class ProhibitedPracticeFinding(BaseModel):
    """Evaluation of Article 5 prohibited practices."""

    is_prohibited: bool = Field(
        default=False,
        description="Whether the AI system or deployment constitutes a prohibited practice under Article 5.",
    )
    prohibition_type: Optional[str] = Field(
        default=None,
        description="Specific Article 5 paragraph (e.g. Subliminal manipulation 5(1)(a), Social scoring 5(1)(c), Biometric categorization 5(1)(g)).",
    )
    analysis: str = Field(
        default="No Article 5 prohibited practices identified from available evidence.",
        description="Evidence-grounded technical analysis.",
    )


class HighRiskClassificationFinding(BaseModel):
    """Evaluation of Article 6, Annex I, and Annex III high-risk use cases."""

    is_high_risk: bool = Field(
        default=False,
        description="Whether the system qualifies as high-risk under Article 6.",
    )
    annex_type: Optional[str] = Field(
        default=None,
        description="ANNEX_I (safety component of regulated product) or ANNEX_III (standalone high-risk area).",
    )
    annex_point: Optional[str] = Field(
        default=None,
        description="Specific point reference (e.g. Annex III, Point 2: Critical Infrastructure; Point 5: Financial Services).",
    )
    analysis: str = Field(
        default="No high-risk classification established from available evidence.",
        description="Technical justification for classification.",
    )


class TransparencyObligationFinding(BaseModel):
    """Evaluation of Article 50 specific transparency duties."""

    applies: bool = Field(
        default=False,
        description="Whether Article 50 transparency obligations apply.",
    )
    obligations: list[str] = Field(
        default_factory=list,
        description="Specific obligations (e.g. Human interaction notice 50(1), Synthetic media/deepfake watermark 50(2)).",
    )
    analysis: str = Field(
        default="No Article 50 transparency triggers detected.",
        description="Factual analysis.",
    )


class SeriousIncidentFinding(BaseModel):
    """Evaluation of serious incident reporting obligations under Article 73."""

    determination: SeriousIncidentDetermination = Field(
        default=SeriousIncidentDetermination.NOT_ASSESSABLE,
        description="Serious incident determination: SERIOUS_INCIDENT, POTENTIAL_SERIOUS_INCIDENT, NON_SERIOUS, or NOT_ASSESSABLE.",
    )
    criteria_met: list[str] = Field(
        default_factory=list,
        description="Statutory criteria met (e.g. Death/serious injury, Critical infrastructure disruption, Fundamental rights infringement).",
    )
    rationale: str = Field(
        ...,
        description="Detailed causal justification assessing whether threshold for Article 73 is met.",
    )


class ComplianceGapFinding(BaseModel):
    """Granular statutory requirement evaluation and compliance gap finding."""

    article: str = Field(
        ...,
        description="Statutory article citation (e.g. Article 9 Risk Management, Article 14 Human Oversight).",
    )
    requirement_summary: str = Field(
        ...,
        description="Plain-language summary of the statutory requirement.",
    )
    gap_status: ComplianceGapStatus = Field(
        ...,
        description="DOCUMENTED_GAP, POTENTIAL_GAP, NO_GAP_DEMONSTRATED, INSUFFICIENT_EVIDENCE, NOT_APPLICABLE, or NOT_YET_APPLICABLE.",
    )
    finding: str = Field(
        ...,
        description="Technical finding detailing how incident evidence reflects on compliance.",
    )
    evidence_ids: list[str] = Field(
        default_factory=list,
        description="Evidence citations supporting finding.",
    )
    timeline_status: EnforcementTimelineStatus = Field(
        default=EnforcementTimelineStatus.ACTIVE_LAW,
        description="Timeline status under November 2026 baseline.",
    )


class EUAIActComplianceAssessment(BaseModel):
    """Complete EU AI Act regulatory compliance assessment entity."""

    incident_id: str = Field(..., description="Canonical incident identifier.")
    assessed_at: str = Field(..., description="ISO 8601 evaluation timestamp.")
    baseline_date: str = Field(
        default="2026-11-01",
        description="Statutory enforcement baseline date (November 2026).",
    )
    territorial_scope: TerritorialScopeAssessment = Field(
        ...,
        description="Stage 1: Article 2 territorial and market scope evaluation.",
    )
    system_classification: SystemClassification = Field(
        ...,
        description="Stage 2: Overall system classification under EU AI Act.",
    )
    prohibited_practice: ProhibitedPracticeFinding = Field(
        default_factory=ProhibitedPracticeFinding,
        description="Article 5 evaluation.",
    )
    high_risk: HighRiskClassificationFinding = Field(
        default_factory=HighRiskClassificationFinding,
        description="Article 6, Annex I, and Annex III evaluation.",
    )
    transparency: TransparencyObligationFinding = Field(
        default_factory=TransparencyObligationFinding,
        description="Article 50 evaluation.",
    )
    serious_incident: SeriousIncidentFinding = Field(
        ...,
        description="Article 73 serious incident reporting assessment.",
    )
    compliance_gaps: list[ComplianceGapFinding] = Field(
        default_factory=list,
        description="List of statutory gap findings.",
    )
    overall_enforcement_status: EnforcementTimelineStatus = Field(
        ...,
        description="ACTIVE_LAW, PENDING, or NOT_YET_APPLICABLE.",
    )
    timeline_notes: str = Field(
        ...,
        description="Explanatory timeline notes explaining enforceability as of November 2026.",
    )
    disclaimer: str = Field(
        default=(
            "This automated regulatory impact assessment is generated for technical research "
            "and compliance preparedness only. It does not constitute formal legal advice, "
            "regulatory determination, or EU conformity certification."
        ),
        description="Mandatory statutory legal disclaimer.",
    )
    is_legal_advice: bool = Field(
        default=False,
        description="Always false per Constitutional Rule 16 and regulatory assessment charter.",
    )
