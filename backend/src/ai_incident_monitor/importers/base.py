"""Base classes, import limits, and cryptographic file digest computation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import hashlib
import os
from pathlib import Path
import shutil
from typing import Any, Optional

from ai_incident_monitor.db.session import get_repo_root

MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB maximum upload size
MAX_ROWS_PER_IMPORT: int = 5_000  # 5,000 rows max per manual import batch


@dataclass
class ImportRecordResult:
    """Outcome for a single row processed during an import batch."""

    row_index: int
    status: str  # "IMPORTED", "POTENTIAL_DUPLICATE", "SKIPPED", "ERROR"
    incident_id: Optional[str] = None
    error: Optional[str] = None


@dataclass
class ImportBatchSummary:
    """Summary metrics and audit results for an entire import batch."""

    batch_id: str
    filename: str
    source_format: str
    content_hash: str
    total_rows: int = 0
    imported_count: int = 0
    duplicate_count: int = 0
    error_count: int = 0
    staged_path: Optional[str] = None
    records: list[ImportRecordResult] = field(default_factory=list)


def compute_file_sha256(file_path: Path | str) -> str:
    """Compute 64-character hexadecimal SHA-256 digest of a file using 64KB chunks."""
    path = Path(file_path)
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def stage_raw_upload(source_path: Path | str, batch_id: str, filename: str) -> Path:
    """Stage uploaded file in $REPO_ROOT/.data/raw_imports/<batch_id>/ per DEC-P3-002.

    The staging directory is inside the workspace, strictly gitignored, and subjected to a 30-day purge TTL.
    """
    path = Path(source_path)
    staging_dir = get_repo_root() / ".data" / "raw_imports" / batch_id
    staging_dir.mkdir(parents=True, exist_ok=True)
    destination = staging_dir / filename
    shutil.copy2(path, destination)
    return destination


class BaseImporter(ABC):
    """Abstract base class for manual incident file importers."""

    def __init__(self, max_file_size: int = MAX_FILE_SIZE_BYTES, max_rows: int = MAX_ROWS_PER_IMPORT) -> None:
        self.max_file_size = max_file_size
        self.max_rows = max_rows

    def validate_file_size(self, file_path: Path | str) -> None:
        """Verify that the target file does not exceed allowed size limits."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Import file '{file_path}' does not exist.")
        size = path.stat().st_size
        if size > self.max_file_size:
            raise ValueError(
                f"File size ({size} bytes) exceeds maximum limit ({self.max_file_size} bytes)."
            )

    @abstractmethod
    def parse_rows(self, file_path: Path | str) -> list[dict[str, Any]]:
        """Extract and sanitize raw row dictionaries from the target file."""
        ...
