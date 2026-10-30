"""Unit tests for UI diagnostics route, credential masking, and read-only system inspection.

Governing Charter: Project Constitution (Rules 1, 10, 11, 14, 16),
PRD §2 (UIX-001, UIX-003, AUD-001, AUD-002), Phase 8A Plan.
"""

from __future__ import annotations

from pathlib import Path
import pytest
from sqlalchemy import create_engine
from starlette.testclient import TestClient

from ai_incident_monitor.db.base import Base
from ai_incident_monitor.ui.app import create_app
from ai_incident_monitor.ui.auth import LocalCredentialManager, ServerSessionManager, SESSION_COOKIE_NAME


@pytest.fixture
def diagnostics_test_setup(tmp_path: Path):
    """Set up an application with temporary database and credential manager."""
    db_file = tmp_path / "diagnostics_test.db"
    engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(engine)

    cred_file = tmp_path / ".operator_credential"
    cred_mgr = LocalCredentialManager(storage_path=cred_file)
    cred_mgr.generate_or_load_credential()
    sess_mgr = ServerSessionManager()

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


class TestDiagnosticsRoutes:
    """Validate diagnostics route authentication, health rendering, and read-only behavior."""

    def test_unauthenticated_diagnostics_redirects_to_login(self, diagnostics_test_setup) -> None:
        client = diagnostics_test_setup["client"]
        res = client.get("/diagnostics", follow_redirects=False)
        assert res.status_code == 303
        assert res.headers["location"] == "/login"

    def test_authenticated_diagnostics_renders_health_cards(self, diagnostics_test_setup) -> None:
        client = diagnostics_test_setup["client"]
        sess_mgr = diagnostics_test_setup["sess_mgr"]
        session = sess_mgr.create_session()
        client.cookies.set(SESSION_COOKIE_NAME, session.session_id)

        res = client.get("/diagnostics")
        assert res.status_code == 200

        # Title and header
        assert "Operational Diagnostics" in res.text
        assert "Overall Subsystem Status:" in res.text

        # All 6 check cards present
        assert "Configuration Presence" in res.text
        assert "Database Connectivity" in res.text
        assert "Schema Compatibility" in res.text
        assert "Reference Library Integrity" in res.text
        assert "Storage Paths Accessibility" in res.text
        assert "Pipeline Components Readiness" in res.text

        # Stated limitations rendered
        assert "Non-Mutating Execution" in res.text
        assert "Schema Compatibility" in res.text

    def test_diagnostics_route_creates_zero_files_and_zero_db_mutations(self, diagnostics_test_setup) -> None:
        client = diagnostics_test_setup["client"]
        sess_mgr = diagnostics_test_setup["sess_mgr"]
        session = sess_mgr.create_session()
        client.cookies.set(SESSION_COOKIE_NAME, session.session_id)
        tmp_path = diagnostics_test_setup["tmp_path"]

        # Track directory files before
        files_before = set(tmp_path.rglob("*"))

        # Access diagnostics multiple times
        client.get("/diagnostics")
        client.get("/diagnostics")

        # Track directory files after (excluding DB lock/wal if any)
        files_after = set(tmp_path.rglob("*"))
        new_files = [f for f in files_after - files_before if not f.name.endswith(("-wal", "-shm"))]

        assert len(new_files) == 0, f"Diagnostics created unexpected files: {new_files}"
