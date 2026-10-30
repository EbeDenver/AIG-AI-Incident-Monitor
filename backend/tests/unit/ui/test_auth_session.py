"""Unit tests for Phase 8A ephemeral credential management, rate-limiting, and server-side sessions.

Governing Charter: Project Constitution (Rules 1, 10, 14, 15, 16),
PRD §2 (UIX-001, UIX-003, AUD-001, AUD-002), Phase 8A Plan.
"""

from __future__ import annotations

import os
from pathlib import Path
import stat
import time

import pytest

from ai_incident_monitor.ui.auth import (
    DEFAULT_ABSOLUTE_LIFETIME_SECONDS,
    DEFAULT_IDLE_TIMEOUT_SECONDS,
    LocalCredentialManager,
    LoginRateLimiter,
    ServerSessionManager,
    SessionRecord,
)


class TestLocalCredentialManager:
    """Validate ephemeral local credential generation, permissions, and symlink rejection."""

    def test_credential_generation_creates_file_with_0600_permissions(self, tmp_path: Path) -> None:
        cred_file = tmp_path / "creds" / ".operator_credential"
        mgr = LocalCredentialManager(storage_path=cred_file)

        token = mgr.generate_or_load_credential(now=1000.0)

        assert token is not None
        assert len(token) >= 32
        assert cred_file.exists()

        # Check permissions: owner read/write only (0o600)
        mode = stat.S_IMODE(os.stat(cred_file).st_mode)
        assert mode == 0o600

        # Reloading at same epoch returns identical token
        token_reloaded = mgr.generate_or_load_credential(now=1000.0)
        assert token_reloaded == token

    def test_expired_credential_file_is_automatically_regenerated(self, tmp_path: Path) -> None:
        cred_file = tmp_path / ".operator_credential"
        mgr = LocalCredentialManager(storage_path=cred_file, validity_seconds=3600.0)

        token1 = mgr.generate_or_load_credential(now=1000.0)

        # 4000s later (> 3600s validity)
        token2 = mgr.generate_or_load_credential(now=5000.0)

        assert token2 != token1

    def test_symlink_credential_target_is_strictly_rejected(self, tmp_path: Path) -> None:
        real_file = tmp_path / "real_file.json"
        real_file.write_text("{}", encoding="utf-8")

        symlink_target = tmp_path / "symlink_creds"
        os.symlink(real_file, symlink_target)

        mgr = LocalCredentialManager(storage_path=symlink_target)

        with pytest.raises(ValueError, match="symbolic link"):
            mgr.generate_or_load_credential()

    def test_constant_time_credential_verification(self, tmp_path: Path) -> None:
        cred_file = tmp_path / ".operator_credential"
        mgr = LocalCredentialManager(storage_path=cred_file)

        valid_token = mgr.generate_or_load_credential(now=1000.0)

        assert mgr.verify_credential(valid_token, now=1000.0) is True
        assert mgr.verify_credential(valid_token + "tampered", now=1000.0) is False
        assert mgr.verify_credential("", now=1000.0) is False
        assert mgr.verify_credential("completely_wrong_secret", now=1000.0) is False


class TestLoginRateLimiter:
    """Validate sliding-window rate limiting on failed login attempts."""

    def test_rate_limiting_blocks_after_5_failures_within_window(self) -> None:
        limiter = LoginRateLimiter(max_attempts=5, window_seconds=300.0)
        client_ip = "127.0.0.1"

        # 4 failures within window
        for i in range(4):
            limiter.record_failure(client_ip, now=100.0 + i)
            blocked, _ = limiter.is_blocked(client_ip, now=100.0 + i)
            assert blocked is False

        # 5th failure triggers block
        limiter.record_failure(client_ip, now=105.0)
        blocked, cooldown = limiter.is_blocked(client_ip, now=105.0)
        assert blocked is True
        assert cooldown > 0.0

        # After window passes (now = 500.0), client is unblocked
        blocked_after, _ = limiter.is_blocked(client_ip, now=500.0)
        assert blocked_after is False

    def test_reset_clears_failure_history(self) -> None:
        limiter = LoginRateLimiter(max_attempts=3, window_seconds=300.0)
        client_ip = "127.0.0.1"

        for i in range(3):
            limiter.record_failure(client_ip, now=100.0)

        blocked, _ = limiter.is_blocked(client_ip, now=100.0)
        assert blocked is True

        # Successful login resets
        limiter.reset(client_ip)
        blocked_reset, _ = limiter.is_blocked(client_ip, now=100.0)
        assert blocked_reset is False


class TestServerSessionManager:
    """Validate server-side session lifecycle, idle timeout, absolute timeout, and CSRF tokens."""

    def test_session_creation_generates_fresh_tokens(self) -> None:
        mgr = ServerSessionManager()
        s1 = mgr.create_session(now=1000.0)
        s2 = mgr.create_session(now=1000.0)

        assert s1.session_id != s2.session_id
        assert s1.csrf_token != s2.csrf_token
        assert s1.is_human is True
        assert s1.actor_id == "local_operator"
        assert mgr.active_session_count == 2

    def test_session_idle_timeout_expiration(self) -> None:
        mgr = ServerSessionManager(idle_timeout=14400.0, absolute_lifetime=86400.0)
        session = mgr.create_session(now=1000.0)

        # 3 hours later (< 4 hours idle limit) -> valid and updates last_active
        retrieved = mgr.get_session(session.session_id, now=1000.0 + 10800.0)
        assert retrieved is not None
        assert retrieved.last_active_at_utc == 1000.0 + 10800.0

        # Now 5 hours of inactivity (> 4 hours idle limit) -> expired and purged
        expired = mgr.get_session(session.session_id, now=1000.0 + 10800.0 + 18000.0)
        assert expired is None
        assert mgr.active_session_count == 0

    def test_session_absolute_lifetime_ceiling(self) -> None:
        # 10s idle, 30s absolute
        mgr = ServerSessionManager(idle_timeout=10.0, absolute_lifetime=30.0)
        session = mgr.create_session(now=1000.0)

        # Continuous activity every 5 seconds (never idling)
        mgr.get_session(session.session_id, now=1005.0)
        mgr.get_session(session.session_id, now=1010.0)
        mgr.get_session(session.session_id, now=1015.0)
        mgr.get_session(session.session_id, now=1025.0)

        # At 35s (> 30s absolute ceiling), session expires despite continuous activity
        expired = mgr.get_session(session.session_id, now=1035.0)
        assert expired is None
        assert mgr.active_session_count == 0

    def test_session_invalidation_on_logout(self) -> None:
        mgr = ServerSessionManager()
        session = mgr.create_session()

        assert mgr.get_session(session.session_id) is not None

        mgr.invalidate_session(session.session_id)
        assert mgr.get_session(session.session_id) is None

    def test_constant_time_csrf_validation(self) -> None:
        mgr = ServerSessionManager()
        session = mgr.create_session()

        assert mgr.validate_csrf(session, session.csrf_token) is True
        assert mgr.validate_csrf(session, session.csrf_token + "_tampered") is False
        assert mgr.validate_csrf(session, "") is False
        assert mgr.validate_csrf(session, None) is False
