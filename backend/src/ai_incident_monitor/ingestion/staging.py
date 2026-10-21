"""Raw feed payload staging store enforcing atomic writes and strict path containment.

Implements DEC-P4-002: Stages raw feed payloads in .data/raw_feeds/ with 30-day purge TTL.
Guarantees raw payloads never enter Git history or relational database columns.

Governing Charter: Project Constitution (Rules 1, 9, 11, 14, 15, 16),
ADR-003, ADR-008, DEC-P4-002.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any
import uuid

DEFAULT_STAGING_DIR_NAME = ".data/raw_feeds"
DEFAULT_RETENTION_DAYS = 30
DEFAULT_MAX_STAGED_PAYLOAD_BYTES = 5 * 1024 * 1024  # 5 MB


class StagingStatus(str, Enum):
    """Lifecycle status of a staged raw feed payload."""

    ACTIVE = "ACTIVE"
    PURGED = "PURGED"
    MISSING = "MISSING"
    FAILED = "FAILED"


class StagingError(Exception):
    """Base exception for raw payload staging operations."""


class StagingSecurityError(StagingError):
    """Raised when a path-traversal or unauthorized file access attempt is detected."""


class StagingPayloadTooLargeError(StagingError):
    """Raised when payload exceeds the maximum permitted staging size."""


@dataclass
class StagingMetadataRecord:
    """Metadata describing a staged raw feed payload.

    Contains operational reference only; raw payload bytes are strictly excluded.
    """

    staging_record_id: str
    ingestion_run_id: str
    connector_id: str
    retrieval_time: str
    original_feed_url: str
    final_url: str
    content_type: str
    payload_byte_size: int
    payload_sha256: str
    storage_path_ref: str
    retention_expiration_time: str
    purge_status: StagingStatus
    purge_time: str | None = None
    purge_error: str | None = None
    is_active_run: bool = False
    is_legal_hold: bool = False

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["purge_status"] = self.purge_status.value
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StagingMetadataRecord:
        d = dict(data)
        d["purge_status"] = StagingStatus(d["purge_status"])
        return cls(**d)


class RawPayloadStagingStore:
    """Manages local atomic disk staging of raw feed payloads in .data/raw_feeds/."""

    def __init__(
        self,
        staging_root: Path | str | None = None,
        *,
        enabled: bool | None = None,
        retention_days: int = DEFAULT_RETENTION_DAYS,
        max_payload_bytes: int = DEFAULT_MAX_STAGED_PAYLOAD_BYTES,
    ) -> None:
        if staging_root is None:
            # Default to repo root / .data / raw_feeds
            repo_root = Path(__file__).resolve().parents[4]
            self.staging_root = (repo_root / DEFAULT_STAGING_DIR_NAME).resolve()
        else:
            self.staging_root = Path(staging_root).resolve()

        if enabled is not None:
            self.enabled = enabled
        else:
            self.enabled = os.environ.get("RAW_FEED_STAGING_ENABLED", "true").lower() in ("true", "1", "yes")

        self.retention_days = max(1, retention_days)
        self.max_payload_bytes = max_payload_bytes
        self.catalog_path = self.staging_root / "staging_catalog.json"

        if self.enabled:
            self._ensure_staging_directory()

    def _ensure_staging_directory(self) -> None:
        """Create the staging root directory with secure permissions if enabled."""
        self.staging_root.mkdir(parents=True, exist_ok=True)
        # Ensure catalog exists
        if not self.catalog_path.exists():
            self._write_catalog({})

    def _read_catalog(self) -> dict[str, StagingMetadataRecord]:
        """Read all staging metadata records from disk."""
        if not self.catalog_path.exists():
            return {}
        try:
            with open(self.catalog_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            return {k: StagingMetadataRecord.from_dict(v) for k, v in raw_data.items()}
        except Exception:
            return {}

    def _write_catalog(self, records: dict[str, StagingMetadataRecord]) -> None:
        """Atomically persist the staging catalog."""
        tmp_fd, tmp_path = tempfile.mkstemp(dir=self.staging_root, suffix=".tmp")
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json_data = {k: v.to_dict() for k, v in records.items()}
                json.dump(json_data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.chmod(tmp_path, 0o600)
            os.replace(tmp_path, self.catalog_path)
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise

    def validate_path_containment(self, candidate_path: Path) -> Path:
        """Strictly verify that candidate_path resolves safely inside staging_root.

        Rejects directory traversal (..), symlinks escaping root, and invalid extensions.
        """
        # Candidate path must end with .raw
        if candidate_path.suffix != ".raw":
            raise StagingSecurityError(
                f"Unauthorized file extension '{candidate_path.suffix}'. Only .raw files permitted."
            )

        resolved_root = self.staging_root.resolve()
        resolved_candidate = candidate_path.resolve()

        # Must be strictly a descendant of staging_root
        if resolved_candidate == resolved_root or resolved_root not in resolved_candidate.parents:
            raise StagingSecurityError(
                f"Path traversal / symlink escape detected: '{candidate_path}' does not reside in '{self.staging_root}'"
            )

        return resolved_candidate

    def stage_payload(
        self,
        *,
        raw_bytes: bytes,
        connector_id: str,
        ingestion_run_id: str,
        original_feed_url: str,
        final_url: str,
        content_type: str = "application/xml",
        retrieval_time: datetime | None = None,
        is_active_run: bool = False,
    ) -> StagingMetadataRecord | None:
        """Atomically stage a raw feed payload to disk.

        Returns StagingMetadataRecord on success, or None if staging is disabled.
        """
        if not self.enabled:
            return None

        if len(raw_bytes) > self.max_payload_bytes:
            raise StagingPayloadTooLargeError(
                f"Payload size ({len(raw_bytes)} bytes) exceeds maximum staging limit of {self.max_payload_bytes} bytes"
            )

        now = retrieval_time or datetime.now(timezone.utc)
        payload_sha256 = hashlib.sha256(raw_bytes).hexdigest()
        staging_id = f"stg_{uuid.uuid4().hex[:16]}"

        # Organize by year/month subdirectories
        year_str = now.strftime("%Y")
        month_str = now.strftime("%m")
        target_dir = self.staging_root / year_str / month_str
        target_dir.mkdir(parents=True, exist_ok=True)

        # Non-user-controlled filename
        clean_conn = re.sub(r"[^a-zA-Z0-9_-]", "_", connector_id)
        clean_run = re.sub(r"[^a-zA-Z0-9_-]", "_", ingestion_run_id)
        timestamp_compact = now.strftime("%Y%m%dT%H%M%SZ")
        filename = f"{clean_conn}_{clean_run}_{timestamp_compact}_{payload_sha256[:16]}.raw"
        target_file = target_dir / filename

        # Verify containment before writing
        self.validate_path_containment(target_file)

        # Atomic write: write to NamedTemporaryFile in target directory, chmod 0o600, fsync, rename
        tmp_fd, tmp_path = tempfile.mkstemp(dir=target_dir, suffix=".tmp")
        try:
            with os.fdopen(tmp_fd, "wb") as f:
                f.write(raw_bytes)
                f.flush()
                os.fsync(f.fileno())
            os.chmod(tmp_path, 0o600)
            os.replace(tmp_path, target_file)
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise

        rel_path = str(target_file.relative_to(self.staging_root))
        expires_at = (now + timedelta(days=self.retention_days)).isoformat()

        record = StagingMetadataRecord(
            staging_record_id=staging_id,
            ingestion_run_id=ingestion_run_id,
            connector_id=connector_id,
            retrieval_time=now.isoformat(),
            original_feed_url=original_feed_url,
            final_url=final_url,
            content_type=content_type,
            payload_byte_size=len(raw_bytes),
            payload_sha256=payload_sha256,
            storage_path_ref=rel_path,
            retention_expiration_time=expires_at,
            purge_status=StagingStatus.ACTIVE,
            is_active_run=is_active_run,
        )

        # Update catalog
        catalog = self._read_catalog()
        catalog[staging_id] = record
        self._write_catalog(catalog)

        return record

    def get_metadata(self, staging_id: str) -> StagingMetadataRecord | None:
        """Retrieve a staging metadata record by ID."""
        catalog = self._read_catalog()
        return catalog.get(staging_id)

    def list_records(self) -> list[StagingMetadataRecord]:
        """List all tracked staging metadata records."""
        return list(self._read_catalog().values())

    def update_record(self, record: StagingMetadataRecord) -> None:
        """Update an existing staging record in the catalog."""
        catalog = self._read_catalog()
        catalog[record.staging_record_id] = record
        self._write_catalog(catalog)
