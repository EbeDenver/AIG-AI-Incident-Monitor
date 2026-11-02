"""macOS launchd scheduler configuration and validation for automated ingestion.

Generates and validates standalone launchd LaunchAgent property list (.plist)
specifications without activating background daemons or persisting unauthorized jobs.

Governing Charter: Project Constitution (Rules 1, 11, 14, 16),
ADR-008, OPS-002, OPS-003.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import plistlib
import sys
from typing import Any, Optional

from ai_incident_monitor.db.session import get_repo_root

DEFAULT_JOB_LABEL = "com.aiguardians.incident-monitor.ingest"
DEFAULT_INTERVAL_SECONDS = 3600  # 60 minutes


def generate_launchd_dict(
    *,
    repo_root: Path,
    python_bin: Path,
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
    job_label: str = DEFAULT_JOB_LABEL,
) -> dict[str, Any]:
    """Construct deterministic launchd plist dictionary."""
    log_dir = repo_root / ".data" / "logs"
    stdout_log = log_dir / "ingestion_stdout.log"
    stderr_log = log_dir / "ingestion_stderr.log"

    # Preserve virtualenv binary path rather than following symlink to base python
    python_str = str(python_bin if python_bin.is_absolute() else (repo_root / python_bin).resolve())

    return {
        "Label": job_label,
        "ProgramArguments": [
            python_str,
            "-m",
            "ai_incident_monitor.ingestion.cycle",
            "--trigger",
            "scheduled",
        ],
        "WorkingDirectory": str(repo_root.resolve()),
        "StartInterval": max(60, interval_seconds),
        "RunAtLoad": False,
        "StandardOutPath": str(stdout_log.resolve()),
        "StandardErrorPath": str(stderr_log.resolve()),
        "EnvironmentVariables": {
            "PYTHONUNBUFFERED": "1",
            "PATH": "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
            "REPO_ROOT": str(repo_root.resolve()),
        },
    }


def generate_launchd_plist_bytes(
    *,
    repo_root: Optional[Path] = None,
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
    job_label: str = DEFAULT_JOB_LABEL,
) -> bytes:
    """Serialize launchd configuration dictionary to valid XML plist bytes."""
    root = repo_root or get_repo_root()
    python_bin = root / ".venv" / "bin" / "python"
    if not python_bin.exists():
        python_bin = Path(sys.executable)

    data = generate_launchd_dict(
        repo_root=root,
        python_bin=python_bin,
        interval_seconds=interval_seconds,
        job_label=job_label,
    )
    return plistlib.dumps(data, fmt=plistlib.FMT_XML)


def validate_launchd_plist_bytes(plist_bytes: bytes) -> tuple[bool, Optional[str], dict[str, Any]]:
    """Validate that plist bytes parse cleanly and conform to required scheduler structure."""
    try:
        parsed = plistlib.loads(plist_bytes)
    except Exception as exc:
        return False, f"Invalid plist syntax: {exc}", {}

    if not isinstance(parsed, dict):
        return False, "Plist root must be a dictionary", {}

    required_keys = ["Label", "ProgramArguments", "WorkingDirectory", "StartInterval"]
    for k in required_keys:
        if k not in parsed:
            return False, f"Missing required launchd key: '{k}'", parsed

    if parsed["StartInterval"] < 60:
        return False, "StartInterval must be at least 60 seconds", parsed

    if len(parsed["ProgramArguments"]) < 3:
        return False, "ProgramArguments must specify Python binary and module", parsed

    return True, None, parsed


def write_launchd_plist_file(
    output_path: Optional[Path] = None,
    *,
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
    job_label: str = DEFAULT_JOB_LABEL,
) -> Path:
    """Generate and write template launchd plist to disk without activating it."""
    root = get_repo_root()
    target = output_path or (root / "config" / "launchd" / f"{job_label}.plist")
    target.parent.mkdir(parents=True, exist_ok=True)

    plist_data = generate_launchd_plist_bytes(
        repo_root=root,
        interval_seconds=interval_seconds,
        job_label=job_label,
    )

    is_valid, err, _ = validate_launchd_plist_bytes(plist_data)
    if not is_valid:
        raise ValueError(f"Generated launchd configuration is invalid: {err}")

    with open(target, "wb") as f:
        f.write(plist_data)

    return target


def main(argv: Optional[list[str]] = None) -> int:
    """CLI tool for generating and validating the macOS launchd agent configuration."""
    parser = argparse.ArgumentParser(
        description="Generate macOS launchd LaunchAgent configuration for scheduled incident ingestion."
    )
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=DEFAULT_INTERVAL_SECONDS,
        help="Polling interval in seconds (default: 3600 [60 minutes]).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output path for the generated plist (default: config/launchd/com.aiguardians.incident-monitor.ingest.plist).",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate existing generated plist without overwriting.",
    )
    args = parser.parse_args(argv)

    root = get_repo_root()
    target_path = Path(args.output) if args.output else (root / "config" / "launchd" / f"{DEFAULT_JOB_LABEL}.plist")

    if args.validate_only:
        if not target_path.exists():
            print(f"[FAIL] Plist file not found at: {target_path}")
            return 1
        with open(target_path, "rb") as f:
            valid, err, parsed = validate_launchd_plist_bytes(f.read())
        if valid:
            print(f"[OK] Plist at {target_path} is valid.")
            print(f"  Label: {parsed.get('Label')}")
            print(f"  Interval: {parsed.get('StartInterval')}s")
            return 0
        else:
            print(f"[FAIL] Validation error: {err}")
            return 1

    written_path = write_launchd_plist_file(
        output_path=target_path,
        interval_seconds=args.interval_seconds,
    )
    print(f"\n[SUCCESS] Generated launchd LaunchAgent plist:")
    print(f"  Path: {written_path}")
    print(f"  Configured Interval: {args.interval_seconds}s ({(args.interval_seconds // 60)} minutes)")
    print(f"\nNOTE: Job is NOT activated. To activate after operator approval, run:")
    print(f"  cp {written_path} ~/Library/LaunchAgents/")
    print(f"  launchctl load ~/Library/LaunchAgents/{DEFAULT_JOB_LABEL}.plist\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
