"""Unit tests for EditorialSourceSelector verifying source selection and exclusion policies."""

from __future__ import annotations

from datetime import date, datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ai_incident_monitor.db.base import Base
from ai_incident_monitor.db.models.claim import ClaimRecordModel
from ai_incident_monitor.db.models.evidence import (
    ClaimEvidenceLinkModel,
    EvidenceRecordModel,
)
from ai_incident_monitor.db.models.governance import (
    EULegalRelevanceScreenModel,
    FrameworkReferenceSetModel,
)
from ai_incident_monitor.db.models.incident import IncidentModel
from ai_incident_monitor.db.models.severity import SeverityAssessmentModel
from ai_incident_monitor.db.models.source import SourceReferenceModel
from ai_incident_monitor.db.models.uncertainty import (
    DisputedFactModel,
    UncertaintyRecordModel,
)
from ai_incident_monitor.editorial.source_selector import EditorialSourceSelector


@pytest.fixture
def sqlite_session() -> Session:
    """In-memory SQLite session with full relational schema initialized."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def seed_test_data(sqlite_session: Session) -> dict[str, str]:
    """Helper to populate realistic incident, source, evidence, and EU screen data."""
    now = datetime.now(timezone.utc)

    # 1. Source reference
    src = SourceReferenceModel(
        id="src_tech_news_01",
        title="Autonomous Agent Outage Deep-Dive",
        publisher="Tech Wire",
        url="https://example.com/tech-wire/incident-1",
        source_type="JOURNALISTIC_ARTICLE",
        access_status="OPEN_PUBLIC",
        authority="INDEPENDENT_OBSERVER",
        reliability="HIGH",
        independence="INDEPENDENT_ORIGINAL",
        content_hash="1" * 64,
        retrieval_date=now,
    )
    sqlite_session.add(src)

    # 2. Evidence record
    ev1 = EvidenceRecordModel(
        id="ev_001",
        source_id="src_tech_news_01",
        short_summary="Telemetry confirms database deletion at 04:15 UTC",
        evidence_type="TECHNICAL_POSTMORTEM",
        directness="PRIMARY_DIRECT",
        specificity="HIGHLY_SPECIFIC",
        corroboration_status="FULLY_CORROBORATED",
        ingested_at=now,
        payload_hash="2" * 64,
    )
    sqlite_session.add(ev1)

    # 3. Incident 1: Ordinary incident without EU screen (unapproved source, fully eligible for draft)
    inc1 = IncidentModel(
        id="inc_ordinary_01",
        title="Agent Database Truncation",
        summary="Autonomous agent executed unauthorized DROP TABLE.",
        status="UNDER_INVESTIGATION",  # Not human-approved!
        incident_exact_date=date(2026, 3, 1),
    )
    sqlite_session.add(inc1)

    claim1 = ClaimRecordModel(
        id="clm_001",
        incident_id="inc_ordinary_01",
        claim_text="Database table 'users' was truncated by agent.",
        claim_type="TECHNICAL_FACT",
        epistemic_status="VERIFIED",
        confidence="HIGH",
        materiality="HIGH",
    )
    sqlite_session.add(claim1)

    link1 = ClaimEvidenceLinkModel(
        claim_id="clm_001",
        evidence_id="ev_001",
        link_type="SUPPORTING",
    )
    sqlite_session.add(link1)

    # 4. Incident 2: Incident with unapproved EU screen
    inc2 = IncidentModel(
        id="inc_unapproved_eu_02",
        title="Medical Diagnostic Scoring Drift",
        summary="Diagnostic algorithm showed disparate false negative rates.",
        status="UNDER_INVESTIGATION",
        incident_exact_date=date(2026, 3, 2),
    )
    sqlite_session.add(inc2)

    ev2 = EvidenceRecordModel(
        id="ev_002",
        source_id="src_tech_news_01",
        short_summary="Clinical trial audit report",
        evidence_type="AUDIT_REPORT",
        directness="PRIMARY_DIRECT",
        specificity="HIGHLY_SPECIFIC",
        corroboration_status="FULLY_CORROBORATED",
        ingested_at=now,
        payload_hash="3" * 64,
    )
    sqlite_session.add(ev2)

    claim2 = ClaimRecordModel(
        id="clm_002",
        incident_id="inc_unapproved_eu_02",
        claim_text="Algorithm exhibited 15% discrepancy across age cohorts.",
        claim_type="STATISTICAL_FINDING",
        epistemic_status="VERIFIED",
        confidence="HIGH",
        materiality="HIGH",
    )
    sqlite_session.add(claim2)

    link2 = ClaimEvidenceLinkModel(
        claim_id="clm_002",
        evidence_id="ev_002",
        link_type="SUPPORTING",
    )
    sqlite_session.add(link2)

    ref_set = FrameworkReferenceSetModel(
        id="ref_eu_ai_act_2024",
        framework_code="EU_AI_ACT",
        framework_name="Regulation (EU) 2024/1689 (EU AI Act)",
        version="2024-1689-1.0",
        source_url="https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=OJ:L_202401689",
        publisher="Publications Office of the European Union",
        retrieved_at=now,
        verified_at=now,
        verified_by="legal_engineer_1",
        content_hash="4" * 64,
    )
    sqlite_session.add(ref_set)

    eu_draft = EULegalRelevanceScreenModel(
        id="eu_screen_draft_01",
        incident_id="inc_unapproved_eu_02",
        reference_set_id="ref_eu_ai_act_2024",
        screen_version="1.0.0",
        status="DRAFT",  # UNAPPROVED EU screen
        relevance_level="POTENTIALLY_RELEVANT_FOR_QUALIFIED_REVIEW",
        nexus_assessment="UNION_MARKET_PLACING",
        generated_by="system",
        generated_at=now,
        disclaimer_version="2024-1689-v2",
        disclaimer_text="Mandatory EU disclaimer text...",
    )
    sqlite_session.add(eu_draft)

    # 5. Incident 3: Incident with APPROVED_INFORMATIONAL EU screen
    inc3 = IncidentModel(
        id="inc_approved_eu_03",
        title="Biometric Emotion Analysis Tool in Workplace",
        summary="Company deployed biometric camera detecting worker fatigue.",
        status="UNDER_INVESTIGATION",
        incident_exact_date=date(2026, 3, 3),
    )
    sqlite_session.add(inc3)

    ev3 = EvidenceRecordModel(
        id="ev_003",
        source_id="src_tech_news_01",
        short_summary="Worker union grievance document",
        evidence_type="LEGAL_FILING",
        directness="PRIMARY_DIRECT",
        specificity="HIGHLY_SPECIFIC",
        corroboration_status="FULLY_CORROBORATED",
        ingested_at=now,
        payload_hash="5" * 64,
    )
    sqlite_session.add(ev3)

    claim3 = ClaimRecordModel(
        id="clm_003",
        incident_id="inc_approved_eu_03",
        claim_text="Emotion recognition system operated continuously in call center.",
        claim_type="OPERATIONAL_FACT",
        epistemic_status="VERIFIED",
        confidence="HIGH",
        materiality="HIGH",
    )
    sqlite_session.add(claim3)

    link3 = ClaimEvidenceLinkModel(
        claim_id="clm_003",
        evidence_id="ev_003",
        link_type="SUPPORTING",
    )
    sqlite_session.add(link3)

    eu_approved = EULegalRelevanceScreenModel(
        id="eu_screen_approved_01",
        incident_id="inc_approved_eu_03",
        reference_set_id="ref_eu_ai_act_2024",
        screen_version="1.0.0",
        status="APPROVED_INFORMATIONAL",  # APPROVED EU screen
        relevance_level="CONCEPTUALLY_RELEVANT",
        nexus_assessment="UNION_MARKET_PLACING",
        generated_by="system",
        reviewed_by="human_evaluator_1",
        generated_at=now,
        reviewed_at=now,
        disclaimer_version="2024-1689-v2",
        disclaimer_text="Mandatory EU disclaimer text...",
    )
    sqlite_session.add(eu_approved)

    # 6. Incident 4: Incident with ZERO evidence links (ineligible)
    inc4 = IncidentModel(
        id="inc_no_evidence_04",
        title="Unsubstantiated Social Media Rumor",
        summary="Viral post claimed AI chatbot caused power grid disruption.",
        status="UNDER_INVESTIGATION",
    )
    sqlite_session.add(inc4)

    # 7. Incident 5: Incident with disputed facts and allegations
    inc5 = IncidentModel(
        id="inc_disputed_05",
        title="Autonomous Vehicle Sensor Failure Dispute",
        summary="Conflicting reports regarding whether sensor fusion failed before collision.",
        status="UNDER_INVESTIGATION",
        incident_exact_date=date(2026, 3, 5),
    )
    sqlite_session.add(inc5)

    ev5 = EvidenceRecordModel(
        id="ev_005",
        source_id="src_tech_news_01",
        short_summary="Investigative report on vehicle collision",
        evidence_type="INVESTIGATIVE_REPORT",
        directness="SECONDARY_REPORTED",
        specificity="MODERATE",
        corroboration_status="PARTIALLY_CORROBORATED",
        ingested_at=now,
        payload_hash="6" * 64,
    )
    sqlite_session.add(ev5)

    claim5 = ClaimRecordModel(
        id="clm_005",
        incident_id="inc_disputed_05",
        claim_text="Plaintiff alleges vehicle lidar suffered blindness due to glare.",
        claim_type="ALLEGATION",
        epistemic_status="ALLEGATION",
        confidence="MEDIUM",
        materiality="HIGH",
    )
    sqlite_session.add(claim5)

    link5 = ClaimEvidenceLinkModel(
        claim_id="clm_005",
        evidence_id="ev_005",
        link_type="SUPPORTING",
    )
    sqlite_session.add(link5)

    unc5 = UncertaintyRecordModel(
        id="unc_005",
        incident_id="inc_disputed_05",
        known_facts=["Collision occurred at 14:00"],
        unknown_facts=["Did lidar sensor shut down before impact?"],
        missing_evidence=["Raw vehicle event data recorder log"],
        conflicting_evidence=["Eyewitness statement vs telematics"],
        reason_unresolved="Litigation ongoing",
        schema_version="1.0.0",
    )
    sqlite_session.add(unc5)

    disp5 = DisputedFactModel(
        uncertainty_id="unc_005",
        assertion="Lidar hardware failure caused vehicle to ignore pedestrian",
        contesting_party="Vehicle Manufacturer",
        supporting_evidence_ids=["ev_005"],
        contradicting_evidence_ids=[],
    )
    sqlite_session.add(disp5)

    sqlite_session.commit()

    return {
        "ordinary": "inc_ordinary_01",
        "unapproved_eu": "inc_unapproved_eu_02",
        "approved_eu": "inc_approved_eu_03",
        "no_evidence": "inc_no_evidence_04",
        "disputed": "inc_disputed_05",
    }


class TestEditorialSourceSelector:
    def test_ordinary_attributed_reporting_enters_draft_without_human_approval(
        self, sqlite_session: Session, seed_test_data: dict[str, str]
    ) -> None:
        """Requirement: Ordinary reporting enters drafts without per-incident human approval."""
        selector = EditorialSourceSelector(sqlite_session)
        inc = sqlite_session.get(IncidentModel, seed_test_data["ordinary"])
        assert inc is not None

        candidate = selector.evaluate_candidate_incident(inc)
        assert candidate.is_eligible is True
        assert candidate.incident_id == seed_test_data["ordinary"]
        assert len(candidate.evidence_ids) >= 1
        assert candidate.eu_screen_id is None
        assert candidate.eu_commentary is None
        assert "No EU screen associated" in str(candidate.omitted_eu_reason)

    def test_unapproved_eu_commentary_omitted_without_blocking_ordinary_reporting(
        self, sqlite_session: Session, seed_test_data: dict[str, str]
    ) -> None:
        """Requirement: Unapproved EU screen commentary is cleanly omitted while preserving incident."""
        selector = EditorialSourceSelector(sqlite_session)
        inc = sqlite_session.get(IncidentModel, seed_test_data["unapproved_eu"])
        assert inc is not None

        candidate = selector.evaluate_candidate_incident(inc)
        # Incident itself MUST be eligible
        assert candidate.is_eligible is True
        # EU screen is detected but marked ineligible for external/dossier commentary
        assert candidate.eu_screen_id == "eu_screen_draft_01"
        assert candidate.eu_screen_status == "DRAFT"
        assert candidate.eu_screen_eligible is False
        assert candidate.eu_commentary is None
        assert "not APPROVED_INFORMATIONAL" in str(candidate.omitted_eu_reason)

    def test_approved_eu_commentary_included_with_safeguards(
        self, sqlite_session: Session, seed_test_data: dict[str, str]
    ) -> None:
        """Requirement: Approved EU screen commentary is included with proper disclaimers."""
        selector = EditorialSourceSelector(sqlite_session)
        inc = sqlite_session.get(IncidentModel, seed_test_data["approved_eu"])
        assert inc is not None

        candidate = selector.evaluate_candidate_incident(inc)
        assert candidate.is_eligible is True
        assert candidate.eu_screen_status == "APPROVED_INFORMATIONAL"
        assert candidate.eu_screen_eligible is True
        assert candidate.eu_commentary is not None
        assert "Level=CONCEPTUALLY_RELEVANT" in candidate.eu_commentary
        assert candidate.omitted_eu_reason is None

    def test_incident_with_zero_evidence_marked_ineligible(
        self, sqlite_session: Session, seed_test_data: dict[str, str]
    ) -> None:
        """Requirement: Incident with no evidence records fails closed (Rule 1)."""
        selector = EditorialSourceSelector(sqlite_session)
        inc = sqlite_session.get(IncidentModel, seed_test_data["no_evidence"])
        assert inc is not None

        candidate = selector.evaluate_candidate_incident(inc)
        assert candidate.is_eligible is False
        assert any("Rule 1 violation" in r for r in candidate.exclusion_reasons)

    def test_conflicting_claims_and_allegations_preserved(
        self, sqlite_session: Session, seed_test_data: dict[str, str]
    ) -> None:
        """Requirement: Disputed facts and allegations are preserved with attribution."""
        selector = EditorialSourceSelector(sqlite_session)
        inc = sqlite_session.get(IncidentModel, seed_test_data["disputed"])
        assert inc is not None

        candidate = selector.evaluate_candidate_incident(inc)
        assert candidate.is_eligible is True
        assert len(candidate.disputed_claims) == 1
        disp = candidate.disputed_claims[0]
        assert "Lidar hardware failure" in disp["topic"]
        assert "Vehicle Manufacturer" in disp["position_a"]

        # Check allegation labeling
        allegation_facts = [f for f in candidate.known_facts if f["is_allegation"]]
        assert len(allegation_facts) == 1
        assert "Reported assertion" in allegation_facts[0]["attribution"]

    def test_select_candidates_filters_and_limits(
        self, sqlite_session: Session, seed_test_data: dict[str, str]
    ) -> None:
        """Requirement: select_candidates returns only eligible by default and respects limits."""
        selector = EditorialSourceSelector(sqlite_session)

        # By default only_eligible=True: inc_no_evidence_04 should be excluded
        candidates = selector.select_candidates(limit=10)
        candidate_ids = [c.incident_id for c in candidates]
        assert seed_test_data["no_evidence"] not in candidate_ids
        assert seed_test_data["ordinary"] in candidate_ids
        assert seed_test_data["approved_eu"] in candidate_ids

        # If only_eligible=False: all returned
        all_candidates = selector.select_candidates(only_eligible=False)
        all_ids = [c.incident_id for c in all_candidates]
        assert seed_test_data["no_evidence"] in all_ids

    def test_empty_title_or_summary_marked_ineligible(self, sqlite_session: Session) -> None:
        """Requirement: Malformed incidents with empty title or summary are marked ineligible."""
        selector = EditorialSourceSelector(sqlite_session)
        malformed = IncidentModel(
            id="inc_malformed_empty_title",
            title="   ",
            summary="Some summary.",
            status="UNDER_INVESTIGATION",
        )
        sqlite_session.add(malformed)
        sqlite_session.commit()

        candidate = selector.evaluate_candidate_incident(malformed)
        assert candidate.is_eligible is False
        assert any("Incident title is empty" in r for r in candidate.exclusion_reasons)
