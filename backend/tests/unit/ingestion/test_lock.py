"""Unit tests for shared concurrency locking and stale-state recovery."""

import json
import os
from pathlib import Path
import pytest

from ai_incident_monitor.ingestion.lock import (
    IngestionActiveConflictError,
    IngestionLock,
    is_process_alive,
)


class TestIngestionLock:
    """Validate concurrency mutual exclusion, process liveness, and stale lock recovery."""

    def test_process_liveness_check(self) -> None:
        # Current process is alive
        assert is_process_alive(os.getpid())
        # Invalid PID <= 0 is not alive
        assert not is_process_alive(-1)
        assert not is_process_alive(0)
        # Unallocated high PID is not alive
        assert not is_process_alive(99999999)

    def test_single_lock_acquire_and_release(self, tmp_path: Path) -> None:
        lock_file = tmp_path / "ingestion.lock"
        lock = IngestionLock(trigger="cli", run_id="run_001", lock_file_path=lock_file)

        with lock:
            assert lock_file.exists()
            info = lock.read_active_info()
            assert info is not None
            assert info.pid == os.getpid()
            assert info.run_id == "run_001"
            assert info.trigger == "cli"

        # Released
        assert not lock_file.exists()

    def test_concurrent_lock_conflict_detection(self, tmp_path: Path) -> None:
        lock_file = tmp_path / "ingestion.lock"
        lock1 = IngestionLock(trigger="cli", run_id="run_001", lock_file_path=lock_file)
        lock2 = IngestionLock(trigger="portal", run_id="run_002", lock_file_path=lock_file)

        lock1.acquire()
        try:
            # Second acquire while first is held must raise IngestionActiveConflictError
            with pytest.raises(IngestionActiveConflictError) as exc_info:
                lock2.acquire()

            conflict = exc_info.value.active_info
            assert conflict.run_id == "run_001"
            assert conflict.trigger == "cli"
            assert conflict.pid == os.getpid()
        finally:
            lock1.release()

        # After lock1 releases, lock2 can acquire cleanly
        lock2.acquire()
        lock2.release()

    def test_stale_lock_recovery_when_pid_dead(self, tmp_path: Path) -> None:
        lock_file = tmp_path / "ingestion.lock"

        # Write a simulated dead PID to the lock file
        dead_pid = 99999999
        assert not is_process_alive(dead_pid)

        payload = {
            "pid": dead_pid,
            "trigger": "scheduled",
            "run_id": "stale_run",
            "started_at_utc": "2026-11-01T00:00:00Z",
        }
        lock_file.write_text(json.dumps(payload), encoding="utf-8")

        # New lock should be able to acquire because no process holds the kernel flock on the file
        lock = IngestionLock(trigger="cli", run_id="recovery_run", lock_file_path=lock_file)
        lock.acquire()
        try:
            info = lock.read_active_info()
            assert info is not None
            assert info.run_id == "recovery_run"
            assert info.pid == os.getpid()
        finally:
            lock.release()
