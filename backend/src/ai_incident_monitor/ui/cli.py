"""CLI entry point for running the local operator explorer web application.

Governing Charter: Project Constitution (Rules 1, 10, 11, 14, 16),
PRD §2 (UIX-001, UIX-003, AUD-001, AUD-002), Phase 8A Plan.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

import uvicorn

from ai_incident_monitor.db.session import get_engine, get_repo_root
from ai_incident_monitor.ui.app import create_app
from ai_incident_monitor.ui.auth import LocalCredentialManager

LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def validate_loopback_host(host: str) -> None:
    """Validate that the bind host is strictly a local loopback interface."""
    host_clean = host.strip().lower()
    if host_clean not in LOOPBACK_HOSTS:
        print(
            f"[SECURITY ERROR] Host '{host}' is forbidden. Local development mode permits "
            f"loopback binding ({', '.join(sorted(LOOPBACK_HOSTS))}) only.\n"
            "Binding to 0.0.0.0 or public interfaces is strictly rejected for operator security.",
            file=sys.stderr,
        )
        sys.exit(1)


def main(argv: list[str] | None = None) -> None:
    """Parse arguments, verify loopback host, ensure local credential, and launch uvicorn."""
    parser = argparse.ArgumentParser(
        description="Launch the AI Incident Monitor Local Operator Explorer."
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Local loopback interface to bind (default: 127.0.0.1).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port number to listen on (default: 8000).",
    )

    args = parser.parse_args(argv)

    validate_loopback_host(args.host)

    repo_root = get_repo_root()
    cred_file = repo_root / ".data" / ".operator_credential"
    cred_mgr = LocalCredentialManager(storage_path=cred_file)

    # Ensure credential exists and is securely permissions-checked (0o600)
    try:
        _ = cred_mgr.generate_or_load_credential()
    except Exception as exc:
        print(f"[ERROR] Failed to initialize local operator credential: {exc}", file=sys.stderr)
        sys.exit(1)

    allowed_hosts = {
        f"{args.host}:{args.port}",
        args.host,
        "127.0.0.1:8000",
        "127.0.0.1",
        "localhost:8000",
        "localhost",
        "[::1]:8000",
        "[::1]",
    }

    engine = get_engine()
    app = create_app(
        db_engine=engine,
        repo_root=repo_root,
        credential_manager=cred_mgr,
        allowed_hosts=allowed_hosts,
    )

    print("=" * 76)
    print("AI INCIDENT MONITOR — LOCAL OPERATOR EXPLORER")
    print(f"Bound to:         http://{args.host}:{args.port}")
    print(f"Credential file:  {cred_file} (mode 0600)")
    print(f"Login URL:        http://{args.host}:{args.port}/login")
    print("Security:         Loopback-only, host-validated, CSRF-protected, 4h idle timeout.")
    print("Notice:           Possession of credential grants explorer inspection only;")
    print("                  does not authorize dossier publication under Rule 14.")
    print("=" * 76)

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
