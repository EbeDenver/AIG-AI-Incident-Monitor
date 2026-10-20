"""OECD Export Adapter implementing official export and fixture parsing (DEC-P4-001).

Zero live scraping, zero polling of undocumented endpoints, formula injection defense,
and preservation of raw OECD records with explicit epistemic separation.

Governing Charter: Project Constitution (Rules 1, 3, 7, 9, 11, 14, 15, 16),
ADR-008, ADR-009, DEC-P4-001.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from enum import Enum
import hashlib
import io
import json
import os
from pathlib import Path
from typing import Any, BinaryIO
import urllib.parse

import openpyxl

from ai_incident_monitor.importers.oecd_mapper import COLUMN_ALIASES, _find_field_value
from ai_incident_monitor.importers.sanitizers import (
    sanitize_cell_value,
    sanitize_formula_injection,
    sanitize_row_dict,
)
from ai_incident_monitor.ingestion.connectors.base import ConnectorDisabledError
from ai_incident_monitor.ingestion.models import IngestedItem


class OECDSourceMode(str, Enum):
    """Permitted source ingestion modes for OECD AIM data."""

    MANUAL_OFFICIAL_EXPORT = "MANUAL_OFFICIAL_EXPORT"
    RECORDED_TEST_FIXTURE = "RECORDED_TEST_FIXTURE"
    FUTURE_OFFICIAL_API_DISABLED = "FUTURE_OFFICIAL_API_DISABLED"


class OECDRecord:
    """Immutable normalized representation of an imported OECD incident record."""

    def __init__(
        self,
        *,
        source_mode: OECDSourceMode,
        original_file_name: str,
        file_sha256: str,
        import_timestamp: str,
        operator_id: str,
        original_source_record_id: str | None,
        original_source_url: str | None,
        original_record_title: str,
        original_record_dates: str | None,
        normalized_fields: dict[str, Any],
        validation_warnings: list[str],
        original_record_dict: dict[str, Any],
        duplicate_resolution_result: str | None = None,
        ingestion_manifest_id: str | None = None,
        methodology_version: str = "OECD-Adapter-1.0.0",
        requires_dedup_review: bool = False,
    ) -> None:
        self.source_system = "OECD_AIM"
        self.source_mode = source_mode
        self.original_file_name = original_file_name
        self.file_sha256 = file_sha256
        self.import_timestamp = import_timestamp
        self.operator_id = operator_id
        self.original_source_record_id = original_source_record_id
        self.original_source_url = original_source_url
        self.original_record_title = original_record_title
        self.original_record_dates = original_record_dates
        self.normalized_fields = normalized_fields
        self.validation_warnings = validation_warnings
        self.original_record_dict = original_record_dict
        self.duplicate_resolution_result = duplicate_resolution_result
        self.ingestion_manifest_id = ingestion_manifest_id
        self.methodology_version = methodology_version
        self.requires_dedup_review = requires_dedup_review

        # Content signature
        sig = f"{original_source_record_id or ''}|{original_record_title}|{original_record_dates or ''}|{original_source_url or ''}"
        self.item_sha256 = hashlib.sha256(sig.encode("utf-8")).hexdigest()

    def to_ingested_item(self) -> IngestedItem:
        """Map to standard pipeline IngestedItem."""
        source_id = (
            f"SRC-OECD-{self.original_source_record_id}"
            if self.original_source_record_id
            else f"SRC-OECD-{self.item_sha256[:12]}"
        )
        summary = self.normalized_fields.get("summary_snippet", "")
        canonical_url = self.original_source_url or f"https://oecd.ai/en/incidents/{self.original_source_record_id or 'unidentified'}"

        return IngestedItem(
            source_id=source_id,
            connector_name="oecd_export_adapter",
            title=self.original_record_title,
            canonical_url=canonical_url,
            published_date=self.original_record_dates,
            summary_snippet=summary,
            content_sha256=self.item_sha256,
            raw_item_dict=self.original_record_dict,
            metadata={
                "source_system": self.source_system,
                "source_mode": self.source_mode.value,
                "file_sha256": self.file_sha256,
                "requires_dedup_review": self.requires_dedup_review,
                "oecd_principles": self.normalized_fields.get("oecd_principles"),
                "oecd_harm_category": self.normalized_fields.get("harm_category"),
                "ai_system": self.normalized_fields.get("ai_system"),
                "epistemic_disclaimer": "OECD classifications are source metadata, not verified legal findings or AIG-ISI severity",
            },
            is_research_context=False,
        )


class OECDExportAdapter:
    """Secure, offline adapter for OECD AIM export files.

    Maintains DEC-P4-001: Zero live web scraping, zero polling of undocumented endpoints.
    Operates strictly on operator-provided export files (CSV, JSON, XLSX) or recorded fixtures.
    """

    def __init__(
        self,
        *,
        operator_id: str = "system_operator",
        default_mode: OECDSourceMode = OECDSourceMode.MANUAL_OFFICIAL_EXPORT,
        max_file_size_bytes: int = 20 * 1024 * 1024,  # 20 MB ceiling
    ) -> None:
        self.operator_id = operator_id
        self.default_mode = default_mode
        self.max_file_size_bytes = max_file_size_bytes

    def parse_file(
        self,
        file_path: str | Path,
        *,
        source_mode: OECDSourceMode | None = None,
        ingestion_manifest_id: str | None = None,
    ) -> list[OECDRecord]:
        """Parse an OECD export file from disk."""
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"OECD export file not found: {file_path}")

        file_size = path.stat().st_size
        if file_size > self.max_file_size_bytes:
            raise ValueError(
                f"File size ({file_size} bytes) exceeds maximum allowed limit of {self.max_file_size_bytes} bytes"
            )

        with open(path, "rb") as f:
            raw_bytes = f.read()

        return self.parse_bytes(
            raw_bytes,
            path.name,
            source_mode=source_mode or self.default_mode,
            ingestion_manifest_id=ingestion_manifest_id,
        )

    def parse_bytes(
        self,
        raw_bytes: bytes,
        file_name: str,
        *,
        source_mode: OECDSourceMode | None = None,
        ingestion_manifest_id: str | None = None,
    ) -> list[OECDRecord]:
        """Parse raw OECD export bytes in memory."""
        mode = source_mode or self.default_mode

        # Enforce DEC-P4-001: Future API mode is disabled
        if mode == OECDSourceMode.FUTURE_OFFICIAL_API_DISABLED:
            raise ConnectorDisabledError(
                "Future OECD API connector is disabled by default under DEC-P4-001. "
                "Only MANUAL_OFFICIAL_EXPORT and RECORDED_TEST_FIXTURE modes are permitted."
            )

        if not raw_bytes:
            return []

        if len(raw_bytes) > self.max_file_size_bytes:
            raise ValueError(
                f"Payload size ({len(raw_bytes)} bytes) exceeds maximum limit of {self.max_file_size_bytes} bytes"
            )

        file_sha256 = hashlib.sha256(raw_bytes).hexdigest()
        import_ts = datetime.now(timezone.utc).isoformat()
        lower_name = file_name.lower()

        if lower_name.endswith(".csv"):
            raw_rows = self._parse_csv_bytes(raw_bytes)
        elif lower_name.endswith((".json", ".jsonl", ".ndjson")):
            raw_rows = self._parse_json_bytes(raw_bytes)
        elif lower_name.endswith(".xlsx"):
            raw_rows = self._parse_xlsx_bytes(raw_bytes)
        else:
            ext = Path(file_name).suffix
            raise ValueError(
                f"Unsupported file format '{ext}' for OECD export. "
                f"Supported formats: CSV, JSON, XLSX."
            )

        records: list[OECDRecord] = []
        for row in raw_rows:
            record = self._map_row_to_oecd_record(
                row=row,
                source_mode=mode,
                original_file_name=file_name,
                file_sha256=file_sha256,
                import_timestamp=import_ts,
                ingestion_manifest_id=ingestion_manifest_id,
            )
            records.append(record)

        return records

    def _parse_csv_bytes(self, raw_bytes: bytes) -> list[dict[str, Any]]:
        text = raw_bytes.decode("utf-8", errors="replace")
        lines = [line for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]
        if not lines:
            return []
        reader = csv.DictReader(lines)
        rows: list[dict[str, Any]] = []
        for r in reader:
            if any(v for v in r.values() if v and str(v).strip()):
                rows.append(dict(r))
        return rows

    def _parse_json_bytes(self, raw_bytes: bytes) -> list[dict[str, Any]]:
        text = raw_bytes.decode("utf-8", errors="replace").strip()
        if not text:
            return []

        # Try standard JSON
        try:
            data = json.loads(text)
            if isinstance(data, list):
                return [r for r in data if isinstance(r, dict)]
            if isinstance(data, dict):
                # Common wrappers: "incidents", "data", "records", "items"
                for key in ("incidents", "data", "records", "items"):
                    if key in data and isinstance(data[key], list):
                        return [r for r in data[key] if isinstance(r, dict)]
                return [data]
        except json.JSONDecodeError:
            pass

        # Try NDJSON (newline-delimited)
        rows: list[dict[str, Any]] = []
        for line in text.splitlines():
            line_str = line.strip()
            if line_str:
                try:
                    obj = json.loads(line_str)
                    if isinstance(obj, dict):
                        rows.append(obj)
                except json.JSONDecodeError:
                    continue
        return rows

    def _parse_xlsx_bytes(self, raw_bytes: bytes) -> list[dict[str, Any]]:
        wb = openpyxl.load_workbook(io.BytesIO(raw_bytes), read_only=True, data_only=True)
        sheet = wb.active
        if sheet is None:
            return []

        rows_iter = sheet.iter_rows(values_only=True)
        try:
            header_row = next(rows_iter)
        except StopIteration:
            return []

        headers = [str(h).strip() if h is not None else f"col_{idx}" for idx, h in enumerate(header_row)]
        rows: list[dict[str, Any]] = []
        for row in rows_iter:
            if not any(v is not None for v in row):
                continue
            row_dict = {
                headers[idx]: v for idx, v in enumerate(row) if idx < len(headers)
            }
            rows.append(row_dict)

        wb.close()
        return rows

    def _map_row_to_oecd_record(
        self,
        row: dict[str, Any],
        source_mode: OECDSourceMode,
        original_file_name: str,
        file_sha256: str,
        import_timestamp: str,
        ingestion_manifest_id: str | None,
    ) -> OECDRecord:
        """Map raw OECD export row dictionary into an OECDRecord with formula sanitization."""
        # Sanitize row against formula injection per CWE-1236
        sanitized_row = sanitize_row_dict(row)
        warnings: list[str] = []

        raw_id = _find_field_value(sanitized_row, "id")
        requires_dedup_review = False
        if not raw_id:
            requires_dedup_review = True
            warnings.append("Missing stable OECD record identifier; flagged for human deduplication review")

        title = _find_field_value(sanitized_row, "title") or "Untitled OECD Incident"
        raw_date = _find_field_value(sanitized_row, "date")
        raw_url = _find_field_value(sanitized_row, "url")
        raw_summary = _find_field_value(sanitized_row, "summary") or ""
        summary_snippet = raw_summary[:500].rstrip() if len(raw_summary) > 500 else raw_summary

        harm_type = _find_field_value(sanitized_row, "harm_type")
        ai_system = _find_field_value(sanitized_row, "ai_system")
        principles = sanitized_row.get("oecd_principles") or sanitized_row.get("principles")

        normalized = {
            "title": title,
            "incident_date": raw_date,
            "canonical_url": raw_url,
            "summary_snippet": summary_snippet,
            "harm_category": harm_type,
            "ai_system": ai_system,
            "oecd_principles": principles,
        }

        return OECDRecord(
            source_mode=source_mode,
            original_file_name=original_file_name,
            file_sha256=file_sha256,
            import_timestamp=import_timestamp,
            operator_id=self.operator_id,
            original_source_record_id=raw_id,
            original_source_url=raw_url,
            original_record_title=title,
            original_record_dates=raw_date,
            normalized_fields=normalized,
            validation_warnings=warnings,
            original_record_dict=row,  # Preserve exact original dictionary
            duplicate_resolution_result=None,
            ingestion_manifest_id=ingestion_manifest_id,
            requires_dedup_review=requires_dedup_review,
        )


def main() -> None:
    """CLI entry point for manual OECD export ingestion."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Manual OECD AIM export file adapter (DEC-P4-001)."
    )
    parser.add_argument(
        "--file",
        type=str,
        required=True,
        help="Path to OECD export file (.csv, .json, .xlsx).",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default=OECDSourceMode.MANUAL_OFFICIAL_EXPORT.value,
        choices=[m.value for m in OECDSourceMode],
        help="Source mode (default: MANUAL_OFFICIAL_EXPORT).",
    )
    parser.add_argument(
        "--operator-id",
        type=str,
        default="system_operator",
        help="Operator or job identifier.",
    )
    args = parser.parse_args()

    mode = OECDSourceMode(args.mode)
    adapter = OECDExportAdapter(operator_id=args.operator_id, default_mode=mode)
    records = adapter.parse_file(args.file, source_mode=mode)

    print(f"\n[OECD EXPORT IMPORT SUCCESS] Mode: {mode.value}")
    print(f"  File Parsed      : {args.file}")
    print(f"  Records Ingested : {len(records)}")
    review_needed = sum(1 for r in records if r.requires_dedup_review)
    print(f"  Flagged for Dedup: {review_needed}\n")


if __name__ == "__main__":
    main()

