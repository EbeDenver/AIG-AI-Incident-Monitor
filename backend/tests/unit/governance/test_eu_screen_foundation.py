"""Unit tests verifying Phase 5 Increment 2C-1 EU Informational Screen Foundation.

Covers:
- EU reference library integrity and ID resolution against frameworks/eu-ai-act/eu-ai-act-2024-1689.yaml
- Controlled vocabularies, schemas, and epistemic modesty fields
- Mandatory immutable disclaimer versioning ('2024-1689-v2') and text validation
- Strict primary evidence link association (MappingEvidenceLinkModel)
- Candidate / review / approval / rejection state machine foundation
- Human-in-the-loop review enforcement (is_human=True, non-human self-approval blocked)
- Immutability of approved screens and append-only supersession chain
- Append-only cryptographic audit logging and hash-chain verification
- Output-eligibility guard blocking unapproved, ungrounded, or unverified screens
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ai_incident_monitor.db.base import Base
from ai_incident_monitor.db.models.governance import (
    EULegalRelevanceScreenModel,
    EUScreenRuleTraceModel,
    FrameworkReferenceSetModel,
    GovernanceAuditLogModel,
    MappingEvidenceLinkModel,
)
from ai_incident_monitor.domain.common import (
    ConstitutionalViolationError,
    ImmutabilityViolationError,
)
from ai_incident_monitor.governance.enums import (
    EUActorRoleConfidence,
    EUNexusAssessment,
    EURelevanceLevel,
    EUScreenStatus,
    EUSeriousIncidentRelevance,
    EUTimingAssessment,
    FrameworkCode,
    GovernanceAuditEventType,
    GovernanceConfidence,
    MappingStatus,
)
from ai_incident_monitor.governance.models import (
    EU_AI_ACT_DISCLAIMER_V2,
    EU_AI_ACT_DISCLAIMER_VERSION,
    EULegalRelevanceScreenSchema,
    EUScreenRuleTraceSchema,
    GovernanceActorIdentity,
    OutputIneligibleError,
    verify_output_eligibility,
)
from ai_incident_monitor.governance.reference_loader import (
    compute_file_sha256,
    load_framework_manifest,
    load_reference_set,
)
from ai_incident_monitor.repositories.governance_repo import GovernanceRepository


@pytest.fixture
def repo_root() -> Path:
    """Return the absolute path to the repository root."""
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


# ==============================================================================
# 1. Reference Library Integrity Tests
# ==============================================================================


class TestEUReferenceLibraryIntegrity:
    """Verify that the official EU AI Act YAML reference library satisfies integrity standards."""

    def test_eu_reference_yaml_matches_manifest(self, repo_root: Path) -> None:
        """Confirm the on-disk YAML SHA-256 matches the cryptographic manifest."""
        manifest = load_framework_manifest(repo_root / "frameworks" / "manifest.json")
        eu_entry = next(fw for fw in manifest.frameworks if fw.framework_code == FrameworkCode.EU_AI_ACT)
        yaml_path = repo_root / eu_entry.file_path
        computed_sha = compute_file_sha256(yaml_path)
        assert computed_sha == eu_entry.content_sha256, "EU AI Act YAML content hash must match manifest"

    def test_eu_reference_controls_coverage_and_identifiers(self, active_eu_reference_set: FrameworkReferenceSetModel) -> None:
        """Confirm all 33 canonical EU AI Act controls load with valid external identifiers and pinpoint locators."""
        controls = active_eu_reference_set.controls
        assert len(controls) == 33, f"Expected exactly 33 controls in EU reference set, got {len(controls)}"

        identifiers = {c.external_identifier for c in controls}
        # Core Articles
        assert "EU-ART-2" in identifiers
        assert "EU-ART-3.1" in identifiers
        assert "EU-ART-5" in identifiers
        assert "EU-ART-50" in identifiers
        assert "EU-ART-51" in identifiers
        # Annex III High-Risk Categories
        assert "EU-ANNEX-III.1" in identifiers
        assert "EU-ANNEX-III.2" in identifiers
        assert "EU-ANNEX-III.4" in identifiers
        assert "EU-ANNEX-III.8" in identifiers
        # Operational Obligations
        assert "EU-ART-12" in identifiers
        assert "EU-ART-14" in identifiers
        assert "EU-ART-72" in identifiers
        assert "EU-ART-73" in identifiers

        for ctrl in controls:
            assert ctrl.source_locator, f"Control {ctrl.external_identifier} missing source_locator"
            assert ctrl.title, f"Control {ctrl.external_identifier} missing title"
            assert ctrl.description, f"Control {ctrl.external_identifier} missing description"


# ==============================================================================
# 2. Controlled Vocabularies & Schema Validation Tests
# ==============================================================================


class TestEUScreenDataModelAndSchemas:
    """Verify controlled vocabularies, Pydantic schemas, and epistemic modesty fields."""

    def test_controlled_enums_integrity(self) -> None:
        """Confirm all planned enum values exist and have non-legal descriptions."""
        # EURelevanceLevel
        expected_relevance = {
            "DIRECT_RELEVANCE",
            "POSSIBLE_RELEVANCE",
            "CONCEPTUAL_RELEVANCE",
            "UNLIKELY_RELEVANCE",
            "OUTSIDE_APPARENT_SCOPE",
            "INSUFFICIENT_INFORMATION",
        }
        assert {e.value for e in EURelevanceLevel} == expected_relevance

        # EUScreenStatus
        expected_status = {
            "DRAFT",
            "CANDIDATE",
            "PENDING_REVIEW",
            "APPROVED_INFORMATIONAL",
            "REJECTED",
            "SUPERSEDED",
            "INSUFFICIENT_EVIDENCE",
        }
        assert {e.value for e in EUScreenStatus} == expected_status
        assert MappingStatus.APPROVED_INFORMATIONAL.value == "APPROVED_INFORMATIONAL"

        # EUNexusAssessment
        expected_nexus = {
            "POSSIBLE_EU_NEXUS",
            "NO_EU_NEXUS_EVIDENCE",
            "INSUFFICIENT_NEXUS_INFORMATION",
            "OUTSIDE_APPARENT_TERRITORIAL_SCOPE",
        }
        assert {e.value for e in EUNexusAssessment} == expected_nexus

        # EUActorRoleConfidence
        expected_role_conf = {
            "IDENTIFIED_FROM_EVIDENCE",
            "POSSIBLE_FROM_EVIDENCE",
            "UNKNOWN",
            "DISPUTED",
        }
        assert {e.value for e in EUActorRoleConfidence} == expected_role_conf

        # EUTimingAssessment
        expected_timing = {
            "REFERENCE_METADATA_ALIGNS",
            "INCIDENT_DATE_UNKNOWN",
            "EFFECTIVE_DATE_UNCERTAIN",
            "TEMPORAL_CONTEXT_REQUIRES_REVIEW",
            "NOT_ASSESSED",
        }
        assert {e.value for e in EUTimingAssessment} == expected_timing

        # EUSeriousIncidentRelevance
        expected_serious = {
            "POTENTIALLY_RELEVANT_FOR_REVIEW",
            "CONCEPTUALLY_RELEVANT",
            "INSUFFICIENT_INFORMATION",
            "NOT_APPARENTLY_RELEVANT",
        }
        assert {e.value for e in EUSeriousIncidentRelevance} == expected_serious

    def test_screen_schema_instantiation_defaults(self) -> None:
        """Verify schema instantiation with proper defaults."""
        schema = EULegalRelevanceScreenSchema(
            incident_id="inc_001",
            reference_set_id="refset_001",
            generated_by="DeterministicGovernanceEngine/1.0",
        )
        assert schema.screen_version == "1.0.0"
        assert schema.status == EUScreenStatus.DRAFT
        assert schema.screen_status == EUScreenStatus.DRAFT
        assert schema.relevance_level == EURelevanceLevel.INSUFFICIENT_INFORMATION
        assert schema.nexus_assessment == EUNexusAssessment.INSUFFICIENT_NEXUS_INFORMATION
        assert schema.actor_role_confidence == EUActorRoleConfidence.UNKNOWN
        assert schema.timing_assessment == EUTimingAssessment.NOT_ASSESSED
        assert schema.disclaimer_version == "2024-1689-v2"
        assert schema.disclaimer_text == EU_AI_ACT_DISCLAIMER_V2
        assert schema.known_facts == []
        assert schema.unknowns == []
        assert schema.disputed_facts == []
        assert schema.missing_facts == []
        assert schema.follow_up_questions == []

    def test_screen_schema_rejects_legal_determination_language(self) -> None:
        """Negative test: Prohibited legal language in narrative fields raises ValueError."""
        # Rationale containing legal conclusion
        with pytest.raises(ValueError, match="Prohibited legal determination language"):
            EULegalRelevanceScreenSchema(
                incident_id="inc_001",
                reference_set_id="refset_001",
                generated_by="Analyst",
                rationale="This incident constitutes a serious violation of Article 5.",
            )

        # Known facts containing noncompliant claim
        with pytest.raises(ValueError, match="Prohibited legal determination language"):
            EULegalRelevanceScreenSchema(
                incident_id="inc_001",
                reference_set_id="refset_001",
                generated_by="Analyst",
                known_facts=["The provider was noncompliant with human oversight rules."],
            )

        # Follow up question asserting statutory duty
        with pytest.raises(ValueError, match="Prohibited legal determination language"):
            EULegalRelevanceScreenSchema(
                incident_id="inc_001",
                reference_set_id="refset_001",
                generated_by="Analyst",
                follow_up_questions=["Why was the statutory duty ignored?"],
            )

    def test_screen_schema_rejects_disclaimer_tampering(self) -> None:
        """Negative test: Tampering with disclaimer text or version raises ValueError."""
        with pytest.raises(ValueError, match="Invalid disclaimer_version"):
            EULegalRelevanceScreenSchema(
                incident_id="inc_001",
                reference_set_id="refset_001",
                generated_by="Analyst",
                disclaimer_version="custom-v1",
            )

        with pytest.raises(ValueError, match="Mandatory disclaimer text mismatch"):
            EULegalRelevanceScreenSchema(
                incident_id="inc_001",
                reference_set_id="refset_001",
                generated_by="Analyst",
                disclaimer_text="Short unapproved disclaimer.",
            )


# ==============================================================================
# 3. Evidence Linkage & XOR Integrity Tests
# ==============================================================================


class TestEUScreenEvidenceLinkage:
    """Verify strict evidence-link foundation for EU legal relevance screens."""

    def test_add_and_retrieve_eu_screen_evidence_links(
        self, sqlite_session: Session, active_eu_reference_set: FrameworkReferenceSetModel
    ) -> None:
        """Verify connecting an evidence record to an EU legal screen."""
        repo = GovernanceRepository(sqlite_session)
        actor = GovernanceActorIdentity(actor_id="investigator_01", is_human=True)

        screen = repo.create_eu_screen(
            screen_data={
                "incident_id": "inc_ev_001",
                "reference_set_id": active_eu_reference_set.id,
                "disclaimer_version": EU_AI_ACT_DISCLAIMER_VERSION,
            },
            actor=actor,
        )

        link = repo.add_eu_screen_evidence_link(
            screen_id=screen.id,
            evidence_id="ev_record_999",
            claim_type="PRIMARY_OBSERVATION",
            relevance_note="EU deployment confirmed via corporate press release.",
            actor=actor,
        )

        assert link.id.startswith("maplink_")
        assert link.eu_legal_relevance_screen_id == screen.id
        assert link.incident_framework_mapping_id is None
        assert link.evidence_id == "ev_record_999"

        fetched_links = repo.get_eu_screen_evidence_links(screen.id)
        assert len(fetched_links) == 1
        assert fetched_links[0].id == link.id


# ==============================================================================
# 4. State Machine & Human Review Gate Tests
# ==============================================================================


class TestCandidateReviewApprovalStateMachine:
    """Verify state machine transitions, human review enforcement, and immutability."""

    def test_automated_actor_cannot_approve_screen(
        self, sqlite_session: Session, active_eu_reference_set: FrameworkReferenceSetModel
    ) -> None:
        """Constitutional Rule 12: Automated models/LLMs cannot approve screens."""
        repo = GovernanceRepository(sqlite_session)
        automated_actor = GovernanceActorIdentity(actor_id="LLM_ScreenEngine_v1", is_human=False)

        screen = repo.create_eu_screen(
            screen_data={
                "incident_id": "inc_rev_001",
                "reference_set_id": active_eu_reference_set.id,
                "disclaimer_version": EU_AI_ACT_DISCLAIMER_VERSION,
            },
            actor=automated_actor,
        )

        # Link evidence so lack of evidence is not the failure reason
        repo.add_eu_screen_evidence_link(
            screen_id=screen.id,
            evidence_id="ev_001",
            actor=automated_actor,
        )

        # Attempting approval with is_human=False must be strictly rejected
        with pytest.raises(ConstitutionalViolationError, match="Automated self-approval forbidden"):
            repo.transition_eu_screen_status(
                screen_id=screen.id,
                new_status=EUScreenStatus.APPROVED_INFORMATIONAL,
                actor=automated_actor,
                rationale="Automated self-approval attempt.",
            )

    def test_human_approval_workflow_success(
        self, sqlite_session: Session, active_eu_reference_set: FrameworkReferenceSetModel
    ) -> None:
        """Authenticated human reviewer can approve a fully-grounded screen."""
        repo = GovernanceRepository(sqlite_session)
        analyst = GovernanceActorIdentity(actor_id="senior_analyst_01", is_human=True, role="Lead Analyst")

        screen = repo.create_eu_screen(
            screen_data={
                "incident_id": "inc_rev_002",
                "reference_set_id": active_eu_reference_set.id,
                "disclaimer_version": EU_AI_ACT_DISCLAIMER_VERSION,
            },
            actor=analyst,
        )

        # Connect evidence
        repo.add_eu_screen_evidence_link(
            screen_id=screen.id,
            evidence_id="ev_002",
            actor=analyst,
        )

        # Transition DRAFT -> CANDIDATE -> PENDING_REVIEW -> APPROVED_INFORMATIONAL
        repo.transition_eu_screen_status(screen.id, EUScreenStatus.CANDIDATE, actor=analyst)
        assert screen.status == EUScreenStatus.CANDIDATE.value

        repo.transition_eu_screen_status(screen.id, EUScreenStatus.PENDING_REVIEW, actor=analyst)
        assert screen.status == EUScreenStatus.PENDING_REVIEW.value

        approved_screen = repo.transition_eu_screen_status(
            screen.id,
            EUScreenStatus.APPROVED_INFORMATIONAL,
            actor=analyst,
            rationale="Verified primary source and factual neutrality.",
        )
        assert approved_screen.status == EUScreenStatus.APPROVED_INFORMATIONAL.value
        assert approved_screen.reviewed_by == "senior_analyst_01"
        assert approved_screen.reviewed_at is not None

    def test_rejection_workflow(
        self, sqlite_session: Session, active_eu_reference_set: FrameworkReferenceSetModel
    ) -> None:
        """Human reviewer can reject a candidate screen."""
        repo = GovernanceRepository(sqlite_session)
        analyst = GovernanceActorIdentity(actor_id="reviewer_02", is_human=True)

        screen = repo.create_eu_screen(
            screen_data={
                "incident_id": "inc_rev_003",
                "reference_set_id": active_eu_reference_set.id,
                "disclaimer_version": EU_AI_ACT_DISCLAIMER_VERSION,
            },
            actor=analyst,
        )

        rejected_screen = repo.transition_eu_screen_status(
            screen.id,
            EUScreenStatus.REJECTED,
            actor=analyst,
            rationale="Insufficient factual grounding for informational screening.",
        )
        assert rejected_screen.status == EUScreenStatus.REJECTED.value
        assert rejected_screen.reviewed_by == "reviewer_02"

    def test_prevent_in_place_mutation_of_approved_screen(
        self, sqlite_session: Session, active_eu_reference_set: FrameworkReferenceSetModel
    ) -> None:
        """Constitutional Rule: Approved screens are immutable in place; edits must supersede."""
        repo = GovernanceRepository(sqlite_session)
        analyst = GovernanceActorIdentity(actor_id="analyst_03", is_human=True)

        screen = repo.create_eu_screen(
            screen_data={
                "incident_id": "inc_rev_004",
                "reference_set_id": active_eu_reference_set.id,
                "disclaimer_version": EU_AI_ACT_DISCLAIMER_VERSION,
            },
            actor=analyst,
        )
        repo.add_eu_screen_evidence_link(screen.id, evidence_id="ev_004", actor=analyst)
        repo.transition_eu_screen_status(screen.id, EUScreenStatus.APPROVED_INFORMATIONAL, actor=analyst)

        # In-place status transition attempt on APPROVED screen must raise ImmutabilityViolationError
        with pytest.raises(ImmutabilityViolationError, match="Cannot mutate approved EU screen"):
            repo.transition_eu_screen_status(screen.id, EUScreenStatus.PENDING_REVIEW, actor=analyst)


# ==============================================================================
# 5. Immutable Supersession & Lineage Tests
# ==============================================================================


class TestEUScreenSupersessionLineage:
    """Verify append-only supersession behavior for EU screens."""

    def test_supersede_preserves_original_and_links_lineage(
        self, sqlite_session: Session, active_eu_reference_set: FrameworkReferenceSetModel
    ) -> None:
        """Superseding an EU screen creates a new revision and links supersedes/superseded_by pointers."""
        repo = GovernanceRepository(sqlite_session)
        analyst = GovernanceActorIdentity(actor_id="analyst_04", is_human=True)

        original = repo.create_eu_screen(
            screen_data={
                "incident_id": "inc_sup_001",
                "reference_set_id": active_eu_reference_set.id,
                "screen_version": "1.0.0",
                "disclaimer_version": EU_AI_ACT_DISCLAIMER_VERSION,
                "nexus_assessment": EUNexusAssessment.INSUFFICIENT_NEXUS_INFORMATION.value,
                "relevance_level": EURelevanceLevel.INSUFFICIENT_INFORMATION.value,
            },
            actor=analyst,
        )

        superseding = repo.supersede_eu_screen(
            original_screen_id=original.id,
            updated_attributes={
                "nexus_assessment": EUNexusAssessment.POSSIBLE_EU_NEXUS.value,
                "relevance_level": EURelevanceLevel.DIRECT_RELEVANCE.value,
                "screen_version": "1.0.1",
            },
            actor=analyst,
            rationale="Updated nexus assessment following regulatory press dispatch.",
        )

        assert superseding.id != original.id
        assert superseding.supersedes_screen_id == original.id
        assert superseding.nexus_assessment == EUNexusAssessment.POSSIBLE_EU_NEXUS.value
        assert superseding.relevance_level == EURelevanceLevel.DIRECT_RELEVANCE.value
        assert superseding.disclaimer_version == EU_AI_ACT_DISCLAIMER_VERSION
        assert superseding.disclaimer_text == EU_AI_ACT_DISCLAIMER_V2

        sqlite_session.refresh(original)
        assert original.status == EUScreenStatus.SUPERSEDED.value
        assert original.superseded_by_id == superseding.id

    def test_cannot_supersede_already_superseded_screen(
        self, sqlite_session: Session, active_eu_reference_set: FrameworkReferenceSetModel
    ) -> None:
        """An already superseded screen cannot be superseded a second time."""
        repo = GovernanceRepository(sqlite_session)
        analyst = GovernanceActorIdentity(actor_id="analyst_05", is_human=True)

        screen = repo.create_eu_screen(
            screen_data={
                "incident_id": "inc_sup_002",
                "reference_set_id": active_eu_reference_set.id,
                "disclaimer_version": EU_AI_ACT_DISCLAIMER_VERSION,
            },
            actor=analyst,
        )

        repo.supersede_eu_screen(
            original_screen_id=screen.id,
            updated_attributes={},
            actor=analyst,
            rationale="Initial correction.",
        )

        # Attempting second supersession of original must fail
        with pytest.raises(ValueError, match="already been superseded"):
            repo.supersede_eu_screen(
                original_screen_id=screen.id,
                updated_attributes={},
                actor=analyst,
                rationale="Second correction attempt on old node.",
            )


# ==============================================================================
# 6. Cryptographic Audit Trail Tests
# ==============================================================================


class TestEUScreenCryptographicAuditTrail:
    """Verify cryptographic hash chaining across EU screen lifecycle events."""

    def test_eu_screen_audit_chain_verification_and_tamper_detection(
        self, sqlite_session: Session, active_eu_reference_set: FrameworkReferenceSetModel
    ) -> None:
        """Audit chain connects CREATE, ADD_EVIDENCE_LINK, and TRANSITION_STATE events with valid hashes."""
        repo = GovernanceRepository(sqlite_session)
        actor = GovernanceActorIdentity(actor_id="auditor_01", is_human=True)

        screen = repo.create_eu_screen(
            screen_data={
                "incident_id": "inc_audit_001",
                "reference_set_id": active_eu_reference_set.id,
                "disclaimer_version": EU_AI_ACT_DISCLAIMER_VERSION,
            },
            actor=actor,
        )

        repo.add_eu_screen_evidence_link(screen.id, evidence_id="ev_aud_001", actor=actor)
        repo.transition_eu_screen_status(screen.id, EUScreenStatus.CANDIDATE, actor=actor)
        repo.transition_eu_screen_status(screen.id, EUScreenStatus.PENDING_REVIEW, actor=actor)
        repo.transition_eu_screen_status(screen.id, EUScreenStatus.APPROVED_INFORMATIONAL, actor=actor)

        is_valid, errors = repo.verify_governance_audit_chain("eu_legal_relevance_screens", screen.id)
        assert is_valid is True
        assert len(errors) == 0

        # Simulate tampering with an audit log event
        audit_log = (
            sqlite_session.query(GovernanceAuditLogModel)
            .filter_by(entity_id=screen.id)
            .order_by(GovernanceAuditLogModel.created_at.asc())
            .first()
        )
        assert audit_log is not None
        audit_log.event_hash = "f" * 64
        sqlite_session.commit()

        is_tampered_valid, tamper_errors = repo.verify_governance_audit_chain("eu_legal_relevance_screens", screen.id)
        assert is_tampered_valid is False
        assert len(tamper_errors) > 0


# ==============================================================================
# 7. Fine-Grained Rule Traces Foundation Tests
# ==============================================================================


class TestEUScreenRuleTracesFoundation:
    """Verify EUScreenRuleTraceModel and repository methods."""

    def test_add_and_retrieve_rule_traces(
        self, sqlite_session: Session, active_eu_reference_set: FrameworkReferenceSetModel
    ) -> None:
        """Rule traces record exact rule_id, rule_version, and matched conditions."""
        repo = GovernanceRepository(sqlite_session)
        actor = GovernanceActorIdentity(actor_id="engine_actor", is_human=False)

        screen = repo.create_eu_screen(
            screen_data={
                "incident_id": "inc_trace_001",
                "reference_set_id": active_eu_reference_set.id,
                "disclaimer_version": EU_AI_ACT_DISCLAIMER_VERSION,
            },
            actor=actor,
        )

        trace1 = repo.add_eu_screen_rule_trace(
            screen_id=screen.id,
            rule_id="RULE-EU-NEXUS-01",
            rule_version="1.0.0",
            reference_set_id=active_eu_reference_set.id,
            matched_condition_ids=["COND-EU-ESTABLISHED", "COND-COMMERCIAL-PRESENCE"],
        )
        trace2 = repo.add_eu_screen_rule_trace(
            screen_id=screen.id,
            rule_id="RULE-EU-AISYS-01",
            rule_version="1.0.0",
            reference_set_id=active_eu_reference_set.id,
            matched_condition_ids=["COND-AUTONOMY-LEVEL-2", "COND-MACHINE-BASED"],
        )

        assert trace1.id.startswith("eutrace_")
        assert trace2.id.startswith("eutrace_")

        traces = repo.get_eu_screen_rule_traces(screen.id)
        assert len(traces) == 2
        assert traces[0].rule_id == "RULE-EU-NEXUS-01"
        assert traces[1].rule_id == "RULE-EU-AISYS-01"
        assert "COND-EU-ESTABLISHED" in traces[0].matched_condition_ids


# ==============================================================================
# 8. Output Eligibility Guard Tests
# ==============================================================================


class TestOutputEligibilityGuard:
    """Verify that verify_output_eligibility blocks screens lacking required preconditions."""

    def test_eligible_screen_passes(
        self, sqlite_session: Session, active_eu_reference_set: FrameworkReferenceSetModel
    ) -> None:
        """Fully-approved screen with disclaimer v2, evidence links, and human review is eligible."""
        repo = GovernanceRepository(sqlite_session)
        actor = GovernanceActorIdentity(actor_id="human_verifier", is_human=True)

        screen = repo.create_eu_screen(
            screen_data={
                "incident_id": "inc_elig_001",
                "reference_set_id": active_eu_reference_set.id,
                "disclaimer_version": EU_AI_ACT_DISCLAIMER_VERSION,
            },
            actor=actor,
        )
        repo.add_eu_screen_evidence_link(screen.id, evidence_id="ev_001", actor=actor)
        repo.transition_eu_screen_status(screen.id, EUScreenStatus.APPROVED_INFORMATIONAL, actor=actor)

        evidence_links = repo.get_eu_screen_evidence_links(screen.id)
        is_eligible, reasons = verify_output_eligibility(screen, evidence_links=evidence_links)
        assert is_eligible is True
        assert len(reasons) == 0

        # Should not raise error when raise_error=True
        verify_output_eligibility(screen, evidence_links=evidence_links, raise_error=True)

    def test_ineligible_due_to_unapproved_state(self) -> None:
        """Candidate or Pending Review screen is not eligible for reporting output."""
        schema = EULegalRelevanceScreenSchema(
            incident_id="inc_elig_002",
            reference_set_id="refset_001",
            status=EUScreenStatus.PENDING_REVIEW,
            evidence_ids=["ev_001"],
            reviewed_by="analyst",
            reviewed_at=datetime.now(timezone.utc),
            generated_by="analyst",
        )
        is_eligible, reasons = verify_output_eligibility(schema)
        assert is_eligible is False
        assert any("Screen status is 'PENDING_REVIEW'" in r for r in reasons)

        with pytest.raises(OutputIneligibleError, match="Screen status is 'PENDING_REVIEW'"):
            verify_output_eligibility(schema, raise_error=True)

    def test_ineligible_due_to_missing_evidence_links(self) -> None:
        """Approved screen with zero evidence links is rejected."""
        schema = EULegalRelevanceScreenSchema(
            incident_id="inc_elig_003",
            reference_set_id="refset_001",
            status=EUScreenStatus.APPROVED_INFORMATIONAL,
            evidence_ids=[],
            reviewed_by="human_analyst",
            reviewed_at=datetime.now(timezone.utc),
            generated_by="analyst",
        )
        is_eligible, reasons = verify_output_eligibility(schema)
        assert is_eligible is False
        assert any("lacks required primary evidence links" in r for r in reasons)

    def test_ineligible_due_to_missing_human_reviewer(self) -> None:
        """Approved screen missing reviewed_by or reviewed_at is rejected."""
        schema = EULegalRelevanceScreenSchema(
            incident_id="inc_elig_004",
            reference_set_id="refset_001",
            status=EUScreenStatus.APPROVED_INFORMATIONAL,
            evidence_ids=["ev_001"],
            reviewed_by=None,
            reviewed_at=None,
            generated_by="analyst",
        )
        is_eligible, reasons = verify_output_eligibility(schema)
        assert is_eligible is False
        assert any("lacks authenticated reviewer identity" in r for r in reasons)
        assert any("lacks review timestamp" in r for r in reasons)
