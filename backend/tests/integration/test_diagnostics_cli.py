"""Integration tests for local operational diagnostics CLI commands.

Governing Charter: Project Constitution (Rules 1, 10, 11, 14, 16),
PRD §5 (TST-001, AUD-004), Phase 7B Plan.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from ai_incident_monitor.db.base import Base
from ai_incident_monitor.diagnostics.cli import main as diag_main, run_diagnostics_cli
from ai_incident_monitor.diagnostics.enums import CheckStatus
from ai_incident_monitor.diagnostics.runner import LocalDiagnosticsRunner
from ai_incident_monitor.editorial.cli import main as editorial_cli_main


@pytest.fixture
def memory_engine():
    """Create in-memory SQLite engine with complete initialized schema."""
    engine = create_engine("sqlite:///:memory:")
    from ai_incident_monitor.db.models import (  # noqa: F401
        audit,
        claim,
        editorial,
        evidence,
        governance,
        import_record,
        incident,
        review,
        severity,
        source,
        uncertainty,
    )
    Base.metadata.create_all(engine)
    return engine


class TestDiagnosticsCLI:
    """Validate diagnostics CLI behavior, JSON output, and exit codes."""

    def test_cli_healthy_text_output_and_exit_code_0(self, tmp_path: Path, memory_engine) -> None:
        export_dir = tmp_path / "exports"
        staging_dir = tmp_path / "staging"
        export_dir.mkdir()
        staging_dir.mkdir()

        runner = LocalDiagnosticsRunner(
            engine=memory_engine,
            export_dir=export_dir,
            staging_dir=staging_dir,
        )

        out_buffer = io.StringIO()
        exit_code = run_diagnostics_cli(as_json=False, runner=runner, file=out_buffer)

        output = out_buffer.getvalue()
        assert exit_code == 0
        assert "LOCAL OPERATIONAL DIAGNOSTICS REPORT" in output
        assert "[OK]" in output
        assert "Overall Status: [HEALTHY]" in output

    def test_cli_json_output_and_exit_code_0(self, tmp_path: Path, memory_engine) -> None:
        export_dir = tmp_path / "exports"
        staging_dir = tmp_path / "staging"
        export_dir.mkdir()
        staging_dir.mkdir()

        runner = LocalDiagnosticsRunner(
            engine=memory_engine,
            export_dir=export_dir,
            staging_dir=staging_dir,
        )

        out_buffer = io.StringIO()
        exit_code = run_diagnostics_cli(as_json=True, runner=runner, file=out_buffer)

        assert exit_code == 0
        report_data = json.loads(out_buffer.getvalue())

        assert report_data["schema_version"] == "1.0.0"
        assert report_data["overall_status"] == "HEALTHY"
        assert report_data["exit_code"] == 0
        assert len(report_data["checks"]) == 6

    def test_cli_unhealthy_exit_code_2(self) -> None:
        empty_engine = create_engine("sqlite:///:memory:")
        runner = LocalDiagnosticsRunner(engine=empty_engine)

        out_buffer = io.StringIO()
        exit_code = run_diagnostics_cli(as_json=True, runner=runner, file=out_buffer)

        assert exit_code == 2
        report_data = json.loads(out_buffer.getvalue())
        assert report_data["overall_status"] == "UNHEALTHY"
        assert report_data["exit_code"] == 2

    def test_editorial_cli_diagnose_subcommand(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Mock sys.argv / argv to run `editorial.cli diagnose --json`
        mock_stdout = io.StringIO()
        monkeypatch.setattr("sys.stdout", mock_stdout)

        # Invoking `diagnose --json` through editorial.cli.main
        exit_code = editorial_cli_main(["diagnose", "--json"])
        # Should return an integer exit code (0, 1, or 2)
        assert exit_code in (0, 1, 2)
        output = mock_stdout.getvalue()
        data = json.loads(output)
        assert "schema_version" in data
        assert "overall_status" in data
