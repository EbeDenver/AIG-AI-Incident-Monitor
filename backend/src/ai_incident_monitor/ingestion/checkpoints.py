"""Durable checkpoint persistence for ingestion sources.

Tracks per-source run timestamps, HTTP conditional validation tokens (ETag,
Last-Modified), and processing metrics across CLI, scheduled, and portal runs.

Governing Charter: Project Constitution (Rules 1, 4, 11, 14, 16),
ADR-008, AUD-004.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from ai_incident_monitor.db.session import get_repo_root


class SourceCheckpoint(BaseModel):
    """Execution state and metrics for an individual source."""

    source_id: str
    last_run_utc: Optional[str] = None
    last_success_utc: Optional[str] = None
    last_status: str = "NEVER_RUN"
    etag: Optional[str] = None
    last_modified: Optional[str] = None
    last_seen_item_id: Optional[str] = None
    records_fetched: int = 0
    records_created: int = 0
    records_updated: int = 0
    records_skipped: int = 0
    records_failed: int = 0
    error_message: Optional[str] = None


class CheckpointStore:
    """Atomic persistent store for source ingestion checkpoints."""

    def __init__(self, file_path: Optional[Path] = None) -> None:
        if file_path is None:
            repo_root = get_repo_root()
            self.file_path = repo_root / ".data" / "ingestion_checkpoints.json"
        else:
            self.file_path = file_path

    def _ensure_dir(self) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def load_all(self) -> dict[str, SourceCheckpoint]:
        """Load all checkpoints from disk. Returns empty dict if file does not exist."""
        if not self.file_path.exists():
            return {}

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {}
            return {
                k: SourceCheckpoint(**v)
                for k, v in data.items()
                if isinstance(v, dict)
            }
        except Exception:
            return {}

    def get_checkpoint(self, source_id: str) -> SourceCheckpoint:
        """Retrieve checkpoint for specific source or a fresh empty checkpoint."""
        all_cps = self.load_all()
        return all_cps.get(source_id, SourceCheckpoint(source_id=source_id))

    def save_checkpoint(
        self,
        source_id: str,
        *,
        status: str,
        etag: Optional[str] = None,
        last_modified: Optional[str] = None,
        last_seen_item_id: Optional[str] = None,
        records_fetched: int = 0,
        records_created: int = 0,
        records_updated: int = 0,
        records_skipped: int = 0,
        records_failed: int = 0,
        error_message: Optional[str] = None,
    ) -> SourceCheckpoint:
        """Update and atomically persist a source checkpoint.
        
        INVARIANT: last_success_utc is ONLY updated when status indicates success
        (e.g. SUCCESS or NOT_MODIFIED). It is never updated on failure.
        """
        self._ensure_dir()
        all_cps = self.load_all()

        now_utc = datetime.now(timezone.utc).isoformat()
        current = all_cps.get(source_id, SourceCheckpoint(source_id=source_id))

        is_success = status in ("SUCCESS", "NOT_MODIFIED")
        last_success = now_utc if is_success else current.last_success_utc

        # Preserve previous etag/last_modified if not newly provided
        resolved_etag = etag if etag is not None else current.etag
        resolved_last_modified = last_modified if last_modified is not None else current.last_modified
        resolved_last_seen = last_seen_item_id if last_seen_item_id is not None else current.last_seen_item_id

        updated = SourceCheckpoint(
            source_id=source_id,
            last_run_utc=now_utc,
            last_success_utc=last_success,
            last_status=status,
            etag=resolved_etag,
            last_modified=resolved_last_modified,
            last_seen_item_id=resolved_last_seen,
            records_fetched=records_fetched,
            records_created=records_created,
            records_updated=records_updated,
            records_skipped=records_skipped,
            records_failed=records_failed,
            error_message=error_message,
        )

        all_cps[source_id] = updated

        # Atomic file write pattern
        tmp_path = self.file_path.with_suffix(".tmp")
        payload = {k: v.model_dump() for k, v in all_cps.items()}
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
        os.replace(tmp_path, self.file_path)

        return updated
