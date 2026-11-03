"""Unit tests for incident category taxonomy and accessible metadata.

Governing Charter: Project Constitution (Rules 1, 2, 3, 6, 8, 14),
ADR-002, WCAG 2.1 AA Compliance.
"""

import pytest

from ai_incident_monitor.domain.taxonomy import (
    CATEGORY_REGISTRY,
    IncidentCategory,
    classify_incident_category,
    get_category_metadata,
)


def test_all_categories_have_complete_accessible_metadata():
    """Verify that every defined category has icons, text symbols, and contrast colors."""
    for cat in IncidentCategory:
        meta = get_category_metadata(cat)
        assert meta.category == cat
        assert meta.icon != ""
        assert meta.display_name != ""
        assert meta.short_label != ""
        assert meta.text_symbol.startswith("[") and meta.text_symbol.endswith("]")
        assert meta.border_hex.startswith("#")
        assert meta.bg_hex.startswith("#")
        assert meta.text_hex.startswith("#")
        assert meta.css_class.startswith("badge-cat-")


def test_classify_oecd_wire_tags():
    """Verify deterministic classification from upstream OECD wire tags."""
    # Cyberattack / hacker tags or keywords
    cat, tags = classify_incident_category(
        title="19-year-old arrested in Bulgaria over alleged AI-assisted cyberattacks",
        summary="Attacks involved data theft and trading stolen information.",
        source_tags=["RIGHTS", "SAFETY"],
        level="incident",
    )
    assert cat == IncidentCategory.CYBERSECURITY
    assert "CYBERSECURITY" in tags

    # Physical / Safety tags
    cat, tags = classify_incident_category(
        title="Autonomous rover collision in warehouse",
        summary="Sensors failed causing collision.",
        source_tags=["PHYSICAL"],
        level="incident",
    )
    assert cat == IncidentCategory.SAFETY
    assert "PHYSICAL" in tags

    # Economic / Financial tags
    cat, tags = classify_incident_category(
        title="Banks restrict unauthorized AI agents in customer accounts",
        summary="Preventing automated fund transfers and market losses.",
        source_tags=["ECONOMIC"],
        level="incident",
    )
    assert cat == IncidentCategory.FINANCIAL
    assert "ECONOMIC" in tags

    # Rights / Psychological tags
    cat, tags = classify_incident_category(
        title="Police deploy facial recognition at sports arena",
        summary="Privacy concerns raised over mass scanning.",
        source_tags=["RIGHTS"],
        level="hazard",
    )
    assert cat == IncidentCategory.RIGHTS

    # Reputational tags
    cat, tags = classify_incident_category(
        title="Study finds AI smart glasses used for exam cheating",
        summary="Academic integrity compromised during standardized tests.",
        source_tags=["REPUTATIONAL"],
        level="incident",
    )
    assert cat == IncidentCategory.REPUTATIONAL

    # Systemic Hazard level
    cat, tags = classify_incident_category(
        title="Frontier model autonomy breakout simulation",
        summary="Simulated multi-agent cascade risk.",
        source_tags=[],
        level="hazard",
    )
    assert cat == IncidentCategory.SYSTEMIC_HAZARD


def test_classify_text_keyword_heuristics_fallback():
    """Verify text heuristics when no upstream tags are provided."""
    # Financial keywords
    cat, _ = classify_incident_category(
        title="Crypto trading algorithm causes $2 billion flash crash",
        summary="High frequency selling cascaded across exchanges.",
    )
    assert cat == IncidentCategory.FINANCIAL

    # Safety keywords
    cat, _ = classify_incident_category(
        title="Delivery drone crashes into residential power lines",
        summary="Motor failure caused rapid descent and fire.",
    )
    assert cat == IncidentCategory.SAFETY

    # Rights keywords
    cat, _ = classify_incident_category(
        title="Court strikes down automated welfare fraud detection",
        summary="Discrimination and bias against low-income applicants.",
    )
    assert cat == IncidentCategory.RIGHTS

    # Fallback to uncategorized
    cat, _ = classify_incident_category(
        title="Generic announcement about future technology symposium",
        summary="A panel discussed general trends in computation.",
    )
    assert cat == IncidentCategory.UNCATEGORIZED
