"""Unit tests verifying GovernanceRepository CRUD, immutability, supersession, and audit chaining."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ai_incident_monitor.db.base import Base
from ai_incident_monitor.db.models.evidence import EvidenceRecordModel
from ai_incident_monitor.db.models.governance import GovernanceAuditLogModel
from ai_incident_monitor.db.models.incident import IncidentModel
from ai_incident_monitor.db.models.source import SourceReferenceModel
from ai_incident_monitor.domain.common import (
    ConstitutionalViolationError,
    ImmutabilityViolationError,
)
from ai_incident_monitor.governance.enums import (
    GovernanceAuditEventType,
    MappingStatus,
    OECDApplicability,
)
from ai_incident_monitor.governance.models import (
    EU_AI_ACT_STATUTORY_DISCLAIMER,
    GovernanceActorIdentity,
)
from ai_incident_monitor.governance.reference_loader import (
    load_reference_set,
)
from ai_incident_monitor.repositories.governance_repo import (
    GovernanceRepository,
)


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


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
    """Helper creating a test incident and evidence record in the database."""
    now = datetime.now(timezone.utc)
    incident = IncidentModel(
        id="inc_gov_test_001",
        title="Automated Hiring Bias Incident",
        summary="Automated tool exhibited systematic demographic bias.",
        status="UNDER_INVESTIGATION",
        schema_version="1.0.0",
    )
    sqlite_session.add(incident)

    source = SourceReferenceModel(
        id="src_gov_test_001",
        title="Biased Tool Report",
        publisher="Audit Journal",
        url="https://example.com/reports/bias-incident",
        canonical_url="https://example.com/reports/bias-incident",
        source_type="INVESTIGATIVE_REPORT",
        retrieval_date=now,
        access_status="PUBLIC_WEB",
        authority="JOURNALISTIC",
        reliability="GENERALLY_RELIABLE",
        independence="INDEPENDENT",
        content_hash="e" * 64,
    )
    sqlite_session.add(source)

    evidence = EvidenceRecordModel(
        id="evd_gov_test_001",
        source_id="src_gov_test_001",
        short_summary="Independent audit confirmed disparity ratio of 0.58.",
        evidence_type="EMPIRICAL_STUDY",
        directness="DIRECT_OBSERVATION",
        specificity="HIGHLY_SPECIFIC",
        corroboration_status="CORROBORATED",
        review_status="APPROVED",
        ingested_at=now,
        payload_hash="f" * 64,
    )
    sqlite_session.add(evidence)
    sqlite_session.commit()
    return incident.id


class TestGovernanceRepository:
    """Verifies typed repository methods, immutability, supersession, and cryptographic audit chains."""

    def test_create_and_fetch_reference_set_and_controls(
        self,
        sqlite_session: Session,
        repo_root: Path,
    ) -> None:
        """Verify seeding and retrieving reference sets and controls."""
        repo = GovernanceRepository(sqlite_session)
        oecd_path = repo_root / "frameworks" / "oecd" / "oecd-principles-2024.yaml"
        ref_schema = load_reference_set(oecd_path)

        ref_model = repo.create_reference_set(ref_schema, content_hash="hash_123")
        assert ref_model.id.startswith("refset_")
        assert ref_model.framework_code == "OECD_AI_PRINCIPLES"

        # Query by ID
        fetched = repo.get_reference_set(ref_model.id)
        assert fetched is not None
        assert fetched.version == "2024.1"

        # Query by code and version
        fetched_by_code = repo.get_reference_set_by_code_and_version("OECD_AI_PRINCIPLES", "2024.1")
        assert fetched_by_code is not None
        assert fetched_by_code.id == ref_model.id

        # Query controls
        controls = repo.list_controls_for_reference_set(ref_model.id)
        assert len(controls) == len(ref_schema.controls)

        p1_ctrl = repo.get_control_by_external_id(ref_model.id, "OECD-P1.2")
        assert p1_ctrl is not None
        assert p1_ctrl.title == "Human rights and democratic values, including fairness and privacy"

    def test_create_mapping_and_audit_event_generation(
        self,
        sqlite_session: Session,
        repo_root: Path,
        seed_incident: str,
    ) -> None:
        """Verify creating an incident-framework mapping and automatic audit event generation."""
        repo = GovernanceRepository(sqlite_session)
        ref_schema = load_reference_set(repo_root / "frameworks" / "oecd" / "oecd-principles-2024.yaml")
        ref_model = repo.create_reference_set(ref_schema, content_hash="hash_123")
        ctrl = repo.get_control_by_external_id(ref_model.id, "OECD-P1.2")
        assert ctrl is not None

        actor = GovernanceActorIdentity(actor_id="analyst_jane", is_human=True, role="Senior Analyst")
        mapping = repo.create_mapping(
            mapping_data={
                "incident_id": seed_incident,
                "framework_code": "OECD_AI_PRINCIPLES",
                "reference_set_id": ref_model.id,
                "framework_control_id": ctrl.id,
                "mapping_level": "PRINCIPLE",
                "applicability": OECDApplicability.DIRECTLY_IMPLICATED.value,
                "confidence": "HIGH",
                "rationale": "Audit confirmed systemic exclusion based on demographic proxies.",
                "known_facts": ["Disparity ratio 0.58 documented in audit."],
                "unknowns": ["Vendor training data origin unknown."],
                "disputed_facts": [],
                "evidence_ids": ["evd_gov_test_001"],
            },
            actor=actor,
        )

        assert mapping.id.startswith("map_")
        assert mapping.mapping_status == "DRAFT"

        # Check audit event
        stmt_log = sqlite_session.query(GovernanceAuditLogModel).filter_by(entity_id=mapping.id).first()
        assert stmt_log is not None
        assert stmt_log.transition_type == GovernanceAuditEventType.CREATE_MAPPING.value
        assert stmt_log.actor_id == "analyst_jane"
        assert stmt_log.is_human is True
        assert stmt_log.event_hash is not None

    def test_evidence_link_xor_constraint(
        self,
        sqlite_session: Session,
        repo_root: Path,
        seed_incident: str,
    ) -> None:
        """Verify evidence link XOR parent constraint (exactly one parent mapping or screen)."""
        repo = GovernanceRepository(sqlite_session)
        ref_schema = load_reference_set(repo_root / "frameworks" / "oecd" / "oecd-principles-2024.yaml")
        ref_model = repo.create_reference_set(ref_schema, content_hash="hash_123")
        actor = GovernanceActorIdentity(actor_id="analyst_jane", is_human=True)

        mapping = repo.create_mapping(
            mapping_data={
                "incident_id": seed_incident,
                "framework_code": "OECD_AI_PRINCIPLES",
                "reference_set_id": ref_model.id,
                "mapping_level": "FRAMEWORK",
                "applicability": "DIRECTLY_IMPLICATED",
                "rationale": "Evidence link test.",
            },
            actor=actor,
        )

        # Successful single link
        link = repo.add_evidence_link(
            mapping_id=mapping.id,
            screen_id=None,
            evidence_id="evd_gov_test_001",
            claim_type="HARM_MATERIALIZATION",
            actor=actor,
        )
        assert link.id.startswith("maplink_")
        assert link.incident_framework_mapping_id == mapping.id

        # Rejection of both parents
        with pytest.raises(ValueError, match="Exactly one of mapping_id or screen_id"):
            repo.add_evidence_link(
                mapping_id=mapping.id,
                screen_id="some_screen_id",
                evidence_id="evd_gov_test_001",
                claim_type="HARM_MATERIALIZATION",
            )

        # Rejection of neither parent
        with pytest.raises(ValueError, match="Exactly one of mapping_id or screen_id"):
            repo.add_evidence_link(
                mapping_id=None,
                screen_id=None,
                evidence_id="evd_gov_test_001",
                claim_type="HARM_MATERIALIZATION",
            )

    def test_human_approval_workflow_and_actor_identity(
        self,
        sqlite_session: Session,
        repo_root: Path,
        seed_incident: str,
    ) -> None:
        """Constitutional Rule 12 & 13: Automated model cannot approve; requires human reviewer."""
        repo = GovernanceRepository(sqlite_session)
        ref_schema = load_reference_set(repo_root / "frameworks" / "oecd" / "oecd-principles-2024.yaml")
        ref_model = repo.create_reference_set(ref_schema, content_hash="hash_123")

        machine_actor = GovernanceActorIdentity(actor_id="engine:automated-rule", is_human=False)
        human_actor = GovernanceActorIdentity(actor_id="lead_reviewer_bob", is_human=True)

        mapping = repo.create_mapping(
            mapping_data={
                "incident_id": seed_incident,
                "framework_code": "OECD_AI_PRINCIPLES",
                "reference_set_id": ref_model.id,
                "mapping_level": "FRAMEWORK",
                "applicability": "DIRECTLY_IMPLICATED",
                "rationale": "Rule 12 check.",
            },
            actor=machine_actor,
        )

        # Machine attempt to approve MUST raise ConstitutionalViolationError
        with pytest.raises(ConstitutionalViolationError, match="Automated self-approval forbidden"):
            repo.transition_mapping_status(
                mapping_id=mapping.id,
                new_status=MappingStatus.APPROVED,
                actor=machine_actor,
                rationale="Automated approval attempt",
            )

        # Human approval succeeds
        approved_mapping = repo.transition_mapping_status(
            mapping_id=mapping.id,
            new_status=MappingStatus.APPROVED,
            actor=human_actor,
            rationale="Reviewed and verified against independent audit.",
        )
        assert approved_mapping.mapping_status == MappingStatus.APPROVED.value
        assert approved_mapping.reviewed_by == "lead_reviewer_bob"
        assert approved_mapping.reviewed_at is not None

    def test_prevent_in_place_mutation_of_approved_mapping(
        self,
        sqlite_session: Session,
        repo_root: Path,
        seed_incident: str,
    ) -> None:
        """Binding Correction 7: Reviewer edit never mutates approved mapping in place."""
        repo = GovernanceRepository(sqlite_session)
        ref_schema = load_reference_set(repo_root / "frameworks" / "oecd" / "oecd-principles-2024.yaml")
        ref_model = repo.create_reference_set(ref_schema, content_hash="hash_123")
        human_actor = GovernanceActorIdentity(actor_id="lead_reviewer_bob", is_human=True)

        mapping = repo.create_mapping(
            mapping_data={
                "incident_id": seed_incident,
                "framework_code": "OECD_AI_PRINCIPLES",
                "reference_set_id": ref_model.id,
                "mapping_level": "FRAMEWORK",
                "applicability": "DIRECTLY_IMPLICATED",
                "rationale": "Immutability check.",
            },
            actor=human_actor,
        )
        repo.transition_mapping_status(mapping.id, MappingStatus.APPROVED, human_actor, "Sign off")

        # In-place transition attempt on APPROVED mapping raises ImmutabilityViolationError
        with pytest.raises(ImmutabilityViolationError, match="Cannot mutate approved mapping"):
            repo.transition_mapping_status(
                mapping_id=mapping.id,
                new_status=MappingStatus.CANDIDATE,
                actor=human_actor,
                rationale="Attempt in-place edit",
            )

    def test_supersede_mapping_workflow(
        self,
        sqlite_session: Session,
        repo_root: Path,
        seed_incident: str,
    ) -> None:
        """Binding Correction 7: Supersession creates new record, marks old superseded, and chains audits."""
        repo = GovernanceRepository(sqlite_session)
        ref_schema = load_reference_set(repo_root / "frameworks" / "oecd" / "oecd-principles-2024.yaml")
        ref_model = repo.create_reference_set(ref_schema, content_hash="hash_123")
        human_actor = GovernanceActorIdentity(actor_id="lead_reviewer_bob", is_human=True)

        original = repo.create_mapping(
            mapping_data={
                "incident_id": seed_incident,
                "framework_code": "OECD_AI_PRINCIPLES",
                "reference_set_id": ref_model.id,
                "mapping_level": "FRAMEWORK",
                "applicability": "BROADER_GOVERNANCE_LESSON",
                "rationale": "Initial conservative assessment.",
            },
            actor=human_actor,
        )
        repo.transition_mapping_status(original.id, MappingStatus.APPROVED, human_actor, "Initial approval")

        # Supersede with stronger evidence
        superseding = repo.supersede_mapping(
            original_mapping_id=original.id,
            updated_attributes={
                "applicability": "DIRECTLY_IMPLICATED",
                "rationale": "Updated with newly disclosed technical audit findings.",
            },
            actor=human_actor,
            rationale="Substantive correction based on primary source evidence.",
        )

        assert superseding.id != original.id
        assert superseding.supersedes_mapping_id == original.id
        assert superseding.applicability == "DIRECTLY_IMPLICATED"

        # Verify original record state
        sqlite_session.refresh(original)
        assert original.superseded_by_id == superseding.id
        assert original.mapping_status == MappingStatus.SUPERSEDED.value

        # Attempting to supersede an already superseded mapping raises ValueError
        with pytest.raises(ValueError, match="has already been superseded"):
            repo.supersede_mapping(original.id, {}, human_actor, "Double supersede attempt")

    def test_create_and_supersede_eu_legal_screen(
        self,
        sqlite_session: Session,
        repo_root: Path,
        seed_incident: str,
    ) -> None:
        """Verify EU legal relevance screen creation, mandatory disclaimer, and supersession."""
        repo = GovernanceRepository(sqlite_session)
        ref_schema = load_reference_set(repo_root / "frameworks" / "eu-ai-act" / "eu-ai-act-2024-1689.yaml")
        ref_model = repo.create_reference_set(ref_schema, content_hash="hash_eu_123")
        actor = GovernanceActorIdentity(actor_id="legal_analyst", is_human=True)

        screen = repo.create_eu_screen(
            screen_data={
                "incident_id": seed_incident,
                "reference_set_id": ref_model.id,
                "territorial_nexus": "EU_PLACED_ON_MARKET",
                "ai_system_relevance": "MEETS_DEFINITION",
                "actor_roles": ["DEPLOYER"],
                "risk_class": "HIGH_RISK_SYSTEM",
                "potentially_relevant_articles": ["EU-ANNEX-III.4"],
                "operational_obligations": ["HUMAN_OVERSIGHT", "LOGGING"],
                "applicability_date_assessment": "Effective August 2, 2026 for Annex III high-risk systems.",
                "missing_facts": ["Specific deployment member state unknown."],
                "confidence": "MEDIUM",
            },
            actor=actor,
        )

        assert screen.id.startswith("euscreen_")
        assert screen.disclaimer_text == EU_AI_ACT_STATUTORY_DISCLAIMER
        assert "EU-ANNEX-III.4" in screen.potentially_relevant_articles

        # Supersede screen
        new_screen = repo.supersede_eu_screen(
            original_screen_id=screen.id,
            updated_attributes={
                "confidence": "HIGH",
                "missing_facts": [],
            },
            actor=actor,
            rationale="Clarified geographic nexus from regulator filing.",
        )
        assert new_screen.id != screen.id
        assert new_screen.supersedes_screen_id == screen.id

        sqlite_session.refresh(screen)
        assert screen.superseded_by_id == new_screen.id
        assert screen.status == MappingStatus.SUPERSEDED.value

    def test_cryptographic_audit_chain_verification_and_tamper_detection(
        self,
        sqlite_session: Session,
        repo_root: Path,
        seed_incident: str,
    ) -> None:
        """Binding Correction 6: Cryptographic hash chain across governance transitions and tamper detection."""
        repo = GovernanceRepository(sqlite_session)
        ref_schema = load_reference_set(repo_root / "frameworks" / "oecd" / "oecd-principles-2024.yaml")
        ref_model = repo.create_reference_set(ref_schema, content_hash="hash_123")
        human_actor = GovernanceActorIdentity(actor_id="lead_reviewer_bob", is_human=True)

        mapping = repo.create_mapping(
            mapping_data={
                "incident_id": seed_incident,
                "framework_code": "OECD_AI_PRINCIPLES",
                "reference_set_id": ref_model.id,
                "mapping_level": "FRAMEWORK",
                "applicability": "DIRECTLY_IMPLICATED",
                "rationale": "Audit chain verification.",
            },
            actor=human_actor,
        )
        repo.add_evidence_link(mapping.id, None, "evd_gov_test_001", "EMPIRICAL_STUDY", actor=human_actor)
        repo.transition_mapping_status(mapping.id, MappingStatus.CANDIDATE, human_actor, "Ready for sign-off")
        repo.transition_mapping_status(mapping.id, MappingStatus.APPROVED, human_actor, "Final sign-off")

        # 1. Un-tampered chain passes
        is_valid, errors = repo.verify_governance_audit_chain("incident_framework_mappings", mapping.id)
        assert is_valid is True, f"Chain verification failed: {errors}"
        assert len(errors) == 0

        # 2. Tampering with event_hash is detected
        logs = (
            sqlite_session.query(GovernanceAuditLogModel)
            .filter_by(entity_id=mapping.id)
            .order_by(GovernanceAuditLogModel.created_at.asc())
            .all()
        )
        assert len(logs) >= 3

        target_log = logs[1]
        original_hash = target_log.event_hash
        target_log.event_hash = "0" * 64
        sqlite_session.commit()

        is_valid_tampered, errors_tampered = repo.verify_governance_audit_chain("incident_framework_mappings", mapping.id)
        assert is_valid_tampered is False
        assert any("Tampered event payload" in err for err in errors_tampered)

        # Restore hash
        target_log.event_hash = original_hash
        sqlite_session.commit()

        # 3. Tampering with previous_event_hash is detected
        target_log.previous_event_hash = "1" * 64
        sqlite_session.commit()

        is_valid_broken, errors_broken = repo.verify_governance_audit_chain("incident_framework_mappings", mapping.id)
        assert is_valid_broken is False
        assert any("Chain break" in err for err in errors_broken)

    def test_list_mappings_filtering_superseded(
        self,
        sqlite_session: Session,
        repo_root: Path,
        seed_incident: str,
    ) -> None:
        """Verify list_mappings_for_incident filter on include_superseded flag."""
        repo = GovernanceRepository(sqlite_session)
        ref_schema = load_reference_set(repo_root / "frameworks" / "oecd" / "oecd-principles-2024.yaml")
        ref_model = repo.create_reference_set(ref_schema, content_hash="hash_123")
        actor = GovernanceActorIdentity(actor_id="analyst_jane", is_human=True)

        original = repo.create_mapping(
            mapping_data={
                "incident_id": seed_incident,
                "framework_code": "OECD_AI_PRINCIPLES",
                "reference_set_id": ref_model.id,
                "mapping_level": "FRAMEWORK",
                "applicability": "BROADER_GOVERNANCE_LESSON",
                "rationale": "Initial",
            },
            actor=actor,
        )
        superseding = repo.supersede_mapping(
            original.id,
            {"applicability": "DIRECTLY_IMPLICATED", "rationale": "Updated"},
            actor,
            "Updated",
        )

        active_mappings = repo.list_mappings_for_incident(seed_incident, include_superseded=False)
        assert len(active_mappings) == 1
        assert active_mappings[0].id == superseding.id

        all_mappings = repo.list_mappings_for_incident(seed_incident, include_superseded=True)
        assert len(all_mappings) == 2

    def test_list_eu_screens_filtering_superseded(
        self,
        sqlite_session: Session,
        repo_root: Path,
        seed_incident: str,
    ) -> None:
        """Verify list_eu_screens_for_incident filter on include_superseded flag."""
        repo = GovernanceRepository(sqlite_session)
        ref_schema = load_reference_set(repo_root / "frameworks" / "eu-ai-act" / "eu-ai-act-2024-1689.yaml")
        ref_model = repo.create_reference_set(ref_schema, content_hash="hash_eu_123")
        actor = GovernanceActorIdentity(actor_id="legal_analyst", is_human=True)

        screen1 = repo.create_eu_screen(
            screen_data={"incident_id": seed_incident, "reference_set_id": ref_model.id},
            actor=actor,
        )
        screen2 = repo.supersede_eu_screen(screen1.id, {"confidence": "HIGH"}, actor, "Upgraded")

        active_screens = repo.list_eu_screens_for_incident(seed_incident, include_superseded=False)
        assert len(active_screens) == 1
        assert active_screens[0].id == screen2.id

        all_screens = repo.list_eu_screens_for_incident(seed_incident, include_superseded=True)
        assert len(all_screens) == 2

    def test_transition_mapping_status_invalid_mapping_id(
        self,
        sqlite_session: Session,
    ) -> None:
        """Attempting to transition a non-existent mapping raises ValueError."""
        repo = GovernanceRepository(sqlite_session)
        actor = GovernanceActorIdentity(actor_id="analyst", is_human=True)
        with pytest.raises(ValueError, match="Mapping not found"):
            repo.transition_mapping_status("non_existent_id", MappingStatus.APPROVED, actor)

    def test_supersede_mapping_invalid_mapping_id(
        self,
        sqlite_session: Session,
    ) -> None:
        """Attempting to supersede a non-existent mapping raises ValueError."""
        repo = GovernanceRepository(sqlite_session)
        actor = GovernanceActorIdentity(actor_id="analyst", is_human=True)
        with pytest.raises(ValueError, match="Original mapping not found"):
            repo.supersede_mapping("non_existent_id", {}, actor, "Rationale")

    def test_supersede_eu_screen_invalid_screen_id(
        self,
        sqlite_session: Session,
    ) -> None:
        """Attempting to supersede a non-existent EU screen raises ValueError."""
        repo = GovernanceRepository(sqlite_session)
        actor = GovernanceActorIdentity(actor_id="analyst", is_human=True)
        with pytest.raises(ValueError, match="Original EU screen not found"):
            repo.supersede_eu_screen("non_existent_id", {}, actor, "Rationale")

    def test_add_evidence_link_with_actor_generates_audit_event(
        self,
        sqlite_session: Session,
        repo_root: Path,
        seed_incident: str,
    ) -> None:
        """Verify add_evidence_link records an ADD_EVIDENCE_LINK audit event when actor is provided."""
        repo = GovernanceRepository(sqlite_session)
        ref_schema = load_reference_set(repo_root / "frameworks" / "oecd" / "oecd-principles-2024.yaml")
        ref_model = repo.create_reference_set(ref_schema, content_hash="hash_123")
        actor = GovernanceActorIdentity(actor_id="analyst_jane", is_human=True)

        mapping = repo.create_mapping(
            mapping_data={
                "incident_id": seed_incident,
                "framework_code": "OECD_AI_PRINCIPLES",
                "reference_set_id": ref_model.id,
                "mapping_level": "FRAMEWORK",
                "applicability": "DIRECTLY_IMPLICATED",
                "rationale": "Link audit check",
            },
            actor=actor,
        )

        repo.add_evidence_link(
            mapping_id=mapping.id,
            screen_id=None,
            evidence_id="evd_gov_test_001",
            claim_type="EMPIRICAL_STUDY",
            relevance_note="Supporting technical evidence",
            actor=actor,
        )

        logs = (
            sqlite_session.query(GovernanceAuditLogModel)
            .filter_by(entity_id=mapping.id, transition_type=GovernanceAuditEventType.ADD_EVIDENCE_LINK.value)
            .all()
        )
        assert len(logs) == 1
        assert logs[0].actor_id == "analyst_jane"

    def test_audit_chain_verification_empty_history(self, sqlite_session: Session) -> None:
        """Verifying an entity with zero audit events returns (True, [])."""
        repo = GovernanceRepository(sqlite_session)
        is_valid, errors = repo.verify_governance_audit_chain("incident_framework_mappings", "empty_entity_id")
        assert is_valid is True
        assert len(errors) == 0

    def test_audit_chain_genesis_event_has_null_previous_hash(
        self,
        sqlite_session: Session,
        repo_root: Path,
        seed_incident: str,
    ) -> None:
        """Verify that the initial genesis audit event has previous_event_hash is None."""
        repo = GovernanceRepository(sqlite_session)
        ref_schema = load_reference_set(repo_root / "frameworks" / "oecd" / "oecd-principles-2024.yaml")
        ref_model = repo.create_reference_set(ref_schema, content_hash="hash_123")
        actor = GovernanceActorIdentity(actor_id="analyst_jane", is_human=True)

        mapping = repo.create_mapping(
            mapping_data={
                "incident_id": seed_incident,
                "framework_code": "OECD_AI_PRINCIPLES",
                "reference_set_id": ref_model.id,
                "mapping_level": "FRAMEWORK",
                "applicability": "DIRECTLY_IMPLICATED",
                "rationale": "Genesis check",
            },
            actor=actor,
        )

        genesis_log = (
            sqlite_session.query(GovernanceAuditLogModel)
            .filter_by(entity_id=mapping.id)
            .first()
        )
        assert genesis_log is not None
        assert genesis_log.previous_event_hash is None
        assert len(genesis_log.event_hash) == 64

    def test_audit_chain_multi_event_sequential_linking(
        self,
        sqlite_session: Session,
        repo_root: Path,
        seed_incident: str,
    ) -> None:
        """Verify sequential cryptographic linking across multiple successive audit events."""
        repo = GovernanceRepository(sqlite_session)
        ref_schema = load_reference_set(repo_root / "frameworks" / "oecd" / "oecd-principles-2024.yaml")
        ref_model = repo.create_reference_set(ref_schema, content_hash="hash_123")
        actor = GovernanceActorIdentity(actor_id="analyst_jane", is_human=True)

        mapping = repo.create_mapping(
            mapping_data={
                "incident_id": seed_incident,
                "framework_code": "OECD_AI_PRINCIPLES",
                "reference_set_id": ref_model.id,
                "mapping_level": "FRAMEWORK",
                "applicability": "DIRECTLY_IMPLICATED",
                "rationale": "Sequential check",
            },
            actor=actor,
        )
        repo.transition_mapping_status(mapping.id, MappingStatus.CANDIDATE, actor)
        repo.transition_mapping_status(mapping.id, MappingStatus.PENDING_REVIEW, actor)

        logs = (
            sqlite_session.query(GovernanceAuditLogModel)
            .filter_by(entity_id=mapping.id)
            .order_by(GovernanceAuditLogModel.created_at.asc(), GovernanceAuditLogModel.id.asc())
            .all()
        )
        assert len(logs) == 3
        assert logs[0].previous_event_hash is None
        assert logs[1].previous_event_hash == logs[0].event_hash
        assert logs[2].previous_event_hash == logs[1].event_hash

    def test_eu_screen_statutory_disclaimer_immutability(
        self,
        sqlite_session: Session,
        repo_root: Path,
        seed_incident: str,
    ) -> None:
        """Verify EU legal relevance screen always attaches mandatory statutory disclaimer."""
        repo = GovernanceRepository(sqlite_session)
        ref_schema = load_reference_set(repo_root / "frameworks" / "eu-ai-act" / "eu-ai-act-2024-1689.yaml")
        ref_model = repo.create_reference_set(ref_schema, content_hash="hash_eu_123")
        actor = GovernanceActorIdentity(actor_id="legal_analyst", is_human=True)

        screen = repo.create_eu_screen(
            screen_data={
                "incident_id": seed_incident,
                "reference_set_id": ref_model.id,
                "disclaimer_text": "Attempted override of disclaimer",  # Must be ignored/enforced
            },
            actor=actor,
        )
        assert screen.disclaimer_text == EU_AI_ACT_STATUTORY_DISCLAIMER

    def test_get_control_nonexistent_returns_none(self, sqlite_session: Session) -> None:
        """Querying non-existent control returns None."""
        repo = GovernanceRepository(sqlite_session)
        assert repo.get_control("non_existent_control_id") is None

    def test_get_reference_set_nonexistent_returns_none(self, sqlite_session: Session) -> None:
        """Querying non-existent reference set returns None."""
        repo = GovernanceRepository(sqlite_session)
        assert repo.get_reference_set("non_existent_set_id") is None
        assert repo.get_reference_set_by_code_and_version("NON_EXISTENT", "1.0") is None
