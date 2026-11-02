"""Unit tests for portal refresh action, CSRF protection, and operational visibility."""

from pathlib import Path
from unittest.mock import patch
import pytest
from sqlalchemy import create_engine
from starlette.testclient import TestClient

from ai_incident_monitor.db.base import Base
from ai_incident_monitor.ingestion.lock import IngestionLock
from ai_incident_monitor.ui.app import create_app
from ai_incident_monitor.ui.auth import (
    LocalCredentialManager,
    SESSION_COOKIE_NAME,
    ServerSessionManager,
)


@pytest.fixture
def portal_test_setup(tmp_path: Path):
    """Set up application with test database and isolated storage directory."""
    db_file = tmp_path / "portal_test.db"
    engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(engine)

    cred_file = tmp_path / ".operator_credential"
    cred_mgr = LocalCredentialManager(storage_path=cred_file)
    cred_mgr.generate_or_load_credential()
    sess_mgr = ServerSessionManager()

    # Pre-create config directory
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    sources_file = cfg_dir / "sources.json"
    sources_file.write_text("[]", encoding="utf-8")

    app = create_app(
        db_engine=engine,
        repo_root=tmp_path,
        credential_manager=cred_mgr,
        session_manager=sess_mgr,
    )
    client = TestClient(app, raise_server_exceptions=False)
    return {
        "client": client,
        "sess_mgr": sess_mgr,
        "engine": engine,
        "tmp_path": tmp_path,
    }


class TestPortalRefreshRoutes:
    """Validate portal refresh authentication, CSRF, and non-blocking background invocation."""

    def test_unauthenticated_refresh_redirects_to_login(self, portal_test_setup) -> None:
        client = portal_test_setup["client"]
        res = client.post("/diagnostics/refresh", follow_redirects=False)
        assert res.status_code == 303
        assert res.headers["location"] == "/login"

    def test_missing_or_invalid_csrf_returns_403(self, portal_test_setup) -> None:
        client = portal_test_setup["client"]
        sess_mgr = portal_test_setup["sess_mgr"]
        session = sess_mgr.create_session()
        client.cookies.set(SESSION_COOKIE_NAME, session.session_id)

        # POST without CSRF
        res = client.post("/diagnostics/refresh")
        assert res.status_code == 403
        assert "CSRF validation failed" in res.text

        # POST with wrong CSRF
        res = client.post("/diagnostics/refresh", data={"csrf_token": "wrong_csrf"})
        assert res.status_code == 403

    def test_authenticated_refresh_starts_background_run(self, portal_test_setup) -> None:
        client = portal_test_setup["client"]
        sess_mgr = portal_test_setup["sess_mgr"]
        session = sess_mgr.create_session()
        client.cookies.set(SESSION_COOKIE_NAME, session.session_id)

        with patch("subprocess.Popen") as mock_popen:
            res = client.post(
                "/diagnostics/refresh",
                data={"csrf_token": session.csrf_token},
                follow_redirects=False,
            )

            assert res.status_code == 303
            assert "/diagnostics?refresh=started&run_id=run_" in res.headers["location"]
            assert mock_popen.called

            # Verify subprocess call arguments
            call_args = mock_popen.call_args
            cmd = call_args[0][0]
            assert "-m" in cmd
            assert "ai_incident_monitor.ingestion.cycle" in cmd
            assert "--trigger" in cmd
            assert "portal" in cmd

    def test_refresh_during_active_run_returns_conflict_notice(self, portal_test_setup) -> None:
        client = portal_test_setup["client"]
        sess_mgr = portal_test_setup["sess_mgr"]
        session = sess_mgr.create_session()
        client.cookies.set(SESSION_COOKIE_NAME, session.session_id)
        tmp_path = portal_test_setup["tmp_path"]

        # Hold the lock as an active process
        lock = IngestionLock(
            trigger="cli",
            run_id="run_blocking_123",
            lock_file_path=tmp_path / ".data" / "ingestion.lock",
        )
        lock.acquire()

        try:
            with patch("subprocess.Popen") as mock_popen:
                res = client.post(
                    "/diagnostics/refresh",
                    data={"csrf_token": session.csrf_token},
                    follow_redirects=False,
                )
                assert res.status_code == 303
                assert "/diagnostics?refresh=conflict&run_id=run_blocking_123" in res.headers["location"]
                assert not mock_popen.called
        finally:
            lock.release()

    def test_json_api_refresh_and_status(self, portal_test_setup) -> None:
        client = portal_test_setup["client"]
        sess_mgr = portal_test_setup["sess_mgr"]
        session = sess_mgr.create_session()
        client.cookies.set(SESSION_COOKIE_NAME, session.session_id)

        # GET status
        status_res = client.get("/api/ingestion/status")
        assert status_res.status_code == 200
        data = status_res.json()
        assert "active_run" in data
        assert "sources" in data
        assert "checkpoints" in data

        # POST refresh JSON
        with patch("subprocess.Popen"):
            refresh_res = client.post(
                "/api/ingestion/refresh",
                data={"csrf_token": session.csrf_token},
            )
            assert refresh_res.status_code == 200
            resp_data = refresh_res.json()
            assert resp_data["status"] == "started"
            assert "run_id" in resp_data
            assert resp_data["trigger"] == "portal"

    def test_diagnostics_page_renders_ingestion_controls(self, portal_test_setup) -> None:
        client = portal_test_setup["client"]
        sess_mgr = portal_test_setup["sess_mgr"]
        session = sess_mgr.create_session()
        client.cookies.set(SESSION_COOKIE_NAME, session.session_id)

        res = client.get("/diagnostics")
        assert res.status_code == 200
        assert "Automated Ingestion &amp; Monitoring Status" in res.text or "Automated Ingestion & Monitoring Status" in res.text
        assert "Refresh Incidents Now" in res.text
        assert "Configured Frequency:" in res.text
        assert "macOS launchd Scheduler:" in res.text
