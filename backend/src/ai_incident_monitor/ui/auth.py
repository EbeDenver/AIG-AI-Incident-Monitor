"""Ephemeral bootstrap authentication, server-side session registry, and CSRF protection.

Governing Charter: Project Constitution (Rules 1, 10, 14, 15, 16),
PRD §2 (UIX-001, UIX-003, AUD-001, AUD-002), Phase 8A Plan.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hmac
import json
import os
from pathlib import Path
import secrets
import stat
import time
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

# Constants for session policy
DEFAULT_IDLE_TIMEOUT_SECONDS = 14400      # 4 hours
DEFAULT_ABSOLUTE_LIFETIME_SECONDS = 86400  # 24 hours
DEFAULT_CREDENTIAL_VALIDITY_SECONDS = 86400 # 24 hours
MAX_FAILED_LOGIN_ATTEMPTS = 5
LOGIN_ATTEMPT_WINDOW_SECONDS = 300        # 5 minutes
SESSION_COOKIE_NAME = "aig_operator_session"


class OperatorPrincipal(BaseModel):
    """Authenticated operator context for local exploration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    actor_id: str = Field(min_length=1, max_length=64)
    role: str = Field(default="LOCAL_EXPLORER")
    is_human: bool = Field(default=True)
    auth_method: str = Field(default="LOCAL_BOOTSTRAP")


@dataclass
class SessionRecord:
    """Server-side session record enforcing idle and absolute timeout envelopes."""

    session_id: str
    actor_id: str
    role: str
    is_human: bool
    created_at_utc: float
    last_active_at_utc: float
    csrf_token: str

    def is_expired(
        self,
        now: Optional[float] = None,
        idle_timeout: float = DEFAULT_IDLE_TIMEOUT_SECONDS,
        absolute_lifetime: float = DEFAULT_ABSOLUTE_LIFETIME_SECONDS,
    ) -> tuple[bool, str]:
        """Evaluate if the session is expired under idle or absolute envelopes."""
        current_time = now if now is not None else time.time()
        if (current_time - self.created_at_utc) > absolute_lifetime:
            return True, "ABSOLUTE_LIFETIME_EXCEEDED"
        if (current_time - self.last_active_at_utc) > idle_timeout:
            return True, "IDLE_TIMEOUT_EXCEEDED"
        return False, "VALID"

    def touch(self, now: Optional[float] = None) -> None:
        """Update last active timestamp on authenticated request."""
        self.last_active_at_utc = now if now is not None else time.time()


class LocalCredentialManager:
    """Manages ephemeral local operator credentials with secure file permissions."""

    def __init__(
        self,
        storage_path: Path,
        validity_seconds: float = DEFAULT_CREDENTIAL_VALIDITY_SECONDS,
    ) -> None:
        self.storage_path = storage_path
        self.validity_seconds = validity_seconds

    def _ensure_safe_parent(self) -> None:
        parent = self.storage_path.parent
        if not parent.exists():
            parent.mkdir(parents=True, exist_ok=True)

    def generate_or_load_credential(self, now: Optional[float] = None) -> str:
        """Load an existing valid credential or generate a fresh one with owner-only permissions."""
        self._ensure_safe_parent()
        current_time = now if now is not None else time.time()

        # Reject symlinks unconditionally
        if os.path.islink(self.storage_path):
            raise ValueError(
                f"Unsafe credential path: '{self.storage_path}' is a symbolic link."
            )

        # Check if existing credential file is valid
        if self.storage_path.exists():
            try:
                content = json.loads(self.storage_path.read_text(encoding="utf-8"))
                created_at = content.get("created_at_epoch", 0.0)
                credential = content.get("credential", "")
                if credential and (current_time - created_at) < self.validity_seconds:
                    return str(credential)
            except Exception:
                # Malformed file -> regenerate
                pass

        # Generate fresh 256-bit cryptographically secure credential
        fresh_token = secrets.token_urlsafe(32)
        payload = {
            "credential": fresh_token,
            "created_at_epoch": current_time,
            "created_at_iso": datetime.now(timezone.utc).isoformat(),
            "validity_seconds": self.validity_seconds,
            "role": "LOCAL_EXPLORER",
        }

        # Write securely with 0o600 permissions (owner read/write only)
        flags = os.O_CREAT | os.O_WRONLY | os.O_TRUNC
        mode = stat.S_IRUSR | stat.S_IWUSR  # 0o600
        fd = os.open(self.storage_path, flags, mode)
        try:
            with open(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        finally:
            pass  # open() takes ownership of fd and closes it on exit

        # Ensure mode 0o600 even if umask modified it
        os.chmod(self.storage_path, 0o600)
        return fresh_token

    def verify_credential(self, candidate: str, now: Optional[float] = None) -> bool:
        """Verify candidate credential in constant time against active credential."""
        if not candidate or not isinstance(candidate, str):
            return False
        active_token = self.generate_or_load_credential(now=now)
        return hmac.compare_digest(candidate.strip(), active_token.strip())


class LoginRateLimiter:
    """Tracks failed login attempts per client identifier (IP address) to defend against brute force."""

    def __init__(
        self,
        max_attempts: int = MAX_FAILED_LOGIN_ATTEMPTS,
        window_seconds: float = LOGIN_ATTEMPT_WINDOW_SECONDS,
    ) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._failed_attempts: dict[str, list[float]] = defaultdict(list)

    def is_blocked(self, client_id: str, now: Optional[float] = None) -> tuple[bool, float]:
        """Check if client is currently blocked due to repeated failures."""
        current_time = now if now is not None else time.time()
        cutoff = current_time - self.window_seconds
        # Clean older attempts
        attempts = [t for t in self._failed_attempts[client_id] if t > cutoff]
        self._failed_attempts[client_id] = attempts

        if len(attempts) >= self.max_attempts:
            oldest_relevant = attempts[0]
            cooldown_remaining = max(0.0, self.window_seconds - (current_time - oldest_relevant))
            return True, cooldown_remaining
        return False, 0.0

    def record_failure(self, client_id: str, now: Optional[float] = None) -> None:
        """Record a failed login attempt timestamp for client."""
        current_time = now if now is not None else time.time()
        self._failed_attempts[client_id].append(current_time)

    def reset(self, client_id: str) -> None:
        """Reset failed attempt history upon successful authentication."""
        if client_id in self._failed_attempts:
            del self._failed_attempts[client_id]


class ServerSessionManager:
    """In-memory server-side session registry enforcing idle and absolute timeout envelopes."""

    def __init__(
        self,
        idle_timeout: float = DEFAULT_IDLE_TIMEOUT_SECONDS,
        absolute_lifetime: float = DEFAULT_ABSOLUTE_LIFETIME_SECONDS,
    ) -> None:
        self.idle_timeout = idle_timeout
        self.absolute_lifetime = absolute_lifetime
        self._sessions: dict[str, SessionRecord] = {}

    def create_session(
        self,
        actor_id: str = "local_operator",
        role: str = "LOCAL_EXPLORER",
        is_human: bool = True,
        now: Optional[float] = None,
    ) -> SessionRecord:
        """Create a fresh server-side session with cryptographically secure session and CSRF tokens."""
        current_time = now if now is not None else time.time()
        session_id = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)

        record = SessionRecord(
            session_id=session_id,
            actor_id=actor_id,
            role=role,
            is_human=is_human,
            created_at_utc=current_time,
            last_active_at_utc=current_time,
            csrf_token=csrf_token,
        )
        self._sessions[session_id] = record
        return record

    def get_session(self, session_id: Optional[str], now: Optional[float] = None) -> Optional[SessionRecord]:
        """Retrieve and validate session, updating last_active timestamp if valid."""
        if not session_id or session_id not in self._sessions:
            return None

        record = self._sessions[session_id]
        expired, reason = record.is_expired(
            now=now,
            idle_timeout=self.idle_timeout,
            absolute_lifetime=self.absolute_lifetime,
        )
        if expired:
            del self._sessions[session_id]
            return None

        record.touch(now=now)
        return record

    def invalidate_session(self, session_id: Optional[str]) -> None:
        """Remove a session from the registry upon logout or revocation."""
        if session_id and session_id in self._sessions:
            del self._sessions[session_id]

    def validate_csrf(self, session: SessionRecord, candidate_token: Optional[str]) -> bool:
        """Verify candidate CSRF token against session token in constant time."""
        if not candidate_token or not isinstance(candidate_token, str):
            return False
        return hmac.compare_digest(session.csrf_token.strip(), candidate_token.strip())

    @property
    def active_session_count(self) -> int:
        """Return total active sessions in memory."""
        return len(self._sessions)
