"""Export manifest and cryptographic provenance schemas for editorial dossier artifacts.

Governing Charter: Project Constitution (Rules 1, 3, 10, 11, 12, 14, 15, 17),
ADR-001, ADR-010, ADR-014, ADR-020, ADR-021.
"""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field

from ai_incident_monitor.editorial.enums import (
    EditorialArtifactPurpose,
    EditorialExportFormat,
    EditorialPresentationProfile,
)
from ai_incident_monitor.editorial.models import canonical_sha256


class EditorialExportManifest(BaseModel):
    """Cryptographic provenance manifest accompanying exported editorial dossier artifacts.

    Differentiates:
    - canonical_dossier_content_hash: SHA-256 of the core dossier domain schema.
    - canonical_payload_hash: SHA-256 of the canonical rendered content excluding file metadata.
    - artifact_file_hash: SHA-256 digest of the complete physical file written to disk.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    manifest_version: str = Field(default="1.0")
    export_id: str = Field(min_length=1, max_length=64)
    exported_at_utc: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)$")
    dossier_id: str = Field(min_length=1, max_length=64)
    dossier_version: int = Field(ge=1)
    artifact_purpose: EditorialArtifactPurpose
    presentation_profile: EditorialPresentationProfile
    format: EditorialExportFormat
    output_filename: str = Field(min_length=1)

    canonical_dossier_content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    canonical_payload_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    artifact_file_hash: Optional[str] = Field(default=None, pattern=r"^[a-f0-9]{64}$")

    source_version_hashes: dict[str, str] = Field(default_factory=dict)
    renderer_version: str = Field(min_length=1)
    disclaimer_version: str = Field(min_length=1)

    review_record_id: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None

    validation_status: str = Field(min_length=1)
    blocking_finding_count: int = Field(ge=0, default=0)
    warning_finding_count: int = Field(ge=0, default=0)

    metadata_json: dict[str, Any] = Field(default_factory=dict)

    def canonical_dict(self) -> dict[str, Any]:
        """Deterministic canonical representation for manifest hashing.

        Excludes artifact_file_hash to prevent circular dependency during generation.
        """
        return {
            "manifest_version": self.manifest_version,
            "export_id": self.export_id,
            "exported_at_utc": self.exported_at_utc,
            "dossier_id": self.dossier_id,
            "dossier_version": self.dossier_version,
            "artifact_purpose": self.artifact_purpose.value,
            "presentation_profile": self.presentation_profile.value,
            "format": self.format.value,
            "output_filename": self.output_filename,
            "canonical_dossier_content_hash": self.canonical_dossier_content_hash,
            "canonical_payload_hash": self.canonical_payload_hash,
            "source_version_hashes": {k: self.source_version_hashes[k] for k in sorted(self.source_version_hashes)},
            "renderer_version": self.renderer_version,
            "disclaimer_version": self.disclaimer_version,
            "review_record_id": self.review_record_id,
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at,
            "validation_status": self.validation_status,
            "blocking_finding_count": self.blocking_finding_count,
            "warning_finding_count": self.warning_finding_count,
        }

    def compute_manifest_hash(self) -> str:
        """Compute SHA-256 hash over canonical manifest fields."""
        return canonical_sha256(self.canonical_dict())
