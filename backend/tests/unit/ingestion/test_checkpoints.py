"""Unit tests for durable checkpoint persistence and invariants."""

from pathlib import Path
import pytest

from ai_incident_monitor.ingestion.checkpoints import CheckpointStore, SourceCheckpoint


class TestCheckpointStore:
    """Validate checkpoint read/write consistency, atomic safety, and timestamp invariants."""

    def test_empty_store_returns_empty_dict(self, tmp_path: Path) -> None:
        store = CheckpointStore(tmp_path / "checkpoints.json")
        assert store.load_all() == {}

        cp = store.get_checkpoint("nonexistent")
        assert cp.source_id == "nonexistent"
        assert cp.last_status == "NEVER_RUN"
        assert cp.last_success_utc is None

    def test_save_successful_checkpoint_updates_last_success(self, tmp_path: Path) -> None:
        store = CheckpointStore(tmp_path / "checkpoints.json")
        cp = store.save_checkpoint(
            "src_test",
            status="SUCCESS",
            etag='"xyz123"',
            last_modified="Mon, 20 Oct 2026 08:30:00 GMT",
            records_fetched=5,
            records_created=2,
            records_updated=3,
        )

        assert cp.last_status == "SUCCESS"
        assert cp.last_run_utc is not None
        assert cp.last_success_utc is not None
        assert cp.etag == '"xyz123"'
        assert cp.records_created == 2

        # Verify on re-read from disk
        reloaded = store.get_checkpoint("src_test")
        assert reloaded.last_status == "SUCCESS"
        assert reloaded.last_success_utc == cp.last_success_utc

    def test_invariant_failed_run_does_not_update_last_success(self, tmp_path: Path) -> None:
        store = CheckpointStore(tmp_path / "checkpoints.json")
        # 1. Successful run sets last_success_utc
        initial = store.save_checkpoint("src_test", status="SUCCESS", records_fetched=3)
        initial_success_time = initial.last_success_utc
        assert initial_success_time is not None

        # 2. Subsequent failed run must NOT update last_success_utc
        failed = store.save_checkpoint(
            "src_test",
            status="FAILED",
            error_message="HTTP 500 Connection reset",
        )
        assert failed.last_status == "FAILED"
        assert failed.last_run_utc > initial_success_time
        assert failed.last_success_utc == initial_success_time  # Invariant: preserved!
        assert failed.error_message == "HTTP 500 Connection reset"

    def test_not_modified_run_preserves_tokens(self, tmp_path: Path) -> None:
        store = CheckpointStore(tmp_path / "checkpoints.json")
        store.save_checkpoint("src_test", status="SUCCESS", etag='"token1"')

        # HTTP 304 response (not modified) passed without new etag
        not_mod = store.save_checkpoint("src_test", status="NOT_MODIFIED")
        assert not_mod.last_status == "NOT_MODIFIED"
        assert not_mod.etag == '"token1"'  # Invariant: token preserved
