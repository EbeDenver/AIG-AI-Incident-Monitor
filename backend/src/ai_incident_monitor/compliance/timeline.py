"""Statutory timeline alignment engine for the EU AI Act (Regulation (EU) 2024/1689).

Evaluates enforceability of statutory requirements against the November 2026 baseline date.

Statutory Milestones:
1. Aug 1, 2024: Entry into force.
2. Feb 2, 2025: Chapter I (General) & Chapter II (Prohibited Practices - Art 5), AI literacy (Art 4).
3. Aug 2, 2025: Chapter V (General Purpose AI / GPAI - Arts 51-56), Governance, Penalties.
4. Aug 2, 2026: Article 50 (Transparency Obligations), High-Risk classification rules.
5. Dec 2, 2026: Additional biometric prohibitions (PENDING as of November 2026).
6. Dec 2, 2027: Annex III High-Risk systems obligations (Articles 8-15) (NOT_YET_APPLICABLE as of November 2026).
7. Aug 2, 2028: Annex I High-Risk products (NOT_YET_APPLICABLE as of November 2026).
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from ai_incident_monitor.compliance.schemas import (
    ComplianceGapStatus,
    EnforcementTimelineStatus,
    SystemClassification,
)

BASELINE_EVALUATION_DATE = date(2026, 11, 1)

# Enforceability milestone dates
DATE_ENTRY_INTO_FORCE = date(2024, 8, 1)
DATE_PHASE_1_PROHIBITIONS = date(2025, 2, 2)
DATE_PHASE_2_GPAI = date(2025, 8, 2)
DATE_PHASE_3_TRANSPARENCY = date(2026, 8, 2)
DATE_PHASE_4_BIOMETRIC_EXPANSION = date(2026, 12, 2)
DATE_PHASE_5_ANNEX_III_HIGH_RISK = date(2027, 12, 2)
DATE_PHASE_6_ANNEX_I_PRODUCTS = date(2028, 8, 2)


def get_timeline_status_for_article(
    article: str,
    as_of: date = BASELINE_EVALUATION_DATE,
) -> tuple[EnforcementTimelineStatus, str]:
    """Determine enforceability status and statutory context for a given article citation."""
    cleaned = article.upper().replace(" ", "")

    # Annex III High-Risk obligations (Articles 8-15)
    for art_num in ["ARTICLE8", "ARTICLE9", "ARTICLE10", "ARTICLE11", "ARTICLE12", "ARTICLE13", "ARTICLE14", "ARTICLE15"]:
        if art_num in cleaned or "ANNEXIII" in cleaned:
            if as_of < DATE_PHASE_5_ANNEX_III_HIGH_RISK:
                return (
                    EnforcementTimelineStatus.NOT_YET_APPLICABLE,
                    "Annex III High-Risk obligations become legally enforceable on December 2, 2027. "
                    "Current evaluation serves as a pre-enforcement gap analysis.",
                )
            return (EnforcementTimelineStatus.ACTIVE_LAW, "Annex III High-Risk obligations are in full legal force.")

    # Annex I Product Safety High-Risk
    if "ANNEXI" in cleaned:
        if as_of < DATE_PHASE_6_ANNEX_I_PRODUCTS:
            return (
                EnforcementTimelineStatus.NOT_YET_APPLICABLE,
                "Annex I product safety high-risk obligations become legally enforceable on August 2, 2028.",
            )
        return (EnforcementTimelineStatus.ACTIVE_LAW, "Annex I High-Risk product rules are in full legal force.")

    # Article 50 Transparency obligations
    if "ARTICLE50" in cleaned:
        return (
            EnforcementTimelineStatus.ACTIVE_LAW,
            "Article 50 Transparency obligations have been in full legal force since August 2, 2026.",
        )

    # GPAI Models (Articles 51-56)
    if any(f"ARTICLE5{i}" in cleaned for i in range(1, 7)):
        return (
            EnforcementTimelineStatus.ACTIVE_LAW,
            "General-Purpose AI model obligations have been in full legal force since August 2, 2025.",
        )

    # Article 5 Prohibited practices (Ensure Article 50/51-56 are handled first)
    if "ARTICLE5" in cleaned:
        if "BIOMETRIC" in cleaned and as_of < DATE_PHASE_4_BIOMETRIC_EXPANSION:
            return (
                EnforcementTimelineStatus.PENDING,
                "Expanded biometric prohibitions enter force on December 2, 2026 (1 month from baseline).",
            )
        return (
            EnforcementTimelineStatus.ACTIVE_LAW,
            "Article 5 Prohibited AI Practices have been in full legal force since February 2, 2025.",
        )

    # Article 73 Serious Incident Reporting
    if "ARTICLE73" in cleaned:
        # Article 73 applies to high-risk systems under Annex III or Annex I
        if as_of < DATE_PHASE_5_ANNEX_III_HIGH_RISK:
            return (
                EnforcementTimelineStatus.NOT_YET_APPLICABLE,
                "Formal Article 73 serious incident reporting aligns with high-risk system entry-into-force (Dec 2, 2027). "
                "Evaluated for governance tracking and preparedness.",
            )
        return (EnforcementTimelineStatus.ACTIVE_LAW, "Article 73 reporting obligations are in full force.")

    # Default fallback
    return (
        EnforcementTimelineStatus.ACTIVE_LAW,
        "General framework provisions are in legal force as of the November 2026 baseline.",
    )


def adjust_gap_status_for_timeline(
    gap_status: ComplianceGapStatus,
    timeline_status: EnforcementTimelineStatus,
) -> ComplianceGapStatus:
    """Ensure compliance gap findings do not declare active noncompliance for provisions not yet enforceable."""
    if timeline_status == EnforcementTimelineStatus.NOT_YET_APPLICABLE:
        if gap_status in (ComplianceGapStatus.DOCUMENTED_GAP, ComplianceGapStatus.POTENTIAL_GAP):
            return ComplianceGapStatus.NOT_YET_APPLICABLE
    return gap_status
