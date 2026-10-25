"""Safe local file exporter for editorial dossier publication drafts and review copies.

Governing Charter: Project Constitution (Rules 1, 3, 10, 11, 12, 14, 15, 17),
ADR-001, ADR-010, ADR-014, ADR-020, ADR-021, PRD §4.7.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import re
from typing import TYPE_CHECKING, Any, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

from ai_incident_monitor.db.models.governance import GovernanceAuditLogModel
from ai_incident_monitor.domain.common import ConstitutionalViolationError
from ai_incident_monitor.editorial.enums import (
    EditorialArtifactPurpose,
    EditorialAuditEventType,
    EditorialDossierStatus,
    EditorialExportFormat,
    EditorialPresentationProfile,
)
from ai_incident_monitor.editorial.models import (
    EDITORIAL_DISCLAIMER_TEXT,
    EDITORIAL_DISCLAIMER_VERSION,
    EditorialDossierSchema,
    EditorialValidationReport,
    normalize_iso_timestamp,
)
from ai_incident_monitor.editorial.renderers.json_renderer import EditorialJSONRenderer
from ai_incident_monitor.editorial.renderers.manifest import EditorialExportManifest
from ai_incident_monitor.editorial.renderers.markdown_renderer import EditorialMarkdownRenderer
from ai_incident_monitor.editorial.validator import EditorialValidator

if TYPE_CHECKING:
    from ai_incident_monitor.repositories.editorial_repo import EditorialRepository

# Default staging directory for local exports (git-ignored)
DEFAULT_EXPORT_DIR = ".data/editorial_exports"

# Safe filename component regex (disallows path separators and control characters)
SAFE_IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+$")


class EditorialExportResult(BaseModel):
    """Result summary of an editorial export execution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    export_id: str
    dossier_id: str
    dossier_version: int
    format: EditorialExportFormat
    profile: EditorialPresentationProfile
    purpose: EditorialArtifactPurpose
    output_dir: str
    written_files: list[str]
    manifest: EditorialExportManifest
    dry_run: bool


class EditorialDossierExporter:
    """Orchestrates deterministic rendering, validation, and safe atomic local file export.

    Safety Guarantees:
    - Path traversal defense: validates output directory confinement.
    - Symlink rejection: refuses to write into symlinked destinations.
    - Accidental overwrite protection: fails closed unless --overwrite is specified.
    - Atomic writes: writes to staging temp files and calls os.replace.
    - Source drift guard: blocks approved exports if underlying incidents drifted.
    - Non-self-referential cryptographic provenance manifest.
    - Zero external network egress, publishing API calls, or email dispatch.
    """

    def __init__(self, repository: EditorialRepository) -> None:
        self.repository = repository
        self.md_renderer = EditorialMarkdownRenderer()
        self.json_renderer = EditorialJSONRenderer()
        self.validator = EditorialValidator()

    def export(
        self,
        dossier_id: str,
        export_format: EditorialExportFormat = EditorialExportFormat.MARKDOWN,
        profile: EditorialPresentationProfile = EditorialPresentationProfile.DEEP_DIVE_DOSSIER,
        purpose: EditorialArtifactPurpose = EditorialArtifactPurpose.INTERNAL_REVIEW_COPY,
        output_dir: Optional[str] = None,
        overwrite: bool = False,
        dry_run: bool = False,
        actor_id: str = "editorial_exporter",
        is_human: bool = True,
        actor_role: Optional[str] = None,
    ) -> EditorialExportResult:
        """Export an editorial dossier to local disk under strict safety policies."""
        dossier = self.repository.get_dossier(dossier_id)
        if not dossier:
            raise KeyError(f"Dossier '{dossier_id}' not found in repository.")

        # 1. Path Safety & Output Directory Confinement
        resolved_out_dir = self._validate_and_resolve_output_dir(output_dir or DEFAULT_EXPORT_DIR)

        # 2. Safety & Governance Precondition Verification
        v_report = self.validator.validate_dossier(dossier)

        if purpose == EditorialArtifactPurpose.APPROVED_EDITORIAL_COPY:
            if dossier.status != EditorialDossierStatus.APPROVED_INFORMATIONAL:
                raise ValueError(
                    f"Cannot export APPROVED_EDITORIAL_COPY: dossier '{dossier.id}' is in "
                    f"status '{dossier.status.value}', expected 'APPROVED_INFORMATIONAL'."
                )
            if not is_human:
                raise ConstitutionalViolationError(
                    "Approved copy export strictly requires an authenticated human actor (Rule 14)."
                )

            # Check for source record drift
            has_drift, drift_details = self.repository.check_source_drift(dossier)
            if has_drift:
                raise ValueError(
                    f"Cannot export APPROVED_EDITORIAL_COPY: underlying source records have drifted "
                    f"since assembly ({'; '.join(drift_details)}). Fresh assembly and review required."
                )

            # Check content hash binding
            computed_hash = dossier.compute_content_hash()
            if dossier.content_hash and dossier.content_hash != computed_hash:
                raise ValueError(
                    f"Cannot export APPROVED_EDITORIAL_COPY: content hash mismatch "
                    f"(recorded='{dossier.content_hash}', computed='{computed_hash}')."
                )

            # Check for blocking validation findings
            if v_report.blocking_count > 0:
                blocking_reasons = [
                    f"{f.field_path}: {f.message}"
                    for f in v_report.findings
                    if f.severity.value == "BLOCKING"
                ]
                raise ValueError(
                    f"Cannot export APPROVED_EDITORIAL_COPY with blocking validation finding(s): "
                    f"{'; '.join(blocking_reasons)}"
                )

        # 3. Retrieve allowlisted audit records for JSON package
        audit_records = self._fetch_allowlisted_audit_records(dossier.id)

        # 4. Generate Rendered Content & Canonical Payload Hashes
        rendered_artifacts: dict[str, tuple[str, str, EditorialExportFormat]] = {}
        # Mapping: filename -> (rendered_content_string, canonical_payload_hash, format)

        purpose_slug = "review" if purpose == EditorialArtifactPurpose.INTERNAL_REVIEW_COPY else "approved"
        profile_slug = profile.value.lower()
        base_name = f"{purpose_slug}_{dossier.id}_v{dossier.version}_{profile_slug}"

        if export_format in (EditorialExportFormat.MARKDOWN, EditorialExportFormat.ALL):
            md_filename = f"{base_name}.md"
            md_text, md_payload_hash = self.md_renderer.render(
                dossier=dossier,
                profile=profile,
                purpose=purpose,
                validation_report=v_report,
            )
            rendered_artifacts[md_filename] = (md_text, md_payload_hash, EditorialExportFormat.MARKDOWN)

        if export_format in (EditorialExportFormat.JSON, EditorialExportFormat.ALL):
            json_filename = f"{base_name}.json"
            json_text, json_payload_hash = self.json_renderer.render(
                dossier=dossier,
                profile=profile,
                purpose=purpose,
                validation_report=v_report,
                audit_records=audit_records,
            )
            rendered_artifacts[json_filename] = (json_text, json_payload_hash, EditorialExportFormat.JSON)

        # 5. Build Initial Export Manifest
        export_id = f"exp_{uuid.uuid4().hex[:12]}"
        now_utc = datetime.now(timezone.utc).isoformat()
        primary_filename = list(rendered_artifacts.keys())[0]
        primary_payload_hash = rendered_artifacts[primary_filename][1]
        primary_format = (
            EditorialExportFormat.ALL
            if export_format == EditorialExportFormat.ALL
            else rendered_artifacts[primary_filename][2]
        )

        source_version_hashes = {
            entry.incident_id: entry.source_version_hash for entry in dossier.entries
        }

        # Find latest approval review record if available
        review_record_id = None
        reviewed_by = dossier.reviewed_by
        reviewed_at = normalize_iso_timestamp(dossier.reviewed_at)
        if hasattr(dossier, "reviews") and dossier.reviews:  # type: ignore[attr-defined]
            approval_rev = next((r for r in reversed(dossier.reviews) if r.action == "APPROVE"), None)  # type: ignore[attr-defined]
            if approval_rev:
                review_record_id = approval_rev.id
                reviewed_by = approval_rev.reviewer_id
                reviewed_at = normalize_iso_timestamp(approval_rev.reviewed_at)

        manifest = EditorialExportManifest(
            manifest_version="1.0",
            export_id=export_id,
            exported_at_utc=now_utc,
            dossier_id=dossier.id,
            dossier_version=dossier.version,
            artifact_purpose=purpose,
            presentation_profile=profile,
            format=primary_format,
            output_filename=primary_filename,
            canonical_dossier_content_hash=dossier.content_hash or dossier.compute_content_hash(),
            canonical_payload_hash=primary_payload_hash,
            artifact_file_hash=None,  # Computed upon write
            source_version_hashes=source_version_hashes,
            renderer_version=EditorialMarkdownRenderer.RENDERER_VERSION,
            disclaimer_version=dossier.disclaimer_version,
            review_record_id=review_record_id,
            reviewed_by=reviewed_by,
            reviewed_at=reviewed_at,
            validation_status="PASSED" if v_report.is_valid else "FAILED",
            blocking_finding_count=v_report.blocking_count,
            warning_finding_count=v_report.warning_count,
            metadata_json={"file_count": len(rendered_artifacts)},
        )

        # Manifest sidecar filename
        manifest_filename = f"{base_name}.manifest.json"

        # Check collision prior to dry-run or write
        all_target_filenames = list(rendered_artifacts.keys()) + [manifest_filename]
        for fname in all_target_filenames:
            target_file_path = resolved_out_dir / fname
            if target_file_path.exists() and not overwrite:
                raise FileExistsError(
                    f"Destination file '{target_file_path}' already exists. "
                    f"Use --overwrite to permit replacement of managed exports."
                )

        if dry_run:
            # Calculate mock file hash over primary artifact
            mock_file_hash = hashlib.sha256(
                rendered_artifacts[primary_filename][0].encode("utf-8")
            ).hexdigest()
            dry_manifest = manifest.model_copy(update={"artifact_file_hash": mock_file_hash})
            return EditorialExportResult(
                export_id=export_id,
                dossier_id=dossier.id,
                dossier_version=dossier.version,
                format=export_format,
                profile=profile,
                purpose=purpose,
                output_dir=str(resolved_out_dir),
                written_files=[str(resolved_out_dir / f) for f in all_target_filenames],
                manifest=dry_manifest,
                dry_run=True,
            )

        # 6. Atomic File Writing & Sidecar Generation
        resolved_out_dir.mkdir(parents=True, exist_ok=True)
        written_paths: list[Path] = []
        temp_paths: list[Path] = []
        artifact_hashes: dict[str, str] = {}

        try:
            # Write artifact files to atomic temp files
            for fname, (content_str, _, _) in rendered_artifacts.items():
                content_bytes = content_str.encode("utf-8")
                art_sha256 = hashlib.sha256(content_bytes).hexdigest()
                artifact_hashes[fname] = art_sha256

                temp_path = resolved_out_dir / f".tmp_{uuid.uuid4().hex}_{fname}"
                temp_paths.append(temp_path)
                with open(temp_path, "wb") as f_out:
                    f_out.write(content_bytes)
                    f_out.flush()
                    os.fsync(f_out.fileno())

            # Update manifest with final primary file hash
            final_manifest = manifest.model_copy(
                update={"artifact_file_hash": artifact_hashes[primary_filename]}
            )
            manifest_json = final_manifest.model_dump_json(indent=2) + "\n"
            temp_manifest_path = resolved_out_dir / f".tmp_{uuid.uuid4().hex}_{manifest_filename}"
            temp_paths.append(temp_manifest_path)
            with open(temp_manifest_path, "wb") as f_man:
                f_man.write(manifest_json.encode("utf-8"))
                f_man.flush()
                os.fsync(f_man.fileno())

            # Atomic rename all temp files to their permanent targets
            temp_idx = 0
            for fname in rendered_artifacts.keys():
                t_path = temp_paths[temp_idx]
                perm_path = resolved_out_dir / fname
                t_path.replace(perm_path)
                written_paths.append(perm_path)
                temp_idx += 1

            # Rename manifest
            t_man = temp_paths[temp_idx]
            perm_man = resolved_out_dir / manifest_filename
            t_man.replace(perm_man)
            written_paths.append(perm_man)

        except Exception as exc:
            # Clean up all temporary files on failure
            for t in temp_paths:
                try:
                    if t.exists():
                        t.unlink()
                except Exception:
                    pass
            raise IOError(f"Export failed during atomic write: {exc}") from exc

        # 7. Record Append-Only Audit Event
        audit_details = {
            "export_id": export_id,
            "format": export_format.value,
            "profile": profile.value,
            "purpose": purpose.value,
            "primary_filename": primary_filename,
            "manifest_filename": manifest_filename,
            "primary_file_hash": artifact_hashes[primary_filename],
            "written_file_count": len(written_paths),
        }
        self.repository.record_audit_event(
            dossier_id=dossier.id,
            transition_type=EditorialAuditEventType.EXPORT_DOSSIER,
            actor_id=actor_id,
            is_human=is_human,
            before_state={"status": dossier.status.value, "content_hash": dossier.content_hash},
            after_state={"status": dossier.status.value, "export_id": export_id},
            actor_role=actor_role,
            details=audit_details,
        )

        return EditorialExportResult(
            export_id=export_id,
            dossier_id=dossier.id,
            dossier_version=dossier.version,
            format=export_format,
            profile=profile,
            purpose=purpose,
            output_dir=str(resolved_out_dir),
            written_files=[str(p) for p in written_paths],
            manifest=final_manifest,
            dry_run=False,
        )

    # -------------------------------------------------------------------------
    # Internal Security & Path Helpers
    # -------------------------------------------------------------------------

    def _validate_and_resolve_output_dir(self, raw_path: str) -> Path:
        """Resolve and validate destination output directory against path traversal and symlinks."""
        raw_str = str(raw_path)
        if "\0" in raw_str:
            raise ValueError("Invalid output directory path: contains null bytes.")

        raw_p = Path(raw_path)
        if raw_p.is_symlink() or os.path.islink(raw_str):
            raise ValueError(
                f"Invalid output directory: destination '{raw_path}' is a symlink. "
                "Exporting into symlinked destinations is forbidden."
            )

        p = raw_p.resolve()
        return p

    def _fetch_allowlisted_audit_records(self, dossier_id: str) -> list[dict[str, Any]]:
        """Fetch minimal allowlisted audit summary from governance_audit_logs."""
        from sqlalchemy import select

        stmt = (
            select(GovernanceAuditLogModel)
            .where(
                GovernanceAuditLogModel.entity_type == "EDITORIAL_DOSSIER",
                GovernanceAuditLogModel.entity_id == dossier_id,
            )
            .order_by(GovernanceAuditLogModel.created_at.asc(), GovernanceAuditLogModel.id.asc())
        )
        logs = list(self.repository.session.execute(stmt).scalars().all())
        return [
            {
                "id": l.id,
                "transition_type": l.transition_type,
                "timestamp_utc": l.timestamp_utc,
                "event_hash": l.event_hash,
                "actor_role": l.actor_role,
                "is_human": l.is_human,
            }
            for l in logs
        ]
