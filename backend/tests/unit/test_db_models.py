"""Unit tests for SQLAlchemy relational model persistence, cascades, and constraints."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Generator

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from ai_incident_monitor.db.base import Base
from ai_incident_monitor.db.models import (
    AIInvolvementAssessmentModel,
    AuditLogModel,
    CausalAssessmentModel,
    ClaimEvidenceLinkModel,
    ClaimRecordModel,
    DedupCandidateModel,
    DisputedFactModel,
    EvidenceRecordModel,
    HumanReviewRecordModel,
    IncidentModel,
    QuoteSpanModel,
    RawImportRecordModel,
    SourceReferenceModel,
    UncertaintyRecordModel,
)
from ai_incident_monitor.db.session import get_engine


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provide an in-memory SQLite session with foreign keys enabled."""
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_incident_persistence_with_unknown_date(db_session: Session) -> None:
    """Verify incident persistence maintains unknown date fields as null (Constitutional Rule 2)."""
    incident = IncidentModel(
        id="INC-test-001",
        title="Autonomous Vehicle Sensor Failure",
        summary="A test autonomous vehicle sensor failure in testing grounds.",
        status="UNDER_INVESTIGATION",
        incident_date_precision="UNKNOWN",
        incident_exact_date=None,
        incident_start_date=None,
        incident_end_date=None,
    )
    db_session.add(incident)
    db_session.commit()

    retrieved = db_session.get(IncidentModel, "INC-test-001")
    assert retrieved is not None
    assert retrieved.title == "Autonomous Vehicle Sensor Failure"
    assert retrieved.incident_date_precision == "UNKNOWN"
    assert retrieved.incident_exact_date is None
    assert retrieved.created_at is not None


def test_claim_monetary_unknown_is_null(db_session: Session) -> None:
    """Verify monetary claims maintain NULL for unknown amounts, never zero (Rule 2)."""
    incident = IncidentModel(
        id="INC-test-002",
        title="Trading Algorithm Anomaly",
        summary="High frequency trading algorithm order spike.",
        status="UNDER_INVESTIGATION",
        incident_date_precision="EXACT",
        incident_exact_date=date(2025, 4, 1),
    )
    db_session.add(incident)
    db_session.commit()

    claim = ClaimRecordModel(
        id="CLM-test-001",
        incident_id="INC-test-002",
        claim_text="Total financial damage resulting from the spike is unverified.",
        claim_type="NUMERIC_METRIC",
        epistemic_status="UNVERIFIED_ALLEGATION",
        confidence="LOW",
        materiality="SECONDARY_CONTRIBUTOR",
        is_numeric_claim=True,
        monetary_amount_status="UNKNOWN",
        monetary_exact_amount=None,  # Unknown must remain None, never 0.00
        monetary_currency=None,
    )
    db_session.add(claim)
    db_session.commit()

    retrieved_claim = db_session.get(ClaimRecordModel, "CLM-test-001")
    assert retrieved_claim is not None
    assert retrieved_claim.monetary_amount_status == "UNKNOWN"
    assert retrieved_claim.monetary_exact_amount is None


def test_quote_span_check_constraint_offset_order(db_session: Session) -> None:
    """Verify quote spans enforce end_char_offset > start_char_offset."""
    source = SourceReferenceModel(
        id="SRC-test-001",
        title="Technical Report on Failure Mode",
        publisher="Safety Institute",
        url="https://example.com/report.pdf",
        source_type="OFFICIAL_POSTMORTEM",
        publication_date_precision="EXACT",
        publication_exact_date=date(2025, 5, 10),
        retrieval_date=datetime(2025, 5, 12, 10, 0, tzinfo=timezone.utc),
        access_status="OPEN_PUBLIC",
        authority="FIRST_PARTY_AUTHORITATIVE",
        reliability="HIGH",
        independence="FIRST_PARTY_SELF_REPORT",
    )
    db_session.add(source)
    db_session.commit()

    evidence = EvidenceRecordModel(
        id="EVD-test-001",
        source_id="SRC-test-001",
        short_summary="Direct quote confirming memory overrun in perception node.",
        evidence_type="TECHNICAL_POSTMORTEM",
        directness="PRIMARY_DIRECT",
        specificity="HIGHLY_SPECIFIC",
        corroboration_status="SINGLE_SOURCE_UNCONTESTED",
        ingested_at=datetime.now(timezone.utc),
        payload_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    )
    db_session.add(evidence)
    db_session.commit()

    # Invalid quote span: end_char_offset <= start_char_offset
    invalid_span = QuoteSpanModel(
        evidence_id="EVD-test-001",
        quote_text="Memory overrun observed",
        start_char_offset=100,
        end_char_offset=50,  # Invalid: end < start
    )
    db_session.add(invalid_span)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_human_review_is_human_constraint(db_session: Session) -> None:
    """Verify human review records reject non-human reviewers (Constitutional Rule 14)."""
    now = datetime.now(timezone.utc)
    invalid_review = HumanReviewRecordModel(
        id="REV-test-001",
        reviewer_id="AGENT-LLM-001",
        reviewer_name="Automated Auditor",
        reviewer_email="agent@aiguardians.com",
        reviewer_role="Automated Reviewer",
        is_human=False,  # Prohibited by check constraint
        review_status="HUMAN_APPROVED",
        review_decision="APPROVED",
        rationale="Automated assessment passed all rule criteria.",
        reviewed_at=now,
    )
    db_session.add(invalid_review)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # Valid human review succeeds
    valid_review = HumanReviewRecordModel(
        id="REV-test-002",
        reviewer_id="HUMAN-001",
        reviewer_name="Dr. Jane Doe",
        reviewer_email="j.doe@aiguardians.com",
        reviewer_role="Chief Safety Officer",
        is_human=True,
        review_status="HUMAN_APPROVED",
        review_decision="APPROVED",
        rationale="Verified primary source documentation and validated causal assessment.",
        reviewed_at=now,
    )
    db_session.add(valid_review)
    db_session.commit()

    persisted = db_session.get(HumanReviewRecordModel, "REV-test-002")
    assert persisted is not None
    assert persisted.is_human is True


def test_incident_cascade_deletion(db_session: Session) -> None:
    """Verify deleting an incident cascades to its claims, uncertainties, and AI involvements."""
    incident = IncidentModel(
        id="INC-test-cascade",
        title="Medical Diagnostic Deviation",
        summary="Diagnostic recommendation discrepancy in clinical trial.",
        status="UNDER_INVESTIGATION",
        incident_date_precision="EXACT",
        incident_exact_date=date(2025, 2, 14),
    )
    db_session.add(incident)
    db_session.commit()

    claim = ClaimRecordModel(
        id="CLM-test-cascade",
        incident_id="INC-test-cascade",
        claim_text="System suggested unapproved dosage in 3 cases.",
        claim_type="FACTUAL_EVENT",
        epistemic_status="UNVERIFIED_ALLEGATION",
        confidence="MEDIUM",
        materiality="CORE_IMPACT",
    )
    uncertainty = UncertaintyRecordModel(
        id="UNC-test-cascade",
        incident_id="INC-test-cascade",
        reason_unresolved="INVESTIGATION_ONGOING",
    )
    db_session.add_all([claim, uncertainty])
    db_session.commit()

    # Delete incident
    db_session.delete(incident)
    db_session.commit()

    assert db_session.get(IncidentModel, "INC-test-cascade") is None
    assert db_session.get(ClaimRecordModel, "CLM-test-cascade") is None
    assert db_session.get(UncertaintyRecordModel, "UNC-test-cascade") is None
