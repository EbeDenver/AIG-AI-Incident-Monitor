"""Administrative CLI for Local Reviewer Keystore Management.

Provides out-of-band enrollment, key rotation, revocation, and listing for authorized human reviewers:
- python -m ai_incident_monitor.ui.manage_reviewers enroll --reviewer-id ebe --name "Ebe Rolston" --role "Lead Editor"
- python -m ai_incident_monitor.ui.manage_reviewers rotate-key --reviewer-id ebe
- python -m ai_incident_monitor.ui.manage_reviewers revoke --reviewer-id ebe
- python -m ai_incident_monitor.ui.manage_reviewers list
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from ai_incident_monitor.ui.cli import get_repo_root
from ai_incident_monitor.ui.reviewer_auth import ReviewerKeystore


def get_default_keystore_path() -> Path:
    """Return default keystore path in workspace .data directory."""
    return get_repo_root() / ".data" / ".reviewers.json"


def cmd_enroll(args: argparse.Namespace) -> int:
    """Enroll a new authorized human reviewer."""
    keystore = ReviewerKeystore(Path(args.keystore_path))
    try:
        record, raw_key = keystore.enroll_reviewer(
            reviewer_id=args.reviewer_id,
            reviewer_name=args.name,
            reviewer_role=args.role,
        )
        print("\n=======================================================")
        print("  AI Incident Monitor — Reviewer Enrolled Successfully")
        print("=======================================================")
        print(f"  Reviewer ID:   {record.reviewer_id}")
        print(f"  Name:          {record.reviewer_name}")
        print(f"  Role:          {record.reviewer_role}")
        print(f"  Status:        ACTIVE (is_human=True)")
        print(f"  Enrolled At:   {record.enrolled_at_utc}")
        print(f"  Keystore File: {keystore.storage_path}")
        print("-------------------------------------------------------")
        print("  REVIEWER SIGNING KEY (SAVE THIS KEY — SHOWN ONCE):")
        print(f"  {raw_key}")
        print("-------------------------------------------------------")
        print("  Store this key securely in your local password manager.")
        print("  The plaintext secret is never written to disk.")
        print("=======================================================\n")
        return 0
    except Exception as exc:
        print(f"Error enrolling reviewer: {exc}", file=sys.stderr)
        return 1


def cmd_rotate_key(args: argparse.Namespace) -> int:
    """Rotate an enrolled reviewer's key."""
    keystore = ReviewerKeystore(Path(args.keystore_path))
    try:
        raw_key = keystore.rotate_key(reviewer_id=args.reviewer_id)
        print("\n=======================================================")
        print("  AI Incident Monitor — Reviewer Key Rotated")
        print("=======================================================")
        print(f"  Reviewer ID:   {args.reviewer_id}")
        print("-------------------------------------------------------")
        print("  NEW REVIEWER SIGNING KEY (SHOWN ONCE):")
        print(f"  {raw_key}")
        print("-------------------------------------------------------")
        print("  The previous key is now immediately invalid.")
        print("=======================================================\n")
        return 0
    except Exception as exc:
        print(f"Error rotating reviewer key: {exc}", file=sys.stderr)
        return 1


def cmd_revoke(args: argparse.Namespace) -> int:
    """Revoke a reviewer's approval authorization."""
    keystore = ReviewerKeystore(Path(args.keystore_path))
    try:
        keystore.revoke_reviewer(reviewer_id=args.reviewer_id)
        print(f"\n[REVOKED] Reviewer '{args.reviewer_id}' has been marked inactive.")
        print("Any subsequent approval attempts using this identity will be rejected.\n")
        return 0
    except Exception as exc:
        print(f"Error revoking reviewer: {exc}", file=sys.stderr)
        return 1


def cmd_list(args: argparse.Namespace) -> int:
    """List enrolled reviewers."""
    keystore = ReviewerKeystore(Path(args.keystore_path))
    try:
        reviewers = keystore.list_reviewers()
        if not reviewers:
            print(f"No reviewers enrolled in '{keystore.storage_path}'.")
            return 0

        print(f"\nEnrolled Reviewers in '{keystore.storage_path}':")
        print("-" * 75)
        print(f"{'REVIEWER ID':<15} {'NAME':<20} {'ROLE':<18} {'STATUS':<10} {'ENROLLED':<12}")
        print("-" * 75)
        for r in reviewers:
            status_str = "ACTIVE" if r.is_active else "REVOKED"
            date_short = r.enrolled_at_utc[:10] if r.enrolled_at_utc else "unknown"
            print(f"{r.reviewer_id:<15} {r.reviewer_name:<20} {r.reviewer_role:<18} {status_str:<10} {date_short:<12}")
        print("-" * 75 + "\n")
        return 0
    except Exception as exc:
        print(f"Error listing reviewers: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser for reviewer management CLI."""
    parser = argparse.ArgumentParser(
        prog="python -m ai_incident_monitor.ui.manage_reviewers",
        description="Administrative CLI for local reviewer keystore management.",
    )
    parser.add_argument(
        "--keystore-path",
        type=str,
        default=str(get_default_keystore_path()),
        help="Path to .reviewers.json keystore file (default: .data/.reviewers.json)",
    )

    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # enroll
    p_enroll = subparsers.add_parser("enroll", help="Enroll an authorized human reviewer")
    p_enroll.add_argument("--reviewer-id", type=str, required=True, help="Unique reviewer ID")
    p_enroll.add_argument("--name", type=str, required=True, help="Full reviewer name")
    p_enroll.add_argument("--role", type=str, required=True, help="Reviewer role (e.g. Lead Editor)")
    p_enroll.set_defaults(func=cmd_enroll)

    # rotate-key
    p_rotate = subparsers.add_parser("rotate-key", help="Rotate a reviewer's signing key")
    p_rotate.add_argument("--reviewer-id", type=str, required=True, help="Unique reviewer ID")
    p_rotate.set_defaults(func=cmd_rotate_key)

    # revoke
    p_revoke = subparsers.add_parser("revoke", help="Revoke reviewer approval authority")
    p_revoke.add_argument("--reviewer-id", type=str, required=True, help="Unique reviewer ID")
    p_revoke.set_defaults(func=cmd_revoke)

    # list
    p_list = subparsers.add_parser("list", help="List enrolled reviewers")
    p_list.set_defaults(func=cmd_list)

    return parser


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
