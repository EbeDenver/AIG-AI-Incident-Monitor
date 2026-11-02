"""End-to-end integration test suite exercising the complete automated monitoring loop.

Validates Acceptance Criteria A through H:
A. Bounded collection & provenance chaining
B. Deduplication & update handling
C. Portal refresh execution & authentication
D. Host scheduler launchd configuration
E. Concurrency mutual exclusion
F. Source failure isolation
G. Interruption & stale lock recovery
H. End-to-end epistemic trace from feed to unapproved export package

Governing Charter: Project Constitution (Rules 1, 3, 4, 11, 14, 15, 16),
ADR-008, ADR-010, SEC-002, AUD-004.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from ai_incident_monitor.db.base import Base
from ai_incident_monitor.db.models.claim import ClaimRecordModel
from ai_incident_monitor.db.models.editorial import EditorialDossierModel
from ai_incident_monitor.db.models.incident import IncidentModel
from ai_incident_monitor.ingestion.checkpoints import CheckpointStore
from ai_incident_monitor.ingestion.cycle import run_ingestion_cycle
from ai_incident_monitor.ingestion.lock import IngestionLock
from ai_incident_monitor.ingestion.manifest import ManifestChainStore, verify_provenance_chain
from ai_incident_monitor.ingestion.models import ConnectorType
from ai_incident_monitor.ingestion.scheduler import (
    DEFAULT_JOB_LABEL,
    generate_launchd_plist_bytes,
    validate_launchd_plist_bytes,
)
from ai_incident_monitor.ingestion.sources import SourceConfig, SourceRole
from ai_incident_monitor.security import SecureHTTPClient, SecureHTTPResponse
from ai_incident_monitor.ui.app import create_app
from ai_incident_monitor.ui.auth import (
    LocalCredentialManager,
    SESSION_COOKIE_NAME,
    ServerSessionManager,
)

SAMPLE_FEED_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Autonomous Systems Incident Monitor</title>
    <link>https://monitored-incidents.org</link>
    <description>Verified incident stream</description>
    <item>
      <title>Autonomous Baggage Tug Collision with Gate Terminal</title>
      <link>https://monitored-incidents.org/incident/baggage-tug-2026</link>
      <description>Autonomous electric baggage transport tug experienced steering fault at Airport Terminal 3.</description>
      <pubDate>Wed, 28 Oct 2026 14:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""

SAMPLE_FEED_UPDATED_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Autonomous Systems Incident Monitor</title>
    <link>https://monitored-incidents.org</link>
    <description>Verified incident stream</description>
    <item>
      <title>Autonomous Baggage Tug Collision with Gate Terminal (Investigation Complete)</title>
      <link>https://monitored-incidents.org/incident/baggage-tug-2026</link>
      <description>Updated Report: Autonomous electric baggage transport tug experienced steering fault at Airport Terminal 3 due to wet tarmac sensor slip.</description>
      <pubDate>Wed, 28 Oct 2026 16:30:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""


@pytest.fixture
def cycle_test_env(tmp_path: Path):
    """Isolated environment for cycle testing."""
    db_file = tmp_path / ".data" / "dev.db"
    db_file.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(engine)

    cred_file = tmp_path / ".data" / ".operator_credential"
    cred_mgr = LocalCredentialManager(storage_path=cred_file)
    cred_mgr.generate_or_load_credential()
    sess_mgr = ServerSessionManager()

    # Pre-create sources config
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir(parents=True, exist_ok=True)

    app = create_app(
        db_engine=engine,
        repo_root=tmp_path,
        credential_manager=cred_mgr,
        session_manager=sess_mgr,
    )
    client = TestClient(app, raise_server_exceptions=False)

    return {
        "engine": engine,
        "repo_root": tmp_path,
        "cred_mgr": cred_mgr,
        "sess_mgr": sess_mgr,
        "client": client,
    }


class TestIngestionCycleE2E:
    """Comprehensive test harness for Acceptance Tests A through H."""

    # ACCEPTANCE TEST A: Bounded Collection
    def test_acceptance_a_bounded_collection(self, cycle_test_env) -> None:
        root = cycle_test_env["repo_root"]
        engine = cycle_test_env["engine"]

        mock_http = MagicMock(spec=SecureHTTPClient)
        mock_http.get.return_value = SecureHTTPResponse(
            status_code=200,
            headers={"Content-Type": "application/rss+xml"},
            body=SAMPLE_FEED_XML,
            final_url="https://monitored-incidents.org/feed.xml",
            pinned_ip="93.184.216.34",
        )

        test_source = SourceConfig(
            source_id="incident_feed_live",
            name="Autonomous Incident Feed",
            connector_type=ConnectorType.RSS,
            role=SourceRole.PRIMARY_INCIDENT_REPORT,
            endpoint_url="https://monitored-incidents.org/feed.xml",
            allowed_hosts=["monitored-incidents.org"],
            enabled=True,
        )

        summary = run_ingestion_cycle(
            trigger="cli",
            repo_root=root,
            custom_sources=[test_source],
            custom_http_client=mock_http,
            db_engine=engine,
        )

        assert summary.overall_status == "SUCCESS"
        assert summary.total_fetched == 1
        assert summary.total_created == 1
        assert summary.total_failed == 0

        # Verify staged raw payload
        staged_files = list((root / ".data" / "raw_feeds").rglob("*.raw"))
        assert len(staged_files) == 1

        # Verify provenance manifest chain
        manifest_store = ManifestChainStore(storage_dir=root / ".data" / "manifests")
        chain = manifest_store.get_chain()
        chain_report = verify_provenance_chain(chain)
        assert chain_report.is_valid is True
        assert chain_report.total_manifests == 1

        # Verify incident and claim persisted in database
        with Session(engine) as session:
            incidents = session.execute(select(IncidentModel)).scalars().all()
            assert len(incidents) == 1
            inc = incidents[0]
            assert "Autonomous Baggage Tug" in inc.title
            assert inc.status == "NEW"

            claims = session.execute(select(ClaimRecordModel)).scalars().all()
            assert len(claims) == 1
            assert claims[0].incident_id == inc.id

        # Verify durable checkpoint
        cp_store = CheckpointStore(root / ".data" / "ingestion_checkpoints.json")
        cp = cp_store.get_checkpoint("incident_feed_live")
        assert cp.last_status == "SUCCESS"
        assert cp.last_success_utc is not None
        assert cp.records_created == 1

    # ACCEPTANCE TEST B: Deduplication & Update Handling
    def test_acceptance_b_deduplication(self, cycle_test_env) -> None:
        root = cycle_test_env["repo_root"]
        engine = cycle_test_env["engine"]

        mock_http = MagicMock(spec=SecureHTTPClient)
        test_source = SourceConfig(
            source_id="incident_feed_live",
            name="Autonomous Incident Feed",
            connector_type=ConnectorType.RSS,
            role=SourceRole.PRIMARY_INCIDENT_REPORT,
            endpoint_url="https://monitored-incidents.org/feed.xml",
            allowed_hosts=["monitored-incidents.org"],
            enabled=True,
        )

        # Pass 1: Initial ingestion
        mock_http.get.return_value = SecureHTTPResponse(
            status_code=200,
            headers={"Content-Type": "application/rss+xml"},
            body=SAMPLE_FEED_XML,
            final_url="https://monitored-incidents.org/feed.xml",
            pinned_ip="93.184.216.34",
        )
        res1 = run_ingestion_cycle(
            trigger="cli",
            repo_root=root,
            custom_sources=[test_source],
            custom_http_client=mock_http,
            db_engine=engine,
        )
        assert res1.total_created == 1

        # Pass 2: Repeat collection with identical payload -> Zero duplicates created!
        res2 = run_ingestion_cycle(
            trigger="cli",
            repo_root=root,
            custom_sources=[test_source],
            custom_http_client=mock_http,
            db_engine=engine,
        )
        assert res2.total_created == 0
        assert res2.total_updated == 1  # Tier 2 matched and linked

        # Verify total incidents in DB remains exactly 1
        with Session(engine) as session:
            count = len(session.execute(select(IncidentModel)).scalars().all())
            assert count == 1

        # Pass 3: Repeat collection with updated article title & description for same URL
        mock_http.get.return_value = SecureHTTPResponse(
            status_code=200,
            headers={"Content-Type": "application/rss+xml"},
            body=SAMPLE_FEED_UPDATED_XML,
            final_url="https://monitored-incidents.org/feed.xml",
            pinned_ip="93.184.216.34",
        )
        res3 = run_ingestion_cycle(
            trigger="cli",
            repo_root=root,
            custom_sources=[test_source],
            custom_http_client=mock_http,
            db_engine=engine,
        )
        assert res3.total_created == 0
        assert res3.total_updated == 1

        # Still exactly 1 incident record
        with Session(engine) as session:
            count = len(session.execute(select(IncidentModel)).scalars().all())
            assert count == 1

    # ACCEPTANCE TEST C: Portal Refresh
    def test_acceptance_c_portal_refresh(self, cycle_test_env) -> None:
        client = cycle_test_env["client"]
        sess_mgr = cycle_test_env["sess_mgr"]
        session = sess_mgr.create_session()
        client.cookies.set(SESSION_COOKIE_NAME, session.session_id)

        # 1. Reject invalid CSRF
        bad_csrf = client.post("/diagnostics/refresh", data={"csrf_token": "invalid"})
        assert bad_csrf.status_code == 403

        # 2. Authenticated valid trigger launches background cycle
        with patch("subprocess.Popen") as mock_popen:
            res = client.post(
                "/diagnostics/refresh",
                data={"csrf_token": session.csrf_token},
                follow_redirects=False,
            )
            assert res.status_code == 303
            assert "/diagnostics?refresh=started" in res.headers["location"]
            assert mock_popen.called
            cmd = mock_popen.call_args[0][0]
            assert "ai_incident_monitor.ingestion.cycle" in cmd
            assert "--trigger" in cmd
            assert "portal" in cmd

    # ACCEPTANCE TEST D: Host Scheduler launchd Configuration
    def test_acceptance_d_scheduler_configuration(self, cycle_test_env) -> None:
        root = cycle_test_env["repo_root"]
        plist_bytes = generate_launchd_plist_bytes(
            repo_root=root,
            interval_seconds=3600,
        )
        is_valid, err, parsed = validate_launchd_plist_bytes(plist_bytes)

        assert is_valid is True
        assert err is None
        assert parsed["Label"] == DEFAULT_JOB_LABEL
        assert parsed["StartInterval"] == 3600
        assert parsed["WorkingDirectory"] == str(root.resolve())
        # Confirm absolute python binary
        assert os.path.isabs(parsed["ProgramArguments"][0])

    # ACCEPTANCE TEST E: Concurrency Mutual Exclusion
    def test_acceptance_e_concurrency_conflict(self, cycle_test_env) -> None:
        root = cycle_test_env["repo_root"]

        # Hold the lock
        lock = IngestionLock(
            trigger="scheduled",
            run_id="run_blocking_999",
            lock_file_path=root / ".data" / "ingestion.lock",
        )
        lock.acquire()

        try:
            # Second run must report ALREADY_RUNNING and exit safely
            summary = run_ingestion_cycle(
                trigger="portal",
                repo_root=root,
            )
            assert summary.overall_status == "ALREADY_RUNNING"
            assert summary.active_conflict is not None
            assert summary.active_conflict["run_id"] == "run_blocking_999"
            assert summary.total_created == 0
        finally:
            lock.release()

    # ACCEPTANCE TEST F: Source Failure Isolation
    def test_acceptance_f_failure_isolation(self, cycle_test_env) -> None:
        root = cycle_test_env["repo_root"]
        engine = cycle_test_env["engine"]

        mock_http = MagicMock(spec=SecureHTTPClient)

        def mock_get(url, **kwargs):
            if "broken" in url:
                raise ConnectionError("Host unreachable: broken.example.org")
            return SecureHTTPResponse(
                status_code=200,
                headers={"Content-Type": "application/rss+xml"},
                body=SAMPLE_FEED_XML,
                final_url=url,
                pinned_ip="93.184.216.34",
            )

        mock_http.get.side_effect = mock_get

        source_broken = SourceConfig(
            source_id="broken_src",
            name="Broken Source",
            connector_type=ConnectorType.RSS,
            role=SourceRole.PRIMARY_INCIDENT_REPORT,
            endpoint_url="https://broken.example.org/feed.xml",
            allowed_hosts=["broken.example.org"],
            enabled=True,
        )
        source_healthy = SourceConfig(
            source_id="healthy_src",
            name="Healthy Source",
            connector_type=ConnectorType.RSS,
            role=SourceRole.PRIMARY_INCIDENT_REPORT,
            endpoint_url="https://monitored-incidents.org/feed.xml",
            allowed_hosts=["monitored-incidents.org"],
            enabled=True,
        )

        summary = run_ingestion_cycle(
            trigger="cli",
            repo_root=root,
            custom_sources=[source_broken, source_healthy],
            custom_http_client=mock_http,
            db_engine=engine,
        )

        assert summary.overall_status == "PARTIAL"
        assert len(summary.sources) == 2

        broken_res = next(s for s in summary.sources if s.source_id == "broken_src")
        assert broken_res.status == "FAILED"
        assert "Host unreachable" in (broken_res.error_message or "")

        healthy_res = next(s for s in summary.sources if s.source_id == "healthy_src")
        assert healthy_res.status == "SUCCESS"
        assert healthy_res.records_created == 1

        # Checkpoint verification: Broken source MUST NOT update last_success_utc
        cp_store = CheckpointStore(root / ".data" / "ingestion_checkpoints.json")
        cp_broken = cp_store.get_checkpoint("broken_src")
        assert cp_broken.last_status == "FAILED"
        assert cp_broken.last_success_utc is None

        cp_healthy = cp_store.get_checkpoint("healthy_src")
        assert cp_healthy.last_status == "SUCCESS"
        assert cp_healthy.last_success_utc is not None

        # Confirm valid records reached database despite sibling failure
        with Session(engine) as session:
            count = len(session.execute(select(IncidentModel)).scalars().all())
            assert count == 1

    # ACCEPTANCE TEST G: Interruption & Stale Lock Recovery
    def test_acceptance_g_interruption_and_stale_lock_recovery(self, cycle_test_env) -> None:
        root = cycle_test_env["repo_root"]
        lock_file = root / ".data" / "ingestion.lock"
        lock_file.parent.mkdir(parents=True, exist_ok=True)

        # Simulate dead process lock (interruption / sudden reboot)
        dead_pid = 99999999
        stale_payload = {
            "pid": dead_pid,
            "trigger": "scheduled",
            "run_id": "interrupted_run",
            "started_at_utc": "2026-11-01T12:00:00Z",
        }
        lock_file.write_text(json.dumps(stale_payload), encoding="utf-8")

        mock_http = MagicMock(spec=SecureHTTPClient)
        mock_http.get.return_value = SecureHTTPResponse(
            status_code=200,
            headers={"Content-Type": "application/rss+xml"},
            body=SAMPLE_FEED_XML,
            final_url="https://monitored-incidents.org/feed.xml",
            pinned_ip="93.184.216.34",
        )
        source = SourceConfig(
            source_id="src_recovery",
            name="Recovery Source",
            connector_type=ConnectorType.RSS,
            role=SourceRole.PRIMARY_INCIDENT_REPORT,
            endpoint_url="https://monitored-incidents.org/feed.xml",
            allowed_hosts=["monitored-incidents.org"],
            enabled=True,
        )

        # Must recover lock cleanly and complete cycle
        summary = run_ingestion_cycle(
            trigger="cli",
            repo_root=root,
            custom_sources=[source],
            custom_http_client=mock_http,
            db_engine=cycle_test_env["engine"],
        )
        assert summary.overall_status == "SUCCESS"
        assert summary.total_created == 1

    # ACCEPTANCE TEST H: End-to-End Epistemic Trace
    def test_acceptance_h_end_to_end_trace(self, cycle_test_env) -> None:
        client = cycle_test_env["client"]
        sess_mgr = cycle_test_env["sess_mgr"]
        session = sess_mgr.create_session()
        client.cookies.set(SESSION_COOKIE_NAME, session.session_id)
        root = cycle_test_env["repo_root"]
        engine = cycle_test_env["engine"]

        # 1. Ingest item via cycle
        mock_http = MagicMock(spec=SecureHTTPClient)
        mock_http.get.return_value = SecureHTTPResponse(
            status_code=200,
            headers={"Content-Type": "application/rss+xml"},
            body=SAMPLE_FEED_XML,
            final_url="https://monitored-incidents.org/feed.xml",
            pinned_ip="93.184.216.34",
        )
        test_source = SourceConfig(
            source_id="monitored_incidents",
            name="Autonomous Incident Feed",
            connector_type=ConnectorType.RSS,
            role=SourceRole.PRIMARY_INCIDENT_REPORT,
            endpoint_url="https://monitored-incidents.org/feed.xml",
            allowed_hosts=["monitored-incidents.org"],
            enabled=True,
        )
        run_ingestion_cycle(
            trigger="cli",
            repo_root=root,
            custom_sources=[test_source],
            custom_http_client=mock_http,
            db_engine=engine,
        )

        # 2. Verify incident is visible in dashboard /incidents
        res_incidents = client.get("/incidents")
        assert res_incidents.status_code == 200
        assert "Autonomous Baggage Tug" in res_incidents.text

        # Extract incident ID
        with Session(engine) as db_session:
            inc = db_session.execute(select(IncidentModel)).scalars().first()
            assert inc is not None
            inc_id = inc.id

        # 3. Assemble dossier with candidate incident
        assemble_res = client.post(
            "/dossiers",
            data={
                "csrf_token": session.csrf_token,
                "title": "Dossier for Autonomous Baggage Incident",
                "incident_ids": [inc_id],
            },
            follow_redirects=False,
        )
        assert assemble_res.status_code == 303
        dossier_id = assemble_res.headers["location"].split("/")[-1]

        # 4. Preview artifacts (zero approval gates)
        preview_res = client.get(f"/dossiers/{dossier_id}/preview")
        assert preview_res.status_code == 200
        assert "Autonomous Baggage Tug" in preview_res.text

        # 5. Export package creation (zero approval gates)
        pkg_res = client.post(
            f"/dossiers/{dossier_id}/export",
            data={
                "csrf_token": session.csrf_token,
                "profile": "EXECUTIVE_BRIEF",
                "format": "MARKDOWN",
                "artifact_purpose": "INTERNAL_REVIEW_COPY",
            },
            follow_redirects=False,
        )
        assert pkg_res.status_code == 303
        pkg_id = pkg_res.headers["location"].split("/")[-1]

        # 6. Authenticated package download
        filename = f"snapshot_{dossier_id}_v1_executive_brief.md"
        download_res = client.get(f"/packages/{pkg_id}/download/{filename}")
        assert download_res.status_code == 200
        assert download_res.headers["content-type"].startswith("text/markdown")
        assert "Autonomous Baggage Tug" in download_res.text
        assert download_res.headers["content-type"].startswith("text/markdown")
        assert "Autonomous Baggage Tug" in download_res.text
