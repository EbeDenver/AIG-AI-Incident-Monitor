"""Unit tests for EU AI Act output eligibility enforcement and reviewer attestation.

Enforces Constitutional Rules 10, 11, 12, 13, 14 & 15:
- All 7 output-eligibility gates fail closed.
- Automated actors cannot self-approve or self-attest.
- Linter violations and disclaimer alterations unconditionally block output.
- Relational repository transitions and append-only audit events are cryptographically chained.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ai_incident_monitor.db.base import Base
from ai_incident_monitor.db.models.governance import (
    FrameworkReferenceSetModel,
)
from ai_incident_monitor.domain.common import (
    ConstitutionalViolationError,
)
from ai_incident_monitor.governance.enums import (
    ControlLevel,
    EUScreenStatus,
    FrameworkCode,
    FrameworkStatus,
    GovernanceAuditEventType,
)
from ai_incident_monitor.governance.eu_output_linter import EUOutputLinter
from ai_incident_monitor.governance.models import (
    EU_AI_ACT_DISCLAIMER_V2,
    EU_AI_ACT_DISCLAIMER_VERSION,
    EULegalRelevanceScreenSchema,
    EUReviewerAttestationSchema,
    GovernanceActorIdentity,
    OutputIneligibleError,
    verify_output_eligibility,
)
from ai_incident_monitor.governance.reference_loader import (
    compute_file_sha256,
    load_reference_set,
)
from ai_incident_monitor.repositories.governance_repo import GovernanceRepository


@pytest.fixture
def repo_root() -> Path:
    """Return repository root path."""
    return Path(__file__).resolve().parents[4]


@pytest.fixture
def sqlite_session() -> Session:
    """Provide an in-memory SQLite database session initialized with full schema."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def active_eu_reference_set(sqlite_session: Session, repo_root: Path) -> FrameworkReferenceSetModel:
    """Load and persist the official EU AI Act reference set."""
    yaml_path = repo_root / "frameworks" / "eu-ai-act" / "eu-ai-act-2024-1689.yaml"
    ref_schema = load_reference_set(yaml_path)
    content_hash = compute_file_sha256(yaml_path)
    repo = GovernanceRepository(sqlite_session)
    return repo.create_reference_set(ref_schema, content_hash=content_hash)


@pytest.fixture
def valid_attestation() -> EUReviewerAttestationSchema:
    """Fixture providing a valid human reviewer attestation."""
    return EUReviewerAttestationSchema(
        attestor_id="human_reviewer_01",
        attestor_role="SENIOR_GOVERNANCE_ANALYST",
        is_human=True,
        statement_confirmed=True,
    )


@pytest.fixture
def base_eligible_screen_data(valid_attestation: EUReviewerAttestationSchema) -> dict[str, Any]:
    """Fixture providing dictionary attributes for a fully-eligible approved screen."""
    return {
        "id": "euscreen_elig_test_01",
        "incident_id": "inc_elig_001",
        "reference_set_id": "eu-ai-act-2024-1689",
        "status": EUScreenStatus.APPROVED_INFORMATIONAL.value,
        "disclaimer_version": EU_AI_ACT_DISCLAIMER_VERSION,
        "disclaimer_text": EU_AI_ACT_DISCLAIMER_V2,
        "evidence_ids": ["ev_link_001"],
        "reviewed_by": "human_reviewer_01",
        "reviewed_at": datetime.now(timezone.utc),
        "generated_by": "DeterministicGovernanceEngine/1.0",
        "rationale": "Evidence documents deployment of automated inferencing in public areas.",
        "known_facts": ["Camera hardware connected to inference server."],
        "unknowns": ["Vendor specific algorithm parameters."],
        "disputed_facts": [],
        "missing_facts": [],
        "follow_up_questions": [],
        "metadata_json": {
            "reviewer_attestation": valid_attestation.model_dump(mode="json"),
        },
    }


class TestVerifyOutputEligibilityGates:
    """Test unit isolation of all 7 fail-closed gates in verify_output_eligibility."""

    def test_eligible_screen_passes_all_gates(
        self, base_eligible_screen_data: dict[str, Any], valid_attestation: EUReviewerAttestationSchema
    ) -> None:
        """Screen satisfying all preconditions passes eligibility with zero block reasons."""
        is_eligible, reasons = verify_output_eligibility(
            base_eligible_screen_data,
            reviewer_attestation=valid_attestation,
            raise_error=False,
        )
        assert is_eligible is True
        assert len(reasons) == 0

        # Does not raise when raise_error=True
        verify_output_eligibility(
            base_eligible_screen_data,
            reviewer_attestation=valid_attestation,
            raise_error=True,
        )

    @pytest.mark.parametrize(
        "unapproved_status",
        [
            EUScreenStatus.DRAFT,
            EUScreenStatus.CANDIDATE,
            EUScreenStatus.PENDING_REVIEW,
            EUScreenStatus.REJECTED,
            EUScreenStatus.SUPERSEDED,
            EUScreenStatus.INSUFFICIENT_EVIDENCE,
        ],
    )
    def test_gate1_blocked_unapproved_status(
        self,
        base_eligible_screen_data: dict[str, Any],
        valid_attestation: EUReviewerAttestationSchema,
        unapproved_status: EUScreenStatus,
    ) -> None:
        """Gate 1: Any status other than APPROVED_INFORMATIONAL fails closed."""
        base_eligible_screen_data["status"] = unapproved_status.value
        is_eligible, reasons = verify_output_eligibility(
            base_eligible_screen_data, reviewer_attestation=valid_attestation
        )
        assert is_eligible is False
        assert any("must be 'APPROVED_INFORMATIONAL'" in r for r in reasons)

    def test_gate2_blocked_disclaimer_version_mismatch(
        self, base_eligible_screen_data: dict[str, Any], valid_attestation: EUReviewerAttestationSchema
    ) -> None:
        """Gate 2: Disclaimer version other than 2024-1689-v2 fails closed."""
        base_eligible_screen_data["disclaimer_version"] = "2024-1689-v1"
        is_eligible, reasons = verify_output_eligibility(
            base_eligible_screen_data, reviewer_attestation=valid_attestation
        )
        assert is_eligible is False
        assert any("Invalid disclaimer version" in r for r in reasons)

    def test_gate2_blocked_altered_disclaimer_text(
        self, base_eligible_screen_data: dict[str, Any], valid_attestation: EUReviewerAttestationSchema
    ) -> None:
        """Gate 2: Any edit, truncation, or reordering of disclaimer text fails closed."""
        base_eligible_screen_data["disclaimer_text"] = "Informational governance screen only."
        is_eligible, reasons = verify_output_eligibility(
            base_eligible_screen_data, reviewer_attestation=valid_attestation
        )
        assert is_eligible is False
        assert any("Disclaimer text has been modified" in r for r in reasons)

    def test_gate3_blocked_zero_evidence_links(
        self, base_eligible_screen_data: dict[str, Any], valid_attestation: EUReviewerAttestationSchema
    ) -> None:
        """Gate 3: Screen lacking primary evidence links fails closed."""
        base_eligible_screen_data["evidence_ids"] = []
        is_eligible, reasons = verify_output_eligibility(
            base_eligible_screen_data,
            evidence_links=[],
            reviewer_attestation=valid_attestation,
        )
        assert is_eligible is False
        assert any("lacks required primary evidence links" in r for r in reasons)

    def test_gate4_blocked_missing_reviewer_identity(
        self, base_eligible_screen_data: dict[str, Any], valid_attestation: EUReviewerAttestationSchema
    ) -> None:
        """Gate 4: Missing or blank reviewed_by fails closed."""
        base_eligible_screen_data["reviewed_by"] = None
        is_eligible, reasons = verify_output_eligibility(
            base_eligible_screen_data, reviewer_attestation=valid_attestation
        )
        assert is_eligible is False
        assert any("lacks authenticated reviewer identity" in r for r in reasons)

    def test_gate4_blocked_missing_reviewed_at(
        self, base_eligible_screen_data: dict[str, Any], valid_attestation: EUReviewerAttestationSchema
    ) -> None:
        """Gate 4: Missing reviewed_at timestamp fails closed."""
        base_eligible_screen_data["reviewed_at"] = None
        is_eligible, reasons = verify_output_eligibility(
            base_eligible_screen_data, reviewer_attestation=valid_attestation
        )
        assert is_eligible is False
        assert any("lacks review timestamp" in r for r in reasons)

    def test_gate5_blocked_missing_attestation(
        self, base_eligible_screen_data: dict[str, Any]
    ) -> None:
        """Gate 5: Screen lacking human reviewer attestation fails closed."""
        base_eligible_screen_data["metadata_json"] = {}
        is_eligible, reasons = verify_output_eligibility(
            base_eligible_screen_data, reviewer_attestation=None
        )
        assert is_eligible is False
        assert any("lacks required human reviewer attestation" in r for r in reasons)

    def test_gate5_blocked_automated_attestation_attempt(
        self, base_eligible_screen_data: dict[str, Any]
    ) -> None:
        """Gate 5: Attestation claiming is_human=False fails closed."""
        bot_attestation = {
            "attestor_id": "human_reviewer_01",
            "attestor_role": "AUTOMATED_BOT",
            "is_human": False,
            "statement_confirmed": True,
        }
        is_eligible, reasons = verify_output_eligibility(
            base_eligible_screen_data, reviewer_attestation=bot_attestation
        )
        assert is_eligible is False
        assert any("Reviewer attestation validation failed" in r or "is_human=True" in r for r in reasons)

    def test_gate5_blocked_unconfirmed_statement(
        self, base_eligible_screen_data: dict[str, Any]
    ) -> None:
        """Gate 5: Attestation with statement_confirmed=False fails closed."""
        unconfirmed = {
            "attestor_id": "human_reviewer_01",
            "attestor_role": "SENIOR_ANALYST",
            "is_human": True,
            "statement_confirmed": False,
        }
        is_eligible, reasons = verify_output_eligibility(
            base_eligible_screen_data, reviewer_attestation=unconfirmed
        )
        assert is_eligible is False
        assert any("Reviewer attestation validation failed" in r or "statement was not confirmed" in r for r in reasons)

    def test_gate5_blocked_attestor_id_mismatch(
        self, base_eligible_screen_data: dict[str, Any]
    ) -> None:
        """Gate 5: Attestation signed by a different identity than reviewed_by fails closed."""
        mismatched = EUReviewerAttestationSchema(
            attestor_id="different_reviewer_99",
            attestor_role="ANALYST",
            is_human=True,
            statement_confirmed=True,
        )
        is_eligible, reasons = verify_output_eligibility(
            base_eligible_screen_data, reviewer_attestation=mismatched
        )
        assert is_eligible is False
        assert any("does not match screen reviewed_by" in r for r in reasons)

    def test_gate6_blocked_stale_reference_set(
        self, base_eligible_screen_data: dict[str, Any], valid_attestation: EUReviewerAttestationSchema
    ) -> None:
        """Gate 6: Reference set that is SUPERSEDED or DEPRECATED fails closed."""
        stale_ref = {
            "id": "eu-ai-act-2024-1689",
            "framework_code": FrameworkCode.EU_AI_ACT.value,
            "status": FrameworkStatus.SUPERSEDED.value,
        }
        is_eligible, reasons = verify_output_eligibility(
            base_eligible_screen_data,
            reviewer_attestation=valid_attestation,
            reference_set=stale_ref,
        )
        assert is_eligible is False
        assert any("stale or superseded reference set" in r for r in reasons)

    def test_gate6_blocked_invalid_reference_set(
        self, base_eligible_screen_data: dict[str, Any], valid_attestation: EUReviewerAttestationSchema
    ) -> None:
        """Gate 6: Reference set from non-EU framework fails closed."""
        nist_ref = {
            "id": "nist-ai-rmf-1.0",
            "framework_code": FrameworkCode.NIST_AI_RMF.value,
            "status": FrameworkStatus.ACTIVE.value,
        }
        is_eligible, reasons = verify_output_eligibility(
            base_eligible_screen_data,
            reviewer_attestation=valid_attestation,
            reference_set=nist_ref,
        )
        assert is_eligible is False
        assert any("non-EU AI Act framework" in r for r in reasons)

    def test_gate7_blocked_prohibited_language_in_rationale(
        self, base_eligible_screen_data: dict[str, Any], valid_attestation: EUReviewerAttestationSchema
    ) -> None:
        """Gate 7: Prohibited legal language in rationale blocks output eligibility."""
        base_eligible_screen_data["rationale"] = (
            "The system committed an unlawful breach of safety regulations."
        )
        is_eligible, reasons = verify_output_eligibility(
            base_eligible_screen_data, reviewer_attestation=valid_attestation
        )
        assert is_eligible is False
        assert any("Output linter blocked" in r for r in reasons)
        assert any("rationale" in r for r in reasons)

    def test_gate7_blocked_prohibited_language_in_nested_metadata(
        self, base_eligible_screen_data: dict[str, Any], valid_attestation: EUReviewerAttestationSchema
    ) -> None:
        """Gate 7: Prohibited legal language inside nested metadata_json blocks output eligibility."""
        meta = dict(base_eligible_screen_data["metadata_json"])
        meta["conceptual_findings"] = [
            {
                "control_id": "EU-ART-5.1.h",
                "finding_rationale": "The company operated a prohibited practice in the EU.",
            }
        ]
        base_eligible_screen_data["metadata_json"] = meta

        is_eligible, reasons = verify_output_eligibility(
            base_eligible_screen_data, reviewer_attestation=valid_attestation
        )
        assert is_eligible is False
        assert any("Output linter blocked" in r for r in reasons)
        assert any("conceptual_findings[0].finding_rationale" in r for r in reasons)

    def test_raise_error_raises_output_ineligible_error(
        self, base_eligible_screen_data: dict[str, Any], valid_attestation: EUReviewerAttestationSchema
    ) -> None:
        """OutputIneligibleError is raised when raise_error=True and gates fail."""
        base_eligible_screen_data["status"] = EUScreenStatus.PENDING_REVIEW.value
        with pytest.raises(OutputIneligibleError, match="ineligible for external/reporting output"):
            verify_output_eligibility(
                base_eligible_screen_data,
                reviewer_attestation=valid_attestation,
                raise_error=True,
            )


class TestRepositoryAttestationAndAuditIntegration:
    """Test repository workflow transitions, attestation validation, and audit events."""

    def test_repository_approval_attaches_attestation(
        self, sqlite_session: Session, active_eu_reference_set: FrameworkReferenceSetModel
    ) -> None:
        """Transitioning to APPROVED_INFORMATIONAL via GovernanceRepository attaches attestation."""
        repo = GovernanceRepository(sqlite_session)
        human_actor = GovernanceActorIdentity(actor_id="lead_reviewer_01", is_human=True, role="LEAD")

        screen = repo.create_eu_screen(
            screen_data={
                "incident_id": "inc_repo_attest_01",
                "reference_set_id": active_eu_reference_set.id,
                "disclaimer_version": EU_AI_ACT_DISCLAIMER_VERSION,
            },
            actor=human_actor,
        )
        repo.add_eu_screen_evidence_link(screen.id, evidence_id="ev_r_01", actor=human_actor)

        # Transition to candidate and pending review
        repo.transition_eu_screen_status(screen.id, EUScreenStatus.CANDIDATE, actor=human_actor)
        repo.transition_eu_screen_status(screen.id, EUScreenStatus.PENDING_REVIEW, actor=human_actor)

        # Approve with explicit human reviewer attestation
        attestation = EUReviewerAttestationSchema(
            attestor_id="lead_reviewer_01",
            attestor_role="LEAD",
            is_human=True,
            statement_confirmed=True,
        )
        approved = repo.transition_eu_screen_status(
            screen.id,
            EUScreenStatus.APPROVED_INFORMATIONAL,
            actor=human_actor,
            rationale="Verified primary evidence documents neutral public display context.",
            reviewer_attestation=attestation,
        )

        assert approved.status == EUScreenStatus.APPROVED_INFORMATIONAL.value
        assert approved.reviewed_by == "lead_reviewer_01"
        assert approved.reviewed_at is not None
        assert "reviewer_attestation" in approved.metadata_json
        assert approved.metadata_json["reviewer_attestation"]["attestor_id"] == "lead_reviewer_01"

    def test_repository_approval_blocks_prohibited_rationale(
        self, sqlite_session: Session, active_eu_reference_set: FrameworkReferenceSetModel
    ) -> None:
        """GovernanceRepository blocks approval if reviewer rationale contains prohibited legal terms."""
        repo = GovernanceRepository(sqlite_session)
        human_actor = GovernanceActorIdentity(actor_id="reviewer_02", is_human=True)

        screen = repo.create_eu_screen(
            screen_data={
                "incident_id": "inc_repo_attest_02",
                "reference_set_id": active_eu_reference_set.id,
                "disclaimer_version": EU_AI_ACT_DISCLAIMER_VERSION,
            },
            actor=human_actor,
        )
        repo.add_eu_screen_evidence_link(screen.id, evidence_id="ev_r_02", actor=human_actor)
        repo.transition_eu_screen_status(screen.id, EUScreenStatus.PENDING_REVIEW, actor=human_actor)

        with pytest.raises(ConstitutionalViolationError, match="prohibited legal-conclusion language"):
            repo.transition_eu_screen_status(
                screen.id,
                EUScreenStatus.APPROVED_INFORMATIONAL,
                actor=human_actor,
                rationale="The system committed a severe violation of user privacy.",
            )

    def test_repository_supersede_blocks_prohibited_rationale(
        self, sqlite_session: Session, active_eu_reference_set: FrameworkReferenceSetModel
    ) -> None:
        """GovernanceRepository blocks supersede if rationale contains prohibited legal terms."""
        repo = GovernanceRepository(sqlite_session)
        human_actor = GovernanceActorIdentity(actor_id="reviewer_03", is_human=True)

        screen = repo.create_eu_screen(
            screen_data={
                "incident_id": "inc_repo_attest_03",
                "reference_set_id": active_eu_reference_set.id,
                "disclaimer_version": EU_AI_ACT_DISCLAIMER_VERSION,
            },
            actor=human_actor,
        )
        repo.add_eu_screen_evidence_link(screen.id, evidence_id="ev_r_03", actor=human_actor)

        with pytest.raises(ConstitutionalViolationError, match="prohibited legal-conclusion language"):
            repo.supersede_eu_screen(
                screen.id,
                updated_attributes={"rationale": "Updated facts."},
                actor=human_actor,
                rationale="Superseding because prior deployment was an unlawful illegal action.",
            )

    def test_repository_record_linter_and_eligibility_audit_events(
        self, sqlite_session: Session, active_eu_reference_set: FrameworkReferenceSetModel
    ) -> None:
        """Linter execution and eligibility evaluation record chained append-only audit events."""
        repo = GovernanceRepository(sqlite_session)
        actor = GovernanceActorIdentity(actor_id="auditor_01", is_human=True)

        screen = repo.create_eu_screen(
            screen_data={
                "incident_id": "inc_repo_audit_01",
                "reference_set_id": active_eu_reference_set.id,
                "disclaimer_version": EU_AI_ACT_DISCLAIMER_VERSION,
            },
            actor=actor,
        )

        linter = EUOutputLinter()
        linter_report = linter.lint_screen(screen, check_eligibility_prerequisites=False)

        # Record linter audit event
        linter_event = repo.record_linter_audit_event(screen.id, linter_report, actor=actor)
        assert linter_event.transition_type == GovernanceAuditEventType.LINTER_EXECUTION.value
        assert linter_event.previous_event_hash is not None  # Chained from CREATE_EU_SCREEN

        # Record eligibility check audit event
        is_eligible, reasons = verify_output_eligibility(screen, raise_error=False)
        elig_event = repo.record_output_eligibility_audit_event(
            screen.id, is_eligible=is_eligible, reasons=reasons, actor=actor
        )
        assert elig_event.transition_type == GovernanceAuditEventType.OUTPUT_ELIGIBILITY_CHECK.value
        assert elig_event.previous_event_hash == linter_event.event_hash  # Chained sequentially

        # Verify audit hash chain
        chain_valid, errors = repo.verify_governance_audit_chain(
            "eu_legal_relevance_screens", screen.id
        )
        assert chain_valid is True
        assert len(errors) == 0
