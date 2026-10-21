"""Unit tests for IngestionManifest, canonical serialization, and provenance hash chaining.

Governing Charter: Project Constitution (Rules 1, 4, 11, 14, 15, 16),
ADR-008, ADR-010, SRC-002, AUD-004.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_incident_monitor.ingestion.manifest import (
    DEFAULT_CHAIN_SCOPE,
    IngestionManifest,
    ManifestBuilder,
    ManifestChainStore,
    ManifestForkError,
    ManifestRunStatus,
    ManifestStorageError,
    canonical_json_dumps,
    verify_provenance_chain,
)


class TestCanonicalSerialization:
    """Verifies deterministic canonical JSON serialization."""

    def test_canonical_json_key_sorting_and_whitespace(self) -> None:
        raw_dict = {"z": 1, "a": 2, "m": [3, 2, 1], "b": {"y": True, "x": False}}
        serialized = canonical_json_dumps(raw_dict)
        # Check sort_keys
        assert serialized == '{"a":2,"b":{"x":false,"y":true},"m":[3,2,1],"z":1}'
        assert " " not in serialized  # No whitespace after separators

    def test_manifest_canonical_hash_is_deterministic(self) -> None:
        builder1 = ManifestBuilder(environment="test", chain_scope="test_scope")
        builder1.started_at = "2026-10-20T12:00:00+00:00"
        builder1.source_url = "https://example.com/feed.xml"
        manifest1 = builder1.finalize(previous_manifest_sha256=None)

        # Same data should produce bit-for-bit identical hash
        manifest1_recomputed = manifest1.compute_sha256()
        assert manifest1.manifest_sha256 == manifest1_recomputed
        assert manifest1.verify_self_hash() is True


class TestProvenanceHashChain:
    """Verifies sequential hash linkage, genesis validation, and fork prevention."""

    def test_genesis_manifest_has_none_previous_hash(self, tmp_path: Path) -> None:
        store = ManifestChainStore(storage_dir=tmp_path)
        builder = ManifestBuilder(environment="test", chain_scope="genesis_test")
        genesis = builder.finalize(previous_manifest_sha256=None)

        assert genesis.previous_manifest_sha256 is None
        store.append_manifest(genesis)

        chain = store.get_chain("genesis_test")
        assert len(chain) == 1
        assert chain[0].manifest_id == genesis.manifest_id

    def test_non_genesis_manifest_with_none_previous_hash_rejected(self, tmp_path: Path) -> None:
        store = ManifestChainStore(storage_dir=tmp_path)
        b1 = ManifestBuilder(environment="test", chain_scope="link_test")
        m1 = b1.finalize(previous_manifest_sha256=None)
        store.append_manifest(m1)

        # Second manifest attempting to have previous=None
        b2 = ManifestBuilder(environment="test", chain_scope="link_test")
        m2 = b2.finalize(previous_manifest_sha256=None)

        with pytest.raises(ManifestForkError, match="Chain linkage error"):
            store.append_manifest(m2)

    def test_sequential_hash_chain_success(self, tmp_path: Path) -> None:
        store = ManifestChainStore(storage_dir=tmp_path)
        scope = "chain_valid_test"

        # Manifest 0 (Genesis)
        b0 = ManifestBuilder(environment="test", chain_scope=scope)
        m0 = b0.finalize(previous_manifest_sha256=None)
        store.append_manifest(m0)

        # Manifest 1
        b1 = ManifestBuilder(environment="test", chain_scope=scope)
        m1 = b1.finalize(previous_manifest_sha256=m0.manifest_sha256)
        store.append_manifest(m1)

        # Manifest 2
        b2 = ManifestBuilder(environment="test", chain_scope=scope)
        m2 = b2.finalize(previous_manifest_sha256=m1.manifest_sha256)
        store.append_manifest(m2)

        chain = store.get_chain(scope)
        assert len(chain) == 3
        report = verify_provenance_chain(chain, chain_scope=scope)
        assert report.is_valid is True
        assert len(report.anomalies) == 0
        assert report.head_manifest_sha256 == m2.manifest_sha256
        assert report.genesis_manifest_id == m0.manifest_id

    def test_tampered_manifest_detected_by_verification(self) -> None:
        b0 = ManifestBuilder(environment="test", chain_scope="tamper_test")
        m0 = b0.finalize(previous_manifest_sha256=None)

        b1 = ManifestBuilder(environment="test", chain_scope="tamper_test")
        m1 = b1.finalize(previous_manifest_sha256=m0.manifest_sha256)

        # Tamper with m0 by changing response_bytes but leaving manifest_sha256
        tampered_dict = m0.to_canonical_dict(include_hash=True)
        tampered_dict["response_bytes"] = 999999  # Tampered field
        tampered_m0 = IngestionManifest(
            manifest_id=tampered_dict["manifest_id"],
            schema_version=tampered_dict["schema_version"],
            environment=tampered_dict["environment"],
            chain_scope=tampered_dict["chain_scope"],
            ingestion_run_id=tampered_dict["ingestion_run_id"],
            run_status=ManifestRunStatus(tampered_dict["run_status"]),
            connector_id=tampered_dict["connector_id"],
            connector_version=tampered_dict["connector_version"],
            connector_policy_version=tampered_dict["connector_policy_version"],
            parser_version=tampered_dict["parser_version"],
            build_identifier=tampered_dict["build_identifier"],
            started_at=tampered_dict["started_at"],
            finalized_at=tampered_dict["finalized_at"],
            approved_source_host=tampered_dict["approved_source_host"],
            source_url=tampered_dict["source_url"],
            final_url=tampered_dict["final_url"],
            redirect_chain_summary=tampered_dict["redirect_chain_summary"],
            request_method=tampered_dict["request_method"],
            http_status=tampered_dict["http_status"],
            content_type=tampered_dict["content_type"],
            response_bytes=tampered_dict["response_bytes"],
            response_sha256=tampered_dict["response_sha256"],
            staged_payload_ref=tampered_dict["staged_payload_ref"],
            parse_status=tampered_dict["parse_status"],
            parser_warning_codes=tampered_dict["parser_warning_codes"],
            normalized_record_ids=tampered_dict["normalized_record_ids"],
            normalized_record_count=tampered_dict["normalized_record_count"],
            duplicate_summary=tampered_dict["duplicate_summary"],
            retry_summary=tampered_dict["retry_summary"],
            validation_warning_codes=tampered_dict["validation_warning_codes"],
            previous_manifest_sha256=tampered_dict["previous_manifest_sha256"],
            manifest_sha256=tampered_dict["manifest_sha256"],
        )

        chain = [tampered_m0, m1]
        report = verify_provenance_chain(chain, chain_scope="tamper_test")
        assert report.is_valid is False
        assert any(a.anomaly_type == "ALTERED_MANIFEST_HASH" for a in report.anomalies)

    def test_broken_linkage_detected_by_verification(self) -> None:
        b0 = ManifestBuilder(environment="test", chain_scope="broken_link")
        m0 = b0.finalize(previous_manifest_sha256=None)

        b1 = ManifestBuilder(environment="test", chain_scope="broken_link")
        # Incorrect previous hash
        m1 = b1.finalize(previous_manifest_sha256="deadbeef" * 8)

        chain = [m0, m1]
        report = verify_provenance_chain(chain, chain_scope="broken_link")
        assert report.is_valid is False
        assert any(a.anomaly_type == "BROKEN_CHAIN_LINKAGE" for a in report.anomalies)

    def test_self_link_detected(self) -> None:
        b0 = ManifestBuilder(environment="test", chain_scope="self_link")
        # Manually create self-link manifest
        m0 = b0.finalize(previous_manifest_sha256=None)
        self_linked = IngestionManifest(
            manifest_id=m0.manifest_id,
            schema_version=m0.schema_version,
            environment=m0.environment,
            chain_scope=m0.chain_scope,
            ingestion_run_id=m0.ingestion_run_id,
            run_status=m0.run_status,
            connector_id=m0.connector_id,
            connector_version=m0.connector_version,
            connector_policy_version=m0.connector_policy_version,
            parser_version=m0.parser_version,
            build_identifier=m0.build_identifier,
            started_at=m0.started_at,
            finalized_at=m0.finalized_at,
            approved_source_host=m0.approved_source_host,
            source_url=m0.source_url,
            final_url=m0.final_url,
            redirect_chain_summary=m0.redirect_chain_summary,
            request_method=m0.request_method,
            http_status=m0.http_status,
            content_type=m0.content_type,
            response_bytes=m0.response_bytes,
            response_sha256=m0.response_sha256,
            staged_payload_ref=m0.staged_payload_ref,
            parse_status=m0.parse_status,
            parser_warning_codes=m0.parser_warning_codes,
            normalized_record_ids=m0.normalized_record_ids,
            normalized_record_count=m0.normalized_record_count,
            duplicate_summary=m0.duplicate_summary,
            retry_summary=m0.retry_summary,
            validation_warning_codes=m0.validation_warning_codes,
            previous_manifest_sha256=m0.manifest_sha256,  # Self link!
            manifest_sha256=m0.manifest_sha256,
        )

        chain = [self_linked]
        report = verify_provenance_chain(chain, chain_scope="self_link")
        assert report.is_valid is False
        assert any(a.anomaly_type == "SELF_LINK_DETECTED" for a in report.anomalies)

    def test_timestamp_anomaly_detected(self) -> None:
        b0 = ManifestBuilder(environment="test", chain_scope="time_anomaly")
        b0.started_at = "2026-10-20T12:00:00+00:00"
        m0 = b0.finalize(previous_manifest_sha256=None)
        # Create manifest where finalized_at is earlier than started_at
        time_warped = IngestionManifest(
            manifest_id=m0.manifest_id,
            schema_version=m0.schema_version,
            environment=m0.environment,
            chain_scope=m0.chain_scope,
            ingestion_run_id=m0.ingestion_run_id,
            run_status=m0.run_status,
            connector_id=m0.connector_id,
            connector_version=m0.connector_version,
            connector_policy_version=m0.connector_policy_version,
            parser_version=m0.parser_version,
            build_identifier=m0.build_identifier,
            started_at="2026-10-20T14:00:00+00:00",
            finalized_at="2026-10-20T12:00:00+00:00",  # earlier!
            approved_source_host=m0.approved_source_host,
            source_url=m0.source_url,
            final_url=m0.final_url,
            redirect_chain_summary=m0.redirect_chain_summary,
            request_method=m0.request_method,
            http_status=m0.http_status,
            content_type=m0.content_type,
            response_bytes=m0.response_bytes,
            response_sha256=m0.response_sha256,
            staged_payload_ref=m0.staged_payload_ref,
            parse_status=m0.parse_status,
            parser_warning_codes=m0.parser_warning_codes,
            normalized_record_ids=m0.normalized_record_ids,
            normalized_record_count=m0.normalized_record_count,
            duplicate_summary=m0.duplicate_summary,
            retry_summary=m0.retry_summary,
            validation_warning_codes=m0.validation_warning_codes,
            previous_manifest_sha256=None,
            manifest_sha256="",
        )
        # Finalize hash
        valid_hash_time_warped = IngestionManifest(
            **{**time_warped.__dict__, "manifest_sha256": time_warped.compute_sha256()}
        )

        chain = [valid_hash_time_warped]
        report = verify_provenance_chain(chain, chain_scope="time_anomaly")
        assert report.is_valid is False
        assert any(a.anomaly_type == "TIMESTAMP_ANOMALY" for a in report.anomalies)
