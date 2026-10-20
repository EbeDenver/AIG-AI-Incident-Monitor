"""Unit tests for raw feed payload staging and security containment (DEC-P4-002)."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import stat

import pytest

from ai_incident_monitor.ingestion.staging import (
    RawPayloadStagingStore,
    StagingPayloadTooLargeError,
    StagingSecurityError,
    StagingStatus,
)


class TestRawPayloadStaging:
    """Verifies atomic write, file permissions, path containment, and metadata cataloging."""

    def test_atomic_stage_payload_success(self, tmp_path: Path) -> None:
        store = RawPayloadStagingStore(staging_root=tmp_path, retention_days=30)
        raw_content = b"<rss><channel><title>Staged News</title></channel></rss>"

        record = store.stage_payload(
            raw_bytes=raw_content,
            connector_id="rss_news",
            ingestion_run_id="run_12345",
            original_feed_url="https://safe-news.org/feed.xml",
            final_url="https://safe-news.org/feed.xml",
        )

        assert record is not None
        assert record.payload_byte_size == len(raw_content)
        assert record.payload_sha256 == hashlib.sha256(raw_content).hexdigest()
        assert record.purge_status == StagingStatus.ACTIVE

        # Verify staged file exists on disk
        target_file = tmp_path / record.storage_path_ref
        assert target_file.exists()
        assert target_file.read_bytes() == raw_content

        # Verify POSIX permissions: 0600 (owner read/write only)
        file_mode = stat.S_IMODE(target_file.stat().st_mode)
        assert file_mode == 0o600

    def test_non_user_controlled_filename_structure(self, tmp_path: Path) -> None:
        store = RawPayloadStagingStore(staging_root=tmp_path)
        payload = b"payload test"

        # User attempts to supply path traversal / hostile chars in IDs
        record = store.stage_payload(
            raw_bytes=payload,
            connector_id="../../malicious_connector",
            ingestion_run_id="run/inject/attack",
            original_feed_url="https://example.com/feed",
            final_url="https://example.com/feed",
        )
        assert record is not None
        # Verify hostile path characters were stripped/sanitized in filename
        filename = Path(record.storage_path_ref).name
        assert ".." not in filename
        assert "/" not in filename
        assert filename.endswith(".raw")

    def test_staging_disabled_returns_none_and_writes_nothing(self, tmp_path: Path) -> None:
        store = RawPayloadStagingStore(staging_root=tmp_path, enabled=False)
        record = store.stage_payload(
            raw_bytes=b"should not be written",
            connector_id="rss_disabled",
            ingestion_run_id="run_000",
            original_feed_url="https://example.com/feed",
            final_url="https://example.com/feed",
        )
        assert record is None
        assert len(list(tmp_path.glob("**/*.raw"))) == 0

    def test_payload_exceeding_max_limit_rejected(self, tmp_path: Path) -> None:
        store = RawPayloadStagingStore(staging_root=tmp_path, max_payload_bytes=100)
        oversized = b"A" * 150
        with pytest.raises(StagingPayloadTooLargeError) as exc_info:
            store.stage_payload(
                raw_bytes=oversized,
                connector_id="rss_news",
                ingestion_run_id="run_999",
                original_feed_url="https://example.com/feed",
                final_url="https://example.com/feed",
            )
        assert "exceeds maximum staging limit" in str(exc_info.value)

    def test_path_containment_rejects_directory_traversal(self, tmp_path: Path) -> None:
        store = RawPayloadStagingStore(staging_root=tmp_path)
        # Attempting traversal outside tmp_path
        traversal_target = tmp_path / ".." / "outside.raw"
        with pytest.raises(StagingSecurityError) as exc_info:
            store.validate_path_containment(traversal_target)
        assert "Path traversal" in str(exc_info.value)

    def test_path_containment_rejects_unauthorized_extensions(self, tmp_path: Path) -> None:
        store = RawPayloadStagingStore(staging_root=tmp_path)
        bad_extension_target = tmp_path / "payload.sh"
        with pytest.raises(StagingSecurityError) as exc_info:
            store.validate_path_containment(bad_extension_target)
        assert "Unauthorized file extension" in str(exc_info.value)

    def test_path_containment_rejects_symlink_escape(self, tmp_path: Path) -> None:
        store = RawPayloadStagingStore(staging_root=tmp_path)
        outside_dir = tmp_path.parent / "outside_dir"
        outside_dir.mkdir(exist_ok=True)
        outside_file = outside_dir / "target.raw"
        outside_file.write_bytes(b"outside")

        # Create symlink inside staging pointing outside
        symlink_path = tmp_path / "escape_link.raw"
        symlink_path.symlink_to(outside_file)

        with pytest.raises(StagingSecurityError) as exc_info:
            store.validate_path_containment(symlink_path)
        assert "Path traversal / symlink escape detected" in str(exc_info.value)

    def test_catalog_tracks_metadata_without_raw_payload_bytes(self, tmp_path: Path) -> None:
        store = RawPayloadStagingStore(staging_root=tmp_path)
        payload = b"SECRET RAW COPYRIGHTED CONTENT NEVER IN CATALOG"

        record = store.stage_payload(
            raw_bytes=payload,
            connector_id="rss_feed",
            ingestion_run_id="run_cat",
            original_feed_url="https://example.com/feed",
            final_url="https://example.com/feed",
        )
        assert record is not None

        # Inspect raw catalog JSON on disk
        catalog_content = store.catalog_path.read_text(encoding="utf-8")
        assert "SECRET RAW COPYRIGHTED CONTENT" not in catalog_content
        assert record.payload_sha256 in catalog_content
        assert record.storage_path_ref in catalog_content
