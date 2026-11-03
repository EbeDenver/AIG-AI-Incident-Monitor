"""Unified Ingestion Cycle Service.

Executes sequential, rate-limited, provenance-tracked collection across all
configured sources. Shared by CLI, macOS launchd scheduled runs, and portal refresh.

Governing Charter: Project Constitution (Rules 1, 3, 4, 11, 14, 15, 16),
ADR-008, ADR-010, SEC-002, AUD-004.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import sys
import time
from typing import Any, Optional
import uuid

from sqlalchemy.orm import Session

from ai_incident_monitor.db.session import get_engine, get_repo_root
from ai_incident_monitor.ingestion.checkpoints import CheckpointStore, SourceCheckpoint
from ai_incident_monitor.ingestion.connectors.arxiv import ArXivConnector
from ai_incident_monitor.ingestion.connectors.oecd_aim import OECDAIMFeedConnector
from ai_incident_monitor.ingestion.connectors.rss import RSSConnector
from ai_incident_monitor.ingestion.incident_mapper import IngestionIncidentMapper
from ai_incident_monitor.ingestion.lock import (
    ActiveRunInfo,
    IngestionActiveConflictError,
    IngestionLock,
)
from ai_incident_monitor.ingestion.manifest import ManifestChainStore
from ai_incident_monitor.ingestion.models import ConnectorType, IngestionStatus, RateLimitPolicy
from ai_incident_monitor.ingestion.pipeline import IngestionPipeline
from ai_incident_monitor.ingestion.rate_limiter import ConnectorRateLimiter
from ai_incident_monitor.ingestion.sources import SourceConfig, SourceRole, load_source_configs
from ai_incident_monitor.ingestion.staging import RawPayloadStagingStore
from ai_incident_monitor.security import SecureHTTPClient

# Configure logger
logger = logging.getLogger("ai_incident_monitor.ingestion.cycle")


@dataclass
class SourceExecutionSummary:
    """Outcome of processing an individual source within a cycle."""

    source_id: str
    name: str
    role: str
    status: str
    records_fetched: int = 0
    records_created: int = 0
    records_updated: int = 0
    records_skipped: int = 0
    records_failed: int = 0
    error_message: Optional[str] = None


@dataclass
class IngestionCycleSummary:
    """Comprehensive summary of an ingestion cycle execution."""

    run_id: str
    trigger: str
    started_at_utc: str
    finished_at_utc: Optional[str] = None
    duration_seconds: float = 0.0
    overall_status: str = "STARTED"
    sources: list[SourceExecutionSummary] = field(default_factory=list)
    total_fetched: int = 0
    total_created: int = 0
    total_updated: int = 0
    total_skipped: int = 0
    total_failed: int = 0
    active_conflict: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


SUMMARY_FILE_NAME = "last_ingestion_summary.json"


def save_cycle_summary(summary: IngestionCycleSummary, repo_root: Optional[Path] = None) -> None:
    """Persist the latest cycle summary to .data/last_ingestion_summary.json."""
    root = repo_root or get_repo_root()
    summary_path = root / ".data" / SUMMARY_FILE_NAME
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = summary_path.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(summary.to_dict(), f, indent=2, sort_keys=True)
    os.replace(tmp_path, summary_path)


def load_latest_summary(repo_root: Optional[Path] = None) -> Optional[dict[str, Any]]:
    """Load the latest cycle summary from disk if available."""
    root = repo_root or get_repo_root()
    summary_path = root / ".data" / SUMMARY_FILE_NAME
    if not summary_path.exists():
        return None
    try:
        with open(summary_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def run_ingestion_cycle(
    *,
    trigger: str = "cli",
    run_id: Optional[str] = None,
    repo_root: Optional[Path] = None,
    custom_sources: Optional[list[SourceConfig]] = None,
    custom_http_client: Optional[SecureHTTPClient] = None,
    db_engine: Optional[Any] = None,
    dry_run: bool = False,
    force: bool = False,
) -> IngestionCycleSummary:
    """Execute complete ingestion cycle across configured sources.
    
    Shared by CLI, macOS launchd scheduled runs, and portal refresh.
    """
    start_time = time.time()
    active_run_id = run_id or f"run_{uuid.uuid4().hex[:12]}"
    now_utc = datetime.now(timezone.utc).isoformat()
    root = repo_root or get_repo_root()

    summary = IngestionCycleSummary(
        run_id=active_run_id,
        trigger=trigger,
        started_at_utc=now_utc,
    )

    # 1. Acquire exclusive lock
    lock = IngestionLock(
        trigger=trigger,
        run_id=active_run_id,
        lock_file_path=root / ".data" / "ingestion.lock",
    )

    try:
        lock.acquire()
    except IngestionActiveConflictError as conflict:
        logger.warning(
            f"Ingestion cycle aborted: existing run '{conflict.active_info.run_id}' "
            f"triggered by '{conflict.active_info.trigger}' is currently active."
        )
        summary.overall_status = "ALREADY_RUNNING"
        summary.finished_at_utc = datetime.now(timezone.utc).isoformat()
        summary.duration_seconds = time.time() - start_time
        summary.active_conflict = asdict(conflict.active_info)
        # We do NOT overwrite the summary of an active run with a collision notice
        return summary

    try:
        # 2. Initialize stores and configs
        checkpoint_store = CheckpointStore(root / ".data" / "ingestion_checkpoints.json")
        manifest_store = ManifestChainStore(root / ".data" / "manifests")
        staging_store = RawPayloadStagingStore(root / ".data" / "raw_feeds")
        if db_engine is not None:
            engine = db_engine
        elif repo_root is not None:
            engine = get_engine(f"sqlite:///{root}/.data/dev.db")
        else:
            engine = get_engine()

        sources = custom_sources if custom_sources is not None else load_source_configs()

        has_partial_failure = False
        has_fatal_failure = False

        # 3. Process sources sequentially
        for src in sources:
            src_summary = SourceExecutionSummary(
                source_id=src.source_id,
                name=src.name,
                role=src.role.value,
                status="SKIPPED",
            )

            # Skip offline/manual sources during unattended polling
            if src.role == SourceRole.OFFICIAL_MANUAL_EXPORT or src.connector_type == ConnectorType.OECD_EXPORT:
                src_summary.status = "SKIPPED_OFFLINE_SOURCE"
                summary.sources.append(src_summary)
                continue

            # Skip disabled sources or feeds without configured URLs
            if not src.enabled or not src.endpoint_url:
                src_summary.status = "DISABLED" if not src.enabled else "NO_LIVE_FEED_CONFIGURED"
                summary.sources.append(src_summary)
                continue

            # Rate limit check before outbound call
            limiter = ConnectorRateLimiter(policy=RateLimitPolicy(min_interval_seconds=src.rate_limit_seconds))
            limiter.acquire()

            # Load checkpoint tokens for conditional GET unless force=True
            checkpoint = checkpoint_store.get_checkpoint(src.source_id)
            req_etag = None if force else checkpoint.etag
            req_last_modified = None if force else checkpoint.last_modified

            # Build connector
            http_client = custom_http_client or SecureHTTPClient()
            connector = None
            if src.connector_type == ConnectorType.ARXIV:
                connector = ArXivConnector(
                    http_client=http_client,
                    enabled=True,
                    rate_limit_seconds=src.rate_limit_seconds,
                )
            elif src.connector_type in (ConnectorType.RSS, ConnectorType.ATOM):
                connector = RSSConnector(
                    http_client=http_client,
                    allowed_source_hosts=set(src.allowed_hosts),
                    enabled=True,
                )
            elif src.connector_type == ConnectorType.OECD_AIM_FEED:
                connector = OECDAIMFeedConnector(
                    http_client=http_client,
                    rate_limit_seconds=src.rate_limit_seconds,
                    enabled=True,
                )

            if not connector:
                src_summary.status = "UNSUPPORTED_CONNECTOR"
                summary.sources.append(src_summary)
                continue

            # Execute pipeline
            try:
                with Session(engine) as db_session:
                    pipeline = IngestionPipeline(
                        connector=connector,
                        staging_store=staging_store,
                        manifest_store=manifest_store,
                        db_session=db_session,
                        environment="production" if trigger == "scheduled" else "development",
                    )

                    pipe_res = pipeline.execute_run(
                        target_url=src.endpoint_url,
                        etag=req_etag,
                        last_modified=req_last_modified,
                    )

                    src_summary.records_fetched = len(pipe_res.items)

                    if not pipe_res.is_success:
                        src_summary.status = "FAILED"
                        src_summary.error_message = pipe_res.error_details or f"Ingestion error: {pipe_res.manifest.parse_status}"
                        has_partial_failure = True
                        checkpoint_store.save_checkpoint(
                            src.source_id,
                            status="FAILED",
                            error_message=src_summary.error_message,
                        )
                        summary.sources.append(src_summary)
                        continue

                    if pipe_res.manifest.http_status == 304 or not pipe_res.items:
                        src_summary.status = "NOT_MODIFIED"
                        if not dry_run:
                            checkpoint_store.save_checkpoint(
                                src.source_id,
                                status="NOT_MODIFIED",
                                etag=pipe_res.etag or checkpoint.etag,
                                last_modified=pipe_res.last_modified or checkpoint.last_modified,
                                records_fetched=0,
                                records_skipped=len(pipe_res.items),
                            )
                        summary.sources.append(src_summary)
                        continue

                    # Persist items to database
                    created_count = 0
                    updated_count = 0
                    skipped_count = 0
                    failed_count = 0

                    if not dry_run:
                        mapper = IngestionIncidentMapper(db_session)
                        for item in pipe_res.items:
                            try:
                                inc_id, outcome = mapper.process_item(
                                    item=item,
                                    source_config=src,
                                    manifest_id=pipe_res.manifest.manifest_id,
                                )
                                if outcome == "CREATED":
                                    created_count += 1
                                elif outcome in ("AUTO_LINKED", "POTENTIAL_DUPLICATE"):
                                    updated_count += 1
                                else:
                                    skipped_count += 1
                            except Exception as item_exc:
                                logger.error(f"Failed processing item '{item.source_id}': {item_exc}")
                                failed_count += 1

                        db_session.commit()

                src_summary.records_created = created_count
                src_summary.records_updated = updated_count
                src_summary.records_skipped = skipped_count
                src_summary.records_failed = failed_count

                if pipe_res.is_success:
                    src_summary.status = "SUCCESS"
                else:
                    src_summary.status = "PARTIAL"
                    has_partial_failure = True

                # Save checkpoint - updating success timestamp only on success
                if not dry_run:
                    checkpoint_store.save_checkpoint(
                        src.source_id,
                        status=src_summary.status,
                        etag=pipe_res.etag or checkpoint.etag,
                        last_modified=pipe_res.last_modified or checkpoint.last_modified,
                        records_fetched=src_summary.records_fetched,
                        records_created=src_summary.records_created,
                        records_updated=src_summary.records_updated,
                        records_skipped=src_summary.records_skipped,
                        records_failed=src_summary.records_failed,
                    )

            except Exception as src_exc:
                logger.error(f"Error during ingestion of source '{src.source_id}': {src_exc}")
                src_summary.status = "FAILED"
                src_summary.error_message = str(src_exc)
                has_partial_failure = True
                checkpoint_store.save_checkpoint(
                    src.source_id,
                    status="FAILED",
                    error_message=str(src_exc),
                )

            summary.sources.append(src_summary)

        # 3.5 Bounded Automatic Intelligence Enrichment for newly ingested incidents
        if not dry_run and summary.sources:
            try:
                from ai_incident_monitor.intelligence.service import EnrichmentService
                enrich_service = EnrichmentService()
                with Session(engine) as enrich_session:
                    enrich_service.enrich_batch(enrich_session, limit=10)
            except Exception as enr_exc:
                logger.warning(f"Automatic intelligence enrichment encountered non-fatal error: {enr_exc}")

        # 4. Synthesize overall outcome
        summary.finished_at_utc = datetime.now(timezone.utc).isoformat()
        summary.duration_seconds = round(time.time() - start_time, 3)

        summary.total_fetched = sum(s.records_fetched for s in summary.sources)
        summary.total_created = sum(s.records_created for s in summary.sources)
        summary.total_updated = sum(s.records_updated for s in summary.sources)
        summary.total_skipped = sum(s.records_skipped for s in summary.sources)
        summary.total_failed = sum(s.records_failed for s in summary.sources)

        if has_fatal_failure:
            summary.overall_status = "FAILED"
        elif has_partial_failure:
            summary.overall_status = "PARTIAL"
        elif any(s.status == "SUCCESS" for s in summary.sources):
            summary.overall_status = "SUCCESS"
        else:
            summary.overall_status = "NOT_MODIFIED"

        save_cycle_summary(summary, repo_root=root)
        return summary

    finally:
        lock.release()


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entrypoint for executing an ingestion cycle."""
    parser = argparse.ArgumentParser(
        description="Execute unattended AI incident ingestion cycle across configured sources."
    )
    parser.add_argument(
        "--trigger",
        type=str,
        default="cli",
        choices=["cli", "scheduled", "portal"],
        help="Execution trigger context (default: cli).",
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="Optional explicit run identifier.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform network retrieval and manifest chaining without database persistence.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore cached ETags and checkpoints, forcing a full fetch.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    print(f"\n[INGESTION CYCLE] Starting cycle (trigger: {args.trigger})...")
    summary = run_ingestion_cycle(
        trigger=args.trigger,
        run_id=args.run_id,
        dry_run=args.dry_run,
        force=args.force,
    )

    print(f"[INGESTION CYCLE] Finished in {summary.duration_seconds:.2f}s :: Status: [{summary.overall_status}]")
    print(f"  Run ID       : {summary.run_id}")
    print(f"  Fetched      : {summary.total_fetched}")
    print(f"  New Incidents: {summary.total_created}")
    print(f"  Updated/Dedup: {summary.total_updated}")
    print(f"  Skipped      : {summary.total_skipped}")
    print(f"  Failed       : {summary.total_failed}")

    for s in summary.sources:
        print(f"  - Source: {s.name} ({s.source_id}) -> [{s.status}] (fetched={s.records_fetched}, new={s.records_created})")
        if s.error_message:
            print(f"    Error: {s.error_message}")

    if summary.overall_status in ("SUCCESS", "NOT_MODIFIED"):
        return 0
    elif summary.overall_status in ("PARTIAL", "ALREADY_RUNNING"):
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
