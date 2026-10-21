"""End-to-end ingestion pipeline orchestration.

Governing Charter: Project Constitution (Rules 1, 3, 4, 11, 14, 15, 16),
ADR-008, ADR-009, ADR-010, ADR-011, SRC-001, SRC-002, SRC-003, AUD-004.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
from typing import Any, Optional

from sqlalchemy.orm import Session

from ai_incident_monitor.deduplication.engine import DeduplicationEngine
from ai_incident_monitor.ingestion.connectors.base import BaseConnector
from ai_incident_monitor.ingestion.manifest import (
    DEFAULT_CHAIN_SCOPE,
    IngestionManifest,
    ManifestBuilder,
    ManifestChainStore,
    ManifestRunStatus,
)
from ai_incident_monitor.ingestion.models import ConnectorExecutionResult, IngestedItem, IngestionStatus
from ai_incident_monitor.ingestion.staging import RawPayloadStagingStore, StagingMetadataRecord
from ai_incident_monitor.repositories.audit_repo import AuditRepository
from ai_incident_monitor.repositories.incident_repo import IncidentRepository
from ai_incident_monitor.security import (
    UntrustedSourceContentEnvelope,
    create_untrusted_envelope,
    detect_prompt_injection_signals,
    safe_log_snippet,
    sanitize_feed_text,
)


@dataclass
class PipelineExecutionResult:
    """Outcome of an end-to-end ingestion pipeline run."""

    ingestion_run_id: str
    manifest: IngestionManifest
    items: list[IngestedItem]
    envelopes: list[UntrustedSourceContentEnvelope]
    staged_record: Optional[StagingMetadataRecord]
    duplicate_summary: dict[str, int]
    quarantined_count: int
    is_success: bool


class IngestionPipeline:
    """Orchestrates secure fetch, containment, staging, deduplication, and provenance manifests."""

    def __init__(
        self,
        *,
        connector: BaseConnector,
        staging_store: Optional[RawPayloadStagingStore] = None,
        manifest_store: Optional[ManifestChainStore] = None,
        db_session: Optional[Session] = None,
        chain_scope: str = DEFAULT_CHAIN_SCOPE,
        environment: str = "development",
    ) -> None:
        self.connector = connector
        self.staging_store = staging_store
        self.manifest_store = manifest_store or ManifestChainStore()
        self.db_session = db_session
        self.chain_scope = chain_scope
        self.environment = environment

        # Repositories (optional if db_session provided)
        self.incident_repo = IncidentRepository(db_session) if db_session else None
        self.audit_repo = AuditRepository(db_session) if db_session else None
        self.dedup_engine = DeduplicationEngine if db_session else None

    def execute_run(
        self,
        target_url: str,
        etag: Optional[str] = None,
        last_modified: Optional[str] = None,
    ) -> PipelineExecutionResult:
        """Execute a complete end-to-end ingestion run.

        Lifecycle:
        1. Connector fetches & validates payload via SecureHTTPClient.
        2. Raw payload staged (if staging enabled).
        3. Parsed items wrapped in UntrustedSourceContentEnvelopes.
        4. Deduplication evaluated for parsed items.
        5. IngestionManifest finalized and chained.
        6. Audit record appended to immutable log.
        """
        builder = ManifestBuilder(
            environment=self.environment,
            chain_scope=self.chain_scope,
        )
        builder.connector_id = self.connector.name
        builder.connector_version = self.connector.metadata.version
        builder.connector_policy_version = self.connector.metadata.policy_version
        builder.approved_source_host = urllib_host(target_url)
        builder.source_url = target_url

        # 1. Fetch & parse
        exec_res: ConnectorExecutionResult = self.connector.fetch_and_parse(
            target_url,
            etag=etag,
            last_modified=last_modified,
        )

        builder.final_url = target_url
        builder.http_status = exec_res.status_code or 0
        builder.response_bytes = len(exec_res.raw_payload_bytes)
        builder.response_sha256 = exec_res.payload_sha256
        builder.parse_status = exec_res.status.value.upper()

        if exec_res.is_malformed:
            builder.parser_warning_codes.append("MALFORMED_FEED_SYNTAX")

        # Record retry summary
        builder.retry_summary = {
            "attempts": len(exec_res.retry_history) + 1,
            "retried": len(exec_res.retry_history) > 0,
            "cumulative_wait_seconds": sum(r.delay_seconds for r in exec_res.retry_history),
        }

        # 2. Stage raw payload if staging enabled and payload present
        staged_record: Optional[StagingMetadataRecord] = None
        if self.staging_store and exec_res.raw_payload_bytes:
            staged_record = self.staging_store.stage_payload(
                raw_bytes=exec_res.raw_payload_bytes,
                connector_id=self.connector.name,
                ingestion_run_id=builder.ingestion_run_id,
                original_feed_url=target_url,
                final_url=target_url,
            )
            if staged_record:
                builder.staged_payload_ref = {
                    "staging_record_id": staged_record.staging_record_id,
                    "storage_path_ref": staged_record.storage_path_ref,
                    "payload_sha256": staged_record.payload_sha256,
                    "retention_expiration_time": staged_record.retention_expiration_time,
                }

        # 3. Create UntrustedSourceContentEnvelopes
        envelopes: list[UntrustedSourceContentEnvelope] = []
        quarantined_count = 0
        normalized_record_ids: list[str] = []

        for item in exec_res.items:
            san_result = sanitize_feed_text(item.summary_snippet)
            inj_result = detect_prompt_injection_signals(
                item.summary_snippet,
                had_bidi=san_result.removed_bidi_count > 0,
                had_zero_width=san_result.removed_zero_width_count > 0,
            )

            envelope = create_untrusted_envelope(
                text=san_result.cleaned_text,
                source_system=self.connector.name,
                source_record_id=item.source_id,
                provenance_manifest_id=builder.manifest_id,
                sanitization_actions=san_result.actions_taken,
                injection_signal_codes=inj_result.signal_codes,
                quarantined=inj_result.is_quarantined,
            )
            envelopes.append(envelope)
            normalized_record_ids.append(item.source_id)

            if envelope.quarantined:
                quarantined_count += 1
                builder.validation_warning_codes.append("QUARANTINED_INJECTION_SIGNAL")

        builder.normalized_record_ids = normalized_record_ids
        builder.normalized_record_count = len(normalized_record_ids)

        # 4. Deduplication
        duplicate_summary: dict[str, int] = {
            "tier_1_matches": 0,
            "tier_2_matches": 0,
            "tier_3_candidates": 0,
            "tier_4_distinct": len(exec_res.items),
        }
        # If dedup engine is configured, run checks
        if self.dedup_engine and self.db_session and exec_res.items:
            # Map dedup tiers
            for item in exec_res.items:
                res = self.dedup_engine.evaluate(
                    session=self.db_session,
                    proposed_incident_id=item.source_id,
                    proposed_title=item.title,
                    proposed_date=None,
                    source_urls=[item.canonical_url] if item.canonical_url else [],
                )
                if res.tier == 1:
                    duplicate_summary["tier_1_matches"] += 1
                    duplicate_summary["tier_4_distinct"] -= 1
                elif res.tier == 2:
                    duplicate_summary["tier_2_matches"] += 1
                    duplicate_summary["tier_4_distinct"] -= 1
                elif res.tier == 3:
                    duplicate_summary["tier_3_candidates"] += 1
                    duplicate_summary["tier_4_distinct"] -= 1

        builder.duplicate_summary = duplicate_summary

        # 5. Finalize run status
        if exec_res.status == IngestionStatus.SUCCESS:
            builder.run_status = ManifestRunStatus.COMPLETED
        elif exec_res.status == IngestionStatus.NOT_MODIFIED:
            builder.run_status = ManifestRunStatus.COMPLETED
        elif exec_res.status == IngestionStatus.PARTIAL:
            builder.run_status = ManifestRunStatus.PARTIAL
        else:
            builder.run_status = ManifestRunStatus.FAILED

        # 6. Finalize manifest and chain
        latest = self.manifest_store.get_latest_manifest(self.chain_scope)
        prev_hash = latest.manifest_sha256 if latest else None
        final_manifest = builder.finalize(previous_manifest_sha256=prev_hash)
        self.manifest_store.append_manifest(final_manifest)

        # 7. Record immutable audit entry
        if self.audit_repo:
            self.audit_repo.record_action(
                entity_type="INGESTION_RUN",
                entity_id=builder.ingestion_run_id,
                action="FINALIZE_INGESTION_MANIFEST",
                actor_id=f"connector:{self.connector.name}",
                payload_after={
                    "manifest_id": final_manifest.manifest_id,
                    "manifest_sha256": final_manifest.manifest_sha256,
                    "run_status": final_manifest.run_status.value,
                    "normalized_records": final_manifest.normalized_record_count,
                    "quarantined_records": quarantined_count,
                },
            )

        return PipelineExecutionResult(
            ingestion_run_id=builder.ingestion_run_id,
            manifest=final_manifest,
            items=exec_res.items,
            envelopes=envelopes,
            staged_record=staged_record,
            duplicate_summary=duplicate_summary,
            quarantined_count=quarantined_count,
            is_success=exec_res.is_success,
        )


def urllib_host(url: str) -> str:
    """Extract host string safely from URL."""
    import urllib.parse
    return urllib.parse.urlparse(url).hostname or ""
