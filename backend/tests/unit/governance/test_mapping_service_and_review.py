"""Unit tests verifying GovernanceMappingService orchestration, persistence, and HITL review workflows.

Covers:
- Reference set database initialization and caching
- Candidate mapping generation and persistence (including migration 004 rule_id & rule_version columns)
- Evidence link association
- Mandatory human review enforcement (Constitutional Rule 12 & 13)
- Rejection and revision supersession workflows
- Immutability preservation on approved mappings
- Cryptographic hash chaining in governance audit logs
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from ai_incident_monitor.db.base import Base
from ai_incident_monitor.db.models.governance import (
    FrameworkControlModel,
    FrameworkReferenceSetModel,
    GovernanceAuditLogModel,
    IncidentFrameworkMappingModel,
    MappingEvidenceLinkModel,
)
from ai_incident_monitor.db.models.evidence import EvidenceRecordModel
from ai_incident_monitor.db.models.incident import IncidentModel
from ai_incident_monitor.db.models.source import SourceReferenceModel
from ai_incident_monitor.domain.common import (
    ConstitutionalViolationError,
    ImmutabilityViolationError,
)
from ai_incident_monitor.governance.enums import (
    FrameworkCode,
    GovernanceAuditEventType,
    GovernanceConfidence,
    MappingStatus,
    OECDApplicability,
    SensitiveDomain,
)
from ai_incident_monitor.governance.mapping_service import GovernanceMappingService
from ai_incident_monitor.governance.models import (
    GovernanceActorIdentity,
    IncidentFactContext,
)
from ai_incident_monitor.repositories.governance_repo import GovernanceRepository


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
def seed_incident(sqlite_session: Session) -> dict[str, str]:
    """Helper seeding an incident and associated evidence record."""
    now = datetime.now(timezone.utc)
    incident = IncidentModel(
        id="inc_service_test_001",
        title="Biased Credit Scoring Incident",
        summary="Automated underwriting algorithm disproportionately rejected protected demographic applicants.",
        status="UNDER_INVESTIGATION",
        schema_version="1.0.0",
    )
    sqlite_session.add(incident)

    source = SourceReferenceModel(
        id="src_service_test_001",
        title="Credit Underwriting Audit",
        publisher="Consumer Protection Bureau",
        url="https://example.com/reports/credit-bias",
        canonical_url="https://example.com/reports/credit-bias",
        source_type="REGULATORY_FILING",
        retrieval_date=now,
        access_status="PUBLIC_WEB",
        authority="REGULATORY",
        reliability="GENERALLY_RELIABLE",
        independence="INDEPENDENT",
        content_hash="d" * 64,
    )
    sqlite_session.add(source)

    evidence = EvidenceRecordModel(
        id="evd_service_test_001",
        source_id="src_service_test_001",
        short_summary="Statistical disparity analysis demonstrating 40% higher rejection rate.",
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

    return {"incident_id": incident.id, "evidence_id": evidence.id}


@pytest.fixture
def system_actor() -> GovernanceActorIdentity:
    return GovernanceActorIdentity(
        actor_id="system-mapping-daemon",
        is_human=False,
        role="AUTOMATED_PIPELINE",
    )


@pytest.fixture
def human_actor() -> GovernanceActorIdentity:
    return GovernanceActorIdentity(
        actor_id="usr_analyst_007",
        is_human=True,
        role="GOVERNANCE_REVIEWER",
    )


@pytest.fixture
def mapping_service(sqlite_session: Session, repo_root: Path) -> GovernanceMappingService:
    service = GovernanceMappingService(
        session=sqlite_session,
        frameworks_dir=repo_root / "frameworks",
    )
    # Initialize OECD reference set
    service.initialize_framework_reference(
        framework_code=FrameworkCode.OECD_AI_PRINCIPLES,
        yaml_file=repo_root / "frameworks" / "oecd" / "oecd-principles-2024.yaml",
    )
    # Initialize NIST reference set
    service.initialize_framework_reference(
        framework_code=FrameworkCode.NIST_AI_RMF,
        yaml_file=repo_root / "frameworks" / "nist" / "nist-ai-rmf-1.0.yaml",
    )
    return service


class TestGovernanceMappingService:
    """Verifies service layer execution, relational persistence, and review state machine."""

    def test_initialize_reference_sets_persists_and_caches(
        self,
        sqlite_session: Session,
        mapping_service: GovernanceMappingService,
        repo_root: Path,
    ) -> None:
        """Confirms that reference sets and controls are seeded in database and idempotent."""
        refsets = sqlite_session.execute(select(FrameworkReferenceSetModel)).scalars().all()
        assert len(refsets) == 2
        codes = {r.framework_code for r in refsets}
        assert codes == {"OECD_AI_PRINCIPLES", "NIST_AI_RMF"}

        controls = sqlite_session.execute(select(FrameworkControlModel)).scalars().all()
        assert len(controls) > 10

        # Idempotence: re-initializing returns existing cached model
        re_init = mapping_service.initialize_framework_reference(
            framework_code=FrameworkCode.OECD_AI_PRINCIPLES,
            yaml_file=repo_root / "frameworks" / "oecd" / "oecd-principles-2024.yaml",
        )
        assert re_init.id == refsets[0].id or re_init.id == refsets[1].id

    def test_evaluate_and_persist_candidates(
        self,
        sqlite_session: Session,
        mapping_service: GovernanceMappingService,
        seed_incident: dict[str, str],
        system_actor: GovernanceActorIdentity,
    ) -> None:
        """Verify candidate generation, persistence with migration 004 columns, and evidence linking."""
        context = IncidentFactContext(
            incident_id=seed_incident["incident_id"],
            title="Biased Credit Scoring Incident",
            summary="Automated underwriting algorithm disproportionately rejected protected demographic applicants.",
            evidence_records=[
                {
                    "id": seed_incident["evidence_id"],
                    "directness": "PRIMARY_DIRECT",
                    "corroboration_status": "FULLY_CORROBORATED",
                    "specificity": "HIGHLY_SPECIFIC",
                }
            ],
            known_facts=["Statistical analysis confirmed demographic disparity."],
            unknowns=[],
            disputed_facts=[],
            sensitive_domains=[SensitiveDomain.CREDIT],
            fact_tags=["differential_impact", "bias_or_discrimination"],
        )

        candidates = mapping_service.evaluate_mappings(context)
        assert len(candidates) >= 1

        # Check candidate structure
        oecd_p12 = next(c for c in candidates if c.target_identifier == "OECD-P1.2")
        assert oecd_p12.rule_id == "RULE-OECD-1.2-01"
        assert oecd_p12.rule_version == "1.0.0"
        assert oecd_p12.mapping_status == MappingStatus.PENDING_REVIEW  # CREDIT sensitive domain

        # Persist candidates
        persisted = mapping_service.persist_candidates(candidates, actor=system_actor)
        assert len(persisted) == len(candidates)

        # Verify DB records
        for p in persisted:
            assert p.id is not None
            assert p.incident_id == seed_incident["incident_id"]
            # Verify Migration 004 columns
            assert p.rule_id.startswith("RULE-")
            assert p.rule_version == "1.0.0"
            assert p.mapping_status in {MappingStatus.PENDING_REVIEW, MappingStatus.CANDIDATE}

            # Verify normalized evidence links
            links = sqlite_session.execute(
                select(MappingEvidenceLinkModel).where(
                    MappingEvidenceLinkModel.incident_framework_mapping_id == p.id
                )
            ).scalars().all()
            assert len(links) == 1
            assert links[0].evidence_id == seed_incident["evidence_id"]

            # Verify initial audit event
            events = sqlite_session.execute(
                select(GovernanceAuditLogModel).where(
                    GovernanceAuditLogModel.entity_id == p.id,
                    GovernanceAuditLogModel.transition_type == GovernanceAuditEventType.CREATE_MAPPING,
                )
            ).scalars().all()
            assert len(events) == 1
            assert events[0].actor_id == system_actor.actor_id

    def test_approve_mapping_enforces_human_primacy(
        self,
        sqlite_session: Session,
        mapping_service: GovernanceMappingService,
        seed_incident: dict[str, str],
        system_actor: GovernanceActorIdentity,
        human_actor: GovernanceActorIdentity,
    ) -> None:
        """Constitutional Rules 12 & 13: automated algorithms/LLMs cannot approve governance mappings."""
        context = IncidentFactContext(
            incident_id=seed_incident["incident_id"],
            title="Biased Credit Scoring Incident",
            summary="Automated underwriting algorithm disproportionately rejected protected demographic applicants.",
            evidence_records=[
                {
                    "id": seed_incident["evidence_id"],
                    "directness": "PRIMARY_DIRECT",
                    "corroboration_status": "FULLY_CORROBORATED",
                    "specificity": "HIGHLY_SPECIFIC",
                }
            ],
            fact_tags=["differential_impact", "bias_or_discrimination"],
        )
        candidates = mapping_service.evaluate_mappings(context)
        persisted = mapping_service.persist_candidates(candidates, actor=system_actor)
        mapping_id = persisted[0].id

        # 1. Machine self-approval attempt MUST raise ConstitutionalViolationError
        with pytest.raises(ConstitutionalViolationError, match="Rule 12 Violation: Automated algorithms"):
            mapping_service.approve_mapping(
                mapping_id=mapping_id,
                actor=system_actor,
                rationale="Automated approval attempt.",
            )

        # Mapping status remains unapproved
        mapping_db = sqlite_session.get(IncidentFrameworkMappingModel, mapping_id)
        assert mapping_db.mapping_status != MappingStatus.APPROVED.value

        # 2. Human approval succeeds
        approved_model = mapping_service.approve_mapping(
            mapping_id=mapping_id,
            actor=human_actor,
            rationale="Verified independent statistical disparity evidence.",
        )
        assert approved_model.mapping_status == MappingStatus.APPROVED.value
        assert approved_model.reviewed_by == human_actor.actor_id
        assert approved_model.reviewed_at is not None

    def test_reject_mapping_workflow(
        self,
        sqlite_session: Session,
        mapping_service: GovernanceMappingService,
        seed_incident: dict[str, str],
        system_actor: GovernanceActorIdentity,
        human_actor: GovernanceActorIdentity,
    ) -> None:
        """Verifies rejection transition and audit recording."""
        context = IncidentFactContext(
            incident_id=seed_incident["incident_id"],
            title="Incident",
            evidence_records=[
                {
                    "id": seed_incident["evidence_id"],
                    "directness": "PRIMARY_DIRECT",
                    "corroboration_status": "FULLY_CORROBORATED",
                    "specificity": "HIGHLY_SPECIFIC",
                }
            ],
            fact_tags=["unclear_ownership"],
        )
        candidates = mapping_service.evaluate_mappings(context)
        persisted = mapping_service.persist_candidates(candidates, actor=system_actor)
        mapping_id = persisted[0].id

        rejected_model = mapping_service.reject_mapping(
            mapping_id=mapping_id,
            actor=human_actor,
            rationale="Evidence insufficient to confirm organizational ownership gap.",
        )
        assert rejected_model.mapping_status == MappingStatus.REJECTED.value

    def test_revise_mapping_creates_superseding_record(
        self,
        sqlite_session: Session,
        mapping_service: GovernanceMappingService,
        seed_incident: dict[str, str],
        system_actor: GovernanceActorIdentity,
        human_actor: GovernanceActorIdentity,
    ) -> None:
        """Verifies that revising an approved record creates a new record and supersedes the old one."""
        context = IncidentFactContext(
            incident_id=seed_incident["incident_id"],
            title="Incident",
            evidence_records=[
                {
                    "id": seed_incident["evidence_id"],
                    "directness": "PRIMARY_DIRECT",
                    "corroboration_status": "FULLY_CORROBORATED",
                    "specificity": "HIGHLY_SPECIFIC",
                }
            ],
            fact_tags=["differential_impact", "bias_or_discrimination"],
        )
        candidates = mapping_service.evaluate_mappings(context)
        persisted = mapping_service.persist_candidates(candidates, actor=system_actor)
        orig_id = persisted[0].id

        # Approve original mapping
        mapping_service.approve_mapping(
            mapping_id=orig_id,
            actor=human_actor,
            rationale="Initial human approval.",
        )

        # Revise mapping: create superseding record
        updated_model = mapping_service.revise_mapping(
            mapping_id=orig_id,
            updated_attributes={
                "applicability": OECDApplicability.BROADER_GOVERNANCE_LESSON.value,
                "rationale": "Updated rationale reflecting post-incident remediation.",
            },
            actor=human_actor,
            rationale="Refined applicability following secondary review.",
        )

        assert updated_model.id != orig_id
        assert updated_model.supersedes_mapping_id == orig_id
        assert updated_model.applicability == OECDApplicability.BROADER_GOVERNANCE_LESSON.value

        # Refresh original from DB
        orig_db = sqlite_session.get(IncidentFrameworkMappingModel, orig_id)
        assert orig_db.mapping_status == MappingStatus.SUPERSEDED.value
        assert orig_db.superseded_by_id == updated_model.id

    def test_immutability_violation_on_approved_record(
        self,
        sqlite_session: Session,
        mapping_service: GovernanceMappingService,
        seed_incident: dict[str, str],
        system_actor: GovernanceActorIdentity,
        human_actor: GovernanceActorIdentity,
    ) -> None:
        """Direct mutation of approved mapping raises ImmutabilityViolationError."""
        repo = GovernanceRepository(sqlite_session)
        context = IncidentFactContext(
            incident_id=seed_incident["incident_id"],
            title="Incident",
            evidence_records=[
                {
                    "id": seed_incident["evidence_id"],
                    "directness": "PRIMARY_DIRECT",
                    "corroboration_status": "FULLY_CORROBORATED",
                    "specificity": "HIGHLY_SPECIFIC",
                }
            ],
            fact_tags=["differential_impact", "bias_or_discrimination"],
        )
        candidates = mapping_service.evaluate_mappings(context)
        persisted = mapping_service.persist_candidates(candidates, actor=system_actor)
        orig_id = persisted[0].id

        mapping_service.approve_mapping(orig_id, human_actor, "Approved.")

        # Attempting to mutate status of approved mapping without supersession raises ImmutabilityViolationError
        with pytest.raises(ImmutabilityViolationError, match="Cannot mutate approved mapping"):
            repo.transition_mapping_status(
                mapping_id=orig_id,
                new_status=MappingStatus.CANDIDATE,
                actor=human_actor,
                rationale="Attempted rollback of approved record.",
            )

    def test_audit_trail_cryptographic_hash_chain(
        self,
        sqlite_session: Session,
        mapping_service: GovernanceMappingService,
        seed_incident: dict[str, str],
        system_actor: GovernanceActorIdentity,
        human_actor: GovernanceActorIdentity,
    ) -> None:
        """Verifies that all governance actions maintain an unbroken cryptographic SHA-256 hash chain."""
        repo = GovernanceRepository(sqlite_session)
        context = IncidentFactContext(
            incident_id=seed_incident["incident_id"],
            title="Incident",
            evidence_records=[
                {
                    "id": seed_incident["evidence_id"],
                    "directness": "PRIMARY_DIRECT",
                    "corroboration_status": "FULLY_CORROBORATED",
                    "specificity": "HIGHLY_SPECIFIC",
                }
            ],
            fact_tags=["differential_impact", "bias_or_discrimination"],
        )
        candidates = mapping_service.evaluate_mappings(context)
        persisted = mapping_service.persist_candidates(candidates, actor=system_actor)
        mapping_id = persisted[0].id

        # 1. Approve
        mapping_service.approve_mapping(mapping_id, human_actor, "Approved.")

        # 2. Supersede
        revised = mapping_service.revise_mapping(
            mapping_id,
            {"applicability": OECDApplicability.BROADER_GOVERNANCE_LESSON.value},
            human_actor,
            "Superseding.",
        )

        # 3. Approve revised
        mapping_service.approve_mapping(revised.id, human_actor, "Approved revised.")

        # Fetch audit events for original mapping entity lineage
        events_orig = (
            sqlite_session.query(GovernanceAuditLogModel)
            .filter_by(entity_id=mapping_id)
            .order_by(GovernanceAuditLogModel.created_at.asc(), GovernanceAuditLogModel.id.asc())
            .all()
        )
        assert len(events_orig) == 4
        assert events_orig[0].previous_event_hash is None
        for i in range(1, len(events_orig)):
            assert events_orig[i].previous_event_hash == events_orig[i - 1].event_hash

        # Cryptographic verification via repository
        is_valid, errors = repo.verify_governance_audit_chain("incident_framework_mappings", mapping_id)
        assert is_valid is True
        assert errors == []

        # Verify revised entity audit chain
        events_revised = (
            sqlite_session.query(GovernanceAuditLogModel)
            .filter_by(entity_id=revised.id)
            .order_by(GovernanceAuditLogModel.created_at.asc(), GovernanceAuditLogModel.id.asc())
            .all()
        )
        assert len(events_revised) == 2
        assert events_revised[0].previous_event_hash is None
        assert events_revised[1].previous_event_hash == events_revised[0].event_hash

        is_valid_rev, errors_rev = repo.verify_governance_audit_chain("incident_framework_mappings", revised.id)
        assert is_valid_rev is True
        assert errors_rev == []
