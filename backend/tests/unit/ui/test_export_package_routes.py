"""Unit tests for Artifact Previews and Export Package Management routes (Phase 8C).

Governing Charter: Project Constitution (Rules 1, 3, 4, 10, 11, 12, 14, 15, 16, 17),
PRD §4.7, Phase 8C Implementation Plan.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from ai_incident_monitor.db.base import Base
from ai_incident_monitor.db.models.claim import ClaimRecordModel
from ai_incident_monitor.db.models.editorial import EditorialDossierModel
from ai_incident_monitor.db.models.evidence import ClaimEvidenceLinkModel, EvidenceRecordModel
from ai_incident_monitor.db.models.governance import GovernanceAuditLogModel
from ai_incident_monitor.db.models.incident import IncidentModel
from ai_incident_monitor.db.models.source import SourceReferenceModel
from ai_incident_monitor.editorial.enums import (
    EditorialAuditEventType,
    EditorialDossierStatus,
)
from ai_incident_monitor.editorial.renderers.exporter import DEFAULT_EXPORT_DIR
from ai_incident_monitor.repositories.editorial_repo import EditorialRepository
from ai_incident_monitor.ui.app import create_app
from ai_incident_monitor.ui.auth import (
    LocalCredentialManager,
    ServerSessionManager,
    SESSION_COOKIE_NAME,
)
from ai_incident_monitor.ui.reviewer_auth import (
    ReviewerKeystore,
    ReviewerRateLimiter,
)


@pytest.fixture
def sqlite_test_engine(tmp_path: Path):
    """Create an isolated SQLite database and build the complete relational schema."""
    db_file = tmp_path / "test_packages_ui.db"
    engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def package_test_setup(sqlite_test_engine, tmp_path: Path):
    """Seed test incidents, sources, and enrolled reviewers into isolated environment."""
    cred_file = tmp_path / ".operator_credential"
    cred_mgr = LocalCredentialManager(storage_path=cred_file)
    cred_mgr.generate_or_load_credential()
    sess_mgr = ServerSessionManager()

    # Enrolled reviewer
    keystore_path = tmp_path / ".reviewers.json"
    keystore = ReviewerKeystore(storage_path=keystore_path)
    reviewer_rec, reviewer_key = keystore.enroll_reviewer(
        reviewer_id="ebe",
        reviewer_name="Ebe Rolston",
        reviewer_role="Lead Editor",
    )

    # Seed data
    with Session(sqlite_test_engine) as session:
        src = SourceReferenceModel(
            id="src_01",
            title="Trading Algorithm Anomaly Investigation",
            publisher="Market Integrity Authority",
            url="https://example.com/algo-anomaly",
            source_type="INVESTIGATIVE_REPORT",
            retrieval_date=datetime.now(timezone.utc),
            access_status="PUBLIC",
            authority="HIGH",
            reliability="HIGH",
            independence="HIGH",
            content_hash="a" * 64,
        )
        session.add(src)

        inc1 = IncidentModel(
            id="INC-2026-0001",
            title="Automated High-Frequency Liquidity Cascade",
            summary="Recursive self-reinforcing cancel bursts caused order book exhaustion.",
            status="VERIFIED",
            incident_exact_date=datetime(2026, 3, 15, tzinfo=timezone.utc),
        )
        session.add(inc1)

        ev1 = EvidenceRecordModel(
            id="ev_01",
            source_id="src_01",
            short_summary="Telemetry logs confirm 400,000 cancellations per second.",
            evidence_type="DIRECT_OBSERVATION",
            directness="DIRECT",
            specificity="SPECIFIC",
            corroboration_status="CORROBORATED",
            ingested_at=datetime.now(timezone.utc),
            payload_hash="c" * 64,
        )
        session.add(ev1)

        claim1 = ClaimRecordModel(
            id="claim_01",
            incident_id="INC-2026-0001",
            claim_text="Cancellation burst depleted matching engine liquidity.",
            claim_type="CONFIRMED_FACT",
            epistemic_status="CONFIRMED",
            confidence="HIGH",
            materiality="HIGH",
            is_causal_claim=True,
        )
        session.add(claim1)

        link1 = ClaimEvidenceLinkModel(
            claim_id="claim_01",
            evidence_id="ev_01",
            link_type="SUPPORTING",
        )
        session.add(link1)
        session.commit()

    rev_limiter = ReviewerRateLimiter()
    app = create_app(
        db_engine=sqlite_test_engine,
        repo_root=tmp_path,
        credential_manager=cred_mgr,
        session_manager=sess_mgr,
        reviewer_keystore=keystore,
        reviewer_rate_limiter=rev_limiter,
    )
    client = TestClient(app)

    return {
        "client": client,
        "sess_mgr": sess_mgr,
        "keystore": keystore,
        "reviewer_rec": reviewer_rec,
        "reviewer_key": reviewer_key,
        "engine": sqlite_test_engine,
        "tmp_path": tmp_path,
    }


def _create_dossier(
    setup_data,
    session,
    status: EditorialDossierStatus = EditorialDossierStatus.DRAFT,
) -> str:
    """Helper to create and optionally advance a dossier using the web interface."""
    client = setup_data["client"]
    client.cookies.set(SESSION_COOKIE_NAME, session.session_id)

    post_data = {
        "title": "Weekly Algorithmic Risk Digest",
        "scope_type": "CUSTOM",
        "incident_ids": ["INC-2026-0001"],
        "methodology_notes": "Deterministic verification against verified evidence.",
        "csrf_token": session.csrf_token,
    }
    res_post = client.post("/dossiers", data=post_data, follow_redirects=False)
    assert res_post.status_code == 303
    dossier_id = res_post.headers["location"].split("/")[-1]

    if status == EditorialDossierStatus.APPROVED_INFORMATIONAL:
        engine = setup_data["engine"]
        with Session(engine) as s:
            row = s.execute(select(EditorialDossierModel).where(EditorialDossierModel.id == dossier_id)).scalar_one()
            row.status = EditorialDossierStatus.APPROVED_INFORMATIONAL.value
            row.reviewed_by = "ebe"
            row.reviewed_at = datetime.now(timezone.utc)
            s.commit()

    return dossier_id


class TestExportPackageRoutes:
    """Comprehensive test suite covering Phase 8C previews and export package routes."""

    def test_unauthenticated_export_package_routes_redirect_to_login(self, package_test_setup) -> None:
        """Unauthenticated requests to preview, packages, or export routes redirect to /login."""
        client = package_test_setup["client"]

        assert client.get("/dossiers/dos_123/preview", follow_redirects=False).status_code == 303
        assert client.get("/packages", follow_redirects=False).status_code == 303
        assert client.get("/packages/exp_123", follow_redirects=False).status_code == 303
        assert client.get("/packages/exp_123/download/file.md", follow_redirects=False).status_code == 303
        assert client.post("/dossiers/dos_123/export", data={}, follow_redirects=False).status_code == 303

    def test_draft_preview_renders_with_neutral_snapshot_banner_and_profiles(self, package_test_setup) -> None:
        """Draft dossier preview displays neutral snapshot banner, profiles, and safe content."""
        client = package_test_setup["client"]
        sess_mgr = package_test_setup["sess_mgr"]
        session = sess_mgr.create_session()
        client.cookies.set(SESSION_COOKIE_NAME, session.session_id)

        dossier_id = _create_dossier(package_test_setup, session=session, status=EditorialDossierStatus.DRAFT)

        # GET markdown preview
        res = client.get(f"/dossiers/{dossier_id}/preview")
        assert res.status_code == 200
        assert "Dossier Artifact Preview (Version 1)" in res.text
        assert "External publication remains the operator's responsibility outside the system" in res.text
        assert "Weekly Algorithmic Risk Digest" in res.text
        assert "INC-2026-0001" in res.text
        assert "DEEP_DIVE_DOSSIER" in res.text
        assert "EXECUTIVE_BRIEF" in res.text
        assert "RAPID_ALERT" in res.text

        # Ensure content is in code/pre block and properly escaped
        assert "<pre" in res.text
        assert "<code" in res.text

    def test_draft_preview_json_format(self, package_test_setup) -> None:
        """Preview can render in JSON format containing canonical payload."""
        client = package_test_setup["client"]
        sess_mgr = package_test_setup["sess_mgr"]
        session = sess_mgr.create_session()
        client.cookies.set(SESSION_COOKIE_NAME, session.session_id)

        dossier_id = _create_dossier(package_test_setup, session=session, status=EditorialDossierStatus.DRAFT)

        res = client.get(f"/dossiers/{dossier_id}/preview?format=json")
        assert res.status_code == 200
        assert "EXPORTED_SNAPSHOT" in res.text
        assert "&#34;package_version&#34;" in res.text or '"package_version"' in res.text

    def test_approved_dossier_preview(self, package_test_setup) -> None:
        """Historical approved dossier preview renders neutral snapshot banner cleanly."""
        client = package_test_setup["client"]
        sess_mgr = package_test_setup["sess_mgr"]
        session = sess_mgr.create_session()
        client.cookies.set(SESSION_COOKIE_NAME, session.session_id)

        dossier_id = _create_dossier(package_test_setup, session=session, status=EditorialDossierStatus.APPROVED_INFORMATIONAL)

        res = client.get(f"/dossiers/{dossier_id}/preview")
        assert res.status_code == 200
        assert "Dossier Artifact Preview (Version 1)" in res.text
        assert "Weekly Algorithmic Risk Digest" in res.text

    def test_preview_get_routes_are_strictly_non_mutating(self, package_test_setup) -> None:
        """Viewing previews must never mutate business records or add audit logs."""
        client = package_test_setup["client"]
        sess_mgr = package_test_setup["sess_mgr"]
        session = sess_mgr.create_session()
        client.cookies.set(SESSION_COOKIE_NAME, session.session_id)

        dossier_id = _create_dossier(package_test_setup, session=session, status=EditorialDossierStatus.DRAFT)
        engine = package_test_setup["engine"]

        with Session(engine) as s:
            audit_count_before = len(s.execute(select(GovernanceAuditLogModel)).scalars().all())

        client.get(f"/dossiers/{dossier_id}/preview")
        client.get(f"/dossiers/{dossier_id}/preview?format=json")
        client.get(f"/dossiers/{dossier_id}/preview?profile=RAPID_ALERT")

        with Session(engine) as s:
            audit_count_after = len(s.execute(select(GovernanceAuditLogModel)).scalars().all())

        assert audit_count_after == audit_count_before

    def test_export_package_creation_csrf_protection(self, package_test_setup) -> None:
        """Export creation rejects missing or invalid CSRF tokens with 403 Forbidden."""
        client = package_test_setup["client"]
        sess_mgr = package_test_setup["sess_mgr"]
        session = sess_mgr.create_session()
        client.cookies.set(SESSION_COOKIE_NAME, session.session_id)

        dossier_id = _create_dossier(package_test_setup, session=session, status=EditorialDossierStatus.DRAFT)

        # Missing CSRF
        res = client.post(f"/dossiers/{dossier_id}/export", data={})
        assert res.status_code == 403

        # Invalid CSRF
        res = client.post(f"/dossiers/{dossier_id}/export", data={"csrf_token": "bad_token"})
        assert res.status_code == 403

    def test_export_package_creation_blocks_approved_copy_on_draft(self, package_test_setup) -> None:
        """Attempting to export APPROVED_EDITORIAL_COPY on a draft dossier fails with 400 Bad Request."""
        client = package_test_setup["client"]
        sess_mgr = package_test_setup["sess_mgr"]
        session = sess_mgr.create_session()
        client.cookies.set(SESSION_COOKIE_NAME, session.session_id)

        dossier_id = _create_dossier(package_test_setup, session=session, status=EditorialDossierStatus.DRAFT)

        res = client.post(
            f"/dossiers/{dossier_id}/export",
            data={
                "profile": "DEEP_DIVE_DOSSIER",
                "format": "MARKDOWN",
                "purpose": "APPROVED_EDITORIAL_COPY",
                "csrf_token": session.csrf_token,
            },
        )
        assert res.status_code == 400
        assert "Cannot export APPROVED_EDITORIAL_COPY" in res.text

    def test_export_package_creation_exported_snapshot_for_draft_dossier(self, package_test_setup) -> None:
        """Assembled/draft dossier exports cleanly as EXPORTED_SNAPSHOT without approval gates."""
        client = package_test_setup["client"]
        sess_mgr = package_test_setup["sess_mgr"]
        session = sess_mgr.create_session()
        client.cookies.set(SESSION_COOKIE_NAME, session.session_id)

        dossier_id = _create_dossier(package_test_setup, session=session, status=EditorialDossierStatus.DRAFT)
        tmp_path = package_test_setup["tmp_path"]

        res = client.post(
            f"/dossiers/{dossier_id}/export",
            data={
                "profile": "DEEP_DIVE_DOSSIER",
                "format": "MARKDOWN",
                "purpose": "EXPORTED_SNAPSHOT",
                "csrf_token": session.csrf_token,
            },
            follow_redirects=False,
        )
        assert res.status_code == 303
        redirect_url = res.headers["location"]
        assert redirect_url.startswith("/packages/exp_")
        export_id = redirect_url.split("/")[-1]

        export_dir = tmp_path / DEFAULT_EXPORT_DIR
        manifest_files = list(export_dir.glob("*.manifest.json"))
        matched = False
        for mf in manifest_files:
            with open(mf, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)
                if manifest_data["export_id"] == export_id:
                    matched = True
                    assert manifest_data["dossier_id"] == dossier_id
                    assert manifest_data["artifact_purpose"] == "EXPORTED_SNAPSHOT"
                    assert manifest_data["output_filename"] == f"snapshot_{dossier_id}_v1_deep_dive_dossier.md"
        assert matched

        # Download artifact and assert neutral banner
        res_dl = client.get(f"/packages/{export_id}/download/snapshot_{dossier_id}_v1_deep_dive_dossier.md")
        assert res_dl.status_code == 200
        assert "AI GUARDIANS RESEARCH DOSSIER — EXPORTED SNAPSHOT" in res_dl.text

    def test_export_package_creation_internal_review_copy_success(self, package_test_setup) -> None:
        """Draft dossier can be exported as INTERNAL_REVIEW_COPY, writing files and audit record."""
        client = package_test_setup["client"]
        sess_mgr = package_test_setup["sess_mgr"]
        session = sess_mgr.create_session()
        client.cookies.set(SESSION_COOKIE_NAME, session.session_id)

        dossier_id = _create_dossier(package_test_setup, session=session, status=EditorialDossierStatus.DRAFT)
        tmp_path = package_test_setup["tmp_path"]

        res = client.post(
            f"/dossiers/{dossier_id}/export",
            data={
                "profile": "DEEP_DIVE_DOSSIER",
                "format": "MARKDOWN",
                "purpose": "INTERNAL_REVIEW_COPY",
                "csrf_token": session.csrf_token,
            },
            follow_redirects=False,
        )
        assert res.status_code == 303
        redirect_url = res.headers["location"]
        assert redirect_url.startswith("/packages/exp_")
        export_id = redirect_url.split("/")[-1]

        # Verify export directory files
        export_dir = tmp_path / DEFAULT_EXPORT_DIR
        assert export_dir.exists()
        manifest_files = list(export_dir.glob("*.manifest.json"))
        assert len(manifest_files) >= 1

        matched = False
        for mf in manifest_files:
            with open(mf, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)
                if manifest_data["export_id"] == export_id:
                    matched = True
                    assert manifest_data["dossier_id"] == dossier_id
                    assert manifest_data["artifact_purpose"] == "INTERNAL_REVIEW_COPY"
        assert matched, f"Export manifest for '{export_id}' not found."

        # Verify audit event in DB
        engine = package_test_setup["engine"]
        with Session(engine) as s:
            audit = s.execute(
                select(GovernanceAuditLogModel).where(
                    GovernanceAuditLogModel.transition_type == EditorialAuditEventType.EXPORT_DOSSIER.value
                )
            ).scalar_one_or_none()
            assert audit is not None
            assert audit.entity_id == dossier_id

    def test_export_package_creation_approved_copy_success(self, package_test_setup) -> None:
        """Approved dossier exports as APPROVED_EDITORIAL_COPY with full cryptographic manifest."""
        client = package_test_setup["client"]
        sess_mgr = package_test_setup["sess_mgr"]
        session = sess_mgr.create_session()
        client.cookies.set(SESSION_COOKIE_NAME, session.session_id)

        dossier_id = _create_dossier(package_test_setup, session=session, status=EditorialDossierStatus.APPROVED_INFORMATIONAL)
        tmp_path = package_test_setup["tmp_path"]

        res = client.post(
            f"/dossiers/{dossier_id}/export",
            data={
                "profile": "RAPID_ALERT",
                "format": "MARKDOWN",
                "purpose": "APPROVED_EDITORIAL_COPY",
                "csrf_token": session.csrf_token,
            },
            follow_redirects=False,
        )
        assert res.status_code == 303
        export_id = res.headers["location"].split("/")[-1]

        # Verify manifest contents
        export_dir = tmp_path / DEFAULT_EXPORT_DIR
        manifest_files = list(export_dir.glob("*.manifest.json"))
        assert len(manifest_files) >= 1

        matched = False
        for mf in manifest_files:
            with open(mf, "r", encoding="utf-8") as f:
                m = json.load(f)
                if m.get("export_id") == export_id:
                    matched = True
                    assert m["artifact_purpose"] == "APPROVED_EDITORIAL_COPY"
                    assert m["presentation_profile"] == "RAPID_ALERT"
                    assert "canonical_dossier_content_hash" in m
                    assert "canonical_payload_hash" in m
                    assert "artifact_file_hash" in m
                    assert len(m["source_version_hashes"]) == 1
        assert matched, f"Export manifest for '{export_id}' not found."

    def test_export_package_creation_source_drift_guard(self, package_test_setup) -> None:
        """Approved export is blocked if underlying source records drift after approval."""
        client = package_test_setup["client"]
        sess_mgr = package_test_setup["sess_mgr"]
        session = sess_mgr.create_session()
        client.cookies.set(SESSION_COOKIE_NAME, session.session_id)

        dossier_id = _create_dossier(package_test_setup, session=session, status=EditorialDossierStatus.APPROVED_INFORMATIONAL)
        engine = package_test_setup["engine"]

        # Mutate the underlying incident record to simulate external drift
        with Session(engine) as s:
            inc = s.execute(select(IncidentModel).where(IncidentModel.id == "INC-2026-0001")).scalar_one()
            inc.summary = "Drifted incident summary content."
            s.commit()

        res = client.post(
            f"/dossiers/{dossier_id}/export",
            data={
                "profile": "DEEP_DIVE_DOSSIER",
                "format": "MARKDOWN",
                "purpose": "APPROVED_EDITORIAL_COPY",
                "csrf_token": session.csrf_token,
            },
            follow_redirects=False,
        )
        assert res.status_code == 400
        assert "underlying source records have drifted" in res.text

    def test_export_repeat_generation_and_overwrite_handling(self, package_test_setup) -> None:
        """Duplicate export without overwrite flag returns 409 Conflict; succeeds with overwrite."""
        client = package_test_setup["client"]
        sess_mgr = package_test_setup["sess_mgr"]
        session = sess_mgr.create_session()
        client.cookies.set(SESSION_COOKIE_NAME, session.session_id)

        dossier_id = _create_dossier(package_test_setup, session=session, status=EditorialDossierStatus.DRAFT)

        # 1. First export
        res1 = client.post(
            f"/dossiers/{dossier_id}/export",
            data={
                "profile": "DEEP_DIVE_DOSSIER",
                "format": "MARKDOWN",
                "purpose": "INTERNAL_REVIEW_COPY",
                "csrf_token": session.csrf_token,
            },
            follow_redirects=False,
        )
        assert res1.status_code == 303

        # 2. Second export with overwrite=False -> 409 Conflict
        res2 = client.post(
            f"/dossiers/{dossier_id}/export",
            data={
                "profile": "DEEP_DIVE_DOSSIER",
                "format": "MARKDOWN",
                "purpose": "INTERNAL_REVIEW_COPY",
                "overwrite": "false",
                "csrf_token": session.csrf_token,
            },
        )
        assert res2.status_code == 409
        assert "Package file collision" in res2.text

        # 3. Third export with overwrite=True -> 303 Success
        res3 = client.post(
            f"/dossiers/{dossier_id}/export",
            data={
                "profile": "DEEP_DIVE_DOSSIER",
                "format": "MARKDOWN",
                "purpose": "INTERNAL_REVIEW_COPY",
                "overwrite": "true",
                "csrf_token": session.csrf_token,
            },
            follow_redirects=False,
        )
        assert res3.status_code == 303

    def test_packages_list_route(self, package_test_setup) -> None:
        """Packages list route renders all packages and supports filtering."""
        client = package_test_setup["client"]
        sess_mgr = package_test_setup["sess_mgr"]
        session = sess_mgr.create_session()
        client.cookies.set(SESSION_COOKIE_NAME, session.session_id)

        dossier_id = _create_dossier(package_test_setup, session=session, status=EditorialDossierStatus.DRAFT)

        # Generate an export
        client.post(
            f"/dossiers/{dossier_id}/export",
            data={
                "profile": "DEEP_DIVE_DOSSIER",
                "format": "MARKDOWN",
                "purpose": "INTERNAL_REVIEW_COPY",
                "csrf_token": session.csrf_token,
            },
        )

        res = client.get("/packages")
        assert res.status_code == 200
        assert "Export Packages" in res.text
        assert dossier_id in res.text
        assert "REVIEW COPY" in res.text

        # Filter by purpose match
        res_filtered = client.get("/packages?purpose=INTERNAL_REVIEW_COPY")
        assert res_filtered.status_code == 200
        assert dossier_id in res_filtered.text

        # Filter by nonexistent dossier
        res_empty = client.get("/packages?dossier_id=nonexistent_dos")
        assert res_empty.status_code == 200
        assert "No export packages" in res_empty.text

    def test_package_detail_inspection(self, package_test_setup) -> None:
        """Package detail displays complete manifest, provenance hashes, and file links."""
        client = package_test_setup["client"]
        sess_mgr = package_test_setup["sess_mgr"]
        session = sess_mgr.create_session()
        client.cookies.set(SESSION_COOKIE_NAME, session.session_id)

        dossier_id = _create_dossier(package_test_setup, session=session, status=EditorialDossierStatus.DRAFT)

        res_post = client.post(
            f"/dossiers/{dossier_id}/export",
            data={
                "profile": "DEEP_DIVE_DOSSIER",
                "format": "MARKDOWN",
                "purpose": "INTERNAL_REVIEW_COPY",
                "csrf_token": session.csrf_token,
            },
            follow_redirects=False,
        )
        export_id = res_post.headers["location"].split("/")[-1]

        # Valid detail view
        res = client.get(f"/packages/{export_id}")
        assert res.status_code == 200
        assert f"Export Package: {export_id}" in res.text
        assert "Cryptographic Provenance" in res.text
        assert "Canonical Dossier Content Hash" in res.text
        assert "Canonical Payload Hash" in res.text
        assert "Package Files &amp; Downloads" in res.text

        # Nonexistent export ID -> 404
        res_404 = client.get("/packages/exp_999999999999")
        assert res_404.status_code == 404

        # Malformed export ID -> 400
        res_400 = client.get("/packages/invalid-id!")
        assert res_400.status_code == 400

    def test_package_download_route_and_headers(self, package_test_setup) -> None:
        """File download returns correct mime-type, headers, and binary content."""
        client = package_test_setup["client"]
        sess_mgr = package_test_setup["sess_mgr"]
        session = sess_mgr.create_session()
        client.cookies.set(SESSION_COOKIE_NAME, session.session_id)

        dossier_id = _create_dossier(package_test_setup, session=session, status=EditorialDossierStatus.DRAFT)

        res_post = client.post(
            f"/dossiers/{dossier_id}/export",
            data={
                "profile": "DEEP_DIVE_DOSSIER",
                "format": "MARKDOWN",
                "purpose": "INTERNAL_REVIEW_COPY",
                "csrf_token": session.csrf_token,
            },
            follow_redirects=False,
        )
        export_id = res_post.headers["location"].split("/")[-1]

        # Inspect detail to get primary filename
        res_detail = client.get(f"/packages/{export_id}")
        assert res_detail.status_code == 200
        filename = f"review_{dossier_id}_v1_deep_dive_dossier.md"

        # Download markdown
        res_dl = client.get(f"/packages/{export_id}/download/{filename}")
        assert res_dl.status_code == 200
        assert "text/markdown" in res_dl.headers.get("content-type", "")
        assert f'attachment; filename="{filename}"' == res_dl.headers.get("content-disposition", "")
        assert "Weekly Algorithmic Risk Digest" in res_dl.text

        # Download manifest sidecar
        manifest_name = f"review_{dossier_id}_v1_deep_dive_dossier.manifest.json"
        res_mf = client.get(f"/packages/{export_id}/download/{manifest_name}")
        assert res_mf.status_code == 200
        assert "application/json" in res_mf.headers.get("content-type", "")
        assert json.loads(res_mf.text)["export_id"] == export_id

    def test_package_download_path_traversal_defenses(self, package_test_setup) -> None:
        """Download endpoint strictly rejects path traversal and unassociated files."""
        client = package_test_setup["client"]
        sess_mgr = package_test_setup["sess_mgr"]
        session = sess_mgr.create_session()
        client.cookies.set(SESSION_COOKIE_NAME, session.session_id)

        dossier_id = _create_dossier(package_test_setup, session=session, status=EditorialDossierStatus.DRAFT)

        res_post = client.post(
            f"/dossiers/{dossier_id}/export",
            data={
                "profile": "DEEP_DIVE_DOSSIER",
                "format": "MARKDOWN",
                "purpose": "INTERNAL_REVIEW_COPY",
                "csrf_token": session.csrf_token,
            },
            follow_redirects=False,
        )
        export_id = res_post.headers["location"].split("/")[-1]

        # Directory traversal pattern
        res_trav = client.get(f"/packages/{export_id}/download/..%2f..%2fetc%2fpasswd")
        assert res_trav.status_code in (400, 404)

        # Special characters or path separators
        res_slash = client.get(f"/packages/{export_id}/download/subdir/secret.txt")
        assert res_slash.status_code in (400, 404)

        # Unassociated existing file in directory
        tmp_path = package_test_setup["tmp_path"]
        export_dir = tmp_path / DEFAULT_EXPORT_DIR
        unassociated_file = export_dir / "unassociated_secret.txt"
        unassociated_file.write_text("secret")

        res_unassoc = client.get(f"/packages/{export_id}/download/unassociated_secret.txt")
        assert res_unassoc.status_code == 404

    def test_no_reviewer_secret_in_rendered_previews_or_packages(self, package_test_setup) -> None:
        """Reviewer secret keys are strictly excluded from preview HTML, manifests, and package downloads."""
        client = package_test_setup["client"]
        sess_mgr = package_test_setup["sess_mgr"]
        session = sess_mgr.create_session()
        client.cookies.set(SESSION_COOKIE_NAME, session.session_id)

        reviewer_key = package_test_setup["reviewer_key"]
        dossier_id = _create_dossier(package_test_setup, session=session, status=EditorialDossierStatus.APPROVED_INFORMATIONAL)

        # 1. Check preview HTML
        res_prev = client.get(f"/dossiers/{dossier_id}/preview")
        assert reviewer_key not in res_prev.text

        # 2. Check export package creation and manifest
        res_post = client.post(
            f"/dossiers/{dossier_id}/export",
            data={
                "profile": "DEEP_DIVE_DOSSIER",
                "format": "MARKDOWN",
                "purpose": "APPROVED_EDITORIAL_COPY",
                "csrf_token": session.csrf_token,
            },
            follow_redirects=False,
        )
        export_id = res_post.headers["location"].split("/")[-1]

        res_detail = client.get(f"/packages/{export_id}")
        assert reviewer_key not in res_detail.text

        filename = f"approved_{dossier_id}_v1_deep_dive_dossier.md"
        res_dl = client.get(f"/packages/{export_id}/download/{filename}")
        assert reviewer_key not in res_dl.text
