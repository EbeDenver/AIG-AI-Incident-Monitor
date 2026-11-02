"""Unit tests for Phase 8B Reviewer Keystore, Authentication, and CLI."""

from __future__ import annotations

import os
from pathlib import Path
import stat
import subprocess
import sys
import time

import pytest

from ai_incident_monitor.ui.manage_reviewers import build_parser
from ai_incident_monitor.ui.reviewer_auth import (
    DEFAULT_RATE_LIMIT_MAX_FAILURES,
    DEFAULT_RATE_LIMIT_WINDOW_SECONDS,
    ReviewerKeystore,
    ReviewerRateLimiter,
    SecurityError,
)


@pytest.fixture
def keystore(tmp_path: Path) -> ReviewerKeystore:
    """Fixture providing an isolated ReviewerKeystore in tmp_path."""
    keystore_path = tmp_path / "data" / ".reviewers.json"
    return ReviewerKeystore(storage_path=keystore_path)


class TestReviewerKeystore:
    """Test suite for local reviewer keystore security and operations."""

    def test_enroll_reviewer_creates_0600_file_and_generates_key(self, keystore: ReviewerKeystore) -> None:
        """Enrollment generates 256-bit key and stores PBKDF2 hash in 0o600 file."""
        record, raw_key = keystore.enroll_reviewer(
            reviewer_id="ebe",
            reviewer_name="Ebe Rolston",
            reviewer_role="Lead Editor",
        )

        assert record.reviewer_id == "ebe"
        assert record.reviewer_name == "Ebe Rolston"
        assert record.reviewer_role == "Lead Editor"
        assert record.is_human is True
        assert record.is_active is True
        assert raw_key.startswith("rev_")
        assert len(raw_key) > 30

        # Verify keystore file exists with mode 0o600
        assert keystore.storage_path.exists()
        file_mode = stat.S_IMODE(os.stat(keystore.storage_path).st_mode)
        assert file_mode == 0o600

        # Verify plaintext secret is NOT stored
        raw_content = keystore.storage_path.read_text(encoding="utf-8")
        assert raw_key not in raw_content
        assert record.key_hash_hex in raw_content

    def test_duplicate_enrollment_rejected(self, keystore: ReviewerKeystore) -> None:
        """Enrolling an existing reviewer ID raises ValueError."""
        keystore.enroll_reviewer("reviewer1", "Alice", "Editor")
        with pytest.raises(ValueError, match="already enrolled"):
            keystore.enroll_reviewer("reviewer1", "Alice Again", "Editor")

    def test_symlink_keystore_target_strictly_rejected(self, tmp_path: Path) -> None:
        """Symlink keystore targets are strictly rejected under SecurityError."""
        real_file = tmp_path / "real_file.json"
        real_file.write_text("{}", encoding="utf-8")
        os.chmod(real_file, 0o600)

        symlink_path = tmp_path / "symlink_reviewers.json"
        symlink_path.symlink_to(real_file)

        keystore = ReviewerKeystore(storage_path=symlink_path)
        with pytest.raises(SecurityError, match="symlink"):
            keystore.enroll_reviewer("test", "Test", "Role")

    def test_key_verification_happy_path(self, keystore: ReviewerKeystore) -> None:
        """Valid reviewer ID and secret verify successfully in constant time."""
        _, raw_key = keystore.enroll_reviewer("reviewer1", "Bob", "Senior Reviewer")

        is_valid, err, rec = keystore.verify_reviewer_key("reviewer1", raw_key)
        assert is_valid is True
        assert err is None
        assert rec is not None
        assert rec.reviewer_id == "reviewer1"
        assert rec.is_human is True

    def test_key_verification_invalid_key_fails(self, keystore: ReviewerKeystore) -> None:
        """Incorrect key fails verification."""
        keystore.enroll_reviewer("reviewer1", "Bob", "Senior Reviewer")

        is_valid, err, rec = keystore.verify_reviewer_key("reviewer1", "wrong_key_12345")
        assert is_valid is False
        assert "Invalid reviewer key" in err
        assert rec is None

    def test_key_rotation(self, keystore: ReviewerKeystore) -> None:
        """Rotating key replaces stored hash and immediately invalidates old key."""
        _, old_key = keystore.enroll_reviewer("reviewer1", "Bob", "Reviewer")

        # Rotate key
        new_key = keystore.rotate_key("reviewer1")
        assert new_key != old_key
        assert new_key.startswith("rev_")

        # Old key now fails
        is_valid_old, _, _ = keystore.verify_reviewer_key("reviewer1", old_key)
        assert is_valid_old is False

        # New key succeeds
        is_valid_new, _, rec = keystore.verify_reviewer_key("reviewer1", new_key)
        assert is_valid_new is True
        assert rec.reviewer_id == "reviewer1"

    def test_revocation_blocks_verification(self, keystore: ReviewerKeystore) -> None:
        """Revoking a reviewer marks inactive and blocks subsequent verification."""
        _, raw_key = keystore.enroll_reviewer("reviewer1", "Bob", "Reviewer")

        # Revoke
        keystore.revoke_reviewer("reviewer1")
        record = keystore.get_reviewer("reviewer1")
        assert record.is_active is False
        assert record.revoked_at_utc is not None

        # Verification fails
        is_valid, err, _ = keystore.verify_reviewer_key("reviewer1", raw_key)
        assert is_valid is False
        assert "revoked" in err.lower()


class TestReviewerRateLimiter:
    """Test suite for reviewer step-up rate limiting."""

    def test_rate_limiting_after_max_failures(self) -> None:
        """Exceeding max failures blocks client for the window duration."""
        limiter = ReviewerRateLimiter(max_failures=3, window_seconds=600.0)
        client = "127.0.0.1:reviewer1"

        # 2 failures - not blocked
        limiter.record_failure(client, now=100.0)
        limiter.record_failure(client, now=105.0)
        blocked, cooldown = limiter.is_blocked(client, now=110.0)
        assert blocked is False

        # 3rd failure - blocked
        limiter.record_failure(client, now=110.0)
        blocked, cooldown = limiter.is_blocked(client, now=110.0)
        assert blocked is True
        assert 580.0 <= cooldown <= 600.0

        # Successful reset
        limiter.reset(client)
        blocked_after, _ = limiter.is_blocked(client, now=110.0)
        assert blocked_after is False


class TestManageReviewersCLI:
    """Test suite for manage_reviewers CLI entry point."""

    def test_cli_enroll_and_list(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        """CLI enroll command prints key and list shows enrolled reviewer."""
        keystore_path = tmp_path / "cli_reviewers.json"
        parser = build_parser()

        # 1. Enroll
        args_enroll = parser.parse_args([
            "--keystore-path", str(keystore_path),
            "enroll",
            "--reviewer-id", "lead_ed",
            "--name", "Lead Editor",
            "--role", "LEAD_EDITOR",
        ])
        exit_code = args_enroll.func(args_enroll)
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Reviewer Enrolled Successfully" in captured.out
        assert "lead_ed" in captured.out
        assert "rev_" in captured.out

        # 2. List
        args_list = parser.parse_args([
            "--keystore-path", str(keystore_path),
            "list",
        ])
        exit_code_list = args_list.func(args_list)
        assert exit_code_list == 0
        captured_list = capsys.readouterr()
        assert "lead_ed" in captured_list.out
        assert "ACTIVE" in captured_list.out

        # 3. Rotate key
        args_rotate = parser.parse_args([
            "--keystore-path", str(keystore_path),
            "rotate-key",
            "--reviewer-id", "lead_ed",
        ])
        exit_code_rotate = args_rotate.func(args_rotate)
        assert exit_code_rotate == 0
        captured_rotate = capsys.readouterr()
        assert "Reviewer Key Rotated" in captured_rotate.out

        # 4. Revoke
        args_revoke = parser.parse_args([
            "--keystore-path", str(keystore_path),
            "revoke",
            "--reviewer-id", "lead_ed",
        ])
        exit_code_revoke = args_revoke.func(args_revoke)
        assert exit_code_revoke == 0
        captured_revoke = capsys.readouterr()
        assert "REVOKED" in captured_revoke.out
