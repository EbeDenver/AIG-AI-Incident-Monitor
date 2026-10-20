"""JSON and NDJSON file parser with formula injection sanitization and row limits."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ai_incident_monitor.importers.base import BaseImporter
from ai_incident_monitor.importers.sanitizers import sanitize_row_dict


class JSONImporter(BaseImporter):
    """Parses and sanitizes JSON or NDJSON files containing AI incident records."""

    def parse_rows(self, file_path: Path | str) -> list[dict[str, Any]]:
        """Read JSON records, applying formula injection sanitization to all fields."""
        self.validate_file_size(file_path)
        path = Path(file_path)

        with open(path, mode="r", encoding="utf-8") as f:
            content = f.read().strip()

        if not content:
            return []

        raw_records: list[dict[str, Any]] = []

        # Attempt to parse as standard JSON array or wrapped object
        if content.startswith(("[", "{")):
            try:
                parsed = json.loads(content)
                if isinstance(parsed, list):
                    raw_records = parsed
                elif isinstance(parsed, dict):
                    # Check for common wrapper keys like "incidents" or "items"
                    for key in ("incidents", "items", "records", "data"):
                        if key in parsed and isinstance(parsed[key], list):
                            raw_records = parsed[key]
                            break
                    if not raw_records:
                        raw_records = [parsed]
            except json.JSONDecodeError:
                # May be newline-delimited JSON
                raw_records = []

        if not raw_records:
            # Fallback to JSON Lines (NDJSON)
            for line in content.splitlines():
                line = line.strip()
                if line:
                    raw_records.append(json.loads(line))

        if len(raw_records) > self.max_rows:
            raise ValueError(
                f"File exceeds maximum allowed row limit of {self.max_rows} rows."
            )

        sanitized_rows: list[dict[str, Any]] = []
        for rec in raw_records:
            if isinstance(rec, dict):
                sanitized_rows.append(sanitize_row_dict(rec))

        return sanitized_rows
