"""Unit tests for local operational diagnostics runner and health checks.

Governing Charter: Project Constitution (Rules 1, 10, 11, 14, 16),
PRD §5 (TST-001, AUD-004), Phase 7B Plan.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, text

from ai_incident_monitor.db.base import Base
from ai_incident_monitor.diagnostics.enums import CheckCategory, CheckStatus
from ai_incident_monitor.diagnostics.models import DiagnosticReport
from ai_incident_monitor.diagnostics.runner import (
    CORE_SCHEMA_TABLES,
    LocalDiagnosticsRunner,
)


@pytest.fixture
def memory_db_engine():
    """Create an in-memory SQLite engine with complete schema initialized."""
    engine = create_engine("sqlite:///:memory:")
    # Import all models to register them on Base.metadata
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


class TestDiagnosticsRunnerChecks:
    """Validate individual diagnostic check behaviors under healthy and failure conditions."""

    def test_configuration_check_masks_credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DATABASE_URL", "postgresql://db_user:s3cr3t_pass@localhost:5432/incident_db")
        runner = LocalDiagnosticsRunner()
        result = runner.check_configuration()

        assert result.status == CheckStatus.HEALTHY
        assert result.reason_code == "CONFIG_VALID"
        assert "s3cr3t_pass" not in result.details["database_url_masked"]
        assert "db_user:***@" in result.details["database_url_masked"]

    def test_database_connectivity_success(self, memory_db_engine) -> None:
        runner = LocalDiagnosticsRunner(engine=memory_db_engine)
        result = runner.check_database_connectivity()

        assert result.status == CheckStatus.HEALTHY
        assert result.reason_code == "DB_CONNECTED"

    def test_database_connectivity_failure(self) -> None:
        # Create an invalid/unreachable SQLite engine
        broken_engine = create_engine("sqlite:////nonexistent_path/should_fail.db")
        runner = LocalDiagnosticsRunner(engine=broken_engine)
        result = runner.check_database_connectivity()

        assert result.status == CheckStatus.UNHEALTHY
        assert result.reason_code == "DB_CONNECTION_FAILED"

    def test_schema_compatibility_complete(self, memory_db_engine) -> None:
        runner = LocalDiagnosticsRunner(engine=memory_db_engine)
        result = runner.check_schema_compatibility()

        assert result.status == CheckStatus.HEALTHY
        assert result.reason_code == "SCHEMA_COMPATIBLE"

    def test_schema_compatibility_missing_tables(self) -> None:
        # Empty in-memory database with zero tables
        empty_engine = create_engine("sqlite:///:memory:")
        runner = LocalDiagnosticsRunner(engine=empty_engine)
        result = runner.check_schema_compatibility()

        assert result.status == CheckStatus.UNHEALTHY
        assert result.reason_code == "SCHEMA_TABLES_MISSING"
        assert len(result.details["missing_tables"]) > 0

    def test_reference_library_verification_success(self) -> None:
        # Real repo root should have canonical manifest and yaml files
        runner = LocalDiagnosticsRunner()
        result = runner.check_reference_library()

        assert result.status == CheckStatus.HEALTHY
        assert result.reason_code == "REFERENCE_LIBRARY_VERIFIED"
        assert len(result.details["verified_frameworks"]) == 3

    def test_reference_library_missing_manifest(self, tmp_path: Path) -> None:
        fake_repo = tmp_path / "fake_repo"
        fake_repo.mkdir()
        runner = LocalDiagnosticsRunner(repo_root=fake_repo)
        result = runner.check_reference_library()

        assert result.status == CheckStatus.UNHEALTHY
        assert result.reason_code == "MANIFEST_NOT_FOUND"

    def test_reference_library_digest_mismatch(self, tmp_path: Path) -> None:
        fake_repo = tmp_path / "fake_repo"
        fake_fw = fake_repo / "frameworks"
        fake_fw.mkdir(parents=True)

        # Create dummy file with mismatching SHA
        test_yaml = fake_fw / "test.yaml"
        test_yaml.write_text("dummy: content")

        manifest_content = {
            "frameworks": [{
                "framework_code": "TEST_FW",
                "file_path": "frameworks/test.yaml",
                "content_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
            }]
        }
        (fake_fw / "manifest.json").write_text(json.dumps(manifest_content))

        runner = LocalDiagnosticsRunner(repo_root=fake_repo)
        result = runner.check_reference_library()

        assert result.status == CheckStatus.UNHEALTHY
        assert result.reason_code == "REFERENCE_INTEGRITY_VIOLATION"

    def test_storage_paths_non_mutating(self, tmp_path: Path) -> None:
        export_dir = tmp_path / "exports"
        staging_dir = tmp_path / "staging"

        # Neither exists yet, but parent tmp_path is writable
        runner = LocalDiagnosticsRunner(export_dir=export_dir, staging_dir=staging_dir)
        result = runner.check_storage_paths()

        # Must report DEGRADED (pending initialization)
        assert result.status == CheckStatus.DEGRADED
        assert result.reason_code == "STORAGE_PATHS_PENDING_INITIALIZATION"

        # NON-MUTATING GUARANTEE: Neither directory nor dummy files were created!
        assert not export_dir.exists()
        assert not staging_dir.exists()

        # Now create them legitimately
        export_dir.mkdir()
        staging_dir.mkdir()
        result2 = runner.check_storage_paths()
        assert result2.status == CheckStatus.HEALTHY
        assert result2.reason_code == "STORAGE_PATHS_ACCESSIBLE"

    def test_pipeline_components_readiness(self) -> None:
        runner = LocalDiagnosticsRunner()
        result = runner.check_pipeline_components()

        assert result.status == CheckStatus.HEALTHY
        assert result.reason_code == "COMPONENTS_READY"


class TestDiagnosticsReportSynthesis:
    """Validate overall health status and exit code calculation."""

    def test_run_all_checks_healthy_environment(self, tmp_path: Path, memory_db_engine) -> None:
        export_dir = tmp_path / "exports"
        staging_dir = tmp_path / "staging"
        export_dir.mkdir()
        staging_dir.mkdir()

        runner = LocalDiagnosticsRunner(
            engine=memory_db_engine,
            export_dir=export_dir,
            staging_dir=staging_dir,
        )
        report: DiagnosticReport = runner.run_all_checks()

        assert report.overall_status == CheckStatus.HEALTHY
        assert report.exit_code == 0
        assert len(report.checks) == 6

    def test_run_all_checks_unhealthy_exit_code_2(self) -> None:
        # Empty database without schema -> overall UNHEALTHY, exit code 2
        empty_engine = create_engine("sqlite:///:memory:")
        runner = LocalDiagnosticsRunner(engine=empty_engine)
        report = runner.run_all_checks()

        assert report.overall_status == CheckStatus.UNHEALTHY
        assert report.exit_code == 2
