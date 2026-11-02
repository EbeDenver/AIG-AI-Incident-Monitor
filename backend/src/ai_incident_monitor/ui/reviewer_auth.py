"""Local Reviewer Keystore and Step-Up Reviewer Authentication.

Implements the local authorized reviewer keystore for Phase 8B:
- One-way salted hashing (PBKDF2-HMAC-SHA256, 100,000 iterations).
- POSIX 0o600 file permissions and O_NOFOLLOW symlink rejection.
- Constant-time verification (hmac.compare_digest).
- In-memory rate limiting for reviewer authentication attempts.
- Strict separation between ordinary operator dashboard sessions and reviewer signing authority.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import stat
import time
from typing import Any, Optional


REVIEWER_KEY_PREFIX = "rev_"
DEFAULT_PBKDF2_ITERATIONS = 100_000
DEFAULT_RATE_LIMIT_MAX_FAILURES = 3
DEFAULT_RATE_LIMIT_WINDOW_SECONDS = 600.0  # 10 minutes


@dataclass
class ReviewerRecord:
    """Authorized human reviewer record in the local keystore."""

    reviewer_id: str
    reviewer_name: str
    reviewer_role: str
    is_human: bool
    is_active: bool
    salt_hex: str
    key_hash_hex: str
    enrolled_at_utc: str
    revoked_at_utc: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert record to dictionary for JSON persistence."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReviewerRecord:
        """Construct record from dictionary."""
        return cls(
            reviewer_id=data["reviewer_id"],
            reviewer_name=data["reviewer_name"],
            reviewer_role=data["reviewer_role"],
            is_human=bool(data.get("is_human", True)),
            is_active=bool(data.get("is_active", True)),
            salt_hex=data["salt_hex"],
            key_hash_hex=data["key_hash_hex"],
            enrolled_at_utc=data["enrolled_at_utc"],
            revoked_at_utc=data.get("revoked_at_utc"),
        )


class ReviewerKeystore:
    """Local, single-node filesystem keystore for authorized human reviewers."""

    def __init__(self, storage_path: Path) -> None:
        self.storage_path = Path(storage_path)
        self._ensure_storage_dir()

    def _ensure_storage_dir(self) -> None:
        """Ensure parent directory exists with 0o700 permissions."""
        parent = self.storage_path.parent
        parent.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(parent, 0o700)
        except OSError:
            pass

    def _hash_key(self, key: str, salt: bytes) -> str:
        """Compute PBKDF2-HMAC-SHA256 hex digest of reviewer key."""
        return hashlib.pbkdf2_hmac(
            "sha256",
            key.encode("utf-8"),
            salt,
            DEFAULT_PBKDF2_ITERATIONS,
        ).hex()

    def _read_data(self) -> dict[str, ReviewerRecord]:
        """Read keystore file enforcing symlink rejection and 0o600 permissions."""
        # Symlink check
        if os.path.islink(self.storage_path) or self.storage_path.is_symlink():
            raise SecurityError(
                f"Security violation: Keystore path '{self.storage_path}' is a symlink. Rejection mandatory."
            )

        if not self.storage_path.exists():
            return {}

        # File permissions check
        file_stat = os.stat(self.storage_path)
        mode = stat.S_IMODE(file_stat.st_mode)
        if mode & 0o077 != 0:
            raise SecurityError(
                f"Security violation: Keystore file '{self.storage_path}' has insecure mode {oct(mode)}. "
                "Must be strictly 0o600."
            )

        try:
            content = self.storage_path.read_text(encoding="utf-8")
            if not content.strip():
                return {}
            payload = json.loads(content)
            reviewers_dict = payload.get("reviewers", {})
            return {
                rev_id: ReviewerRecord.from_dict(rev_data)
                for rev_id, rev_data in reviewers_dict.items()
            }
        except json.JSONDecodeError as exc:
            raise ValueError(f"Corrupted reviewer keystore at '{self.storage_path}': {exc}")

    def _write_data(self, reviewers: dict[str, ReviewerRecord]) -> None:
        """Write keystore file using atomic write with 0o600 permissions."""
        self._ensure_storage_dir()

        payload = {
            "schema_version": "1.0.0",
            "reviewers": {rev_id: rec.to_dict() for rev_id, rec in reviewers.items()},
        }
        content = json.dumps(payload, indent=2)

        # Reject writing to symlink
        if os.path.islink(self.storage_path) or (self.storage_path.exists() and self.storage_path.is_symlink()):
            raise SecurityError(
                f"Security violation: Cannot write to symlink at '{self.storage_path}'."
            )

        # Write directly with O_NOFOLLOW and mode 0o600
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(self.storage_path, flags, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception:
            try:
                os.close(fd)
            except OSError:
                pass
            raise

        try:
            os.chmod(self.storage_path, 0o600)
        except OSError:
            pass

    def enroll_reviewer(
        self,
        reviewer_id: str,
        reviewer_name: str,
        reviewer_role: str,
    ) -> tuple[ReviewerRecord, str]:
        """Enroll a new authorized human reviewer, generating a 256-bit secret key.

        Returns (ReviewerRecord, generated_raw_key).
        """
        r_id = reviewer_id.strip()
        if not r_id:
            raise ValueError("Reviewer ID cannot be empty.")
        r_name = reviewer_name.strip()
        if not r_name:
            raise ValueError("Reviewer name cannot be empty.")
        r_role = reviewer_role.strip()
        if not r_role:
            raise ValueError("Reviewer role cannot be empty.")

        data = self._read_data()
        if r_id in data:
            raise ValueError(f"Reviewer '{r_id}' is already enrolled.")

        # Generate 256-bit high-entropy secret key
        raw_key = f"{REVIEWER_KEY_PREFIX}{secrets.token_urlsafe(32)}"
        salt = secrets.token_bytes(32)
        key_hash = self._hash_key(raw_key, salt)

        now_str = datetime.now(timezone.utc).isoformat()
        record = ReviewerRecord(
            reviewer_id=r_id,
            reviewer_name=r_name,
            reviewer_role=r_role,
            is_human=True,
            is_active=True,
            salt_hex=salt.hex(),
            key_hash_hex=key_hash,
            enrolled_at_utc=now_str,
            revoked_at_utc=None,
        )

        data[r_id] = record
        self._write_data(data)
        return record, raw_key

    def rotate_key(self, reviewer_id: str) -> str:
        """Generate a new key for an enrolled reviewer and update stored hash."""
        r_id = reviewer_id.strip()
        data = self._read_data()
        if r_id not in data:
            raise KeyError(f"Reviewer '{r_id}' not found.")

        record = data[r_id]
        if not record.is_active:
            raise ValueError(f"Cannot rotate key for revoked reviewer '{r_id}'.")

        raw_key = f"{REVIEWER_KEY_PREFIX}{secrets.token_urlsafe(32)}"
        salt = secrets.token_bytes(32)
        key_hash = self._hash_key(raw_key, salt)

        record.salt_hex = salt.hex()
        record.key_hash_hex = key_hash
        self._write_data(data)
        return raw_key

    def revoke_reviewer(self, reviewer_id: str) -> None:
        """Revoke a reviewer's approval authorization."""
        r_id = reviewer_id.strip()
        data = self._read_data()
        if r_id not in data:
            raise KeyError(f"Reviewer '{r_id}' not found.")

        record = data[r_id]
        record.is_active = False
        record.revoked_at_utc = datetime.now(timezone.utc).isoformat()
        self._write_data(data)

    def get_reviewer(self, reviewer_id: str) -> Optional[ReviewerRecord]:
        """Fetch reviewer record by ID."""
        data = self._read_data()
        return data.get(reviewer_id.strip())

    def list_reviewers(self) -> list[ReviewerRecord]:
        """List all enrolled reviewer records."""
        data = self._read_data()
        return list(data.values())

    def verify_reviewer_key(
        self,
        reviewer_id: str,
        candidate_key: str,
    ) -> tuple[bool, Optional[str], Optional[ReviewerRecord]]:
        """Verify candidate key in constant time against stored PBKDF2 hash.

        Returns (is_valid, error_reason, reviewer_record).
        """
        r_id = reviewer_id.strip()
        if not r_id:
            return False, "Reviewer ID cannot be empty.", None

        if not candidate_key or not isinstance(candidate_key, str) or not candidate_key.strip():
            return False, "Reviewer key cannot be empty.", None

        record = self.get_reviewer(r_id)
        if not record:
            return False, "Invalid reviewer ID or inactive reviewer.", None

        if not record.is_active:
            return False, f"Reviewer '{r_id}' has been revoked.", None

        if not record.is_human:
            return False, f"Reviewer '{r_id}' is not an authorized human reviewer.", None

        salt = bytes.fromhex(record.salt_hex)
        expected_hash = record.key_hash_hex
        computed_hash = self._hash_key(candidate_key.strip(), salt)

        if not hmac.compare_digest(expected_hash, computed_hash):
            return False, "Invalid reviewer key.", None

        return True, None, record


class ReviewerRateLimiter:
    """In-memory rate limiter for reviewer key verification attempts."""

    def __init__(
        self,
        max_failures: int = DEFAULT_RATE_LIMIT_MAX_FAILURES,
        window_seconds: float = DEFAULT_RATE_LIMIT_WINDOW_SECONDS,
    ) -> None:
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self._failures: dict[str, list[float]] = defaultdict(list)

    def _purge_old(self, client_id: str, now: float) -> None:
        """Purge failures outside the sliding window."""
        cutoff = now - self.window_seconds
        self._failures[client_id] = [t for t in self._failures[client_id] if t > cutoff]

    def is_blocked(self, client_id: str, now: Optional[float] = None) -> tuple[bool, float]:
        """Return (is_blocked, remaining_cooldown_seconds)."""
        current_time = now if now is not None else time.time()
        self._purge_old(client_id, current_time)
        failures = self._failures[client_id]

        if len(failures) >= self.max_failures:
            oldest_relevant = failures[-self.max_failures]
            elapsed = current_time - oldest_relevant
            remaining = max(0.0, self.window_seconds - elapsed)
            if remaining > 0:
                return True, remaining

        return False, 0.0

    def record_failure(self, client_id: str, now: Optional[float] = None) -> None:
        """Record a failed verification attempt."""
        current_time = now if now is not None else time.time()
        self._failures[client_id].append(current_time)

    def reset(self, client_id: str) -> None:
        """Reset failed attempts for client."""
        if client_id in self._failures:
            del self._failures[client_id]


class SecurityError(Exception):
    """Raised on security and boundary violations."""
    pass
