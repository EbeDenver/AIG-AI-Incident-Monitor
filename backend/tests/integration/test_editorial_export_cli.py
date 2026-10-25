"""Integration tests for the editorial review CLI export-dossier interface."""

from __future__ import annotations

from datetime import date, datetime, timezone
import json
import os
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
from ai_incident_monitor.db.models.governance import GovernanceAuditLogModel
from ai_incident_monitor.db.models.incident import IncidentModel
from ai_incident_monitor.db.models.source import SourceReferenceModel
from ai_incident_monitor.editorial.cli import main
from ai_incident_monitor.editorial.models import EDITORIAL_ATTESTATION_STATEMENT


@pytest.fixture
def temp_db_with_dossier(tmp_path: Path) -> tuple[str, str]:
    """Temporary SQLite database URL with seeded incident and assembled dossier."""
    db_file = tmp_path / "export_test.db"
    db_url = f"sqlite:///{db_file}"
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)

    session = Session(engine)
    now = datetime.now(timezone.utc)
    src = SourceReferenceModel(
        id="src_export_01",
        title="Export Test Source",
        publisher="Tech Monitor",
        url="https://example.com/export-test",
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
        id="ev_export_01",
        source_id="src_export_01",
        short_summary="Telemetry logs evidence",
        evidence_type="TECHNICAL_POSTMORTEM",
        directness="PRIMARY_DIRECT",
        specificity="HIGHLY_SPECIFIC",
        corroboration_status="FULLY_CORROBORATED",
        ingested_at=now,
        payload_hash="2" * 64,
    )
    session.add(ev)

    inc = IncidentModel(
        id="inc_export_100",
        title="Dispatch Failover Anomaly",
        summary="Emergency dispatch failover routed non-emergency calls to hotline.",
        status="UNDER_INVESTIGATION",
        incident_exact_date=date(2026, 3, 1),
    )
    session.add(inc)

    clm = ClaimRecordModel(
        id="clm_export_01",
        incident_id="inc_export_100",
        claim_text="Failover logic misclassified secondary queue priority.",
        claim_type="TECHNICAL_FACT",
        epistemic_status="VERIFIED",
        confidence="HIGH",
        materiality="HIGH",
    )
    session.add(clm)

    link = ClaimEvidenceLinkModel(
        claim_id="clm_export_01",
        evidence_id="ev_export_01",
        link_type="SUPPORTING",
    )
    session.add(link)
    session.commit()
    session.close()
    engine.dispose()

    # Assemble a dossier via CLI
    assemble_code = main(
        [
            "--db-url",
            db_url,
            "assemble-dossier",
            "--dossier-id",
            "dos_export_w10",
            "--title",
            "Weekly Dispatch Anomaly Report",
            "--incident-id",
            "inc_export_100",
            "--actor-id",
            "test_analyst",
            "--json",
        ]
    )
    assert assemble_code == 0

    return db_url, "dos_export_w10"


class TestEditorialExportCLI:
    def test_cli_export_dry_run(
        self, temp_db_with_dossier: tuple[str, str], capsys: pytest.CaptureFixture[str]
    ) -> None:
        db_url, dossier_id = temp_db_with_dossier

        with tempfile.TemporaryDirectory() as tmp_dir:
            exit_code = main(
                [
                    "--db-url",
                    db_url,
                    "export-dossier",
                    "--dossier-id",
                    dossier_id,
                    "--output-dir",
                    tmp_dir,
                    "--dry-run",
                    "--json",
                ]
            )
            assert exit_code == 0
            captured = capsys.readouterr()
            data = json.loads(captured.out)

            assert data["dry_run"] is True
            assert data["dossier_id"] == dossier_id
            # Zero files created in target directory
            assert len(os.listdir(tmp_dir)) == 0

            # Zero export audit records written to database
            engine = create_engine(db_url)
            with Session(engine) as session:
                export_events = (
                    session.query(GovernanceAuditLogModel)
                    .filter(GovernanceAuditLogModel.transition_type == "EXPORT_DOSSIER")
                    .all()
                )
                assert len(export_events) == 0

    def test_cli_export_format_all(
        self, temp_db_with_dossier: tuple[str, str], capsys: pytest.CaptureFixture[str]
    ) -> None:
        db_url, dossier_id = temp_db_with_dossier

        with tempfile.TemporaryDirectory() as tmp_dir:
            exit_code = main(
                [
                    "--db-url",
                    db_url,
                    "export-dossier",
                    "--dossier-id",
                    dossier_id,
                    "--format",
                    "ALL",
                    "--output-dir",
                    tmp_dir,
                    "--json",
                ]
            )
            assert exit_code == 0
            captured = capsys.readouterr()
            data = json.loads(captured.out)

            assert data["dry_run"] is False
            assert len(data["written_files"]) == 3

            # Verify files on disk
            files = os.listdir(tmp_dir)
            assert len(files) == 3
            assert any(f.endswith(".md") for f in files)
            assert any(f.endswith(".json") and not f.endswith(".manifest.json") for f in files)
            assert any(f.endswith(".manifest.json") for f in files)

            # Read and verify manifest
            manifest_file = [f for f in files if f.endswith(".manifest.json")][0]
            with open(Path(tmp_dir) / manifest_file, "r") as mf:
                manifest_data = json.load(mf)
                assert manifest_data["dossier_id"] == dossier_id
                assert manifest_data["artifact_file_hash"] is not None
                assert len(manifest_data["artifact_file_hash"]) == 64

    def test_cli_export_collision_without_overwrite(
        self, temp_db_with_dossier: tuple[str, str], capsys: pytest.CaptureFixture[str]
    ) -> None:
        db_url, dossier_id = temp_db_with_dossier

        with tempfile.TemporaryDirectory() as tmp_dir:
            # First export succeeds
            code1 = main(
                [
                    "--db-url",
                    db_url,
                    "export-dossier",
                    "--dossier-id",
                    dossier_id,
                    "--format",
                    "MARKDOWN",
                    "--output-dir",
                    tmp_dir,
                ]
            )
            assert code1 == 0

            # Second export without --overwrite fails with exit code 3
            code2 = main(
                [
                    "--db-url",
                    db_url,
                    "export-dossier",
                    "--dossier-id",
                    dossier_id,
                    "--format",
                    "MARKDOWN",
                    "--output-dir",
                    tmp_dir,
                ]
            )
            assert code2 == 3

    def test_cli_export_with_overwrite(
        self, temp_db_with_dossier: tuple[str, str], capsys: pytest.CaptureFixture[str]
    ) -> None:
        db_url, dossier_id = temp_db_with_dossier

        with tempfile.TemporaryDirectory() as tmp_dir:
            code1 = main(
                [
                    "--db-url",
                    db_url,
                    "export-dossier",
                    "--dossier-id",
                    dossier_id,
                    "--format",
                    "MARKDOWN",
                    "--output-dir",
                    tmp_dir,
                ]
            )
            assert code1 == 0

            # Re-export with --overwrite succeeds
            code2 = main(
                [
                    "--db-url",
                    db_url,
                    "export-dossier",
                    "--dossier-id",
                    dossier_id,
                    "--format",
                    "MARKDOWN",
                    "--output-dir",
                    tmp_dir,
                    "--overwrite",
                ]
            )
            assert code2 == 0

    def test_cli_export_approved_copy_unapproved_fails(
        self, temp_db_with_dossier: tuple[str, str], capsys: pytest.CaptureFixture[str]
    ) -> None:
        db_url, dossier_id = temp_db_with_dossier

        with tempfile.TemporaryDirectory() as tmp_dir:
            exit_code = main(
                [
                    "--db-url",
                    db_url,
                    "export-dossier",
                    "--dossier-id",
                    dossier_id,
                    "--purpose",
                    "APPROVED",
                    "--output-dir",
                    tmp_dir,
                ]
            )
            assert exit_code == 1
            captured = capsys.readouterr()
            assert "expected 'APPROVED_INFORMATIONAL'" in captured.err

    def test_cli_export_approved_copy_happy_path_and_audit_verify(
        self, temp_db_with_dossier: tuple[str, str], capsys: pytest.CaptureFixture[str]
    ) -> None:
        db_url, dossier_id = temp_db_with_dossier

        # 1. Submit for review
        capsys.readouterr()  # clear buffer
        submit_code = main(
            [
                "--db-url",
                db_url,
                "submit-for-review",
                "--dossier-id",
                dossier_id,
                "--actor-id",
                "test_analyst",
                "--json",
            ]
        )
        assert submit_code == 0
        capsys.readouterr()  # clear buffer

        # 2. Approve dossier
        approve_code = main(
            [
                "--db-url",
                db_url,
                "approve-dossier",
                "--dossier-id",
                dossier_id,
                "--reviewer-id",
                "editor_lead",
                "--reviewer-role",
                "Senior Editor",
                "--is-human",
                "--confirm-statement",
                "--json",
            ]
        )
        assert approve_code == 0
        capsys.readouterr()  # clear buffer

        # 3. Export approved copy
        with tempfile.TemporaryDirectory() as tmp_dir:
            export_code = main(
                [
                    "--db-url",
                    db_url,
                    "export-dossier",
                    "--dossier-id",
                    dossier_id,
                    "--purpose",
                    "APPROVED",
                    "--profile",
                    "DEEP_DIVE_DOSSIER",
                    "--format",
                    "MARKDOWN",
                    "--output-dir",
                    tmp_dir,
                    "--actor-id",
                    "editor_lead",
                    "--actor-role",
                    "Senior Editor",
                    "--json",
                ]
            )
            assert export_code == 0
            export_data = json.loads(capsys.readouterr().out)
            assert export_data["purpose"] == "APPROVED_EDITORIAL_COPY"

        # 4. Verify audit chain integrity
        audit_code = main(["--db-url", db_url, "verify-audit", "--dossier-id", dossier_id, "--json"])
        assert audit_code == 0
        audit_data = json.loads(capsys.readouterr().out)
        assert audit_data["is_valid"] is True
        assert audit_data["anomaly_count"] == 0

    def test_cli_export_human_enforcement_on_approved_copy(
        self, temp_db_with_dossier: tuple[str, str], capsys: pytest.CaptureFixture[str]
    ) -> None:
        db_url, dossier_id = temp_db_with_dossier

        # 1. Submit for review
        submit_code = main(
            [
                "--db-url",
                db_url,
                "submit-for-review",
                "--dossier-id",
                dossier_id,
                "--actor-id",
                "test_analyst",
                "--json",
            ]
        )
        assert submit_code == 0

        # 2. Approve dossier
        approve_code = main(
            [
                "--db-url",
                db_url,
                "approve-dossier",
                "--dossier-id",
                dossier_id,
                "--reviewer-id",
                "editor_lead",
                "--reviewer-role",
                "Senior Editor",
                "--is-human",
                "--confirm-statement",
                "--json",
            ]
        )
        assert approve_code == 0

        # 3. Non-human export must fail with exit code 4
        with tempfile.TemporaryDirectory() as tmp_dir:
            exit_code = main(
                [
                    "--db-url",
                    db_url,
                    "export-dossier",
                    "--dossier-id",
                    dossier_id,
                    "--purpose",
                    "APPROVED",
                    "--output-dir",
                    tmp_dir,
                    "--non-human",
                ]
            )
            assert exit_code == 4
            captured = capsys.readouterr()
            assert "human actor" in captured.err
