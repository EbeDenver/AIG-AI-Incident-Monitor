"""Streaming CSV file parser with formula injection sanitization and row limits."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from ai_incident_monitor.importers.base import BaseImporter
from ai_incident_monitor.importers.sanitizers import sanitize_row_dict


class CSVImporter(BaseImporter):
    """Parses and sanitizes CSV files containing AI incident records."""

    def parse_rows(self, file_path: Path | str) -> list[dict[str, Any]]:
        """Read CSV rows, applying formula injection sanitization to all cells."""
        self.validate_file_size(file_path)
        path = Path(file_path)

        rows: list[dict[str, Any]] = []
        try:
            # utf-8-sig automatically strips Excel UTF-8 BOM if present
            with open(path, mode="r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for index, raw_row in enumerate(reader, start=1):
                    if index > self.max_rows:
                        raise ValueError(
                            f"File exceeds maximum allowed row limit of {self.max_rows} rows."
                        )
                    sanitized_row = sanitize_row_dict(raw_row)
                    rows.append(sanitized_row)
        except UnicodeDecodeError:
            # Fallback for legacy Western European CSV files
            with open(path, mode="r", encoding="latin-1", newline="") as f:
                reader = csv.DictReader(f)
                for index, raw_row in enumerate(reader, start=1):
                    if index > self.max_rows:
                        raise ValueError(
                            f"File exceeds maximum allowed row limit of {self.max_rows} rows."
                        )
                    sanitized_row = sanitize_row_dict(raw_row)
                    rows.append(sanitized_row)

        return rows
