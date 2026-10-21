"""Unit tests for the OECD Export Adapter (DEC-P4-001).

Validates CSV, JSON, and XLSX parsing, formula injection neutralization,
handling of missing record IDs, source-mode restrictions, and zero live network requests.
"""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import patch

import pytest

from ai_incident_monitor.ingestion.connectors.base import ConnectorDisabledError
from ai_incident_monitor.ingestion.oecd_adapter import (
    OECDExportAdapter,
    OECDRecord,
    OECDSourceMode,
)

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "oecd"


class TestOECDExportAdapter:
    """Verifies OECD export ingestion, mapping, formula defense, and isolation."""

    def test_parse_official_csv_export_file(self) -> None:
        csv_path = FIXTURES_DIR / "sanitized_oecd_export.csv"
        adapter = OECDExportAdapter(operator_id="test_admin")

        records = adapter.parse_file(csv_path, source_mode=OECDSourceMode.MANUAL_OFFICIAL_EXPORT)
        assert len(records) == 3

        # Record 1: Normal with ID
        r1 = records[0]
        assert r1.original_source_record_id == "OECD-2026-001"
        assert r1.original_record_title == "Autonomous Drone Delivery Drift"
        assert r1.original_record_dates == "2026-03-15"
        assert r1.source_system == "OECD_AIM"
        assert r1.source_mode == OECDSourceMode.MANUAL_OFFICIAL_EXPORT
        assert r1.requires_dedup_review is False
        assert r1.original_record_dict["Incident ID"] == "OECD-2026-001"
        assert r1.normalized_fields["harm_category"] == "Property Damage"

        # Record 3: Missing ID -> Must be flagged for dedup review, never invent ID
        r3 = records[2]
        assert r3.original_source_record_id is None
        assert r3.requires_dedup_review is True
        assert any("Missing stable OECD record identifier" in w for w in r3.validation_warnings)
        assert r3.original_record_title == "Uncataloged Warehouse Robotic Stoppage"

    def test_parse_official_json_export_file(self) -> None:
        json_path = FIXTURES_DIR / "sanitized_oecd_export.json"
        adapter = OECDExportAdapter()

        records = adapter.parse_file(json_path, source_mode=OECDSourceMode.RECORDED_TEST_FIXTURE)
        assert len(records) == 2

        r1 = records[0]
        assert r1.original_source_record_id == "OECD-2026-101"
        assert r1.original_record_title == "Smart Grid Load Balancing Oscillation"
        assert r1.normalized_fields["harm_category"] == "Infrastructure Instability"
        assert r1.source_mode == OECDSourceMode.RECORDED_TEST_FIXTURE

    def test_parse_official_xlsx_export_file(self) -> None:
        xlsx_path = FIXTURES_DIR / "sanitized_oecd_export.xlsx"
        adapter = OECDExportAdapter()

        records = adapter.parse_file(xlsx_path)
        assert len(records) == 2

        r1 = records[0]
        assert r1.original_source_record_id == "OECD-2026-201"
        assert r1.original_record_title == "Financial Trading Flash Order Spike"
        assert r1.original_record_dates == "2026-07-04"
        assert r1.normalized_fields["ai_system"] == "ApexTrader AI"

    def test_formula_injection_defense_neutralizes_triggers(self) -> None:
        """Verify that spreadsheet formula triggers (=, +, -, @) are prepended with quote."""
        csv_payload = (
            "Incident ID,Title,Date,URL,Description\n"
            "OECD-999,=cmd|' /C calc'!A0,2026-08-01,https://example.com,@SUM(1+2)\n"
        ).encode("utf-8")

        adapter = OECDExportAdapter()
        records = adapter.parse_bytes(csv_payload, "exploit.csv")
        assert len(records) == 1

        rec = records[0]
        # In normalized fields, dangerous formula triggers must be sanitized
        assert rec.original_record_title.startswith("'=")
        assert rec.normalized_fields["summary_snippet"].startswith("'@")

    def test_future_official_api_mode_is_disabled_under_dec_p4_001(self) -> None:
        adapter = OECDExportAdapter()
        with pytest.raises(ConnectorDisabledError) as exc_info:
            adapter.parse_bytes(
                b"id,title\n1,test\n",
                "test.csv",
                source_mode=OECDSourceMode.FUTURE_OFFICIAL_API_DISABLED,
            )
        assert "disabled by default under DEC-P4-001" in str(exc_info.value)

    def test_unsupported_file_extension_raises_value_error(self) -> None:
        adapter = OECDExportAdapter()
        with pytest.raises(ValueError) as exc_info:
            adapter.parse_bytes(b"data", "export.pdf")
        assert "Unsupported file format '.pdf'" in str(exc_info.value)

    def test_oversized_file_rejected(self) -> None:
        adapter = OECDExportAdapter(max_file_size_bytes=100)
        large_bytes = b"Incident ID,Title\n1,Oversized content\n" * 20
        with pytest.raises(ValueError) as exc_info:
            adapter.parse_bytes(large_bytes, "oversized.csv")
        assert "exceeds maximum limit" in str(exc_info.value)

    def test_to_ingested_item_mapping_and_epistemic_disclaimer(self) -> None:
        adapter = OECDExportAdapter()
        raw_csv = (
            "Incident ID,Title,Date,URL,Description,OECD Principles\n"
            "OECD-555,Autonomous Train Brake Failure,2026-09-01,https://oecd.ai/incidents/555,Braking delay in rain,Safety\n"
        ).encode("utf-8")

        records = adapter.parse_bytes(raw_csv, "train.csv")
        item = records[0].to_ingested_item()

        assert item.source_id == "SRC-OECD-OECD-555"
        assert item.title == "Autonomous Train Brake Failure"
        assert item.is_research_context is False
        assert "OECD classifications are source metadata" in item.metadata["epistemic_disclaimer"]

    def test_zero_network_calls_guaranteed(self) -> None:
        """Prove that the OECD export adapter performs zero network socket or HTTP requests."""
        csv_path = FIXTURES_DIR / "sanitized_oecd_export.csv"
        adapter = OECDExportAdapter()

        with patch("socket.socket") as mock_sock, patch("urllib.request.urlopen") as mock_url:
            records = adapter.parse_file(csv_path)
            assert len(records) == 3
            mock_sock.assert_not_called()
            mock_url.assert_not_called()
