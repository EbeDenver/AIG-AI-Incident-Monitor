"""Unit tests for Phase 8A security middleware, host validation, origin checks, and headers.

Governing Charter: Project Constitution (Rules 1, 10, 11, 14, 16),
PRD §2 (UIX-001, UIX-003, AUD-001, AUD-002), Phase 8A Plan.
"""

from __future__ import annotations

from pathlib import Path
import pytest
from starlette.testclient import TestClient

from ai_incident_monitor.ui.app import create_app
from ai_incident_monitor.ui.auth import LocalCredentialManager
from ai_incident_monitor.ui.cli import validate_loopback_host


@pytest.fixture
def test_client(tmp_path: Path) -> TestClient:
    """Create a test client configured with temporary storage and local allowlist."""
    cred_file = tmp_path / ".operator_credential"
    cred_mgr = LocalCredentialManager(storage_path=cred_file)
    cred_mgr.generate_or_load_credential()

    app = create_app(
        repo_root=tmp_path,
        credential_manager=cred_mgr,
        allowed_hosts={"testserver", "127.0.0.1:8000", "127.0.0.1", "localhost:8000", "localhost"},
    )
    return TestClient(app, raise_server_exceptions=False)


class TestSecurityMiddleware:
    """Validate host header allowlist, request body limit, and origin verification."""

    def test_allowed_host_header_succeeds(self, test_client: TestClient) -> None:
        response = test_client.get("/login", headers={"host": "127.0.0.1:8000"})
        assert response.status_code == 200

    def test_unauthorized_host_header_returns_400(self, test_client: TestClient) -> None:
        response = test_client.get("/login", headers={"host": "malicious-attacker.com"})
        assert response.status_code == 400
        assert "not in the local allowlist" in response.text

    def test_security_headers_present_on_all_responses(self, test_client: TestClient) -> None:
        response = test_client.get("/login")
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
        assert "default-src 'self'" in response.headers["content-security-policy"]
        assert "frame-ancestors 'none'" in response.headers["content-security-policy"]

    def test_payload_exceeding_1mb_returns_413(self, test_client: TestClient) -> None:
        large_body_size = 1024 * 1024 + 10  # > 1MB
        response = test_client.post(
            "/login",
            content="A" * 100,
            headers={"content-length": str(large_body_size)},
        )
        assert response.status_code == 413
        assert "Payload Too Large" in response.text

    def test_state_change_with_unauthorized_origin_returns_403(self, test_client: TestClient) -> None:
        response = test_client.post(
            "/login",
            data={"credential": "any", "csrf_token": "any"},
            headers={"origin": "http://evil-external-site.com"},
        )
        assert response.status_code == 403
        assert "Origin 'http://evil-external-site.com' is not authorized" in response.text


class TestLoopbackHostValidation:
    """Validate CLI host validation strictly rejecting non-loopback binds."""

    def test_valid_loopback_hosts_pass(self) -> None:
        validate_loopback_host("127.0.0.1")
        validate_loopback_host("localhost")
        validate_loopback_host("::1")

    def test_external_binds_exit_with_error(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            validate_loopback_host("0.0.0.0")
        assert exc_info.value.code == 1

        with pytest.raises(SystemExit) as exc_info2:
            validate_loopback_host("192.168.1.50")
        assert exc_info2.value.code == 1
