"""Unit tests for SeverityRepository persistence, versioning, overrides, and audit trails."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Generator

import pytest
from sqlalchemy.orm import Session, sessionmaker

from ai_incident_monitor.db.base import Base
from ai_incident_monitor.db.models.incident import IncidentModel
from ai_incident_monitor.db.session import get_engine
from ai_incident_monitor.repositories.audit_repo import AuditRepository
from ai_incident_monitor.repositories.severity_repo import SeverityRepository
from ai_incident_monitor.scoring.engine import calculate_aig_isi_assessment
from ai_incident_monitor.scoring.enums import (
    ConfidenceLevel,
    HumanReviewState,
    ISIDimension,
    SeverityTier,
)
from ai_incident_monitor.scoring.models import DimensionScoreInput, ScoreOverride


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


@pytest.fixture
def incident(session: Session) -> IncidentModel:
    """Create a parent incident in the test database."""
    inc = IncidentModel(
        id="inc-test-rep-001",
        title="Autonomous Navigation Glitch",
        summary="Automated shuttle navigation error during adverse weather.",
        status="UNDER_INVESTIGATION",
    )
    session.add(inc)
    session.commit()
    return inc


def _sample_inputs(score: int = 1) -> dict[ISIDimension, DimensionScoreInput]:
    return {
        dim: DimensionScoreInput(
            score=score,
            rationale=f"Observed impact level {score}",
            confidence=ConfidenceLevel.HIGH,
        )
        for dim in ISIDimension
    }


def test_save_and_get_assessment(session: Session, incident: IncidentModel) -> None:
    """Verify persisting an AIG-ISI assessment and retrieving it by ID."""
    audit_repo = AuditRepository(session)
    repo = SeverityRepository(session, audit_repo)

    inputs = _sample_inputs(score=2)
    score_result = calculate_aig_isi_assessment(
        incident_id=incident.id,
        actual_inputs=inputs,
        potential_inputs=inputs,
    )

    saved = repo.save_assessment(score_result, actor_id="usr_tester")
    assert saved.id == score_result.assessment_id
    assert saved.incident_id == incident.id
    assert saved.actual_tier == SeverityTier.SIGNIFICANT.value
    assert saved.actual_normalized_score == 40.0
    assert saved.methodology_version == "AIG-ISI-1.0.0"

    # Query back
    fetched = repo.get_by_id(saved.id)
    assert fetched is not None
    assert fetched.id == saved.id
    assert fetched.actual_lower_bound == 40.0
    assert fetched.actual_completeness_pct == 100.0

    # Verify audit log was recorded
    audit_logs = audit_repo.get_audit_trail(saved.id)
    assert len(audit_logs) == 1
    assert audit_logs[0].action == "CREATE_ASSESSMENT"
    assert audit_logs[0].actor_id == "usr_tester"


def test_get_latest_for_incident(session: Session, incident: IncidentModel) -> None:
    """Verify fetching the latest active assessment for an incident."""
    repo = SeverityRepository(session)

    inputs_1 = _sample_inputs(score=1)
    res_1 = calculate_aig_isi_assessment(incident.id, inputs_1, inputs_1, assessment_id="isi-first-01")
    repo.save_assessment(res_1, actor_id="usr_tester")

    inputs_2 = _sample_inputs(score=3)
    res_2 = calculate_aig_isi_assessment(incident.id, inputs_2, inputs_2, assessment_id="isi-second-02")
    repo.save_assessment(res_2, actor_id="usr_tester", supersedes_id="isi-first-01")

    latest = repo.get_latest_for_incident(incident.id)
    assert latest is not None
    assert latest.id == "isi-second-02"
    assert latest.actual_normalized_score == 60.0

    # Prior assessment should be marked superseded
    prior = repo.get_by_id("isi-first-01")
    assert prior is not None
    assert prior.superseded_by_id == "isi-second-02"
    assert prior.review_state == HumanReviewState.SUPERSEDED.value


def test_apply_override_and_audit(session: Session, incident: IncidentModel) -> None:
    """Verify applying an override modifies the score and records audit history."""
    repo = SeverityRepository(session)
    audit_repo = repo.audit_repo

    inputs = _sample_inputs(score=1)
    score_result = calculate_aig_isi_assessment(incident.id, inputs, inputs)
    saved = repo.save_assessment(score_result, actor_id="usr_tester")

    override = ScoreOverride(
        target="actual_impact",
        original_score=20.0,
        overridden_score=75.0,
        original_tier=SeverityTier.MODERATE,
        overridden_tier=SeverityTier.SEVERE,
        rationale="Unreported enterprise disruption corroborated by external telemetry.",
        applied_by_id="usr_senior_analyst",
        applied_at_utc=datetime.now(timezone.utc),
    )

    updated = repo.apply_override(saved.id, override, actor_id="usr_senior_analyst")
    assert updated.actual_normalized_score == 75.0
    assert updated.actual_tier == SeverityTier.SEVERE.value
    assert updated.is_pending_review is True
    assert updated.review_state == HumanReviewState.PENDING_REVIEW.value
    assert len(updated.overrides) == 1

    # Verify audit log captures override
    logs = audit_repo.get_audit_trail(saved.id)
    override_log = next(log for log in logs if log.action == "APPLY_OVERRIDE")
    assert override_log.actor_id == "usr_senior_analyst"
    assert override_log.payload_after["overridden_score"] == 75.0


def test_update_review_state(session: Session, incident: IncidentModel) -> None:
    """Verify human reviewer state updates."""
    repo = SeverityRepository(session)
    inputs = _sample_inputs(score=1)
    score_result = calculate_aig_isi_assessment(incident.id, inputs, inputs)
    saved = repo.save_assessment(score_result, actor_id="usr_tester")

    approved = repo.update_review_state(
        saved.id,
        new_state=HumanReviewState.APPROVED,
        actor_id="usr_lead_editor",
        rationale="All evidence citations verified against official docket.",
    )
    assert approved.review_state == HumanReviewState.APPROVED.value
    assert approved.is_pending_review is False

    logs = repo.audit_repo.get_audit_trail(saved.id)
    review_log = next(log for log in logs if log.action == "UPDATE_REVIEW_STATE")
    assert review_log.actor_id == "usr_lead_editor"
    assert review_log.payload_after["review_state"] == "APPROVED"
