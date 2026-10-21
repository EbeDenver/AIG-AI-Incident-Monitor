"""Unit tests validating governance reference schemas, anti-fabrication constraints, and manifest hashing."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import pytest
from pydantic import ValidationError

from ai_incident_monitor.governance.enums import (
    ControlLevel,
    FrameworkCode,
    FrameworkStatus,
    GovernanceAuditEventType,
)
from ai_incident_monitor.governance.models import (
    FrameworkControlSchema,
    FrameworkManifestSchema,
    FrameworkReferenceSetSchema,
    GovernanceActorIdentity,
    GovernanceAuditEvent,
    ManifestEntrySchema,
)
from ai_incident_monitor.governance.reference_loader import (
    canonical_json_dumps,
    compute_file_sha256,
    compute_manifest_hash,
    load_framework_manifest,
    load_reference_set,
    parse_block_yaml,
    verify_framework_manifest,
)


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


class TestReferenceSchemas:
    """Tests for reference file integrity, schema validation, and anti-fabrication rules."""

    def test_all_official_reference_files_validate_cleanly(self, repo_root: Path) -> None:
        """Confirm that all repository reference YAML files load and satisfy strict schema constraints."""
        framework_paths = [
            repo_root / "frameworks" / "oecd" / "oecd-principles-2024.yaml",
            repo_root / "frameworks" / "nist" / "nist-ai-rmf-1.0.yaml",
            repo_root / "frameworks" / "eu-ai-act" / "eu-ai-act-2024-1689.yaml",
        ]
        for path in framework_paths:
            assert path.exists(), f"Reference file missing: {path}"
            ref_set = load_reference_set(path)
            assert isinstance(ref_set, FrameworkReferenceSetSchema)
            assert ref_set.framework_code in FrameworkCode
            assert len(ref_set.controls) > 0
            for ctrl in ref_set.controls:
                assert ctrl.source_locator, f"Missing source_locator on {ctrl.external_identifier}"
                assert ctrl.title
                assert ctrl.description

    def test_manifest_verification_happy_path(self, repo_root: Path) -> None:
        """Verify that the official manifest.json matches on-disk SHA-256 hashes perfectly."""
        manifest_path = repo_root / "frameworks" / "manifest.json"
        is_valid, errors = verify_framework_manifest(manifest_path, repo_root)
        assert is_valid is True, f"Manifest verification failed with errors: {errors}"
        assert len(errors) == 0

    def test_deterministic_manifest_hashing_repeatability(self, repo_root: Path) -> None:
        """Confirm that manifest hashing produces identical digests across repeated executions."""
        manifest_path = repo_root / "frameworks" / "manifest.json"
        manifest_obj = load_framework_manifest(manifest_path)
        manifest_dict = manifest_obj.model_dump(mode="json")

        digest1 = compute_manifest_hash(manifest_dict)
        digest2 = compute_manifest_hash(manifest_dict)
        assert digest1 == digest2
        assert len(digest1) == 64

        # Mutation must produce distinct hash
        mutated_dict = copy.deepcopy(manifest_dict)
        mutated_dict["manifest_version"] = "1.0.1-mutated"
        digest_mutated = compute_manifest_hash(mutated_dict)
        assert digest1 != digest_mutated

    def test_negative_reject_unknown_fields_in_control_schema(self) -> None:
        """Binding Correction 4: Reject unknown fields in control schemas (extra='forbid')."""
        with pytest.raises(ValidationError) as exc:
            FrameworkControlSchema(
                external_identifier="TEST-001",
                parent_identifier=None,
                title="Test Title",
                description="Test Description",
                control_level=ControlLevel.PRINCIPLE,
                source_locator="Test Source Locator p. 1",
                status=FrameworkStatus.ACTIVE,
                unknown_fabricated_field="forbidden_payload",  # type: ignore[call-arg]
            )
        assert "extra_forbidden" in str(exc.value)

    def test_negative_reject_unknown_fields_in_reference_set_schema(self) -> None:
        """Binding Correction 4: Reject unknown fields in reference set schema."""
        with pytest.raises(ValidationError) as exc:
            FrameworkReferenceSetSchema(
                framework_code=FrameworkCode.OECD_AI_PRINCIPLES,
                framework_name="OECD Principles",
                version="2024.1",
                source_url="https://legalinstruments.oecd.org/en/instruments/OECD-LEGAL-0449",
                publisher="OECD",
                retrieved_at_utc=datetime.now(timezone.utc),
                verified_at_utc=datetime.now(timezone.utc),
                verified_by="Analyst",
                status=FrameworkStatus.ACTIVE,
                controls=[
                    FrameworkControlSchema(
                        external_identifier="P1",
                        title="T",
                        description="D",
                        control_level=ControlLevel.PRINCIPLE,
                        source_locator="Loc",
                    )
                ],
                fabricated_root_field="unauthorized",  # type: ignore[call-arg]
            )
        assert "extra_forbidden" in str(exc.value)

    def test_negative_reject_duplicate_external_identifiers(self) -> None:
        """Binding Correction 4: Reject duplicate external identifiers in reference set."""
        now = datetime.now(timezone.utc)
        ctrl1 = FrameworkControlSchema(
            external_identifier="IDENTICAL-ID",
            title="First",
            description="Desc 1",
            control_level=ControlLevel.PRINCIPLE,
            source_locator="Loc 1",
        )
        ctrl2 = FrameworkControlSchema(
            external_identifier="IDENTICAL-ID",
            title="Second",
            description="Desc 2",
            control_level=ControlLevel.PRINCIPLE,
            source_locator="Loc 2",
        )
        with pytest.raises(ValidationError) as exc:
            FrameworkReferenceSetSchema(
                framework_code=FrameworkCode.OECD_AI_PRINCIPLES,
                framework_name="OECD Principles",
                version="2024.1",
                source_url="https://legalinstruments.oecd.org/en/instruments/OECD-LEGAL-0449",
                publisher="OECD",
                retrieved_at_utc=now,
                verified_at_utc=now,
                verified_by="Analyst",
                controls=[ctrl1, ctrl2],
            )
        assert "Duplicate external_identifier 'IDENTICAL-ID'" in str(exc.value)

    def test_negative_reject_invalid_parent_identifier(self) -> None:
        """Binding Correction 4: Reject non-existent parent identifiers."""
        now = datetime.now(timezone.utc)
        ctrl = FrameworkControlSchema(
            external_identifier="CHILD-01",
            parent_identifier="NON_EXISTENT_PARENT",
            title="Child",
            description="Child Desc",
            control_level=ControlLevel.SUBCATEGORY,
            source_locator="Loc",
        )
        with pytest.raises(ValidationError) as exc:
            FrameworkReferenceSetSchema(
                framework_code=FrameworkCode.NIST_AI_RMF,
                framework_name="NIST",
                version="1.0.0",
                source_url="https://doi.org/10.6028/NIST.AI.100-1",
                publisher="NIST",
                retrieved_at_utc=now,
                verified_at_utc=now,
                verified_by="Analyst",
                controls=[ctrl],
            )
        assert "references unknown parent_identifier 'NON_EXISTENT_PARENT'" in str(exc.value)

    def test_negative_reject_self_parent_identifier(self) -> None:
        """Binding Correction 4: Reject a control referencing itself as parent."""
        now = datetime.now(timezone.utc)
        ctrl = FrameworkControlSchema(
            external_identifier="SELF-REF",
            parent_identifier="SELF-REF",
            title="Self",
            description="Self Desc",
            control_level=ControlLevel.FUNCTION,
            source_locator="Loc",
        )
        with pytest.raises(ValidationError) as exc:
            FrameworkReferenceSetSchema(
                framework_code=FrameworkCode.NIST_AI_RMF,
                framework_name="NIST",
                version="1.0.0",
                source_url="https://doi.org/10.6028/NIST.AI.100-1",
                publisher="NIST",
                retrieved_at_utc=now,
                verified_at_utc=now,
                verified_by="Analyst",
                controls=[ctrl],
            )
        assert "cannot reference itself as parent" in str(exc.value)

    def test_negative_reject_missing_source_locator(self) -> None:
        """Binding Correction 4: Reject controls with empty source locator."""
        with pytest.raises(ValidationError):
            FrameworkControlSchema(
                external_identifier="P1",
                title="T",
                description="D",
                control_level=ControlLevel.PRINCIPLE,
                source_locator="",  # Empty string rejected by min_length=1
            )

    def test_negative_reject_invalid_url_scheme(self) -> None:
        """Binding Correction 4: Reject non-http(s) source URLs."""
        now = datetime.now(timezone.utc)
        ctrl = FrameworkControlSchema(
            external_identifier="P1",
            title="T",
            description="D",
            control_level=ControlLevel.PRINCIPLE,
            source_locator="Loc",
        )
        with pytest.raises(ValidationError) as exc:
            FrameworkReferenceSetSchema(
                framework_code=FrameworkCode.OECD_AI_PRINCIPLES,
                framework_name="OECD",
                version="2024.1",
                source_url="ftp://malicious.org/repo",
                publisher="OECD",
                retrieved_at_utc=now,
                verified_at_utc=now,
                verified_by="Analyst",
                controls=[ctrl],
            )
        assert "must be an http or https URL" in str(exc.value)

    def test_negative_reject_invalid_sha256_in_manifest(self) -> None:
        """Binding Correction 4: Reject invalid hex SHA-256 strings in manifest."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValidationError) as exc:
            ManifestEntrySchema(
                framework_code=FrameworkCode.OECD_AI_PRINCIPLES,
                version="2024.1",
                file_path="frameworks/oecd/test.yaml",
                content_sha256="NOT_A_VALID_64_CHAR_HEX_HASH",
                publisher="OECD",
                official_source_url="https://example.com",
                retrieved_at_utc=now,
                verified_at_utc=now,
                verified_by="Analyst",
            )
        assert "must be a 64-character lowercase hex string" in str(exc.value)

    def test_negative_tampered_reference_file_detected_by_manifest(self, repo_root: Path) -> None:
        """Verify that altering a single byte in a reference file triggers cryptographic mismatch."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            manifest_path = tmp_root / "manifest.json"
            yaml_path = tmp_root / "test.yaml"

            yaml_path.write_text("dummy: content", encoding="utf-8")
            actual_sha = compute_file_sha256(yaml_path)

            manifest_content = {
                "manifest_version": "1.0.0",
                "updated_at_utc": "2026-10-21T00:00:00Z",
                "hashing_methodology": "SHA-256 over raw UTF-8 bytes",
                "frameworks": [
                    {
                        "framework_code": "OECD_AI_PRINCIPLES",
                        "version": "2024.1",
                        "file_path": "test.yaml",
                        "content_sha256": actual_sha,
                        "publisher": "OECD",
                        "official_source_url": "https://legalinstruments.oecd.org",
                        "retrieved_at_utc": "2024-05-03T00:00:00Z",
                        "verified_at_utc": "2026-10-20T00:00:00Z",
                        "verified_by": "Analyst",
                    }
                ],
            }
            manifest_path.write_text(canonical_json_dumps(manifest_content), encoding="utf-8")

            # Tamper with file
            yaml_path.write_text("dummy: tampered_content", encoding="utf-8")

            is_valid, errors = verify_framework_manifest(manifest_path, tmp_root)
            assert is_valid is False
            assert any("SHA-256 mismatch" in err for err in errors)

    def test_oecd_individual_principles_content(self, repo_root: Path) -> None:
        """Verify content integrity of all 5 OECD AI Principles."""
        ref_set = load_reference_set(repo_root / "frameworks" / "oecd" / "oecd-principles-2024.yaml")
        expected_ids = {"OECD-P1.1", "OECD-P1.2", "OECD-P1.3", "OECD-P1.4", "OECD-P1.5"}
        actual_ids = {c.external_identifier for c in ref_set.controls}
        assert expected_ids == actual_ids

        for c in ref_set.controls:
            assert c.control_level == ControlLevel.PRINCIPLE
            assert c.source_locator.startswith("OECD/LEGAL/0449 Section 1")
            assert c.parent_identifier is None

    def test_nist_functions_and_categories_hierarchy(self, repo_root: Path) -> None:
        """Verify hierarchical integrity of NIST AI RMF functions and categories."""
        ref_set = load_reference_set(repo_root / "frameworks" / "nist" / "nist-ai-rmf-1.0.yaml")
        ctrl_map = {c.external_identifier: c for c in ref_set.controls}

        functions = ["NIST-GOVERN", "NIST-MAP", "NIST-MEASURE", "NIST-MANAGE"]
        for fn in functions:
            assert fn in ctrl_map
            assert ctrl_map[fn].control_level == ControlLevel.FUNCTION
            assert ctrl_map[fn].parent_identifier is None

        # Verify child categories point to valid parent function
        assert ctrl_map["NIST-GOVERN-1"].parent_identifier == "NIST-GOVERN"
        assert ctrl_map["NIST-MAP-1"].parent_identifier == "NIST-MAP"
        assert ctrl_map["NIST-MEASURE-2"].parent_identifier == "NIST-MEASURE"
        assert ctrl_map["NIST-MANAGE-1"].parent_identifier == "NIST-MANAGE"

        # Verify subcategory points to category
        assert ctrl_map["NIST-MEASURE-2.1"].parent_identifier == "NIST-MEASURE-2"

    def test_eu_ai_act_prohibited_and_high_risk_structure(self, repo_root: Path) -> None:
        """Verify EU AI Act Article 5 prohibited and Annex III high risk structures."""
        ref_set = load_reference_set(repo_root / "frameworks" / "eu-ai-act" / "eu-ai-act-2024-1689.yaml")
        ctrl_map = {c.external_identifier: c for c in ref_set.controls}

        # Prohibited practices
        assert "EU-ART-5" in ctrl_map
        prohibited_subs = [
            "EU-ART-5.1.a", "EU-ART-5.1.b", "EU-ART-5.1.c", "EU-ART-5.1.d",
            "EU-ART-5.1.e", "EU-ART-5.1.f", "EU-ART-5.1.g", "EU-ART-5.1.h",
        ]
        for p in prohibited_subs:
            assert p in ctrl_map
            assert ctrl_map[p].parent_identifier == "EU-ART-5"

        # High-risk annex III areas
        assert "EU-ART-6" in ctrl_map
        for point in range(1, 9):
            ext_id = f"EU-ANNEX-III.{point}"
            assert ext_id in ctrl_map
            assert ctrl_map[ext_id].parent_identifier == "EU-ART-6"

    def test_manifest_schema_rejects_duplicate_framework_code(self) -> None:
        """Reject manifest containing duplicate framework_code entries."""
        now = datetime.now(timezone.utc)
        entry1 = ManifestEntrySchema(
            framework_code=FrameworkCode.OECD_AI_PRINCIPLES,
            version="2024.1",
            file_path="p1.yaml",
            content_sha256="a" * 64,
            publisher="OECD",
            official_source_url="https://example.com",
            retrieved_at_utc=now,
            verified_at_utc=now,
            verified_by="Analyst",
        )
        entry2 = ManifestEntrySchema(
            framework_code=FrameworkCode.OECD_AI_PRINCIPLES,
            version="2024.2",
            file_path="p2.yaml",
            content_sha256="b" * 64,
            publisher="OECD",
            official_source_url="https://example.com",
            retrieved_at_utc=now,
            verified_at_utc=now,
            verified_by="Analyst",
        )
        with pytest.raises(ValidationError, match="Duplicate framework_code"):
            FrameworkManifestSchema(
                manifest_version="1.0.0",
                updated_at_utc=now,
                hashing_methodology="SHA-256",
                frameworks=[entry1, entry2],
            )

    def test_manifest_schema_rejects_duplicate_file_path(self) -> None:
        """Reject manifest containing duplicate file_path entries."""
        now = datetime.now(timezone.utc)
        entry1 = ManifestEntrySchema(
            framework_code=FrameworkCode.OECD_AI_PRINCIPLES,
            version="2024.1",
            file_path="same_path.yaml",
            content_sha256="a" * 64,
            publisher="OECD",
            official_source_url="https://example.com",
            retrieved_at_utc=now,
            verified_at_utc=now,
            verified_by="Analyst",
        )
        entry2 = ManifestEntrySchema(
            framework_code=FrameworkCode.NIST_AI_RMF,
            version="1.0.0",
            file_path="same_path.yaml",
            content_sha256="b" * 64,
            publisher="NIST",
            official_source_url="https://example.com",
            retrieved_at_utc=now,
            verified_at_utc=now,
            verified_by="Analyst",
        )
        with pytest.raises(ValidationError, match="Duplicate file_path"):
            FrameworkManifestSchema(
                manifest_version="1.0.0",
                updated_at_utc=now,
                hashing_methodology="SHA-256",
                frameworks=[entry1, entry2],
            )

    def test_parse_block_yaml_folded_and_literal_strings(self) -> None:
        """Test parse_block_yaml handling of folded (>) and literal (|) strings."""
        sample_yaml = """
title: >
  Line one of title
  line two of title.
content: |
  Exact line 1
  Exact line 2
key: "value"
"""
        parsed = parse_block_yaml(sample_yaml)
        assert parsed["title"] == "Line one of title line two of title."
        assert "Exact line 1\nExact line 2" in parsed["content"]
        assert parsed["key"] == "value"

    def test_load_reference_set_file_not_found(self) -> None:
        """Loading a non-existent reference file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_reference_set(Path("non_existent_reference_file.yaml"))

    def test_load_manifest_file_not_found(self) -> None:
        """Loading a non-existent manifest file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_framework_manifest(Path("non_existent_manifest.json"))

    def test_reference_set_empty_controls_rejected(self) -> None:
        """Reject reference set with empty controls list."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValidationError):
            FrameworkReferenceSetSchema(
                framework_code=FrameworkCode.OECD_AI_PRINCIPLES,
                framework_name="OECD",
                version="2024.1",
                source_url="https://example.com",
                publisher="OECD",
                retrieved_at_utc=now,
                verified_at_utc=now,
                verified_by="Analyst",
                controls=[],  # min_length=1 constraint
            )

    def test_governance_actor_identity_validation(self) -> None:
        """Test GovernanceActorIdentity constraints (extra='forbid', required fields)."""
        actor = GovernanceActorIdentity(
            actor_id="reviewer@aiguardians.com",
            is_human=True,
            role="Lead Analyst",
        )
        assert actor.actor_id == "reviewer@aiguardians.com"
        assert actor.is_human is True
        assert actor.role == "Lead Analyst"

        # Rejects empty actor_id
        with pytest.raises(ValidationError):
            GovernanceActorIdentity(actor_id="", is_human=True)

        # Rejects unknown fields (extra='forbid')
        with pytest.raises(ValidationError):
            GovernanceActorIdentity(
                actor_id="reviewer@aiguardians.com",
                is_human=True,
                unauthorized_attr="forbidden",  # type: ignore[call-arg]
            )

    def test_governance_audit_event_schema_validation(self) -> None:
        """Test GovernanceAuditEvent schema validation and hex hash enforcement."""
        now = datetime.now(timezone.utc)
        actor = GovernanceActorIdentity(actor_id="analyst1", is_human=True)
        event = GovernanceAuditEvent(
            id="audit-evt-001",
            entity_type="incident_framework_mapping",
            entity_id="map-123",
            transition_type=GovernanceAuditEventType.CREATE_MAPPING,
            actor=actor,
            timestamp_utc=now,
            before_state_digest=None,
            after_state_digest="a" * 64,
            event_hash="b" * 64,
            previous_event_hash=None,
            details={"notes": "Genesis event"},
        )
        assert event.id == "audit-evt-001"
        assert event.after_state_digest == "a" * 64

        # Reject malformed after_state_digest
        with pytest.raises(ValidationError, match="Invalid hash"):
            GovernanceAuditEvent(
                id="audit-evt-002",
                entity_type="incident_framework_mapping",
                entity_id="map-123",
                transition_type=GovernanceAuditEventType.CREATE_MAPPING,
                actor=actor,
                timestamp_utc=now,
                after_state_digest="not-a-valid-sha256-hex",
                event_hash="b" * 64,
            )

    def test_framework_control_effective_date_handling(self) -> None:
        """Test FrameworkControlSchema effective_date field validation and parsing."""
        ctrl = FrameworkControlSchema(
            external_identifier="P1.1-TEST",
            parent_identifier=None,
            title="Principle Test",
            description="Testing effective date",
            control_level=ControlLevel.PRINCIPLE,
            source_locator="Section 1",
            status=FrameworkStatus.ACTIVE,
            effective_date="2024-05-01",
        )
        assert str(ctrl.effective_date) == "2024-05-01"

    def test_framework_control_schema_source_locator_required(self) -> None:
        """Constitutional Rule 4: Source locator must be non-empty on reference controls."""
        with pytest.raises(ValidationError):
            FrameworkControlSchema(
                external_identifier="P1.1-FAIL",
                parent_identifier=None,
                title="Title",
                description="Desc",
                control_level=ControlLevel.PRINCIPLE,
                source_locator="",  # min_length=1
                status=FrameworkStatus.ACTIVE,
            )
