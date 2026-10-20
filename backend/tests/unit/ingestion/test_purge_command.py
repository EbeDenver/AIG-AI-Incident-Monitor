"""Unit tests for the 30-day raw feed purge maintenance command and audit trail (DEC-P4-002)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

from ai_incident_monitor.ingestion.purge import (
    PurgeResult,
    purge_staged_feeds,
)
from ai_incident_monitor.ingestion.staging import (
    RawPayloadStagingStore,
    StagingMetadataRecord,
    StagingStatus,
)


class TestPurgeCommand:
    """Verifies deterministic purge behavior, 30-day boundary, dry-run, and audit trail."""

    def test_30_day_retention_boundary_enforced(self, tmp_path: Path) -> None:
        store = RawPayloadStagingStore(staging_root=tmp_path, retention_days=30)
        now = datetime.now(timezone.utc)

        # 1. Old record (retrieved 31 days ago)
        old_time = now - timedelta(days=31)
        rec_old = store.stage_payload(
            raw_bytes=b"Old payload from 31 days ago",
            connector_id="rss_old",
            ingestion_run_id="run_old",
            original_feed_url="https://example.com/old",
            final_url="https://example.com/old",
            retrieval_time=old_time,
        )
        assert rec_old is not None
        old_file = tmp_path / rec_old.storage_path_ref

        # 2. Recent record (retrieved 5 days ago)
        recent_time = now - timedelta(days=5)
        rec_recent = store.stage_payload(
            raw_bytes=b"Recent payload from 5 days ago",
            connector_id="rss_recent",
            ingestion_run_id="run_recent",
            original_feed_url="https://example.com/recent",
            final_url="https://example.com/recent",
            retrieval_time=recent_time,
        )
        assert rec_recent is not None
        recent_file = tmp_path / rec_recent.storage_path_ref

        # Execute purge
        result = purge_staged_feeds(store, retention_days=30, current_time=now)
        assert result.candidates_count == 1
        assert result.deleted_count == 1

        # Old file was purged
        assert not old_file.exists()
        updated_old = store.get_metadata(rec_old.staging_record_id)
        assert updated_old is not None
        assert updated_old.purge_status == StagingStatus.PURGED
        assert updated_old.purge_time is not None

        # Recent file was preserved
        assert recent_file.exists()
        updated_recent = store.get_metadata(rec_recent.staging_record_id)
        assert updated_recent is not None
        assert updated_recent.purge_status == StagingStatus.ACTIVE

    def test_dry_run_mode_does_not_delete_files(self, tmp_path: Path) -> None:
        store = RawPayloadStagingStore(staging_root=tmp_path, retention_days=30)
        now = datetime.now(timezone.utc)
        old_time = now - timedelta(days=45)

        rec = store.stage_payload(
            raw_bytes=b"Expired payload",
            connector_id="rss_test",
            ingestion_run_id="run_dry",
            original_feed_url="https://example.com/feed",
            final_url="https://example.com/feed",
            retrieval_time=old_time,
        )
        assert rec is not None
        file_path = tmp_path / rec.storage_path_ref

        result = purge_staged_feeds(store, dry_run=True, current_time=now)
        assert result.dry_run is True
        assert result.candidates_count == 1
        assert result.deleted_count == 0
        assert len(result.audit_events) == 1
        assert result.audit_events[0].outcome == "candidate"

        # File must still exist on disk
        assert file_path.exists()
        # Status must remain ACTIVE
        updated = store.get_metadata(rec.staging_record_id)
        assert updated is not None
        assert updated.purge_status == StagingStatus.ACTIVE

    def test_missing_file_on_disk_updates_status_without_failure(self, tmp_path: Path) -> None:
        store = RawPayloadStagingStore(staging_root=tmp_path, retention_days=30)
        now = datetime.now(timezone.utc)
        old_time = now - timedelta(days=40)

        rec = store.stage_payload(
            raw_bytes=b"Payload that will be deleted manually",
            connector_id="rss_test",
            ingestion_run_id="run_missing",
            original_feed_url="https://example.com/feed",
            final_url="https://example.com/feed",
            retrieval_time=old_time,
        )
        assert rec is not None
        file_path = tmp_path / rec.storage_path_ref

        # Manually delete file behind the store's back
        file_path.unlink()
        assert not file_path.exists()

        result = purge_staged_feeds(store, dry_run=False, current_time=now)
        assert result.candidates_count == 1
        assert result.deleted_count == 0
        assert result.missing_count == 1
        assert result.audit_events[0].outcome == "missing"

        updated = store.get_metadata(rec.staging_record_id)
        assert updated is not None
        assert updated.purge_status == StagingStatus.MISSING

    def test_active_run_protection_skips_purge(self, tmp_path: Path) -> None:
        store = RawPayloadStagingStore(staging_root=tmp_path, retention_days=30)
        now = datetime.now(timezone.utc)
        old_time = now - timedelta(days=40)

        rec = store.stage_payload(
            raw_bytes=b"Payload from active ingestion run",
            connector_id="rss_test",
            ingestion_run_id="run_active",
            original_feed_url="https://example.com/feed",
            final_url="https://example.com/feed",
            retrieval_time=old_time,
            is_active_run=True,  # Active run flag set
        )
        assert rec is not None
        file_path = tmp_path / rec.storage_path_ref

        result = purge_staged_feeds(store, dry_run=False, current_time=now)
        assert result.candidates_count == 1
        assert result.skipped_count == 1
        assert result.deleted_count == 0
        assert result.audit_events[0].outcome == "skipped"
        assert "active/incomplete" in result.audit_events[0].reason

        # File must not be deleted
        assert file_path.exists()

    def test_legal_hold_protection_skips_purge(self, tmp_path: Path) -> None:
        store = RawPayloadStagingStore(staging_root=tmp_path, retention_days=30)
        now = datetime.now(timezone.utc)
        old_time = now - timedelta(days=40)

        rec = store.stage_payload(
            raw_bytes=b"Payload under legal hold",
            connector_id="rss_test",
            ingestion_run_id="run_hold",
            original_feed_url="https://example.com/feed",
            final_url="https://example.com/feed",
            retrieval_time=old_time,
        )
        assert rec is not None
        # Put on legal hold
        rec.is_legal_hold = True
        store.update_record(rec)

        result = purge_staged_feeds(store, dry_run=False, current_time=now)
        assert result.candidates_count == 1
        assert result.skipped_count == 1
        assert result.deleted_count == 0
        assert result.audit_events[0].outcome == "skipped"
        assert "legal hold" in result.audit_events[0].reason

    def test_purge_idempotency(self, tmp_path: Path) -> None:
        store = RawPayloadStagingStore(staging_root=tmp_path, retention_days=30)
        now = datetime.now(timezone.utc)
        old_time = now - timedelta(days=50)

        store.stage_payload(
            raw_bytes=b"Expired payload",
            connector_id="rss_test",
            ingestion_run_id="run_idemp",
            original_feed_url="https://example.com/feed",
            final_url="https://example.com/feed",
            retrieval_time=old_time,
        )

        # Run 1: Deletes file
        res1 = purge_staged_feeds(store, current_time=now)
        assert res1.deleted_count == 1

        # Run 2: Nothing left to purge (already PURGED)
        res2 = purge_staged_feeds(store, current_time=now)
        assert res2.candidates_count == 0
        assert res2.deleted_count == 0
