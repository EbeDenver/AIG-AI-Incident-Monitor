"""Command-line interface for the editorial dossier pipeline and human-in-the-loop review.

Governing Charter: Project Constitution (Rules 1, 3, 10, 11, 12, 14, 15, 17),
ADR-001, ADR-014, ADR-020, PRD §4.7 (EDT-001..005, UIX-001..003).

Subcommands:
  select-candidates     Evaluate candidate incidents for inclusion.
  assemble-dossier      Deterministically assemble candidate incidents into a dossier.
  inspect-dossier       Display detailed structured dossier content.
  validate-dossier      Run forensic and safety validation on a dossier draft.
  submit-for-review     Transition an assembled dossier to PENDING_REVIEW.
  approve-dossier       Approve a dossier with human reviewer attestation.
  reject-dossier        Reject a dossier with documented rationale.
  supersede-dossier     Mark an approved dossier superseded by a newer version.
  verify-audit          Verify cryptographic audit hash chain integrity for a dossier.
  export-dossier        Export dossier to local Markdown or JSON drafts.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import sys
from typing import Optional, Sequence

from ai_incident_monitor.db.session import get_db_session, get_engine
from ai_incident_monitor.domain.common import ConstitutionalViolationError
from ai_incident_monitor.editorial.assembly import EditorialDossierAssembler
from ai_incident_monitor.editorial.enums import (
    EditorialArtifactPurpose,
    EditorialDossierStatus,
    EditorialExportFormat,
    EditorialPresentationProfile,
    EditorialScopeType,
)
from ai_incident_monitor.editorial.models import (
    EDITORIAL_ATTESTATION_STATEMENT,
    EditorialReviewerAttestationSchema,
)
from ai_incident_monitor.editorial.renderers import (
    DEFAULT_EXPORT_DIR,
    EditorialDossierExporter,
)
from ai_incident_monitor.editorial.source_selector import EditorialSourceSelector
from ai_incident_monitor.editorial.validator import EditorialValidator
from ai_incident_monitor.repositories.editorial_repo import EditorialRepository


def print_output(data: dict | list, as_json: bool = False, file=None) -> None:
    """Helper to output json or formatted readable text."""
    target_file = file if file is not None else sys.stdout
    if as_json:
        print(json.dumps(data, indent=2, default=str), file=target_file)
    else:
        if isinstance(data, dict):
            for k, v in data.items():
                print(f"{k}: {v}", file=target_file)
        elif isinstance(data, list):
            for item in data:
                print(f"- {item}", file=target_file)


def cmd_select_candidates(args: argparse.Namespace) -> int:
    """Evaluate candidate incidents for inclusion in an editorial dossier."""
    eng = get_engine(url=args.db_url)
    with get_db_session(eng) as session:
        selector = EditorialSourceSelector(session)
        candidates = selector.select_candidates(
            incident_ids=args.incident_id if args.incident_id else None,
            limit=args.limit,
            only_eligible=not args.all,
            include_eu_commentary=not args.no_eu,
        )

        data = [
            {
                "incident_id": c.incident_id,
                "title": c.title,
                "is_eligible": c.is_eligible,
                "evidence_count": len(c.evidence_ids),
                "severity_tier": c.severity_tier,
                "eu_screen_status": c.eu_screen_status,
                "eu_screen_eligible": c.eu_screen_eligible,
                "exclusion_reasons": c.exclusion_reasons,
            }
            for c in candidates
        ]

        if args.json:
            print_output(data, as_json=True)
        else:
            print(f"=== Candidate Incidents ({len(candidates)} found) ===")
            for c in candidates:
                status_marker = "[ELIGIBLE]" if c.is_eligible else "[INELIGIBLE]"
                print(f"{status_marker} {c.incident_id}: {c.title}")
                print(f"   Evidence Links: {len(c.evidence_ids)} | Severity: {c.severity_tier or 'N/A'}")
                if c.eu_screen_status:
                    print(f"   EU Screen: {c.eu_screen_status} (Eligible: {c.eu_screen_eligible})")
                if c.exclusion_reasons:
                    print(f"   Exclusion Reasons: {'; '.join(c.exclusion_reasons)}")
                print()

    return 0


def cmd_assemble_dossier(args: argparse.Namespace) -> int:
    """Deterministically assemble candidate incidents into an editorial dossier."""
    eng = get_engine(url=args.db_url)
    with get_db_session(eng) as session:
        selector = EditorialSourceSelector(session)
        candidates = selector.select_candidates(
            incident_ids=args.incident_id if args.incident_id else None,
            limit=args.limit,
            only_eligible=True,
            include_eu_commentary=not args.no_eu,
        )

        if not candidates:
            print(
                "[ERROR] No eligible candidate incidents found for assembly.",
                file=sys.stderr,
            )
            return 1

        assembler = EditorialDossierAssembler()
        try:
            dossier = assembler.assemble(
                candidates=candidates,
                title=args.title,
                scope_type=EditorialScopeType(args.scope_type),
                methodology_notes=args.methodology_notes,
                executive_summary=args.executive_summary,
                dossier_id=args.dossier_id,
            )
        except Exception as exc:
            print(f"[ERROR] Dossier assembly failed: {exc}", file=sys.stderr)
            return 1

        if not args.dry_run:
            repo = EditorialRepository(session)
            dossier = repo.save_dossier(
                dossier=dossier,
                actor_id=args.actor_id,
                is_human=args.is_human,
                actor_role=args.actor_role,
            )

        resp = {
            "dossier_id": dossier.id,
            "version": dossier.version,
            "title": dossier.title,
            "status": dossier.status.value,
            "content_hash": dossier.content_hash,
            "entry_count": len(dossier.entries),
            "total_evidence_links": dossier.summary.total_evidence_links,
            "disputed_incident_count": dossier.summary.disputed_incident_count,
            "dry_run": args.dry_run,
        }

        if args.json:
            print_output(resp, as_json=True)
        else:
            mode_label = "[DRY RUN] " if args.dry_run else ""
            print(f"=== {mode_label}Dossier Assembled Successfully ===")
            print(f"Dossier ID:     {dossier.id}")
            print(f"Version:        {dossier.version}")
            print(f"Title:          {dossier.title}")
            print(f"Status:         {dossier.status.value}")
            print(f"Content Hash:   {dossier.content_hash}")
            print(f"Entries:        {len(dossier.entries)}")
            print(f"Evidence Links: {dossier.summary.total_evidence_links}")
            print(f"Disputed Facts: {dossier.summary.disputed_incident_count}")

    return 0


def cmd_inspect_dossier(args: argparse.Namespace) -> int:
    """Inspect structured editorial dossier details."""
    eng = get_engine(url=args.db_url)
    with get_db_session(eng) as session:
        repo = EditorialRepository(session)
        dossier = repo.get_dossier(args.dossier_id)
        if not dossier:
            print(f"[ERROR] Dossier '{args.dossier_id}' not found.", file=sys.stderr)
            return 1

        if args.json:
            print_output(dossier.model_dump(mode="json"), as_json=True)
        else:
            print(f"=== Editorial Dossier: {dossier.title} ===")
            print(f"ID:              {dossier.id}")
            print(f"Version:         {dossier.version}")
            print(f"Status:          {dossier.status.value}")
            print(f"Content Hash:    {dossier.content_hash}")
            print(f"Scope:           {dossier.scope_type.value}")
            print(f"Disclaimer:      {dossier.disclaimer_version}")
            print(f"Generated By:    {dossier.generated_by}")
            if dossier.reviewed_by:
                print(f"Reviewed By:     {dossier.reviewed_by} at {dossier.reviewed_at}")
            if dossier.rejection_reason:
                print(f"Rejection Note:  {dossier.rejection_reason}")
            print(f"\nExecutive Summary:\n  {dossier.summary.executive_summary}\n")
            print(f"Entries ({len(dossier.entries)}):")
            for entry in dossier.entries:
                print(f"  [{entry.entry_order}] {entry.incident_id}: {entry.incident_title}")
                print(f"      Evidence IDs: {entry.source_evidence_ids}")
                print(f"      Source Hash:  {entry.source_version_hash}")
                if entry.eu_commentary:
                    print(f"      EU Screen:    {entry.eu_commentary}")
                elif entry.omitted_eu_reason:
                    print(f"      EU Omission:  {entry.omitted_eu_reason}")

    return 0


def cmd_validate_dossier(args: argparse.Namespace) -> int:
    """Run forensic and safety validation on an editorial dossier draft."""
    eng = get_engine(url=args.db_url)
    with get_db_session(eng) as session:
        repo = EditorialRepository(session)
        dossier = repo.get_dossier(args.dossier_id)
        if not dossier:
            print(f"[ERROR] Dossier '{args.dossier_id}' not found.", file=sys.stderr)
            return 1

        validator = EditorialValidator()
        report = validator.validate_dossier(dossier)

        if args.json:
            print_output(report.model_dump(mode="json"), as_json=True)
        else:
            status_text = "PASS" if report.is_valid else "FAIL"
            print(f"=== Dossier Validation Report: {status_text} ===")
            print(f"Dossier ID:      {report.dossier_id}")
            print(f"Total Findings:  {report.total_findings}")
            print(f"Blocking Count:  {report.blocking_count}")
            print(f"Warning Count:   {report.warning_count}")
            if report.findings:
                print("\nFindings:")
                for f in report.findings:
                    print(f"  [{f.severity.value}] {f.finding_code.value} at {f.field_path}: {f.message}")

        return 0 if report.is_valid else 2


def cmd_submit_for_review(args: argparse.Namespace) -> int:
    """Submit an assembled dossier to the human review queue."""
    eng = get_engine(url=args.db_url)
    with get_db_session(eng) as session:
        repo = EditorialRepository(session)
        try:
            if not args.dry_run:
                dossier = repo.submit_for_review(
                    dossier_id=args.dossier_id,
                    actor_id=args.actor_id,
                    is_human=args.is_human,
                    actor_role=args.actor_role,
                )
            else:
                dossier = repo.get_dossier(args.dossier_id)
                if not dossier:
                    print(f"[ERROR] Dossier '{args.dossier_id}' not found.", file=sys.stderr)
                    return 1

            resp = {
                "dossier_id": args.dossier_id,
                "status": "PENDING_REVIEW" if not args.dry_run else dossier.status.value,
                "submitted_by": args.actor_id,
                "dry_run": args.dry_run,
            }
            if args.json:
                print_output(resp, as_json=True)
            else:
                mode_label = "[DRY RUN] " if args.dry_run else ""
                print(f"=== {mode_label}Dossier Submitted For Review ===")
                print(f"Dossier ID:   {args.dossier_id}")
                print(f"New Status:   PENDING_REVIEW")
                print(f"Submitted By: {args.actor_id}")

        except Exception as exc:
            print(f"[ERROR] Submission failed: {exc}", file=sys.stderr)
            return 1

    return 0


def cmd_approve_dossier(args: argparse.Namespace) -> int:
    """Approve an editorial dossier under authenticated human reviewer attestation."""
    if not args.is_human:
        print(
            "[ERROR] Approval strictly requires --is-human flag; automated self-approval is forbidden (Rule 14).",
            file=sys.stderr,
        )
        return 1

    if not args.confirm_statement:
        print(
            "[ERROR] Approval requires explicit statement confirmation via --confirm-statement flag.",
            file=sys.stderr,
        )
        return 1

    eng = get_engine(url=args.db_url)
    with get_db_session(eng) as session:
        repo = EditorialRepository(session)
        dossier = repo.get_dossier(args.dossier_id)
        if not dossier:
            print(f"[ERROR] Dossier '{args.dossier_id}' not found.", file=sys.stderr)
            return 1

        # Run validation
        validator = EditorialValidator()
        validation_report = validator.validate_dossier(dossier)
        if not validation_report.is_valid:
            print(
                f"[ERROR] Approval blocked: dossier has {validation_report.blocking_count} validation findings.",
                file=sys.stderr,
            )
            for f in validation_report.findings:
                if f.severity.value == "BLOCKING":
                    print(f"  - {f.field_path}: {f.message}", file=sys.stderr)
            return 2

        content_hash = dossier.compute_content_hash()
        attestation = EditorialReviewerAttestationSchema(
            reviewer_id=args.reviewer_id,
            reviewer_name=args.reviewer_name,
            reviewer_role=args.reviewer_role,
            is_human=True,
            statement_confirmed=True,
            attestation_statement=EDITORIAL_ATTESTATION_STATEMENT,
            content_hash=content_hash,
            dossier_id=dossier.id,
            dossier_version=dossier.version,
        )

        try:
            if not args.dry_run:
                approved_dossier = repo.approve_dossier(
                    dossier_id=args.dossier_id,
                    attestation=attestation,
                    validation_report=validation_report,
                )
            else:
                approved_dossier = dossier

            resp = {
                "dossier_id": args.dossier_id,
                "version": approved_dossier.version,
                "status": "APPROVED_INFORMATIONAL",
                "reviewed_by": args.reviewer_id,
                "content_hash": content_hash,
                "dry_run": args.dry_run,
            }
            if args.json:
                print_output(resp, as_json=True)
            else:
                mode_label = "[DRY RUN] " if args.dry_run else ""
                print(f"=== {mode_label}Dossier Approved Successfully ===")
                print(f"Dossier ID:   {args.dossier_id}")
                print(f"Version:      {approved_dossier.version}")
                print(f"Status:       APPROVED_INFORMATIONAL")
                print(f"Reviewer ID:  {args.reviewer_id}")
                print(f"Content Hash: {content_hash}")

        except Exception as exc:
            print(f"[ERROR] Approval failed: {exc}", file=sys.stderr)
            return 1

    return 0


def cmd_reject_dossier(args: argparse.Namespace) -> int:
    """Reject an editorial dossier with documented rationale."""
    if not args.is_human:
        print(
            "[ERROR] Rejection must be performed by a human reviewer (Rule 14).",
            file=sys.stderr,
        )
        return 1

    if not args.reason or not args.reason.strip():
        print("[ERROR] Rejection requires non-empty --reason.", file=sys.stderr)
        return 1

    eng = get_engine(url=args.db_url)
    with get_db_session(eng) as session:
        repo = EditorialRepository(session)
        try:
            if not args.dry_run:
                dossier = repo.reject_dossier(
                    dossier_id=args.dossier_id,
                    reviewer_id=args.reviewer_id,
                    is_human=args.is_human,
                    rejection_reason=args.reason,
                    reviewer_name=args.reviewer_name,
                    reviewer_role=args.reviewer_role,
                )
            else:
                dossier = repo.get_dossier(args.dossier_id)
                if not dossier:
                    print(f"[ERROR] Dossier '{args.dossier_id}' not found.", file=sys.stderr)
                    return 1

            resp = {
                "dossier_id": args.dossier_id,
                "status": "REJECTED",
                "reviewer_id": args.reviewer_id,
                "rejection_reason": args.reason,
                "dry_run": args.dry_run,
            }
            if args.json:
                print_output(resp, as_json=True)
            else:
                mode_label = "[DRY RUN] " if args.dry_run else ""
                print(f"=== {mode_label}Dossier Rejected ===")
                print(f"Dossier ID:       {args.dossier_id}")
                print(f"Status:           REJECTED")
                print(f"Reviewer:         {args.reviewer_id}")
                print(f"Rejection Reason: {args.reason}")

        except Exception as exc:
            print(f"[ERROR] Rejection failed: {exc}", file=sys.stderr)
            return 1

    return 0


def cmd_supersede_dossier(args: argparse.Namespace) -> int:
    """Mark an approved dossier superseded by an updated revision."""
    eng = get_engine(url=args.db_url)
    with get_db_session(eng) as session:
        repo = EditorialRepository(session)
        try:
            if not args.dry_run:
                superseded = repo.supersede_dossier(
                    old_dossier_id=args.old_dossier_id,
                    new_dossier_id=args.new_dossier_id,
                    actor_id=args.actor_id,
                    is_human=args.is_human,
                    rationale=args.rationale,
                )
            resp = {
                "old_dossier_id": args.old_dossier_id,
                "new_dossier_id": args.new_dossier_id,
                "status": "SUPERSEDED",
                "actor_id": args.actor_id,
                "dry_run": args.dry_run,
            }
            if args.json:
                print_output(resp, as_json=True)
            else:
                mode_label = "[DRY RUN] " if args.dry_run else ""
                print(f"=== {mode_label}Dossier Superseded ===")
                print(f"Prior Dossier ID: {args.old_dossier_id} -> Status: SUPERSEDED")
                print(f"New Dossier ID:   {args.new_dossier_id}")
                print(f"Actor ID:         {args.actor_id}")

        except Exception as exc:
            print(f"[ERROR] Supersession failed: {exc}", file=sys.stderr)
            return 1

    return 0


def cmd_verify_audit(args: argparse.Namespace) -> int:
    """Verify cryptographic audit hash chain integrity for an editorial dossier."""
    eng = get_engine(url=args.db_url)
    with get_db_session(eng) as session:
        repo = EditorialRepository(session)
        is_valid, anomalies = repo.verify_audit_chain(args.dossier_id)

        resp = {
            "dossier_id": args.dossier_id,
            "is_valid": is_valid,
            "anomaly_count": len(anomalies),
            "anomalies": anomalies,
        }

        if args.json:
            print_output(resp, as_json=True)
        else:
            status_text = "VALID" if is_valid else "CORRUPTED"
            print(f"=== Audit Chain Verification: {status_text} ===")
            print(f"Dossier ID:     {args.dossier_id}")
            print(f"Is Valid:       {is_valid}")
            print(f"Anomaly Count:  {len(anomalies)}")
            if anomalies:
                print("\nAnomalies:")
                for a in anomalies:
                    print(f"  - {a}")

        return 0 if is_valid else 1


def cmd_export_dossier(args: argparse.Namespace) -> int:
    """Export an editorial dossier to local disk under strict safety policies."""
    eng = get_engine(url=args.db_url)
    with get_db_session(eng) as session:
        repo = EditorialRepository(session)
        exporter = EditorialDossierExporter(repo)
        try:
            export_format = EditorialExportFormat(args.format.upper())
            profile = EditorialPresentationProfile(args.profile.upper())

            purpose_val = args.purpose.upper()
            if purpose_val in ("REVIEW", "INTERNAL_REVIEW_COPY"):
                purpose = EditorialArtifactPurpose.INTERNAL_REVIEW_COPY
            elif purpose_val in ("APPROVED", "APPROVED_EDITORIAL_COPY"):
                purpose = EditorialArtifactPurpose.APPROVED_EDITORIAL_COPY
            else:
                purpose = EditorialArtifactPurpose(purpose_val)

            result = exporter.export(
                dossier_id=args.dossier_id,
                export_format=export_format,
                profile=profile,
                purpose=purpose,
                output_dir=args.output_dir,
                overwrite=args.overwrite,
                dry_run=args.dry_run,
                actor_id=args.actor_id,
                is_human=args.is_human,
                actor_role=args.actor_role,
            )
            session.commit()

            output_data = {
                "export_id": result.export_id,
                "dossier_id": result.dossier_id,
                "dossier_version": result.dossier_version,
                "format": result.format.value,
                "profile": result.profile.value,
                "purpose": result.purpose.value,
                "output_dir": result.output_dir,
                "written_files": result.written_files,
                "canonical_dossier_content_hash": result.manifest.canonical_dossier_content_hash,
                "canonical_payload_hash": result.manifest.canonical_payload_hash,
                "artifact_file_hash": result.manifest.artifact_file_hash,
                "dry_run": result.dry_run,
            }

            if args.json:
                print_output(output_data, as_json=True)
            else:
                mode_str = "[DRY-RUN] " if result.dry_run else ""
                print(f"=== {mode_str}Dossier Export Complete ===")
                print(f"Export ID:      {result.export_id}")
                print(f"Dossier ID:     {result.dossier_id} (v{result.dossier_version})")
                print(f"Profile:        {result.profile.value}")
                print(f"Purpose:        {result.purpose.value}")
                print(f"Format:         {result.format.value}")
                print(f"Output Dir:     {result.output_dir}")
                print("Written Files:")
                for f in result.written_files:
                    print(f"  - {f}")
                print(f"Canonical Dossier Hash: {result.manifest.canonical_dossier_content_hash}")
                print(f"Payload Hash:           {result.manifest.canonical_payload_hash}")
                if result.manifest.artifact_file_hash:
                    print(f"Artifact File Hash:     {result.manifest.artifact_file_hash}")

            return 0
        except FileExistsError as e:
            print(f"[COLLISION ERROR] {e}", file=sys.stderr)
            return 3
        except ConstitutionalViolationError as e:
            print(f"[CONSTITUTIONAL VIOLATION] {e}", file=sys.stderr)
            return 4
        except (ValueError, KeyError) as e:
            print(f"[EXPORT ERROR] {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"[UNEXPECTED ERROR] {e}", file=sys.stderr)
            return 2


def build_parser() -> argparse.ArgumentParser:
    """Construct command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="editorial",
        description="AI Guardians editorial dossier pipeline and human-in-the-loop review CLI.",
    )
    parser.add_argument("--db-url", type=str, default=None, help="Database connection URL")

    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # select-candidates
    p_select = subparsers.add_parser("select-candidates", help="Select and evaluate candidate incidents.")
    p_select.add_argument("--limit", type=int, default=20, help="Maximum candidates to return")
    p_select.add_argument("--incident-id", action="append", help="Filter by specific incident ID(s)")
    p_select.add_argument("--all", action="store_true", help="Include ineligible candidates")
    p_select.add_argument("--no-eu", action="store_true", help="Exclude optional EU commentary")
    p_select.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    p_select.set_defaults(func=cmd_select_candidates)

    # assemble-dossier
    p_assemble = subparsers.add_parser("assemble-dossier", help="Assemble candidate incidents into a dossier.")
    p_assemble.add_argument("--title", type=str, required=True, help="Dossier title")
    p_assemble.add_argument(
        "--scope-type",
        type=str,
        default="CUSTOM",
        choices=["WEEKLY", "MONTHLY", "INCIDENT_DEEP_DIVE", "CUSTOM"],
        help="Scope type",
    )
    p_assemble.add_argument("--incident-id", action="append", help="Specific incident ID(s) to include")
    p_assemble.add_argument("--limit", type=int, default=20, help="Max candidates if no specific IDs given")
    p_assemble.add_argument("--methodology-notes", type=str, default=None, help="Custom methodology note")
    p_assemble.add_argument("--executive-summary", type=str, default=None, help="Custom executive summary")
    p_assemble.add_argument("--dossier-id", type=str, default=None, help="Explicit dossier ID")
    p_assemble.add_argument("--actor-id", type=str, default="system", help="Actor initiating assembly")
    p_assemble.add_argument("--actor-role", type=str, default=None, help="Actor role")
    p_assemble.add_argument("--is-human", action="store_true", help="Flag if actor is human")
    p_assemble.add_argument("--no-eu", action="store_true", help="Exclude optional EU commentary")
    p_assemble.add_argument("--dry-run", action="store_true", help="Perform in-memory assembly without DB writes")
    p_assemble.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    p_assemble.set_defaults(func=cmd_assemble_dossier)

    # inspect-dossier
    p_inspect = subparsers.add_parser("inspect-dossier", help="Inspect dossier details.")
    p_inspect.add_argument("--dossier-id", type=str, required=True, help="Dossier ID to inspect")
    p_inspect.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    p_inspect.set_defaults(func=cmd_inspect_dossier)

    # validate-dossier
    p_validate = subparsers.add_parser("validate-dossier", help="Validate dossier draft.")
    p_validate.add_argument("--dossier-id", type=str, required=True, help="Dossier ID to validate")
    p_validate.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    p_validate.set_defaults(func=cmd_validate_dossier)

    # submit-for-review
    p_submit = subparsers.add_parser("submit-for-review", help="Submit dossier to review queue.")
    p_submit.add_argument("--dossier-id", type=str, required=True, help="Dossier ID")
    p_submit.add_argument("--actor-id", type=str, required=True, help="Actor ID submitting dossier")
    p_submit.add_argument("--actor-role", type=str, default=None, help="Actor role")
    p_submit.add_argument("--is-human", action="store_true", default=True, help="Actor is human")
    p_submit.add_argument("--dry-run", action="store_true", help="Dry run without persistence")
    p_submit.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    p_submit.set_defaults(func=cmd_submit_for_review)

    # approve-dossier
    p_approve = subparsers.add_parser("approve-dossier", help="Approve dossier under human attestation.")
    p_approve.add_argument("--dossier-id", type=str, required=True, help="Dossier ID")
    p_approve.add_argument("--reviewer-id", type=str, required=True, help="Authenticated reviewer ID")
    p_approve.add_argument("--reviewer-name", type=str, default=None, help="Reviewer full name")
    p_approve.add_argument("--reviewer-role", type=str, required=True, help="Reviewer role (e.g. Lead Editor)")
    p_approve.add_argument("--is-human", action="store_true", required=True, help="Confirm reviewer is human (Rule 14)")
    p_approve.add_argument("--confirm-statement", action="store_true", required=True, help="Confirm attestation statement")
    p_approve.add_argument("--dry-run", action="store_true", help="Dry run without persistence")
    p_approve.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    p_approve.set_defaults(func=cmd_approve_dossier)

    # reject-dossier
    p_reject = subparsers.add_parser("reject-dossier", help="Reject dossier with documented rationale.")
    p_reject.add_argument("--dossier-id", type=str, required=True, help="Dossier ID")
    p_reject.add_argument("--reviewer-id", type=str, required=True, help="Reviewer ID")
    p_reject.add_argument("--reviewer-name", type=str, default=None, help="Reviewer name")
    p_reject.add_argument("--reviewer-role", type=str, default=None, help="Reviewer role")
    p_reject.add_argument("--is-human", action="store_true", default=True, help="Reviewer is human")
    p_reject.add_argument("--reason", type=str, required=True, help="Documented reason for rejection")
    p_reject.add_argument("--dry-run", action="store_true", help="Dry run without persistence")
    p_reject.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    p_reject.set_defaults(func=cmd_reject_dossier)

    # supersede-dossier
    p_super = subparsers.add_parser("supersede-dossier", help="Supersede an approved dossier.")
    p_super.add_argument("--old-dossier-id", type=str, required=True, help="Prior dossier ID")
    p_super.add_argument("--new-dossier-id", type=str, required=True, help="New dossier ID")
    p_super.add_argument("--actor-id", type=str, required=True, help="Actor ID")
    p_super.add_argument("--is-human", action="store_true", default=True, help="Actor is human")
    p_super.add_argument("--rationale", type=str, default=None, help="Supersession rationale")
    p_super.add_argument("--dry-run", action="store_true", help="Dry run without persistence")
    p_super.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    p_super.set_defaults(func=cmd_supersede_dossier)

    # verify-audit
    p_audit = subparsers.add_parser("verify-audit", help="Verify cryptographic audit chain for dossier.")
    p_audit.add_argument("--dossier-id", type=str, required=True, help="Dossier ID")
    p_audit.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    p_audit.set_defaults(func=cmd_verify_audit)

    # export-dossier
    p_export = subparsers.add_parser("export-dossier", help="Export dossier to local Markdown or JSON drafts.")
    p_export.add_argument("--dossier-id", type=str, required=True, help="Dossier ID to export")
    p_export.add_argument(
        "--format",
        type=str,
        default="MARKDOWN",
        choices=["MARKDOWN", "JSON", "ALL", "markdown", "json", "all"],
        help="Export artifact format (default: MARKDOWN)",
    )
    p_export.add_argument(
        "--profile",
        type=str,
        default="DEEP_DIVE_DOSSIER",
        choices=[
            "DEEP_DIVE_DOSSIER",
            "EXECUTIVE_BRIEF",
            "RAPID_ALERT",
            "deep_dive_dossier",
            "executive_brief",
            "rapid_alert",
        ],
        help="Presentation profile (default: DEEP_DIVE_DOSSIER)",
    )
    p_export.add_argument(
        "--purpose",
        type=str,
        default="INTERNAL_REVIEW_COPY",
        choices=[
            "INTERNAL_REVIEW_COPY",
            "APPROVED_EDITORIAL_COPY",
            "internal_review_copy",
            "approved_editorial_copy",
            "REVIEW",
            "APPROVED",
            "review",
            "approved",
        ],
        help="Export purpose (default: INTERNAL_REVIEW_COPY)",
    )
    p_export.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Destination directory (default: .data/editorial_exports)",
    )
    p_export.add_argument(
        "--overwrite",
        action="store_true",
        help="Permit overwrite of existing managed exports",
    )
    p_export.add_argument(
        "--actor-id",
        type=str,
        default="editorial_exporter",
        help="Actor initiating export",
    )
    p_export.add_argument("--actor-role", type=str, default=None, help="Actor role")
    p_export.add_argument(
        "--is-human",
        action="store_true",
        default=True,
        help="Flag confirming human actor",
    )
    p_export.add_argument(
        "--non-human",
        action="store_false",
        dest="is_human",
        help="Flag indicating non-human actor (fails closed under Rule 14 for approved copies)",
    )
    p_export.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform in-memory export and validation with zero disk/DB writes",
    )
    p_export.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON status",
    )
    p_export.set_defaults(func=cmd_export_dossier)

    # Subcommand: diagnose
    p_diag = subparsers.add_parser(
        "diagnose",
        help="Run safe, non-mutating operational diagnostic checks across local subsystems",
    )
    p_diag.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON diagnostics report",
    )
    p_diag.set_defaults(
        func=lambda args: __import__("ai_incident_monitor.diagnostics.cli", fromlist=["run_diagnostics_cli"]).run_diagnostics_cli(as_json=args.json)
    )

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry point for editorial dossier tool."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if hasattr(args, "func"):
        return args.func(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
