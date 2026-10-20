"""CLI interface for verifying provenance manifest hash chains.

Governing Charter: Project Constitution (Rules 1, 4, 11, 14, 15, 16),
ADR-008, ADR-010, SRC-002, AUD-004.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from ai_incident_monitor.ingestion.manifest import (
    DEFAULT_CHAIN_SCOPE,
    ManifestChainStore,
    VerificationReport,
    verify_provenance_chain,
)


def run_verify(
    chain_scope: str = DEFAULT_CHAIN_SCOPE,
    dry_run: bool = False,
    storage_dir: str | None = None,
) -> int:
    """Run provenance chain verification and return exit code (0 = valid, 1 = corrupted)."""
    store = ManifestChainStore(storage_dir=storage_dir)  # type: ignore[arg-type]
    try:
        chain = store.get_chain(chain_scope)
    except Exception as e:
        print(f"[ERROR] Failed to load manifest chain for scope '{chain_scope}': {e}", file=sys.stderr)
        return 1

    report: VerificationReport = verify_provenance_chain(chain, chain_scope=chain_scope, dry_run=dry_run)
    report_dict = report.to_safe_summary_dict()

    # Redacted, safe JSON output
    print(json.dumps(report_dict, indent=2))

    if not report.is_valid:
        print(
            f"\n[FAILURE] Provenance chain verification failed with {len(report.anomalies)} anomalies.",
            file=sys.stderr,
        )
        return 1

    print(f"\n[SUCCESS] Provenance chain verified ({report.total_manifests} manifests in scope '{chain_scope}').")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify cryptographic provenance manifest chain integrity.")
    parser.add_argument(
        "--scope",
        type=str,
        default=DEFAULT_CHAIN_SCOPE,
        help="Chain scope identifier to verify (default: 'global_environment_default')",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform diagnostic inspection without modifying any state",
    )
    parser.add_argument(
        "--storage-dir",
        type=str,
        default=None,
        help="Optional custom path to manifests directory",
    )
    args = parser.parse_args(argv)
    return run_verify(chain_scope=args.scope, dry_run=args.dry_run, storage_dir=args.storage_dir)


if __name__ == "__main__":
    sys.exit(main())
