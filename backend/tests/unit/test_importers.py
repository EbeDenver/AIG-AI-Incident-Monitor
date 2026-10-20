"""Unit tests for file importers, OECD column mapper, and XLSX cached formula handling."""

from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Generator

import openpyxl
import pytest

from ai_incident_monitor.domain.vocabularies import EpistemicStatus, ReviewStatus
from ai_incident_monitor.importers import (
    CSVImporter,
    JSONImporter,
    OECDIncidentMapper,
    XLSXImporter,
    compute_file_sha256,
    stage_raw_upload,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "imports"


def test_csv_importer_oecd_sample() -> None:
    """Verify CSVImporter parses OECD sample records."""
    importer = CSVImporter()
    csv_path = FIXTURES_DIR / "oecd_sample.csv"
    rows = importer.parse_rows(csv_path)

    assert len(rows) == 3
    assert rows[0]["Incident ID"] == "OECD-2025-001"
    assert rows[0]["Incident Title"] == "Autonomous Sorter Sensor Glitch"
    assert rows[0]["Incident Date"] == "2025-01-15"


def test_csv_importer_formula_injection_defense() -> None:
    """Verify CSVImporter sanitizes formula injection attacks (CWE-1236)."""
    importer = CSVImporter()
    attack_path = FIXTURES_DIR / "formula_injection_attack.csv"
    rows = importer.parse_rows(attack_path)

    assert len(rows) == 5
    for row in rows:
        title = row["Incident Title"]
        # Every formula trigger in the attack fixture must be prepended with a single quote
        assert title.startswith("'"), f"Title '{title}' was not sanitized against formula injection!"


def test_importer_row_limit_enforced() -> None:
    """Verify importer enforces row limit guardrail."""
    importer = CSVImporter(max_rows=2)
    csv_path = FIXTURES_DIR / "oecd_sample.csv"
    with pytest.raises(ValueError, match="exceeds maximum allowed row limit"):
        importer.parse_rows(csv_path)


def test_json_importer_oecd_sample() -> None:
    """Verify JSONImporter parses JSON arrays and extracts sanitized rows."""
    importer = JSONImporter()
    json_path = FIXTURES_DIR / "oecd_sample.json"
    rows = importer.parse_rows(json_path)

    assert len(rows) == 2
    assert rows[0]["id"] == "OECD-JSON-001"
    assert rows[0]["title"] == "Automated Dispatch Route Deviation"


def test_xlsx_importer_cached_values_and_unknowns() -> None:
    """Verify XLSXImporter handles cached values, empty formulas as None, and sanitization."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        xlsx_path = Path(tmp_dir) / "test_import.xlsx"

        # Create synthetic workbook
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Incidents"

        ws.append(["Incident ID", "Incident Title", "Incident Date", "Cached Metric", "Uncached Formula"])
        # Row with cached value 100, formula text '+cmd...' and formula '=A1+B1' that has no cached evaluation
        ws.append(["XLSX-001", "+cmd|' /C calc'!A0", "2025-04-10", 100, "=A1+B1"])
        wb.save(str(xlsx_path))
        wb.close()

        importer = XLSXImporter()
        rows = importer.parse_rows(xlsx_path)

        assert len(rows) == 1
        row = rows[0]
        assert row["Incident ID"] == "XLSX-001"
        # Formula injection trigger '+' in title neutralized by prepending single quote
        assert row["Incident Title"] == "'+cmd|' /C calc'!A0"
        assert row["Cached Metric"] == 100
        # Formula '=A1+B1' without cached evaluation in openpyxl returns strictly None (Rule 2)
        assert row["Uncached Formula"] is None


def test_oecd_mapper_normal_row() -> None:
    """Verify OECDIncidentMapper maps fields, sets UNVERIFIED_ALLEGATION, and links sources."""
    raw_row = {
        "Incident ID": "OECD-999",
        "Incident Title": "Synthetic Diagnostic Deviation",
        "Description": "Medical AI recommended divergent chemotherapy protocol.",
        "Incident Date": "2025-05-20",
        "Source URL": "https://example.com/reports/diagnostic-999.html?utm_source=feed",
        "Entity": "Clinical AI Corp",
        "Harm Type": "Patient Safety Risk",
    }

    incident, claims, sources = OECDIncidentMapper.map_row(
        row=raw_row,
        batch_id="BATCH-001",
        demonstration_notice="DEMONSTRATION DATA — NOT A REAL INCIDENT",
    )

    # 1. Incident checks
    assert incident.id == "INC-OECD-OECD-999"
    assert incident.title == "Synthetic Diagnostic Deviation"
    assert incident.incident_date_precision == "EXACT"
    assert incident.incident_exact_date is not None
    assert incident.status == "UNDER_INVESTIGATION"

    # 2. Claim epistemic integrity checks (Gate 4, Rule 3)
    assert len(claims) == 1
    claim = claims[0]
    assert claim.epistemic_status == EpistemicStatus.UNVERIFIED_ALLEGATION.value
    assert claim.review_status == ReviewStatus.DRAFT_UNREVIEWED.value
    assert claim.claim_text == "Medical AI recommended divergent chemotherapy protocol."

    # 3. Source reference checks
    assert len(sources) == 1
    source = sources[0]
    assert source.url == "https://example.com/reports/diagnostic-999.html?utm_source=feed"
    assert source.canonical_url == "https://example.com/reports/diagnostic-999.html"
    assert source.publisher == "Clinical AI Corp"


def test_oecd_mapper_missing_columns_tolerance() -> None:
    """Verify missing columns do not cause errors and map to UNKNOWN/None (Gate 3)."""
    raw_row = {
        "Notes": "Record with no ID, title, or date columns",
    }

    incident, claims, sources = OECDIncidentMapper.map_row(
        row=raw_row,
        batch_id="BATCH-002",
    )

    assert incident.id.startswith("INC-")
    assert incident.title == "Untitled AI Incident"
    assert incident.incident_date_precision == "UNKNOWN"
    assert incident.incident_exact_date is None
    assert len(sources) == 0


def test_file_digest_and_staging() -> None:
    """Verify compute_file_sha256 and stage_raw_upload preserve raw payloads."""
    csv_path = FIXTURES_DIR / "oecd_sample.csv"
    digest = compute_file_sha256(csv_path)
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)

    staged_path = stage_raw_upload(csv_path, batch_id="TEST-BATCH-99", filename="sample.csv")
    assert staged_path.exists()
    assert staged_path.name == "sample.csv"
    assert ".data/raw_imports/TEST-BATCH-99" in str(staged_path)
