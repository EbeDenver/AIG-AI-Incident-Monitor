"""Unit tests for macOS launchd scheduler configuration generation and validation."""

from pathlib import Path
import plistlib
import pytest

from ai_incident_monitor.ingestion.scheduler import (
    DEFAULT_INTERVAL_SECONDS,
    DEFAULT_JOB_LABEL,
    generate_launchd_dict,
    generate_launchd_plist_bytes,
    validate_launchd_plist_bytes,
    write_launchd_plist_file,
)


class TestSchedulerLaunchd:
    """Validate launchd property list structure, security, and path handling."""

    def test_generate_launchd_dict(self, tmp_path: Path) -> None:
        repo_root = tmp_path / "repo"
        python_bin = repo_root / ".venv" / "bin" / "python"
        data = generate_launchd_dict(
            repo_root=repo_root,
            python_bin=python_bin,
            interval_seconds=1800,
            job_label="com.test.ingest",
        )

        assert data["Label"] == "com.test.ingest"
        assert data["StartInterval"] == 1800
        assert data["RunAtLoad"] is False
        assert data["WorkingDirectory"] == str(repo_root.resolve())
        assert "-m" in data["ProgramArguments"]
        assert "ai_incident_monitor.ingestion.cycle" in data["ProgramArguments"]
        assert "--trigger" in data["ProgramArguments"]
        assert "scheduled" in data["ProgramArguments"]

    def test_generate_and_validate_plist_bytes(self) -> None:
        plist_bytes = generate_launchd_plist_bytes(interval_seconds=3600)
        is_valid, err, parsed = validate_launchd_plist_bytes(plist_bytes)

        assert is_valid
        assert err is None
        assert parsed["Label"] == DEFAULT_JOB_LABEL
        assert parsed["StartInterval"] == 3600
        assert "StandardOutPath" in parsed
        assert "StandardErrorPath" in parsed

    def test_validation_rejects_malformed_plist(self) -> None:
        # Invalid XML
        is_valid, err, _ = validate_launchd_plist_bytes(b"<not-a-plist>")
        assert not is_valid
        assert "Invalid plist syntax" in str(err)

        # Missing required keys
        incomplete = plistlib.dumps({"Label": "foo"}, fmt=plistlib.FMT_XML)
        is_valid, err, _ = validate_launchd_plist_bytes(incomplete)
        assert not is_valid
        assert "Missing required launchd key" in str(err)

        # Interval too short (< 60s)
        short_interval = plistlib.dumps({
            "Label": "foo",
            "ProgramArguments": ["a", "b", "c"],
            "WorkingDirectory": "/tmp",
            "StartInterval": 10,
        }, fmt=plistlib.FMT_XML)
        is_valid, err, _ = validate_launchd_plist_bytes(short_interval)
        assert not is_valid
        assert "at least 60 seconds" in str(err)

    def test_write_plist_file(self, tmp_path: Path) -> None:
        target = tmp_path / "test_job.plist"
        written = write_launchd_plist_file(output_path=target, interval_seconds=7200)

        assert written.exists()
        with open(written, "rb") as f:
            valid, err, parsed = validate_launchd_plist_bytes(f.read())
        assert valid
        assert parsed["StartInterval"] == 7200
