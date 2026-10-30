"""CLI interface for running local operational diagnostics and environment health checks.

Governing Charter: Project Constitution (Rules 1, 10, 11, 14, 16),
PRD §5 (TST-001, AUD-004), Phase 7B Plan.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional, Sequence

from ai_incident_monitor.diagnostics.enums import CheckStatus
from ai_incident_monitor.diagnostics.models import DiagnosticReport
from ai_incident_monitor.diagnostics.runner import LocalDiagnosticsRunner


def print_text_report(report: DiagnosticReport, file=None) -> None:
    """Render human-readable diagnostics table to standard output."""
    out = file or sys.stdout
    print("=" * 80, file=out)
    print(f"AI INCIDENT MONITOR — LOCAL OPERATIONAL DIAGNOSTICS REPORT", file=out)
    print(f"Evaluated At: {report.evaluated_at_utc.isoformat()}", file=out)
    print(f"Overall Status: [{report.overall_status.value}] (Exit Code: {report.exit_code})", file=out)
    print("=" * 80, file=out)

    status_symbols = {
        CheckStatus.HEALTHY: "[OK]      ",
        CheckStatus.DEGRADED: "[DEGRADED]",
        CheckStatus.UNHEALTHY: "[FAIL]    ",
    }

    for check in report.checks:
        symbol = status_symbols.get(check.status, "[UNKNOWN] ")
        print(f"\n{symbol} {check.category.value} :: {check.name}", file=out)
        print(f"           Reason:  {check.reason_code}", file=out)
        print(f"           Summary: {check.message}", file=out)
        if check.details:
            print(f"           Context: {json.dumps(check.details, default=str)}", file=out)

    print("\n" + "=" * 80, file=out)
    if report.overall_status == CheckStatus.HEALTHY:
        print("[SUMMARY] All local subsystems healthy and ready for operational runs.", file=out)
    elif report.overall_status == CheckStatus.DEGRADED:
        print("[SUMMARY] Environment operational with non-critical warnings.", file=out)
    else:
        print("[SUMMARY] Subsystem failures detected. Remediation required before execution.", file=out)
    print("=" * 80, file=out)


def run_diagnostics_cli(
    as_json: bool = False,
    runner: Optional[LocalDiagnosticsRunner] = None,
    file=None,
) -> int:
    """Execute diagnostics and return process exit code (0=HEALTHY, 1=DEGRADED, 2=UNHEALTHY)."""
    active_runner = runner or LocalDiagnosticsRunner()
    report = active_runner.run_all_checks()

    target_file = file or sys.stdout
    if as_json:
        print(report.model_dump_json(indent=2), file=target_file)
    else:
        print_text_report(report, file=target_file)

    return report.exit_code


def main(argv: Optional[Sequence[str]] = None) -> None:
    """Main CLI entrypoint for diagnostics command."""
    parser = argparse.ArgumentParser(
        description="Run safe, non-mutating operational diagnostic checks across local subsystems."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Output machine-readable JSON diagnostics report.",
    )
    args = parser.parse_args(argv)

    exit_code = run_diagnostics_cli(as_json=args.as_json)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
