"""Unit tests for EditorialDossierExporter and EditorialExportManifest."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ai_incident_monitor.db.base import Base
from ai_incident_monitor.db.models.evidence import ClaimEvidenceLinkModel, EvidenceRecordModel
from ai_incident_monitor.db.models.governance import GovernanceAuditLogModel
from ai_incident_monitor.db.models.claim import ClaimRecordModel
from ai_incident_monitor.db.models.incident import IncidentModel
from ai_incident_monitor.db.models.source import SourceReferenceModel
from ai_incident_monitor.domain.common import ConstitutionalViolationError
from ai_incident_monitor.editorial.enums import (
    EditorialArtifactPurpose,
    EditorialAuditEventType,
    EditorialDossierStatus,
    EditorialExportFormat,
    EditorialPresentationProfile,
)
from ai_incident_monitor.editorial.models import (
    EDITORIAL_ATTESTATION_STATEMENT,
    EditorialReviewerAttestationSchema,
)
from ai_incident_monitor.editorial.renderers.exporter import EditorialDossierExporter
from ai_incident_monitor.editorial.validator import EditorialValidator
from ai_incident_monitor.repositories.editorial_repo import EditorialRepository
from tests.unit.editorial.test_editorial_models import create_sample_dossier


@pytest.fixture
def sqlite_session() -> Session:
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
        publisher="Tech Incident Log",
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

    ev1 = EvidenceRecordModel(
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
    sqlite_session.add(ev1)

    ev2 = EvidenceRecordModel(
        id="ev_102",
        source_id="src_001",
        short_summary="Audit log",
        evidence_type="TECHNICAL_POSTMORTEM",
        directness="PRIMARY_DIRECT",
        specificity="HIGHLY_SPECIFIC",
        corroboration_status="FULLY_CORROBORATED",
        ingested_at=now,
        payload_hash="3" * 64,
    )
    sqlite_session.add(ev2)

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


class TestEditorialExporterAndManifest:
    def test_export_markdown_happy_path(
        self, sqlite_session: Session, seed_incident: str
    ) -> None:
        repo = EditorialRepository(sqlite_session)
        dossier = create_sample_dossier()
        repo.save_dossier(dossier, actor_id="analyst_1", is_human=True)

        exporter = EditorialDossierExporter(repo)
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = exporter.export(
                dossier_id=dossier.id,
                export_format=EditorialExportFormat.MARKDOWN,
                profile=EditorialPresentationProfile.DEEP_DIVE_DOSSIER,
                purpose=EditorialArtifactPurpose.INTERNAL_REVIEW_COPY,
                output_dir=tmp_dir,
            )

            assert result.dry_run is False
            assert len(result.written_files) == 2  # .md + .manifest.json
            md_path = next(p for p in result.written_files if p.endswith(".md"))
            man_path = next(p for p in result.written_files if p.endswith(".manifest.json"))

            assert os.path.exists(md_path)
            assert os.path.exists(man_path)

            # Check markdown file hash match
            with open(md_path, "rb") as f:
                content = f.read()
                file_hash = hashlib.sha256(content).hexdigest()
            assert result.manifest.artifact_file_hash == file_hash

            # Check manifest contents
            with open(man_path, "r", encoding="utf-8") as f:
                man_data = json.load(f)
            assert man_data["dossier_id"] == dossier.id
            assert man_data["artifact_file_hash"] == file_hash
            assert man_data["artifact_purpose"] == "INTERNAL_REVIEW_COPY"

    def test_export_json_happy_path(
        self, sqlite_session: Session, seed_incident: str
    ) -> None:
        repo = EditorialRepository(sqlite_session)
        dossier = create_sample_dossier()
        repo.save_dossier(dossier, actor_id="analyst_1", is_human=True)

        exporter = EditorialDossierExporter(repo)
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = exporter.export(
                dossier_id=dossier.id,
                export_format=EditorialExportFormat.JSON,
                profile=EditorialPresentationProfile.DEEP_DIVE_DOSSIER,
                purpose=EditorialArtifactPurpose.INTERNAL_REVIEW_COPY,
                output_dir=tmp_dir,
            )

            assert len(result.written_files) == 2  # .json + .manifest.json
            json_path = next(p for p in result.written_files if p.endswith(".json") and not p.endswith(".manifest.json"))
            with open(json_path, "r", encoding="utf-8") as f:
                pkg = json.load(f)
            assert pkg["dossier"]["id"] == dossier.id
            assert "canonical_payload_hash" in pkg

    def test_export_format_all(
        self, sqlite_session: Session, seed_incident: str
    ) -> None:
        repo = EditorialRepository(sqlite_session)
        dossier = create_sample_dossier()
        repo.save_dossier(dossier, actor_id="analyst_1", is_human=True)

        exporter = EditorialDossierExporter(repo)
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = exporter.export(
                dossier_id=dossier.id,
                export_format=EditorialExportFormat.ALL,
                output_dir=tmp_dir,
            )
            assert len(result.written_files) == 3  # .md, .json, .manifest.json
            exts = {os.path.splitext(f)[1] for f in result.written_files}
            assert ".md" in exts
            assert ".json" in exts

    def test_dry_run_creates_zero_files_and_zero_db_records(
        self, sqlite_session: Session, seed_incident: str
    ) -> None:
        repo = EditorialRepository(sqlite_session)
        dossier = create_sample_dossier()
        repo.save_dossier(dossier, actor_id="analyst_1", is_human=True)

        exporter = EditorialDossierExporter(repo)
        with tempfile.TemporaryDirectory() as tmp_dir:
            target_sub_dir = os.path.join(tmp_dir, "non_existent_folder")

            result = exporter.export(
                dossier_id=dossier.id,
                export_format=EditorialExportFormat.ALL,
                output_dir=target_sub_dir,
                dry_run=True,
            )

            assert result.dry_run is True
            # Folder should NOT have been created
            assert not os.path.exists(target_sub_dir)
            # No files written
            for f in result.written_files:
                assert not os.path.exists(f)

    def test_collision_blocks_without_overwrite_flag(
        self, sqlite_session: Session, seed_incident: str
    ) -> None:
        repo = EditorialRepository(sqlite_session)
        dossier = create_sample_dossier()
        repo.save_dossier(dossier, actor_id="analyst_1", is_human=True)

        exporter = EditorialDossierExporter(repo)
        with tempfile.TemporaryDirectory() as tmp_dir:
            # First export succeeds
            exporter.export(
                dossier_id=dossier.id,
                output_dir=tmp_dir,
                overwrite=False,
            )

            # Second export without overwrite must raise FileExistsError
            with pytest.raises(FileExistsError) as exc:
                exporter.export(
                    dossier_id=dossier.id,
                    output_dir=tmp_dir,
                    overwrite=False,
                )
            assert "already exists" in str(exc.value)

    def test_overwrite_flag_permits_replacement(
        self, sqlite_session: Session, seed_incident: str
    ) -> None:
        repo = EditorialRepository(sqlite_session)
        dossier = create_sample_dossier()
        repo.save_dossier(dossier, actor_id="analyst_1", is_human=True)

        exporter = EditorialDossierExporter(repo)
        with tempfile.TemporaryDirectory() as tmp_dir:
            res1 = exporter.export(dossier_id=dossier.id, output_dir=tmp_dir)
            assert len(res1.written_files) > 0

            # Export with overwrite=True succeeds
            res2 = exporter.export(dossier_id=dossier.id, output_dir=tmp_dir, overwrite=True)
            assert res2.export_id != res1.export_id

    def test_approved_copy_fails_closed_if_unapproved_status(
        self, sqlite_session: Session, seed_incident: str
    ) -> None:
        repo = EditorialRepository(sqlite_session)
        dossier = create_sample_dossier()  # status is ASSEMBLED
        repo.save_dossier(dossier, actor_id="analyst_1", is_human=True)

        exporter = EditorialDossierExporter(repo)
        with tempfile.TemporaryDirectory() as tmp_dir:
            with pytest.raises(ValueError) as exc:
                exporter.export(
                    dossier_id=dossier.id,
                    purpose=EditorialArtifactPurpose.APPROVED_EDITORIAL_COPY,
                    output_dir=tmp_dir,
                )
            assert "expected 'APPROVED_INFORMATIONAL'" in str(exc.value)

    def test_approved_copy_happy_path(
        self, sqlite_session: Session, seed_incident: str
    ) -> None:
        repo = EditorialRepository(sqlite_session)
        dossier = create_sample_dossier()
        repo.save_dossier(dossier, actor_id="analyst_1", is_human=True)
        repo.submit_for_review(dossier.id, actor_id="analyst_1", is_human=True)

        attestation = EditorialReviewerAttestationSchema(
            reviewer_id="human_editor_1",
            reviewer_name="Jane Doe",
            reviewer_role="Senior Editor",
            is_human=True,
            statement_confirmed=True,
            attestation_statement=EDITORIAL_ATTESTATION_STATEMENT,
            content_hash=dossier.compute_content_hash(),
            dossier_id=dossier.id,
            dossier_version=dossier.version,
        )
        validator = EditorialValidator()
        repo.approve_dossier(dossier.id, attestation, validator.validate_dossier(dossier))

        exporter = EditorialDossierExporter(repo)
        with tempfile.TemporaryDirectory() as tmp_dir:
            res = exporter.export(
                dossier_id=dossier.id,
                purpose=EditorialArtifactPurpose.APPROVED_EDITORIAL_COPY,
                output_dir=tmp_dir,
                actor_id="human_editor_1",
                is_human=True,
            )
            assert res.purpose == EditorialArtifactPurpose.APPROVED_EDITORIAL_COPY
            assert any(f.endswith(".md") for f in res.written_files)

    def test_approved_copy_fails_closed_if_source_drifts(
        self, sqlite_session: Session, seed_incident: str
    ) -> None:
        repo = EditorialRepository(sqlite_session)
        dossier = create_sample_dossier()
        repo.save_dossier(dossier, actor_id="analyst_1", is_human=True)
        repo.submit_for_review(dossier.id, actor_id="analyst_1", is_human=True)

        attestation = EditorialReviewerAttestationSchema(
            reviewer_id="human_editor_1",
            reviewer_role="Senior Editor",
            is_human=True,
            statement_confirmed=True,
            content_hash=dossier.compute_content_hash(),
            dossier_id=dossier.id,
            dossier_version=dossier.version,
        )
        validator = EditorialValidator()
        repo.approve_dossier(dossier.id, attestation, validator.validate_dossier(dossier))

        # Cause drift behind the scenes
        inc = sqlite_session.get(IncidentModel, seed_incident)
        assert inc is not None
        inc.summary = "Altered summary inducing drift."
        sqlite_session.commit()

        exporter = EditorialDossierExporter(repo)
        with tempfile.TemporaryDirectory() as tmp_dir:
            with pytest.raises(ValueError) as exc:
                exporter.export(
                    dossier_id=dossier.id,
                    purpose=EditorialArtifactPurpose.APPROVED_EDITORIAL_COPY,
                    output_dir=tmp_dir,
                    actor_id="human_editor_1",
                    is_human=True,
                )
            assert "source records have drifted" in str(exc.value)

    def test_approved_copy_requires_human_actor(
        self, sqlite_session: Session, seed_incident: str
    ) -> None:
        repo = EditorialRepository(sqlite_session)
        dossier = create_sample_dossier()
        repo.save_dossier(dossier, actor_id="analyst_1", is_human=True)
        repo.submit_for_review(dossier.id, actor_id="analyst_1", is_human=True)

        attestation = EditorialReviewerAttestationSchema(
            reviewer_id="human_editor_1",
            reviewer_role="Senior Editor",
            is_human=True,
            statement_confirmed=True,
            content_hash=dossier.compute_content_hash(),
            dossier_id=dossier.id,
            dossier_version=dossier.version,
        )
        validator = EditorialValidator()
        repo.approve_dossier(dossier.id, attestation, validator.validate_dossier(dossier))

        exporter = EditorialDossierExporter(repo)
        with tempfile.TemporaryDirectory() as tmp_dir:
            with pytest.raises(ConstitutionalViolationError) as exc:
                exporter.export(
                    dossier_id=dossier.id,
                    purpose=EditorialArtifactPurpose.APPROVED_EDITORIAL_COPY,
                    output_dir=tmp_dir,
                    actor_id="bot_agent",
                    is_human=False,
                )
            assert "human actor (Rule 14)" in str(exc.value)

    def test_path_traversal_directory_rejected(
        self, sqlite_session: Session, seed_incident: str
    ) -> None:
        repo = EditorialRepository(sqlite_session)
        dossier = create_sample_dossier()
        repo.save_dossier(dossier, actor_id="analyst_1", is_human=True)

        exporter = EditorialDossierExporter(repo)
        with pytest.raises(ValueError) as exc:
            exporter.export(
                dossier_id=dossier.id,
                output_dir="/tmp/path\0with_null",
            )
        assert "null bytes" in str(exc.value)

    def test_symlink_destination_rejected(
        self, sqlite_session: Session, seed_incident: str
    ) -> None:
        repo = EditorialRepository(sqlite_session)
        dossier = create_sample_dossier()
        repo.save_dossier(dossier, actor_id="analyst_1", is_human=True)

        exporter = EditorialDossierExporter(repo)
        with tempfile.TemporaryDirectory() as tmp_dir:
            real_target = os.path.join(tmp_dir, "real_target")
            os.makedirs(real_target)
            symlink_target = os.path.join(tmp_dir, "symlink_dir")
            os.symlink(real_target, symlink_target)

            with pytest.raises(ValueError) as exc:
                exporter.export(
                    dossier_id=dossier.id,
                    output_dir=symlink_target,
                )
            assert "symlink" in str(exc.value)

    def test_audit_event_recorded_on_successful_export(
        self, sqlite_session: Session, seed_incident: str
    ) -> None:
        repo = EditorialRepository(sqlite_session)
        dossier = create_sample_dossier()
        repo.save_dossier(dossier, actor_id="analyst_1", is_human=True)

        exporter = EditorialDossierExporter(repo)
        with tempfile.TemporaryDirectory() as tmp_dir:
            res = exporter.export(
                dossier_id=dossier.id,
                output_dir=tmp_dir,
                actor_id="operator_jane",
                is_human=True,
            )

            is_valid, anomalies = repo.verify_audit_chain(dossier.id)
            assert is_valid is True
            assert len(anomalies) == 0

            # Find audit event for export
            from sqlalchemy import select
            stmt = (
                select(GovernanceAuditLogModel)
                .where(
                    GovernanceAuditLogModel.entity_id == dossier.id,
                    GovernanceAuditLogModel.transition_type == EditorialAuditEventType.EXPORT_DOSSIER.value,
                )
            )
            event = sqlite_session.execute(stmt).scalar_one_or_none()
            assert event is not None
            assert event.details_json["export_id"] == res.export_id
