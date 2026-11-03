"""Incident category taxonomy and accessible classification metadata.

Governing Charter: Project Constitution (Rules 1, 2, 3, 6, 8, 14),
ADR-002 (Orthogonality of Category from Severity), WCAG 2.1 AA Compliance.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Optional, Sequence


class IncidentCategory(str, Enum):
    """Categorical taxonomy for AI incidents and hazards."""

    SAFETY = "SAFETY"
    RIGHTS = "RIGHTS"
    CYBERSECURITY = "CYBERSECURITY"
    FINANCIAL = "FINANCIAL"
    REPUTATIONAL = "REPUTATIONAL"
    SYSTEMIC_HAZARD = "SYSTEMIC_HAZARD"
    UNCATEGORIZED = "UNCATEGORIZED"


@dataclass(frozen=True)
class CategoryMetadata:
    """Accessible visual and descriptive attributes for an incident category."""

    category: IncidentCategory
    display_name: str
    short_label: str
    icon: str
    text_symbol: str
    description: str
    css_class: str
    border_hex: str
    bg_hex: str
    text_hex: str


CATEGORY_REGISTRY: dict[IncidentCategory, CategoryMetadata] = {
    IncidentCategory.SAFETY: CategoryMetadata(
        category=IncidentCategory.SAFETY,
        display_name="Operational & Physical Safety",
        short_label="Safety",
        icon="⚠️",
        text_symbol="[SAFETY]",
        description="Autonomous physical failures, transportation collisions, medical robotics, and operational halts.",
        css_class="badge-cat-safety",
        border_hex="#D97706",
        bg_hex="#FEF3C7",
        text_hex="#78350F",
    ),
    IncidentCategory.RIGHTS: CategoryMetadata(
        category=IncidentCategory.RIGHTS,
        display_name="Civil Rights & Human Harm",
        short_label="Rights",
        icon="⚖️",
        text_symbol="[RIGHTS]",
        description="Algorithmic discrimination, unconstitutional surveillance, biometric bias, and privacy violations.",
        css_class="badge-cat-rights",
        border_hex="#7C3AED",
        bg_hex="#EDE9FE",
        text_hex="#4C1D95",
    ),
    IncidentCategory.CYBERSECURITY: CategoryMetadata(
        category=IncidentCategory.CYBERSECURITY,
        display_name="Adversarial & Agentic Cybersecurity",
        short_label="Cybersecurity",
        icon="🛡️",
        text_symbol="[CYBER]",
        description="AI-generated malware, autonomous agent exploits, prompt injection worms, and API exfiltration.",
        css_class="badge-cat-cybersecurity",
        border_hex="#DC2626",
        bg_hex="#FEE2E2",
        text_hex="#7F1D1D",
    ),
    IncidentCategory.FINANCIAL: CategoryMetadata(
        category=IncidentCategory.FINANCIAL,
        display_name="Economic & Market Integrity",
        short_label="Financial",
        icon="💰",
        text_symbol="[FINANCIAL]",
        description="Algorithmic flash crashes, autonomous trading manipulation, deepfake executive fraud, and labor disruption.",
        css_class="badge-cat-financial",
        border_hex="#059669",
        bg_hex="#D1FAE5",
        text_hex="#064E3B",
    ),
    IncidentCategory.REPUTATIONAL: CategoryMetadata(
        category=IncidentCategory.REPUTATIONAL,
        display_name="Information Integrity & Reputational",
        short_label="Reputation",
        icon="📢",
        text_symbol="[REPUTATION]",
        description="AI hallucinations, deepfakes, mass disinformation campaigns, exam cheating, and academic integrity.",
        css_class="badge-cat-reputational",
        border_hex="#0284C7",
        bg_hex="#E0F2FE",
        text_hex="#0C4A6E",
    ),
    IncidentCategory.SYSTEMIC_HAZARD: CategoryMetadata(
        category=IncidentCategory.SYSTEMIC_HAZARD,
        display_name="Frontier & Systemic Hazard",
        short_label="Hazard",
        icon="🌐",
        text_symbol="[HAZARD]",
        description="Near-misses, unconstrained agent feedback loops, catastrophic frontier risks, and supply-chain monoculture.",
        css_class="badge-cat-systemic_hazard",
        border_hex="#475569",
        bg_hex="#F1F5F9",
        text_hex="#0F172A",
    ),
    IncidentCategory.UNCATEGORIZED: CategoryMetadata(
        category=IncidentCategory.UNCATEGORIZED,
        display_name="Unclassified Incident",
        short_label="Uncategorized",
        icon="❓",
        text_symbol="[UNCATEGORIZED]",
        description="Newly ingested records pending classification review.",
        css_class="badge-cat-uncategorized",
        border_hex="#9CA3AF",
        bg_hex="#F3F4F6",
        text_hex="#1F2937",
    ),
}

# Regex keywords for secondary text-based classification
CYBER_PATTERNS = re.compile(
    r"\b(cyberattacks?|hackers?|malware|phishing|ransomware|vulnerabilit(?:y|ies)|breaches?|exfiltration|backdoors?|exploits?|injected|injection)\b",
    re.IGNORECASE,
)
FINANCIAL_PATTERNS = re.compile(
    r"\b(crypto|bitcoin|trading|banks?|heists?|displace.*jobs|unemployment|financial|billion|wire fraud)\b",
    re.IGNORECASE,
)
SAFETY_PATTERNS = re.compile(
    r"\b(crashes?|collisions?|fires?|killed|injur(?:y|ies)|robots?|drones?|military|physical|hospitals?|medical)\b",
    re.IGNORECASE,
)
RIGHTS_PATTERNS = re.compile(
    r"\b(arrested|police|facial recognition|discrimination|bias|surveillance|privacy|wiretapping|children|lawsuits?|welfare)\b",
    re.IGNORECASE,
)
REPUTATION_PATTERNS = re.compile(
    r"\b(deepfakes?|cheating|sat questions|exams?|disinformation|misinformation|hallucinations?|falsely showing)\b",
    re.IGNORECASE,
)


def get_category_metadata(category: str | IncidentCategory) -> CategoryMetadata:
    """Retrieve metadata for an incident category with safe fallback."""
    if isinstance(category, str):
        try:
            cat_enum = IncidentCategory(category.upper())
        except ValueError:
            cat_enum = IncidentCategory.UNCATEGORIZED
    else:
        cat_enum = category
    return CATEGORY_REGISTRY.get(cat_enum, CATEGORY_REGISTRY[IncidentCategory.UNCATEGORIZED])


def classify_incident_category(
    title: str,
    summary: str,
    source_tags: Optional[Sequence[str]] = None,
    level: Optional[str] = None,
) -> tuple[IncidentCategory, list[str]]:
    """Determine primary incident category and all matching tags deterministically.

    Priority:
    1. Upstream source tags and level (e.g. OECD wire tags).
    2. Specific keyword heuristics (cybersecurity, safety, financial, rights, reputation).
    3. Fallback to UNCATEGORIZED.
    """
    tags_upper = [str(t).upper().strip() for t in (source_tags or [])]
    level_upper = str(level or "").upper().strip()

    assigned_tags: list[str] = list(tags_upper)

    # Check for direct tag mappings
    if "CYBERSECURITY" in tags_upper or CYBER_PATTERNS.search(f"{title} {summary}"):
        if "CYBERSECURITY" not in assigned_tags:
            assigned_tags.append("CYBERSECURITY")
        return IncidentCategory.CYBERSECURITY, assigned_tags

    if "PHYSICAL" in tags_upper or "SAFETY" in tags_upper:
        return IncidentCategory.SAFETY, assigned_tags

    if "ECONOMIC" in tags_upper:
        return IncidentCategory.FINANCIAL, assigned_tags

    if "RIGHTS" in tags_upper or "PSYCHOLOGICAL" in tags_upper:
        return IncidentCategory.RIGHTS, assigned_tags

    if "REPUTATIONAL" in tags_upper:
        return IncidentCategory.REPUTATIONAL, assigned_tags

    if level_upper == "HAZARD":
        return IncidentCategory.SYSTEMIC_HAZARD, assigned_tags

    # Text pattern matching fallback
    combined_text = f"{title} {summary}"
    if FINANCIAL_PATTERNS.search(combined_text):
        return IncidentCategory.FINANCIAL, assigned_tags
    if SAFETY_PATTERNS.search(combined_text):
        return IncidentCategory.SAFETY, assigned_tags
    if RIGHTS_PATTERNS.search(combined_text):
        return IncidentCategory.RIGHTS, assigned_tags
    if REPUTATION_PATTERNS.search(combined_text):
        return IncidentCategory.REPUTATIONAL, assigned_tags

    return IncidentCategory.UNCATEGORIZED, assigned_tags
