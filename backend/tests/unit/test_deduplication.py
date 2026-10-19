"""Unit tests for URL/title normalization and 4-tier deduplication engine."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Generator

import pytest
from sqlalchemy.orm import Session, sessionmaker

from ai_incident_monitor.db.base import Base
from ai_incident_monitor.db.models import (
    ClaimEvidenceLinkModel,
    ClaimRecordModel,
    EvidenceRecordModel,
    IncidentModel,
    SourceReferenceModel,
)
from ai_incident_monitor.db.session import get_engine
from ai_incident_monitor.deduplication import (
    DeduplicationEngine,
    calculate_title_similarity,
    normalize_title,
    normalize_url,
)


@pytest.fixture
def session() -> Generator[Session, None, None]:
    """Provide an in-memory SQLite database session."""
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    sess = session_factory()
    yield sess
    sess.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_url_normalization() -> None:
    """Verify URL normalization strips tracking parameters, fragments, and normalizes host/path."""
    raw = "HTTPS://WWW.EXAMPLE.COM:443/news/article-101/?utm_source=twitter&utm_medium=social&gclid=12345#comments"
    expected = "https://www.example.com/news/article-101"
    assert normalize_url(raw) == expected

    # Retain non-tracking query parameters
    raw_with_query = "https://example.com/search?q=ai+incident&utm_campaign=spring"
    expected_query = "https://example.com/search?q=ai+incident"
    assert normalize_url(raw_with_query) == expected_query


def test_title_normalization_and_similarity() -> None:
    """Verify title normalization and fuzzy similarity scoring."""
    title_a = "Autonomous Vehicle Sensor Failure in Testing Grounds!"
    title_b = "autonomous vehicle sensor failure in testing grounds"
    assert normalize_title(title_a) == normalize_title(title_b)
    assert calculate_title_similarity(title_a, title_b) == 1.0

    # Near-duplicate title
    title_c = "Autonomous Vehicle Sensor Glitch in Testing Grounds"
    sim = calculate_title_similarity(title_a, title_c)
    assert sim >= 0.85

    # Completely different title
    title_d = "Retail Algorithmic Dynamic Pricing Glitch"
    assert calculate_title_similarity(title_a, title_d) < 0.40


def test_dedup_waterfall_tier1_exact_id(session: Session) -> None:
    """Verify Tier 1 exact source ID match returns AUTO_LINK_ID."""
    existing = IncidentModel(
        id="INC-OECD-100",
        title="Automated Drone Collision",
        summary="Commercial drone collided with transmission tower.",
        status="UNDER_INVESTIGATION",
    )
    session.add(existing)
    session.commit()

    decision = DeduplicationEngine.evaluate(
        session=session,
        proposed_incident_id="INC-OECD-100",
        proposed_title="Drone Incident Report",
        proposed_date=None,
        source_urls=[],
    )
    assert decision.tier == 1
    assert decision.outcome == "AUTO_LINK_ID"
    assert decision.matched_incident_id == "INC-OECD-100"


def test_dedup_waterfall_tier2_exact_url(session: Session) -> None:
    """Verify Tier 2 exact canonical URL match returns AUTO_LINK_URL."""
    # 1. Setup existing incident with linked source
    incident = IncidentModel(
        id="INC-EXISTING-200",
        title="Facial Recognition Gate Error",
        summary="False identification at security checkpoint.",
        status="CONFIRMED",
    )
    source = SourceReferenceModel(
        id="SRC-200",
        title="Investigation Article",
        publisher="Tech Investigative News",
        url="https://tech.example.com/articles/gate-error.html",
        canonical_url="https://tech.example.com/articles/gate-error.html",
        source_type="INVESTIGATIVE_OUTLET",
        publication_date_precision="EXACT",
        publication_exact_date=date(2025, 3, 1),
        retrieval_date=datetime.now(timezone.utc),
        access_status="OPEN_PUBLIC",
        authority="ACCREDITED_JOURNALIST",
        reliability="HIGH",
        independence="INDEPENDENT_ORIGINAL",
    )
    evidence = EvidenceRecordModel(
        id="EVD-200",
        source_id="SRC-200",
        short_summary="Summary of evidence",
        evidence_type="INVESTIGATIVE_JOURNALISM",
        directness="SECONDARY_DERIVED",
        specificity="MODERATELY_SPECIFIC",
        corroboration_status="SINGLE_SOURCE_UNCONTESTED",
        ingested_at=datetime.now(timezone.utc),
        payload_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    )
    claim = ClaimRecordModel(
        id="CLM-200",
        incident_id="INC-EXISTING-200",
        claim_text="Biometric system produced wrongful match.",
        claim_type="FACTUAL_EVENT",
        epistemic_status="CONFIRMED_FACT",
        confidence="HIGH",
        materiality="CORE_IMPACT",
    )
    link = ClaimEvidenceLinkModel(claim_id="CLM-200", evidence_id="EVD-200", link_type="SUPPORTING")

    session.add_all([incident, source, evidence, claim, link])
    session.commit()

    # Incoming record with identical canonical URL (plus tracking params)
    incoming_url = "https://tech.example.com/articles/gate-error.html?utm_source=rss"
    decision = DeduplicationEngine.evaluate(
        session=session,
        proposed_incident_id="INC-NEW-999",
        proposed_title="Different Title for Same Incident",
        proposed_date=date(2025, 3, 1),
        source_urls=[incoming_url],
    )
    assert decision.tier == 2
    assert decision.outcome == "AUTO_LINK_URL"
    assert decision.matched_incident_id == "INC-EXISTING-200"


def test_dedup_waterfall_tier3_near_duplicate(session: Session) -> None:
    """Verify Tier 3 near-duplicate title + date queues candidate for human review (Rule 14)."""
    incident = IncidentModel(
        id="INC-EXISTING-300",
        title="Autonomous Shuttle Collision with Parked Delivery Truck",
        summary="Low speed collision on corporate campus.",
        status="UNDER_INVESTIGATION",
        incident_date_precision="EXACT",
        incident_exact_date=date(2025, 5, 10),
    )
    session.add(incident)
    session.commit()

    # Proposed incident with 92% title similarity and date 1 day apart
    decision = DeduplicationEngine.evaluate(
        session=session,
        proposed_incident_id="INC-NEW-301",
        proposed_title="Autonomous Shuttle Collision with Parked Delivery Van",
        proposed_date=date(2025, 5, 11),
        source_urls=["https://different.example.com/other-url.html"],
    )
    assert decision.tier == 3
    assert decision.outcome == "FLAG_FOR_REVIEW"
    assert decision.matched_incident_id == "INC-EXISTING-300"
    assert decision.similarity_score >= 0.90


def test_dedup_waterfall_tier4_distinct(session: Session) -> None:
    """Verify Tier 4 distinct incident is identified when no match exists."""
    incident = IncidentModel(
        id="INC-EXISTING-400",
        title="Medical Diagnostic Sepsis Alert Omission",
        summary="Hospital alarm failure.",
        status="CONFIRMED",
    )
    session.add(incident)
    session.commit()

    decision = DeduplicationEngine.evaluate(
        session=session,
        proposed_incident_id="INC-NEW-500",
        proposed_title="Financial Trading Flash Freeze",
        proposed_date=date(2025, 8, 20),
        source_urls=["https://finance.example.com/freeze.html"],
    )
    assert decision.tier == 4
    assert decision.outcome == "DISTINCT"
    assert decision.matched_incident_id is None
