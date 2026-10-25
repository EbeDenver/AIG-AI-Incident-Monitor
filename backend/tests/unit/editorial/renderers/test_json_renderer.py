"""Unit tests for EditorialJSONRenderer verifying deterministic structured export packages."""

from __future__ import annotations

import json
import pytest

from ai_incident_monitor.editorial.enums import (
    EditorialArtifactPurpose,
    EditorialDossierStatus,
    EditorialPresentationProfile,
    EditorialValidationCode,
    EditorialValidationSeverity,
)
from ai_incident_monitor.editorial.models import (
    EditorialValidationFinding,
    EditorialValidationReport,
)
from ai_incident_monitor.editorial.renderers.json_renderer import EditorialJSONRenderer
from tests.unit.editorial.test_editorial_models import create_sample_dossier


class TestEditorialJSONRenderer:
    def test_deterministic_json_rendering_identical_hashes(self) -> None:
        dossier = create_sample_dossier()
        renderer = EditorialJSONRenderer()

        json1, hash1 = renderer.render(
            dossier,
            profile=EditorialPresentationProfile.DEEP_DIVE_DOSSIER,
            purpose=EditorialArtifactPurpose.INTERNAL_REVIEW_COPY,
        )
        json2, hash2 = renderer.render(
            dossier,
            profile=EditorialPresentationProfile.DEEP_DIVE_DOSSIER,
            purpose=EditorialArtifactPurpose.INTERNAL_REVIEW_COPY,
        )

        assert json1 == json2
        assert hash1 == hash2
        assert len(hash1) == 64

    def test_json_package_structure(self) -> None:
        dossier = create_sample_dossier()
        renderer = EditorialJSONRenderer()

        raw_json, payload_hash = renderer.render(
            dossier,
            profile=EditorialPresentationProfile.DEEP_DIVE_DOSSIER,
            purpose=EditorialArtifactPurpose.INTERNAL_REVIEW_COPY,
        )
        data = json.loads(raw_json)

        assert data["package_version"] == "1.0"
        assert data["artifact_purpose"] == "INTERNAL_REVIEW_COPY"
        assert data["presentation_profile"] == "DEEP_DIVE_DOSSIER"
        assert data["renderer_version"] == "EditorialJSONRenderer/1.0"
        assert data["canonical_payload_hash"] == payload_hash
        assert "dossier" in data
        assert data["dossier"]["id"] == dossier.id
        assert "review_metadata" in data
        assert "validation_summary" in data
        assert "audit_lineage" in data

    def test_non_self_referential_payload_hash(self) -> None:
        dossier = create_sample_dossier()
        renderer = EditorialJSONRenderer()

        raw_json, payload_hash = renderer.render(dossier)
        data = json.loads(raw_json)

        # payload_hash must match canonical_payload_hash stored in metadata
        assert data["canonical_payload_hash"] == payload_hash
        # Ensure the hash is 64 hex characters
        assert len(payload_hash) == 64

    def test_audit_records_sanitized_allowlist_only(self) -> None:
        dossier = create_sample_dossier()
        renderer = EditorialJSONRenderer()

        raw_audit_records = [
            {
                "id": "evt_001",
                "transition_type": "ASSEMBLE_DOSSIER",
                "timestamp_utc": "2026-03-01T12:00:00Z",
                "event_hash": "a" * 64,
                "actor_role": "Lead Editor",
                "is_human": True,
                # Fields that MUST be stripped:
                "secret_token": "bearer-token-12345",
                "private_internal_notes": "Confidential internal discussion",
                "raw_html_body": "<html><body>Raw payload</body></html>",
            }
        ]

        raw_json, _ = renderer.render(dossier, audit_records=raw_audit_records)
        data = json.loads(raw_json)
        lineage = data["audit_lineage"]
        assert len(lineage) == 1
        record = lineage[0]

        assert record["event_id"] == "evt_001"
        assert record["transition_type"] == "ASSEMBLE_DOSSIER"
        assert record["event_hash"] == "a" * 64
        assert record["actor_role"] == "Lead Editor"
        assert record["is_human"] is True

        # Assert unauthorized sensitive fields are stripped
        assert "secret_token" not in record
        assert "private_internal_notes" not in record
        assert "raw_html_body" not in record

    def test_approved_copy_requires_approved_informational_status(self) -> None:
        dossier = create_sample_dossier()  # Status is ASSEMBLED
        renderer = EditorialJSONRenderer()

        with pytest.raises(ValueError) as exc:
            renderer.render(dossier, purpose=EditorialArtifactPurpose.APPROVED_EDITORIAL_COPY)
        assert "expected 'APPROVED_INFORMATIONAL'" in str(exc.value)

    def test_approved_copy_fails_on_content_hash_mismatch(self) -> None:
        dossier = create_sample_dossier().model_copy(
            update={
                "status": EditorialDossierStatus.APPROVED_INFORMATIONAL,
                "reviewed_by": "human_reviewer",
                "content_hash": "e" * 64,  # Corrupt hash
            }
        )
        renderer = EditorialJSONRenderer()

        with pytest.raises(ValueError) as exc:
            renderer.render(dossier, purpose=EditorialArtifactPurpose.APPROVED_EDITORIAL_COPY)
        assert "content hash mismatch" in str(exc.value)

    def test_approved_copy_fails_on_blocking_findings(self) -> None:
        dossier = create_sample_dossier().model_copy(
            update={
                "status": EditorialDossierStatus.APPROVED_INFORMATIONAL,
                "reviewed_by": "human_reviewer",
            }
        )
        dossier = dossier.model_copy(update={"content_hash": dossier.compute_content_hash()})

        v_report = EditorialValidationReport(
            is_valid=False,
            dossier_id=dossier.id,
            dossier_version=dossier.version,
            content_hash=dossier.content_hash,
            total_findings=1,
            blocking_count=1,
            warning_count=0,
            findings=[
                EditorialValidationFinding(
                    severity=EditorialValidationSeverity.BLOCKING,
                    finding_code=EditorialValidationCode.BLOCKED_PROHIBITED_TERM,
                    field_path="title",
                    message="Prohibited statutory assertion.",
                )
            ],
        )

        renderer = EditorialJSONRenderer()
        with pytest.raises(ValueError) as exc:
            renderer.render(
                dossier,
                purpose=EditorialArtifactPurpose.APPROVED_EDITORIAL_COPY,
                validation_report=v_report,
            )
        assert "blocking validation finding" in str(exc.value)

    def test_validation_findings_included_only_in_review_copy(self) -> None:
        dossier = create_sample_dossier()
        v_report = EditorialValidationReport(
            is_valid=False,
            dossier_id=dossier.id,
            dossier_version=dossier.version,
            content_hash=dossier.compute_content_hash(),
            total_findings=1,
            blocking_count=1,
            warning_count=0,
            findings=[
                EditorialValidationFinding(
                    severity=EditorialValidationSeverity.BLOCKING,
                    finding_code=EditorialValidationCode.BLOCKED_PROHIBITED_TERM,
                    field_path="title",
                    message="Prohibited term.",
                )
            ],
        )

        renderer = EditorialJSONRenderer()
        raw_json, _ = renderer.render(
            dossier,
            purpose=EditorialArtifactPurpose.INTERNAL_REVIEW_COPY,
            validation_report=v_report,
        )
        data = json.loads(raw_json)
        assert len(data["validation_summary"]["findings"]) == 1
        assert data["validation_summary"]["findings"][0]["code"] == "BLOCKED_PROHIBITED_TERM"
