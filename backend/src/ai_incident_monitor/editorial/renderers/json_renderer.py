"""Deterministic JSON package renderer for editorial dossiers.

Governing Charter: Project Constitution (Rules 1, 3, 10, 11, 12, 14, 15, 17),
ADR-001, ADR-014, ADR-020, ADR-021, PRD §4.7.
"""

from __future__ import annotations

from datetime import datetime
import json
from typing import Any, Optional

from ai_incident_monitor.editorial.enums import (
    EditorialArtifactPurpose,
    EditorialDossierStatus,
    EditorialPresentationProfile,
)
from ai_incident_monitor.editorial.models import (
    EditorialDossierSchema,
    EditorialValidationReport,
    canonical_sha256,
    normalize_iso_timestamp,
)
from ai_incident_monitor.editorial.renderers.base import BaseEditorialRenderer


class EditorialJSONRenderer(BaseEditorialRenderer):
    """Deterministic, structured JSON package renderer.

    Produces a versioned, machine-readable export package with:
    - Canonical dossier content and entry representations.
    - Minimal allowlisted audit and review metadata.
    - Non-self-referential cryptographic payload hashing.
    - Zero exposure of credentials, auth tokens, or raw full-text bodies.
    """

    RENDERER_VERSION = "EditorialJSONRenderer/1.0"
    PACKAGE_VERSION = "1.0"

    def render(
        self,
        dossier: EditorialDossierSchema,
        profile: EditorialPresentationProfile = EditorialPresentationProfile.DEEP_DIVE_DOSSIER,
        purpose: EditorialArtifactPurpose = EditorialArtifactPurpose.INTERNAL_REVIEW_COPY,
        validation_report: Optional[EditorialValidationReport] = None,
        audit_records: Optional[list[dict[str, Any]]] = None,
    ) -> tuple[str, str]:
        """Render the dossier into a deterministic JSON package.

        Returns:
            tuple[str, str]: (rendered_json_string, canonical_payload_hash)
        """
        # Enforce approved copy preconditions
        if purpose == EditorialArtifactPurpose.APPROVED_EDITORIAL_COPY:
            if dossier.status != EditorialDossierStatus.APPROVED_INFORMATIONAL:
                raise ValueError(
                    f"Cannot render APPROVED_EDITORIAL_COPY: dossier '{dossier.id}' is in "
                    f"status '{dossier.status.value}', expected 'APPROVED_INFORMATIONAL'."
                )
            computed_hash = dossier.compute_content_hash()
            if dossier.content_hash and dossier.content_hash != computed_hash:
                raise ValueError(
                    f"Cannot render APPROVED_EDITORIAL_COPY: dossier content hash mismatch "
                    f"(recorded='{dossier.content_hash}', computed='{computed_hash}')."
                )
            if validation_report and validation_report.blocking_count > 0:
                raise ValueError(
                    f"Cannot render APPROVED_EDITORIAL_COPY: dossier has "
                    f"{validation_report.blocking_count} blocking validation finding(s)."
                )

        # 1. Prepare canonical payload for non-self-referential hashing
        canonical_content = dossier.canonical_content_dict()
        source_version_hashes = {
            entry.incident_id: entry.source_version_hash for entry in dossier.entries
        }

        canonical_hash_payload: dict[str, Any] = {
            "package_version": self.PACKAGE_VERSION,
            "dossier_id": dossier.id,
            "dossier_version": dossier.version,
            "artifact_purpose": purpose.value,
            "presentation_profile": profile.value,
            "canonical_dossier_content": canonical_content,
            "source_version_hashes": {k: source_version_hashes[k] for k in sorted(source_version_hashes)},
        }
        canonical_payload_hash = canonical_sha256(canonical_hash_payload)

        # 2. Minimal allowlisted audit summary (zero credentials, tokens, or private notes)
        sanitized_audit_summary: list[dict[str, Any]] = []
        if audit_records:
            for rec in audit_records:
                ts = rec.get("timestamp_utc")
                if isinstance(ts, datetime):
                    ts_str = normalize_iso_timestamp(ts)
                elif isinstance(ts, str):
                    ts_str = ts
                else:
                    ts_str = None

                sanitized_audit_summary.append(
                    {
                        "event_id": rec.get("event_id") or rec.get("id"),
                        "transition_type": rec.get("transition_type"),
                        "timestamp_utc": ts_str,
                        "event_hash": rec.get("event_hash"),
                        "actor_role": rec.get("actor_role"),
                        "is_human": rec.get("is_human"),
                    }
                )

        # 3. Assemble complete export package
        export_package: dict[str, Any] = {
            "package_version": self.PACKAGE_VERSION,
            "artifact_purpose": purpose.value,
            "presentation_profile": profile.value,
            "renderer_version": self.RENDERER_VERSION,
            "canonical_payload_hash": canonical_payload_hash,
            "canonical_dossier_content_hash": dossier.content_hash or dossier.compute_content_hash(),
            "dossier": {
                "id": dossier.id,
                "version": dossier.version,
                "title": dossier.title,
                "scope_type": dossier.scope_type.value,
                "coverage_period_start": normalize_iso_timestamp(dossier.coverage_period_start),
                "coverage_period_end": normalize_iso_timestamp(dossier.coverage_period_end),
                "status": dossier.status.value,
                "disclaimer_version": dossier.disclaimer_version,
                "disclaimer_text": dossier.disclaimer_text,
                "methodology_notes": dossier.methodology_notes,
                "summary": dossier.summary.canonical_dict(),
                "entries": [e.canonical_dict() for e in dossier.entries],
            },
            "review_metadata": {
                "reviewed_by": dossier.reviewed_by,
                "reviewed_at": normalize_iso_timestamp(dossier.reviewed_at),
                "supersedes_dossier_id": dossier.supersedes_dossier_id,
                "superseded_by_id": dossier.superseded_by_id,
            },
            "validation_summary": {
                "status": (
                    ("PASSED" if validation_report.is_valid else "FAILED")
                    if validation_report
                    else "NOT_EVALUATED"
                ),
                "is_valid": validation_report.is_valid if validation_report else None,
                "total_findings": (
                    validation_report.total_findings if validation_report else 0
                ),
                "blocking_finding_count": (
                    validation_report.blocking_count if validation_report else 0
                ),
                "warning_finding_count": (
                    validation_report.warning_count if validation_report else 0
                ),
                "findings": (
                    [
                        {
                            "severity": f.severity.value,
                            "finding_code": f.finding_code.value,
                            "code": f.finding_code.value,
                            "field_path": f.field_path,
                            "message": f.message,
                        }
                        for f in validation_report.findings
                    ]
                    if validation_report and purpose == EditorialArtifactPurpose.INTERNAL_REVIEW_COPY
                    else []
                ),
            },
            "audit_lineage": sanitized_audit_summary,
        }

        rendered_json = json.dumps(export_package, indent=2, sort_keys=True, default=str) + "\n"
        return rendered_json, canonical_payload_hash
