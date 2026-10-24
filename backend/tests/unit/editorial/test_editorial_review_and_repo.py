"""Unit tests for EditorialReviewStateMachine and EditorialRepository."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ai_incident_monitor.db.base import Base
from ai_incident_monitor.db.models.claim import ClaimRecordModel
from ai_incident_monitor.db.models.evidence import (
    ClaimEvidenceLinkModel,
    EvidenceRecordModel,
)
from ai_incident_monitor.db.models.governance import GovernanceAuditLogModel
from ai_incident_monitor.db.models.incident import IncidentModel
from ai_incident_monitor.db.models.source import SourceReferenceModel
from ai_incident_monitor.domain.common import (
    ConstitutionalViolationError,
    ImmutabilityViolationError,
)
from ai_incident_monitor.editorial.enums import (
    EditorialDossierStatus,
    EditorialValidationCode,
    EditorialValidationSeverity,
)
from ai_incident_monitor.editorial.models import (
    EDITORIAL_ATTESTATION_STATEMENT,
    EditorialReviewerAttestationSchema,
    EditorialValidationFinding,
    EditorialValidationReport,
)
from ai_incident_monitor.editorial.review import EditorialReviewStateMachine
from ai_incident_monitor.editorial.validator import EditorialValidator
from ai_incident_monitor.repositories.editorial_repo import EditorialRepository
from tests.unit.editorial.test_editorial_models import create_sample_dossier


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
def seed_incident(sqlite_session: Session) -> str:
    now = datetime.now(timezone.utc)
    src = SourceReferenceModel(
        id="src_001",
        title="Source Alpha",
        publisher="Publisher Alpha",
        url="https://example.com/alpha",
        source_type="TECHNICAL_POSTMORTEM",
        access_status="OPEN_PUBLIC",
        authority="PRIMARY",
        reliability="HIGH",
        independence="INDEPENDENT_ORIGINAL",
        content_hash="1" * 64,
        retrieval_date=now,
    )
    sqlite_session.add(src)

    ev = EvidenceRecordModel(
        id="ev_101",
        source_id="src_001",
        short_summary="Telemetry log",
        evidence_type="TECHNICAL_POSTMORTEM",
        directness="PRIMARY_DIRECT",
        specificity="HIGHLY_SPECIFIC",
        corroboration_status="FULLY_CORROBORATED",
        ingested_at=now,
        payload_hash="2" * 64,
    )
    sqlite_session.add(ev)

    inc = IncidentModel(
        id="inc_test_100",
        title="Autonomous Agent Database Purge",
        summary="Autonomous code agent deleted customer production records.",
        status="UNDER_INVESTIGATION",
    )
    sqlite_session.add(inc)

    clm = ClaimRecordModel(
        id="clm_100",
        incident_id="inc_test_100",
        claim_text="Agent deleted table 'users' at 04:15 UTC.",
        claim_type="TECHNICAL_FACT",
        epistemic_status="VERIFIED",
        confidence="HIGH",
        materiality="HIGH",
    )
    sqlite_session.add(clm)

    link = ClaimEvidenceLinkModel(
        claim_id="clm_100",
        evidence_id="ev_101",
        link_type="SUPPORTING",
    )
    sqlite_session.add(link)
    sqlite_session.commit()
    return "inc_test_100"


class TestEditorialReviewAndRepository:
    def test_save_and_retrieve_dossier(
        self, sqlite_session: Session, seed_incident: str
    ) -> None:
        repo = EditorialRepository(sqlite_session)
        dossier = create_sample_dossier()

        saved = repo.save_dossier(dossier, actor_id="analyst_1", is_human=True)
        assert saved.id == dossier.id
        assert len(saved.entries) == 1
        assert saved.status == EditorialDossierStatus.ASSEMBLED

        retrieved = repo.get_dossier(dossier.id)
        assert retrieved is not None
        assert retrieved.id == dossier.id
        assert retrieved.title == dossier.title
        assert retrieved.content_hash == dossier.compute_content_hash()

    def test_submit_for_review_lifecycle_transition(
        self, sqlite_session: Session, seed_incident: str
    ) -> None:
        repo = EditorialRepository(sqlite_session)
        dossier = create_sample_dossier()
        repo.save_dossier(dossier, actor_id="analyst_1", is_human=True)

        submitted = repo.submit_for_review(dossier.id, actor_id="analyst_1", is_human=True)
        assert submitted.status == EditorialDossierStatus.PENDING_REVIEW

        # Verify audit log recorded
        is_valid, anomalies = repo.verify_audit_chain(dossier.id)
        assert is_valid is True
        assert len(anomalies) == 0

    def test_approval_requires_human_reviewer(
        self, sqlite_session: Session, seed_incident: str
    ) -> None:
        """Rule 14: Automated algorithms/agents cannot self-approve."""
        repo = EditorialRepository(sqlite_session)
        dossier = create_sample_dossier()
        repo.save_dossier(dossier, actor_id="analyst_1", is_human=True)
        repo.submit_for_review(dossier.id, actor_id="analyst_1", is_human=True)

        validator = EditorialValidator()
        v_report = validator.validate_dossier(dossier)

        # Attestation validation forbids is_human=False at schema level
        with pytest.raises(Exception):
            EditorialReviewerAttestationSchema(
                reviewer_id="bot_reviewer",
                reviewer_role="Bot",
                is_human=False,
                statement_confirmed=True,
                content_hash=dossier.compute_content_hash(),
                dossier_id=dossier.id,
                dossier_version=1,
            )

    def test_approval_happy_path(
        self, sqlite_session: Session, seed_incident: str
    ) -> None:
        repo = EditorialRepository(sqlite_session)
        dossier = create_sample_dossier()
        repo.save_dossier(dossier, actor_id="analyst_1", is_human=True)
        repo.submit_for_review(dossier.id, actor_id="analyst_1", is_human=True)

        content_hash = dossier.compute_content_hash()
        attestation = EditorialReviewerAttestationSchema(
            reviewer_id="human_editor_1",
            reviewer_name="Jane Doe",
            reviewer_role="Senior Editor",
            is_human=True,
            statement_confirmed=True,
            attestation_statement=EDITORIAL_ATTESTATION_STATEMENT,
            content_hash=content_hash,
            dossier_id=dossier.id,
            dossier_version=dossier.version,
        )

        validator = EditorialValidator()
        v_report = validator.validate_dossier(dossier)

        approved = repo.approve_dossier(dossier.id, attestation, v_report)
        assert approved.status == EditorialDossierStatus.APPROVED_INFORMATIONAL
        assert approved.reviewed_by == "human_editor_1"
        assert approved.content_hash == content_hash

        # Verify audit log chaining
        is_valid, anomalies = repo.verify_audit_chain(dossier.id)
        assert is_valid is True
        assert len(anomalies) == 0

    def test_approved_content_is_immutable(
        self, sqlite_session: Session, seed_incident: str
    ) -> None:
        """Requirement: Approved dossier content is strictly immutable."""
        repo = EditorialRepository(sqlite_session)
        dossier = create_sample_dossier()
        repo.save_dossier(dossier, actor_id="analyst_1", is_human=True)
        repo.submit_for_review(dossier.id, actor_id="analyst_1", is_human=True)

        content_hash = dossier.compute_content_hash()
        attestation = EditorialReviewerAttestationSchema(
            reviewer_id="human_editor_1",
            reviewer_role="Senior Editor",
            is_human=True,
            statement_confirmed=True,
            content_hash=content_hash,
            dossier_id=dossier.id,
            dossier_version=1,
        )
        validator = EditorialValidator()
        v_report = validator.validate_dossier(dossier)
        repo.approve_dossier(dossier.id, attestation, v_report)

        # Attempt to mutate approved dossier
        modified_dossier = dossier.model_copy(update={"title": "Mutated Title"})
        with pytest.raises(ImmutabilityViolationError) as exc:
            repo.save_dossier(modified_dossier, actor_id="analyst_1", is_human=True)
        assert "Approved content is strictly immutable" in str(exc.value)

    def test_source_drift_detected_blocks_approval(
        self, sqlite_session: Session, seed_incident: str
    ) -> None:
        """Requirement: Source records modifying underlying incident trigger drift error."""
        repo = EditorialRepository(sqlite_session)
        dossier = create_sample_dossier()
        repo.save_dossier(dossier, actor_id="analyst_1", is_human=True)
        repo.submit_for_review(dossier.id, actor_id="analyst_1", is_human=True)

        # Modify underlying incident summary in DB
        inc = sqlite_session.get(IncidentModel, seed_incident)
        assert inc is not None
        inc.summary = "Drifted incident summary altered behind the scenes."
        sqlite_session.commit()

        content_hash = dossier.compute_content_hash()
        attestation = EditorialReviewerAttestationSchema(
            reviewer_id="human_editor_1",
            reviewer_role="Senior Editor",
            is_human=True,
            statement_confirmed=True,
            content_hash=content_hash,
            dossier_id=dossier.id,
            dossier_version=1,
        )
        validator = EditorialValidator()
        v_report = validator.validate_dossier(dossier)

        with pytest.raises(ValueError) as exc:
            repo.approve_dossier(dossier.id, attestation, v_report)
        assert "drifted" in str(exc.value)

    def test_rejection_requires_reason_and_human(
        self, sqlite_session: Session, seed_incident: str
    ) -> None:
        repo = EditorialRepository(sqlite_session)
        dossier = create_sample_dossier()
        repo.save_dossier(dossier, actor_id="analyst_1", is_human=True)
        repo.submit_for_review(dossier.id, actor_id="analyst_1", is_human=True)

        rejected = repo.reject_dossier(
            dossier_id=dossier.id,
            reviewer_id="editor_reviewer",
            is_human=True,
            rejection_reason="Unclear distinction between whistleblower allegation and fact.",
        )
        assert rejected.status == EditorialDossierStatus.REJECTED
        assert "whistleblower allegation" in str(rejected.rejection_reason)

    def test_supersede_dossier_lifecycle(
        self, sqlite_session: Session, seed_incident: str
    ) -> None:
        repo = EditorialRepository(sqlite_session)
        dossier1 = create_sample_dossier()
        repo.save_dossier(dossier1, actor_id="analyst_1", is_human=True)
        repo.submit_for_review(dossier1.id, actor_id="analyst_1", is_human=True)

        content_hash = dossier1.compute_content_hash()
        attestation = EditorialReviewerAttestationSchema(
            reviewer_id="human_editor_1",
            reviewer_role="Senior Editor",
            is_human=True,
            statement_confirmed=True,
            content_hash=content_hash,
            dossier_id=dossier1.id,
            dossier_version=1,
        )
        validator = EditorialValidator()
        repo.approve_dossier(dossier1.id, attestation, validator.validate_dossier(dossier1))

        # Create revised dossier
        dossier2 = dossier1.model_copy(update={"id": "dos_2026_w10_rev2", "version": 2})
        repo.save_dossier(dossier2, actor_id="analyst_1", is_human=True)

        superseded = repo.supersede_dossier(
            old_dossier_id=dossier1.id,
            new_dossier_id=dossier2.id,
            actor_id="human_editor_1",
            is_human=True,
            rationale="Updated with second witness account.",
        )
        assert superseded.status == EditorialDossierStatus.SUPERSEDED
        assert superseded.superseded_by_id == dossier2.id

    def test_audit_chain_tamper_detection(
        self, sqlite_session: Session, seed_incident: str
    ) -> None:
        repo = EditorialRepository(sqlite_session)
        dossier = create_sample_dossier()
        repo.save_dossier(dossier, actor_id="analyst_1", is_human=True)
        repo.submit_for_review(dossier.id, actor_id="analyst_1", is_human=True)

        # Corrupt one audit event in database
        event = (
            sqlite_session.execute(
                GovernanceAuditLogModel.__table__.select().where(
                    GovernanceAuditLogModel.entity_id == dossier.id
                )
            )
            .first()
        )
        assert event is not None

        sqlite_session.execute(
            GovernanceAuditLogModel.__table__.update()
            .where(GovernanceAuditLogModel.id == event.id)
            .values(after_state_digest="tampered_hash_value" + "0" * 45)
        )
        sqlite_session.commit()

        is_valid, anomalies = repo.verify_audit_chain(dossier.id)
        assert is_valid is False
        assert any("tampered or corrupted" in a for a in anomalies)
