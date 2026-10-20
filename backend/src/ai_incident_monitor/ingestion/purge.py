"""Deterministic 30-day raw feed purge maintenance command and audit trail.

Implements DEC-P4-002: Deletes aged raw feed payloads exceeding retention TTL (default 30 days),
records append-only audit events, and maintains provenance metadata.

Governing Charter: Project Constitution (Rules 1, 9, 11, 14, 15, 16),
ADR-003, ADR-008, DEC-P4-002.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any

from ai_incident_monitor.ingestion.staging import (
    DEFAULT_RETENTION_DAYS,
    RawPayloadStagingStore,
    StagingMetadataRecord,
    StagingSecurityError,
    StagingStatus,
)


@dataclass
class PurgeAuditEvent:
    """Immutable audit record documenting a raw feed purge decision or action."""

    staging_record_id: str
    ingestion_run_id: str
    storage_path_ref: str
    payload_sha256: str
    outcome: str  # "candidate", "skipped", "deleted", "missing", "failed"
    reason: str
    dry_run: bool
    timestamp_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "staging_record_id": self.staging_record_id,
            "ingestion_run_id": self.ingestion_run_id,
            "storage_path_ref": self.storage_path_ref,
            "payload_sha256": self.payload_sha256,
            "outcome": self.outcome,
            "reason": self.reason,
            "dry_run": self.dry_run,
            "timestamp_utc": self.timestamp_utc,
        }


@dataclass
class PurgeResult:
    """Summary of a raw payload purge run."""

    candidates_count: int = 0
    deleted_count: int = 0
    skipped_count: int = 0
    missing_count: int = 0
    failed_count: int = 0
    dry_run: bool = False
    audit_events: list[PurgeAuditEvent] = field(default_factory=list)


def purge_staged_feeds(
    staging_store: RawPayloadStagingStore,
    *,
    retention_days: int | None = None,
    dry_run: bool = False,
    current_time: datetime | None = None,
) -> PurgeResult:
    """Execute a deterministic purge of aged raw feed payloads.

    Args:
        staging_store: The staging store instance managing the payload directory.
        retention_days: Retention TTL in days (defaults to store's configured retention).
        dry_run: If True, identifies eligible files and records candidates without deleting.
        current_time: Reference time (defaults to datetime.now(timezone.utc)).

    Returns:
        PurgeResult summarizing the run and containing all purge audit events.
    """
    days = retention_days if retention_days is not None else staging_store.retention_days
    now = current_time or datetime.now(timezone.utc)
    now_iso = now.isoformat()

    result = PurgeResult(dry_run=dry_run)
    records = staging_store.list_records()

    for record in records:
        # Only process records that are currently ACTIVE
        if record.purge_status != StagingStatus.ACTIVE:
            continue

        # Check expiration
        try:
            exp_time = datetime.fromisoformat(record.retention_expiration_time)
            # Ensure UTC comparison
            if exp_time.tzinfo is None:
                exp_time = exp_time.replace(tzinfo=timezone.utc)
        except Exception:
            # Fallback if unparseable: skip
            continue

        if now < exp_time:
            # Not yet expired
            continue

        result.candidates_count += 1

        # Check for active run protection
        if record.is_active_run:
            event = PurgeAuditEvent(
                staging_record_id=record.staging_record_id,
                ingestion_run_id=record.ingestion_run_id,
                storage_path_ref=record.storage_path_ref,
                payload_sha256=record.payload_sha256,
                outcome="skipped",
                reason="Protected: ingestion run is currently active/incomplete",
                dry_run=dry_run,
            )
            result.audit_events.append(event)
            result.skipped_count += 1
            continue

        # Check for future legal hold protection
        if record.is_legal_hold:
            event = PurgeAuditEvent(
                staging_record_id=record.staging_record_id,
                ingestion_run_id=record.ingestion_run_id,
                storage_path_ref=record.storage_path_ref,
                payload_sha256=record.payload_sha256,
                outcome="skipped",
                reason="Protected: record is under active legal hold",
                dry_run=dry_run,
            )
            result.audit_events.append(event)
            result.skipped_count += 1
            continue

        # Target file resolution and path containment verification
        target_path = staging_store.staging_root / record.storage_path_ref
        try:
            contained_path = staging_store.validate_path_containment(target_path)
        except StagingSecurityError as sec_err:
            event = PurgeAuditEvent(
                staging_record_id=record.staging_record_id,
                ingestion_run_id=record.ingestion_run_id,
                storage_path_ref=record.storage_path_ref,
                payload_sha256=record.payload_sha256,
                outcome="failed",
                reason=f"Security violation: {sec_err}",
                dry_run=dry_run,
            )
            result.audit_events.append(event)
            result.failed_count += 1
            record.purge_status = StagingStatus.FAILED
            record.purge_error = str(sec_err)
            staging_store.update_record(record)
            continue

        if dry_run:
            event = PurgeAuditEvent(
                staging_record_id=record.staging_record_id,
                ingestion_run_id=record.ingestion_run_id,
                storage_path_ref=record.storage_path_ref,
                payload_sha256=record.payload_sha256,
                outcome="candidate",
                reason=f"Eligible for purge (expired at {record.retention_expiration_time})",
                dry_run=True,
            )
            result.audit_events.append(event)
            continue

        # Real execution: check file existence on disk
        if not contained_path.exists():
            event = PurgeAuditEvent(
                staging_record_id=record.staging_record_id,
                ingestion_run_id=record.ingestion_run_id,
                storage_path_ref=record.storage_path_ref,
                payload_sha256=record.payload_sha256,
                outcome="missing",
                reason="Target file already absent on disk",
                dry_run=False,
            )
            result.audit_events.append(event)
            result.missing_count += 1
            record.purge_status = StagingStatus.MISSING
            record.purge_time = now_iso
            staging_store.update_record(record)
            continue

        try:
            os.remove(contained_path)
            event = PurgeAuditEvent(
                staging_record_id=record.staging_record_id,
                ingestion_run_id=record.ingestion_run_id,
                storage_path_ref=record.storage_path_ref,
                payload_sha256=record.payload_sha256,
                outcome="deleted",
                reason=f"Payload unlinked successfully (retention={days}d)",
                dry_run=False,
            )
            result.audit_events.append(event)
            result.deleted_count += 1
            record.purge_status = StagingStatus.PURGED
            record.purge_time = now_iso
            staging_store.update_record(record)
        except OSError as exc:
            event = PurgeAuditEvent(
                staging_record_id=record.staging_record_id,
                ingestion_run_id=record.ingestion_run_id,
                storage_path_ref=record.storage_path_ref,
                payload_sha256=record.payload_sha256,
                outcome="failed",
                reason=f"OS unlinking error: {exc}",
                dry_run=False,
            )
            result.audit_events.append(event)
            result.failed_count += 1
            record.purge_status = StagingStatus.FAILED
            record.purge_error = str(exc)
            staging_store.update_record(record)

    return result


def main() -> None:
    """CLI entry point for manual raw feed purge."""
    parser = argparse.ArgumentParser(
        description="Deterministic maintenance command to purge raw feed payloads older than retention TTL."
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=int(os.environ.get("RAW_FEED_RETENTION_DAYS", str(DEFAULT_RETENTION_DAYS))),
        help="Retention period in days (default: 30 or RAW_FEED_RETENTION_DAYS).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate purge without deleting files.",
    )
    parser.add_argument(
        "--staging-dir",
        type=str,
        default=None,
        help="Path to staging root (default: .data/raw_feeds).",
    )
    args = parser.parse_args()

    store = RawPayloadStagingStore(staging_root=args.staging_dir, retention_days=args.retention_days)
    result = purge_staged_feeds(store, retention_days=args.retention_days, dry_run=args.dry_run)

    mode_label = "[DRY-RUN]" if result.dry_run else "[EXECUTE]"
    print(f"\n{mode_label} Raw Feed Payload Purge Summary:")
    print(f"  Candidates Evaluated : {result.candidates_count}")
    print(f"  Deleted Successfully : {result.deleted_count}")
    print(f"  Skipped (Active/Hold): {result.skipped_count}")
    print(f"  Missing on Disk      : {result.missing_count}")
    print(f"  Failed Operations    : {result.failed_count}\n")

    for ev in result.audit_events:
        print(f"  - [{ev.outcome.upper()}] {ev.storage_path_ref}: {ev.reason}")


if __name__ == "__main__":
    main()
