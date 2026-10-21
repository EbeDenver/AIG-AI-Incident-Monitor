"""Unit tests verifying governance relational ORM model definitions and constraints."""

from __future__ import annotations

from datetime import date, datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ai_incident_monitor.db.base import Base
from ai_incident_monitor.db.models.governance import (
    EULegalRelevanceScreenModel,
    FrameworkControlModel,
    FrameworkReferenceSetModel,
    GovernanceAuditLogModel,
    IncidentFrameworkMappingModel,
    MappingEvidenceLinkModel,
)
from ai_incident_monitor.db.models.incident import IncidentModel


@pytest.fixture
def sqlite_session() -> Session:
    """In-memory SQLite session with full schema initialized."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


class TestGovernanceModels:
    """Verifies SQLAlchemy ORM model table definitions, columns, and relationships."""

    def test_orm_tables_registered_in_metadata(self) -> None:
        """Confirm all 6 governance tables are registered with expected table names."""
        expected_tables = {
            "framework_reference_sets",
            "framework_controls",
            "incident_framework_mappings",
            "eu_legal_relevance_screens",
            "mapping_evidence_links",
            "governance_audit_logs",
        }
        registered_tables = set(Base.metadata.tables.keys())
        assert expected_tables.issubset(registered_tables)

    def test_framework_reference_set_model_instantiation(self, sqlite_session: Session) -> None:
        """Verify FrameworkReferenceSetModel instantiation and persistence."""
        now = datetime.now(timezone.utc)
        ref_set = FrameworkReferenceSetModel(
            id="refset_test_001",
            framework_code="OECD_AI_PRINCIPLES",
            framework_name="OECD AI Principles",
            version="2024.1",
            source_url="https://legalinstruments.oecd.org/en/instruments/OECD-LEGAL-0449",
            publisher="OECD",
            retrieved_at=now,
            verified_at=now,
            verified_by="Analyst",
            content_hash="a" * 64,
            status="ACTIVE",
            metadata_json={"test_key": "test_val"},
        )
        sqlite_session.add(ref_set)
        sqlite_session.commit()

        fetched = sqlite_session.get(FrameworkReferenceSetModel, "refset_test_001")
        assert fetched is not None
        assert fetched.framework_code == "OECD_AI_PRINCIPLES"
        assert fetched.metadata_json == {"test_key": "test_val"}

    def test_framework_control_model_relationships(self, sqlite_session: Session) -> None:
        """Verify FrameworkControlModel cascade and back-populates from reference set."""
        now = datetime.now(timezone.utc)
        ref_set = FrameworkReferenceSetModel(
            id="refset_rel_001",
            framework_code="NIST_AI_RMF",
            framework_name="NIST AI RMF",
            version="1.0.0",
            source_url="https://doi.org/10.6028/NIST.AI.100-1",
            publisher="NIST",
            retrieved_at=now,
            verified_at=now,
            verified_by="Analyst",
            content_hash="b" * 64,
            status="ACTIVE",
        )
        ctrl = FrameworkControlModel(
            id="ctrl_rel_001",
            reference_set_id="refset_rel_001",
            external_identifier="NIST-GOVERN",
            title="Govern",
            description="Govern Function",
            control_level="FUNCTION",
            source_locator="NIST AI 100-1 p. 20",
            status="ACTIVE",
        )
        ref_set.controls.append(ctrl)
        sqlite_session.add(ref_set)
        sqlite_session.commit()

        fetched_ctrl = sqlite_session.get(FrameworkControlModel, "ctrl_rel_001")
        assert fetched_ctrl is not None
        assert fetched_ctrl.reference_set.id == "refset_rel_001"
        assert len(fetched_ctrl.reference_set.controls) == 1

    def test_governance_audit_log_model(self, sqlite_session: Session) -> None:
        """Verify GovernanceAuditLogModel persistence and fields."""
        now = datetime.now(timezone.utc)
        log = GovernanceAuditLogModel(
            id="govevt_test_001",
            entity_type="incident_framework_mappings",
            entity_id="map_test_001",
            transition_type="CREATE_MAPPING",
            actor_id="analyst_01",
            is_human=True,
            actor_role="Senior Analyst",
            timestamp_utc=now,
            before_state_digest=None,
            after_state_digest="c" * 64,
            event_hash="d" * 64,
            previous_event_hash=None,
            details_json={"action": "init"},
            created_at=now,
        )
        sqlite_session.add(log)
        sqlite_session.commit()

        fetched_log = sqlite_session.get(GovernanceAuditLogModel, "govevt_test_001")
        assert fetched_log is not None
        assert fetched_log.is_human is True
        assert fetched_log.event_hash == "d" * 64
