"""Streaming XLSX spreadsheet parser with cached formula value handling and injection defense."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import openpyxl

from ai_incident_monitor.importers.base import BaseImporter
from ai_incident_monitor.importers.sanitizers import sanitize_row_dict


class XLSXImporter(BaseImporter):
    """Parses Excel XLSX files using read_only and data_only mode (DEC-P3-004 XLSX Clarification).

    TECHNICAL NOTE & LIMITATION:
    openpyxl with data_only=True reads the last cached calculated value stored by
    Excel/LibreOffice when the spreadsheet was last saved. openpyxl does NOT evaluate
    formulas itself. If a formula cell was never evaluated or has no cached value,
    cell.value will be None.

    Per Constitutional Rule 2, any missing cached value is treated strictly as
    missing/unknown (None / UNKNOWN). It is NEVER coerced to zero or extrapolated.
    """

    def parse_rows(self, file_path: Path | str) -> list[dict[str, Any]]:
        """Read active worksheet rows, extracting cached values and sanitizing formula text."""
        self.validate_file_size(file_path)
        path = Path(file_path)

        wb = openpyxl.load_workbook(
            filename=str(path),
            read_only=True,
            data_only=True,  # Extract last cached formula values
            keep_links=False,
        )

        try:
            ws = wb.active
            if ws is None:
                return []

            rows_iter = ws.iter_rows(values_only=True)
            try:
                header_row = next(rows_iter)
            except StopIteration:
                return []

            if not header_row:
                return []

            # Clean and normalize header strings
            headers: list[str] = [
                str(col).strip() if col is not None else f"col_{idx}"
                for idx, col in enumerate(header_row)
            ]

            rows: list[dict[str, Any]] = []
            for row_idx, row_values in enumerate(rows_iter, start=1):
                if row_idx > self.max_rows:
                    raise ValueError(
                        f"File exceeds maximum allowed row limit of {self.max_rows} rows."
                    )

                # Skip completely blank rows
                if not any(v is not None for v in row_values):
                    continue

                raw_row: dict[str, Any] = {}
                for idx, val in enumerate(row_values):
                    if idx < len(headers):
                        header_name = headers[idx]
                        # Missing cached formula value remains None (Constitutional Rule 2)
                        raw_row[header_name] = val

                sanitized = sanitize_row_dict(raw_row)
                rows.append(sanitized)

            return rows
        finally:
            wb.close()
