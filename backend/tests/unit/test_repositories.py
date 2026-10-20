"""Unit tests for typed repositories, audit immutability, and dedup queue."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Generator

import pytest
from sqlalchemy.orm import Session, sessionmaker

from ai_incident_monitor.db.base import Base
from ai_incident_monitor.db.models import (
    ClaimRecordModel,
    EvidenceRecordModel,
    IncidentModel,
    SourceReferenceModel,
)
from ai_incident_monitor.db.session import get_engine
from ai_incident_monitor.domain.common import ImmutabilityViolationError
from ai_incident_monitor.repositories import (
    AuditRepository,
    ClaimRepository,
    ImportRepository,
    IncidentRepository,
    SourceRepository,
)


@pytest.fixture
def session() -> Generator[Session, None, None]:
    """Provide an isolated in-memory SQLite database session."""
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    sess = session_factory()
    yield sess
    sess.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_incident_repository_crud(session: Session) -> None:
    """Verify IncidentRepository create, query, list, and status update."""
    repo = IncidentRepository(session)
    incident = IncidentModel(
        id="INC-test-100",
        title="Automated Drone Collision",
        summary="A commercial delivery drone collided with infrastructure during high wind.",
        status="UNDER_INVESTIGATION",
        incident_date_precision="EXACT",
        incident_exact_date=date(2025, 6, 1),
    )
    repo.create(incident)

    fetched = repo.get("INC-test-100")
    assert fetched is not None
    assert fetched.title == "Automated Drone Collision"

    listed = repo.list_incidents(status="UNDER_INVESTIGATION")
    assert len(listed) == 1
    assert listed[0].id == "INC-test-100"

    updated = repo.update_status("INC-test-100", "CONFIRMED")
    assert updated.status == "CONFIRMED"


def test_claim_repository_supersession_and_evidence_linking(session: Session) -> None:
    """Verify claim creation, evidence linking, and bidirectional supersession lineage."""
    inc_repo = IncidentRepository(session)
    claim_repo = ClaimRepository(session)
    source_repo = SourceRepository(session)

    # 1. Setup Incident, Source, Evidence
    inc_repo.create(
        IncidentModel(
            id="INC-test-200",
            title="Chatbot Misinformation",
            summary="LLM medical assistant provided dangerous dosing advice.",
            status="UNDER_INVESTIGATION",
        )
    )
    source = SourceReferenceModel(
        id="SRC-test-200",
        title="Hospital Safety Incident Report",
        publisher="Metro General Hospital",
        url="https://example.com/reports/metro-200.html",
        source_type="OFFICIAL_POSTMORTEM",
        publication_date_precision="EXACT",
        publication_exact_date=date(2025, 7, 1),
        retrieval_date=datetime(2025, 7, 2, tzinfo=timezone.utc),
        access_status="OPEN_PUBLIC",
        authority="FIRST_PARTY_AUTHORITATIVE",
        reliability="VERY_HIGH",
        independence="FIRST_PARTY_SELF_REPORT",
    )
    source_repo.create(source)

    evidence = EvidenceRecordModel(
        id="EVD-test-200",
        source_id="SRC-test-200",
        short_summary="Clinical review board confirmed erroneous pediatric recommendation.",
        evidence_type="TECHNICAL_POSTMORTEM",
        directness="PRIMARY_DIRECT",
        specificity="HIGHLY_SPECIFIC",
        corroboration_status="FULLY_CORROBORATED",
        ingested_at=datetime.now(timezone.utc),
        payload_hash="2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae",
    )
    session.add(evidence)
    session.flush()

    # 2. Create Initial Claim and link evidence
    original_claim = ClaimRecordModel(
        id="CLM-test-201",
        incident_id="INC-test-200",
        claim_text="Initial report estimated 5 patients were affected.",
        claim_type="FACTUAL_EVENT",
        epistemic_status="UNVERIFIED_ALLEGATION",
        confidence="LOW",
        materiality="CORE_IMPACT",
    )
    claim_repo.create(original_claim)
    claim_repo.link_evidence("CLM-test-201", "EVD-test-200", "SUPPORTING")

    # 3. Supersede claim with verified data
    new_claim = ClaimRecordModel(
        id="CLM-test-202",
        incident_id="INC-test-200",
        claim_text="Hospital safety audit confirmed exactly 2 pediatric patients received erroneous dosage advice.",
        claim_type="FACTUAL_EVENT",
        epistemic_status="CONFIRMED_FACT",
        confidence="VERY_HIGH",
        materiality="CORE_IMPACT",
    )
    claim_repo.supersede_claim("CLM-test-201", new_claim, reason="NEW_PRIMARY_EVIDENCE")

    # Verify bidirectional lineage
    old = claim_repo.get("CLM-test-201")
    assert old is not None
    assert old.lifecycle_status == "SUPERSEDED"
    assert old.superseded_by == "CLM-test-202"

    replacement = claim_repo.get("CLM-test-202")
    assert replacement is not None
    assert replacement.supersedes == "CLM-test-201"
    assert replacement.supersession_reason == "NEW_PRIMARY_EVIDENCE"


def test_source_repository_lookups(session: Session) -> None:
    """Verify source lookups by canonical URL, primary URL, and SHA-256 digest."""
    repo = SourceRepository(session)
    source = SourceReferenceModel(
        id="SRC-test-300",
        title="NTSB Autonomous Vehicle Incident Investigation",
        publisher="National Transportation Safety Board",
        url="https://ntsb.gov/investigations/av-101.htm?utm_source=rss",
        canonical_url="https://ntsb.gov/investigations/av-101.htm",
        source_type="REGULATORY_DOCKET",
        publication_date_precision="EXACT",
        publication_exact_date=date(2025, 8, 15),
        retrieval_date=datetime(2025, 8, 16, tzinfo=timezone.utc),
        access_status="OPEN_PUBLIC",
        authority="REGULATORY_JUDICIAL_AUTHORITY",
        reliability="VERY_HIGH",
        independence="INDEPENDENT_ORIGINAL",
        content_hash="fcde2b2edba56bf408601fb721fe9b5c338d10ee429ea04fae5511b68fbf8fb9",
    )
    repo.create(source)

    by_canonical = repo.find_by_canonical_url("https://ntsb.gov/investigations/av-101.htm")
    assert by_canonical is not None
    assert by_canonical.id == "SRC-test-300"

    by_hash = repo.find_by_content_hash(
        "FCDE2B2EDBA56BF408601FB721FE9B5C338D10EE429EA04FAE5511B68FBF8FB9"
    )
    assert by_hash is not None
    assert by_hash.id == "SRC-test-300"


def test_audit_repository_append_only_enforcement(session: Session) -> None:
    """Verify AuditRepository records actions and strictly forbids delete/update (Rule 16/17)."""
    repo = AuditRepository(session)

    # 1. Record action
    entry = repo.record_action(
        entity_type="INCIDENT",
        entity_id="INC-test-400",
        action="CREATE",
        actor_id="USER-HUMAN-01",
        payload_after={"title": "Test Incident"},
    )
    assert entry.id is not None
    assert entry.entity_id == "INC-test-400"

    # 2. Retrieve history
    trail = repo.get_audit_trail("INC-test-400")
    assert len(trail) == 1
    assert trail[0].action == "CREATE"

    # 3. Verify deletion raises ImmutabilityViolationError
    with pytest.raises(ImmutabilityViolationError, match="strictly forbidden by Constitutional Rule 16"):
        repo.delete(entry)

    # 4. Verify update raises ImmutabilityViolationError
    with pytest.raises(ImmutabilityViolationError, match="strictly forbidden by Constitutional Rule 16"):
        repo.update(entry)


def test_import_repository_raw_preservation_and_dedup_queue(session: Session) -> None:
    """Verify raw import record persistence and near-duplicate human review queue."""
    repo = ImportRepository(session)

    # 1. Store raw record with payload snapshot
    raw_payload = {"incident_title": "Facial Recognition Wrongful Arrest", "date": "2025-03-12"}
    record = repo.create_raw_record(
        batch_id="BATCH-2025-01",
        source_filename="oecd_export_20250315.csv",
        source_format="CSV",
        content_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        row_index=1,
        raw_payload=raw_payload,
        staged_file_path=".data/raw_imports/BATCH-2025-01/oecd_export_20250315.csv",
    )
    assert record.id is not None
    assert record.raw_payload == raw_payload

    # 2. Queue near-duplicate candidate (Tier 3) referencing existing incident
    incident = IncidentModel(
        id="INC-existing-999",
        title="Facial Recognition Wrongful Identification",
        summary="Prior incident with matching entities.",
        status="CONFIRMED",
    )
    session.add(incident)
    session.flush()

    candidate = repo.create_dedup_candidate(
        raw_import_id=record.id,
        existing_incident_id="INC-existing-999",
        tier=3,
        similarity_score=0.94,
        match_rationale="Title similarity 0.94 and event date within 1 day.",
    )
    assert candidate.id is not None
    assert candidate.review_decision is None

    # 3. Query pending queue
    pending = repo.list_pending_dedup_candidates()
    assert len(pending) == 1
    assert pending[0].id == candidate.id

    # 4. Resolve candidate with human gatekeeper decision
    resolved = repo.resolve_dedup_candidate(
        candidate_id=candidate.id,
        decision="MERGED",
        reviewed_by="HUMAN-REVIEWER-01",
    )
    assert resolved.review_decision == "MERGED"
    assert resolved.reviewed_by == "HUMAN-REVIEWER-01"
    assert resolved.reviewed_at is not None

    # Pending queue should now be empty
    assert len(repo.list_pending_dedup_candidates()) == 0
