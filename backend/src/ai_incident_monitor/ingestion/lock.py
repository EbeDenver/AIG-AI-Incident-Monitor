"""Shared concurrency locking and stale-state recovery for ingestion runs.

Enforces mutual exclusion across CLI, scheduled, and portal-triggered executions
using OS-level advisory locks (fcntl.flock) and process-liveness verification.

Governing Charter: Project Constitution (Rules 1, 11, 14, 16),
ADR-008, AUD-004.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
from typing import Any, Optional

from ai_incident_monitor.db.session import get_repo_root


@dataclass
class ActiveRunInfo:
    """Metadata describing an actively executing ingestion run."""

    pid: int
    trigger: str
    run_id: str
    started_at_utc: str


class IngestionActiveConflictError(Exception):
    """Raised when an ingestion run is already active and cannot be interrupted."""

    def __init__(self, active_info: ActiveRunInfo) -> None:
        self.active_info = active_info
        super().__init__(
            f"Ingestion run '{active_info.run_id}' (trigger: {active_info.trigger}, "
            f"pid: {active_info.pid}) is currently in progress since {active_info.started_at_utc}."
        )


def is_process_alive(pid: int) -> bool:
    """Verify whether a process with given PID exists and is running."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


class IngestionLock:
    """Exclusive flock-based concurrency lock with stale process detection."""

    def __init__(
        self,
        *,
        trigger: str,
        run_id: str,
        lock_file_path: Optional[Path] = None,
    ) -> None:
        if lock_file_path is None:
            repo_root = get_repo_root()
            self.lock_file_path = repo_root / ".data" / "ingestion.lock"
        else:
            self.lock_file_path = lock_file_path

        self.trigger = trigger
        self.run_id = run_id
        self._fd: Optional[int] = None
        self._is_acquired = False

    def _ensure_dir(self) -> None:
        self.lock_file_path.parent.mkdir(parents=True, exist_ok=True)

    def read_active_info(self) -> Optional[ActiveRunInfo]:
        """Read active run metadata from lock file if present and valid."""
        if not self.lock_file_path.exists():
            return None
        try:
            with open(self.lock_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "pid" in data and "run_id" in data:
                return ActiveRunInfo(
                    pid=int(data["pid"]),
                    trigger=str(data.get("trigger", "unknown")),
                    run_id=str(data["run_id"]),
                    started_at_utc=str(data.get("started_at_utc", "")),
                )
        except Exception:
            pass
        return None

    def acquire(self) -> None:
        """Acquire exclusive non-blocking lock.
        
        Raises IngestionActiveConflictError if held by an active running process.
        Recovers automatically if the recorded PID is dead (stale lock).
        """
        self._ensure_dir()
        fd = os.open(str(self.lock_file_path), os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (BlockingIOError, OSError):
            # Another process holds the kernel flock.
            # Close file descriptor and inspect metadata.
            os.close(fd)
            active_info = self.read_active_info()
            if active_info and is_process_alive(active_info.pid):
                raise IngestionActiveConflictError(active_info)

            # If flock blocked but process is dead, retry once after short wait
            # in case process just exited and kernel released
            raise IngestionActiveConflictError(
                active_info
                or ActiveRunInfo(
                    pid=-1,
                    trigger="unknown",
                    run_id="unknown",
                    started_at_utc=datetime.now(timezone.utc).isoformat(),
                )
            )

        # We acquired the OS-level flock. Check if previous content was from a dead PID (stale)
        # and overwrite with our run metadata.
        self._fd = fd
        self._is_acquired = True

        payload = {
            "pid": os.getpid(),
            "trigger": self.trigger,
            "run_id": self.run_id,
            "started_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        os.ftruncate(fd, 0)
        os.lseek(fd, 0, os.SEEK_SET)
        os.write(fd, json.dumps(payload, indent=2).encode("utf-8"))
        os.fsync(fd)

    def release(self) -> None:
        """Release the flock and clean up lock file."""
        if self._fd is not None:
            try:
                # Clear content before unlocking
                try:
                    os.ftruncate(self._fd, 0)
                    os.fsync(self._fd)
                except OSError:
                    pass
                fcntl.flock(self._fd, fcntl.LOCK_UN)
                os.close(self._fd)
            except OSError:
                pass
            finally:
                self._fd = None
                self._is_acquired = False

            # Remove file if empty/unlocked
            try:
                if self.lock_file_path.exists():
                    self.lock_file_path.unlink(missing_ok=True)
            except OSError:
                pass

    def __enter__(self) -> IngestionLock:
        self.acquire()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.release()
