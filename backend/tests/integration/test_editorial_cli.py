"""Integration tests for the editorial review CLI interface."""

from __future__ import annotations

from datetime import date, datetime, timezone
import json
from pathlib import Path
import tempfile
from typing import Generator
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ai_incident_monitor.db.base import Base
from ai_incident_monitor.db.models.claim import ClaimRecordModel
from ai_incident_monitor.db.models.evidence import (
    ClaimEvidenceLinkModel,
    EvidenceRecordModel,
)
from ai_incident_monitor.db.models.incident import IncidentModel
from ai_incident_monitor.db.models.source import SourceReferenceModel
from ai_incident_monitor.editorial.cli import main


@pytest.fixture
def temp_db() -> Generator[str, None, None]:
    """Temporary SQLite database URL with initialized schema."""
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = f.name
        db_url = f"sqlite:///{db_path}"
        engine = create_engine(db_url)
        Base.metadata.create_all(engine)

        # Seed candidate incident
        session = Session(engine)
        now = datetime.now(timezone.utc)
        src = SourceReferenceModel(
            id="src_cli_01",
            title="CLI Test Source",
            publisher="Tech Monitor",
            url="https://example.com/cli-test",
            source_type="TECHNICAL_POSTMORTEM",
            access_status="OPEN_PUBLIC",
            authority="PRIMARY",
            reliability="HIGH",
            independence="INDEPENDENT_ORIGINAL",
            content_hash="1" * 64,
            retrieval_date=now,
        )
        session.add(src)

        ev = EvidenceRecordModel(
            id="ev_cli_01",
            source_id="src_cli_01",
            short_summary="Observational telemetry evidence",
            evidence_type="TECHNICAL_POSTMORTEM",
            directness="PRIMARY_DIRECT",
            specificity="HIGHLY_SPECIFIC",
            corroboration_status="FULLY_CORROBORATED",
            ingested_at=now,
            payload_hash="2" * 64,
        )
        session.add(ev)

        inc = IncidentModel(
            id="inc_cli_100",
            title="Automated Routing Incident",
            summary="Autonomous dispatcher misrouted emergency units.",
            status="UNDER_INVESTIGATION",
            incident_exact_date=date(2026, 3, 1),
        )
        session.add(inc)

        clm = ClaimRecordModel(
            id="clm_cli_01",
            incident_id="inc_cli_100",
            claim_text="Dispatcher dropped priority queue flag.",
            claim_type="TECHNICAL_FACT",
            epistemic_status="VERIFIED",
            confidence="HIGH",
            materiality="HIGH",
        )
        session.add(clm)

        link = ClaimEvidenceLinkModel(
            claim_id="clm_cli_01",
            evidence_id="ev_cli_01",
            link_type="SUPPORTING",
        )
        session.add(link)
        session.commit()
        session.close()
        engine.dispose()

        yield db_url


class TestEditorialCLI:
    def test_select_candidates_cli(self, temp_db: str, capsys: pytest.CaptureFixture[str]) -> None:
        exit_code = main(["--db-url", temp_db, "select-candidates", "--json"])
        assert exit_code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert len(data) >= 1
        assert data[0]["incident_id"] == "inc_cli_100"
        assert data[0]["is_eligible"] is True

    def test_assemble_dossier_dry_run_and_persist(
        self, temp_db: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # 1. Dry run
        exit_code = main(
            [
                "--db-url",
                temp_db,
                "assemble-dossier",
                "--title",
                "Dry Run Dossier",
                "--dossier-id",
                "dos_cli_dry",
                "--dry-run",
                "--json",
            ]
        )
        assert exit_code == 0
        captured = capsys.readouterr()
        dry_data = json.loads(captured.out)
        assert dry_data["dry_run"] is True

        # Inspect should fail because dry run did not persist
        exit_inspect = main(
            ["--db-url", temp_db, "inspect-dossier", "--dossier-id", "dos_cli_dry"]
        )
        assert exit_inspect != 0

        # 2. Persisted assemble
        exit_persist = main(
            [
                "--db-url",
                temp_db,
                "assemble-dossier",
                "--title",
                "Persisted Dossier",
                "--dossier-id",
                "dos_cli_persisted",
                "--actor-id",
                "analyst_joe",
                "--is-human",
                "--json",
            ]
        )
        assert exit_persist == 0
        captured = capsys.readouterr()
        persist_data = json.loads(captured.out)
        assert persist_data["dossier_id"] == "dos_cli_persisted"
        assert persist_data["status"] == "ASSEMBLED"

    def test_inspect_and_validate_dossier_cli(
        self, temp_db: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        main(
            [
                "--db-url",
                temp_db,
                "assemble-dossier",
                "--title",
                "Valid Dossier Title",
                "--dossier-id",
                "dos_cli_val",
                "--actor-id",
                "analyst_joe",
                "--is-human",
            ]
        )
        capsys.readouterr()

        # Inspect
        exit_inspect = main(
            ["--db-url", temp_db, "inspect-dossier", "--dossier-id", "dos_cli_val", "--json"]
        )
        assert exit_inspect == 0
        captured = capsys.readouterr()
        dossier_data = json.loads(captured.out)
        assert dossier_data["id"] == "dos_cli_val"

        # Validate
        exit_val = main(
            ["--db-url", temp_db, "validate-dossier", "--dossier-id", "dos_cli_val", "--json"]
        )
        assert exit_val == 0
        captured = capsys.readouterr()
        val_data = json.loads(captured.out)
        assert val_data["is_valid"] is True
        assert val_data["blocking_count"] == 0

    def test_full_review_lifecycle_cli(
        self, temp_db: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # 1. Assemble
        main(
            [
                "--db-url",
                temp_db,
                "assemble-dossier",
                "--title",
                "Lifecycle Dossier",
                "--dossier-id",
                "dos_cli_life",
                "--actor-id",
                "analyst_joe",
                "--is-human",
            ]
        )
        capsys.readouterr()

        # 2. Submit for review
        exit_submit = main(
            [
                "--db-url",
                temp_db,
                "submit-for-review",
                "--dossier-id",
                "dos_cli_life",
                "--actor-id",
                "analyst_joe",
                "--json",
            ]
        )
        assert exit_submit == 0
        capsys.readouterr()

        # 3. Approve dossier
        exit_approve = main(
            [
                "--db-url",
                temp_db,
                "approve-dossier",
                "--dossier-id",
                "dos_cli_life",
                "--reviewer-id",
                "editor_lead",
                "--reviewer-role",
                "Lead Editor",
                "--is-human",
                "--confirm-statement",
                "--json",
            ]
        )
        assert exit_approve == 0
        captured = capsys.readouterr()
        approved_data = json.loads(captured.out)
        assert approved_data["status"] == "APPROVED_INFORMATIONAL"
        assert approved_data["reviewed_by"] == "editor_lead"

        # 4. Verify audit chain
        exit_audit = main(
            ["--db-url", temp_db, "verify-audit", "--dossier-id", "dos_cli_life", "--json"]
        )
        assert exit_audit == 0
        captured = capsys.readouterr()
        audit_data = json.loads(captured.out)
        assert audit_data["is_valid"] is True
        assert audit_data["anomaly_count"] == 0

    def test_reject_and_supersede_cli(
        self, temp_db: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        main(
            [
                "--db-url",
                temp_db,
                "assemble-dossier",
                "--title",
                "Dossier For Rejection",
                "--dossier-id",
                "dos_cli_rej",
                "--actor-id",
                "analyst_joe",
                "--is-human",
            ]
        )
        main(["--db-url", temp_db, "submit-for-review", "--dossier-id", "dos_cli_rej", "--actor-id", "analyst_joe"])
        capsys.readouterr()

        # Reject
        exit_reject = main(
            [
                "--db-url",
                temp_db,
                "reject-dossier",
                "--dossier-id",
                "dos_cli_rej",
                "--reviewer-id",
                "editor_jane",
                "--is-human",
                "--reason",
                "Requires additional secondary evidence regarding priority queues.",
                "--json",
            ]
        )
        assert exit_reject == 0
        captured = capsys.readouterr()
        rej_data = json.loads(captured.out)
        assert rej_data["status"] == "REJECTED"
