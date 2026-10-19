"""Integration tests for manual file import workflow, raw preservation, dedup, and audit."""

from __future__ import annotations

from pathlib import Path
from typing import Generator

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from ai_incident_monitor.db.base import Base
from ai_incident_monitor.db.models import (
    AuditLogModel,
    ClaimRecordModel,
    DedupCandidateModel,
    IncidentModel,
    RawImportRecordModel,
)
from ai_incident_monitor.db.session import get_engine
from ai_incident_monitor.importers import run_manual_import_workflow

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "imports"


@pytest.fixture
def session() -> Generator[Session, None, None]:
    """Provide an isolated in-memory database session."""
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    sess = session_factory()
    yield sess
    sess.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_csv_manual_import_end_to_end(session: Session) -> None:
    """Verify end-to-end CSV manual import workflow preserves raw records and logs audit trail."""
    csv_path = FIXTURES_DIR / "oecd_sample.csv"
    summary = run_manual_import_workflow(
        session=session,
        file_path=csv_path,
        source_format="CSV",
        actor_id="USER-ANALYST-01",
        demonstration_notice="DEMONSTRATION DATA — NOT A REAL INCIDENT",
    )

    # 1. Summary checks
    assert summary.total_rows == 3
    assert summary.imported_count == 3
    assert summary.duplicate_count == 0
    assert summary.error_count == 0
    assert len(summary.content_hash) == 64
    assert summary.staged_path is not None
    assert Path(summary.staged_path).exists()

    # 2. Database persistence verification
    incidents = session.execute(select(IncidentModel)).scalars().all()
    assert len(incidents) == 3

    claims = session.execute(select(ClaimRecordModel)).scalars().all()
    assert len(claims) == 3
    for claim in claims:
        # Constitutional Rule 3 / Gate 4: OECD claims imported as UNVERIFIED_ALLEGATION
        assert claim.epistemic_status == "UNVERIFIED_ALLEGATION"
        assert claim.review_status == "DRAFT_UNREVIEWED"

    raw_records = session.execute(select(RawImportRecordModel)).scalars().all()
    assert len(raw_records) == 3
    for r in raw_records:
        assert r.status == "IMPORTED"
        assert r.content_hash == summary.content_hash
        assert r.incident_id is not None
        assert "Incident Title" in r.raw_payload

    # 3. Audit trail verification (AUD-003, Rule 16)
    audit_logs = session.execute(select(AuditLogModel)).scalars().all()
    assert len(audit_logs) == 1
    log = audit_logs[0]
    assert log.entity_type == "IMPORT_BATCH"
    assert log.action == "IMPORT"
    assert log.actor_id == "USER-ANALYST-01"


def test_reimport_triggers_deduplication(session: Session) -> None:
    """Verify that re-importing the same file triggers Tier 1 auto-linking without duplicates."""
    csv_path = FIXTURES_DIR / "oecd_sample.csv"

    # First import
    run_manual_import_workflow(
        session=session,
        file_path=csv_path,
        source_format="CSV",
        actor_id="USER-ANALYST-01",
    )
    assert len(session.execute(select(IncidentModel)).scalars().all()) == 3

    # Re-import identical file
    second_summary = run_manual_import_workflow(
        session=session,
        file_path=csv_path,
        source_format="CSV",
        actor_id="USER-ANALYST-02",
    )

    # All 3 records should be recognized as duplicates (Tier 1 by ID)
    assert second_summary.imported_count == 0
    assert second_summary.duplicate_count == 3
    # Total incidents in DB must still be 3 (no accidental duplication)
    assert len(session.execute(select(IncidentModel)).scalars().all()) == 3


def test_json_manual_import_end_to_end(session: Session) -> None:
    """Verify end-to-end JSON manual import workflow."""
    json_path = FIXTURES_DIR / "oecd_sample.json"
    summary = run_manual_import_workflow(
        session=session,
        file_path=json_path,
        source_format="JSON",
        actor_id="USER-ANALYST-01",
    )

    assert summary.total_rows == 2
    assert summary.imported_count == 2
    assert summary.duplicate_count == 0

    incidents = session.execute(select(IncidentModel)).scalars().all()
    assert len(incidents) == 2
