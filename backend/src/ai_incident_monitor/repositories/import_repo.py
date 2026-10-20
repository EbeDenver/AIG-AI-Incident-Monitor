"""Import repository managing raw ingested payloads and deduplication review candidates."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ai_incident_monitor.db.models.import_record import (
    DedupCandidateModel,
    RawImportRecordModel,
)
from ai_incident_monitor.repositories.audit_repo import AuditRepository
from ai_incident_monitor.repositories.base import BaseRepository


class ImportRepository(BaseRepository[RawImportRecordModel]):
    """Repository handling raw import preservation and deduplication candidate workflows."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, RawImportRecordModel)

    def create_raw_record(
        self,
        batch_id: str,
        source_filename: str,
        source_format: str,
        content_hash: str,
        row_index: int,
        raw_payload: dict[str, Any],
        staged_file_path: Optional[str] = None,
    ) -> RawImportRecordModel:
        """Persist a raw imported row with content digest and batch provenance."""
        record = RawImportRecordModel(
            batch_id=batch_id,
            source_filename=source_filename,
            source_format=source_format,
            content_hash=content_hash.strip().lower(),
            row_index=row_index,
            raw_payload=raw_payload,
            staged_file_path=staged_file_path,
            status="INGESTED",
        )
        return self.add(record)

    def get_raw_record(
        self,
        record_id: int,
        load_candidates: bool = False,
    ) -> Optional[RawImportRecordModel]:
        """Fetch a raw import record by ID."""
        if not load_candidates:
            return self.get_by_id(record_id)

        stmt = (
            select(RawImportRecordModel)
            .where(RawImportRecordModel.id == record_id)
            .options(selectinload(RawImportRecordModel.dedup_candidates))
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def list_by_batch(self, batch_id: str) -> list[RawImportRecordModel]:
        """List all raw import records belonging to an ingestion batch."""
        stmt = (
            select(RawImportRecordModel)
            .where(RawImportRecordModel.batch_id == batch_id)
            .order_by(RawImportRecordModel.row_index.asc())
        )
        return list(self.session.execute(stmt).scalars().all())

    def update_raw_record_status(
        self,
        record_id: int,
        status: str,
        incident_id: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> RawImportRecordModel:
        """Update processing status and linkage for a raw import record."""
        record = self.get_by_id(record_id)
        if record is None:
            raise KeyError(f"Raw import record '{record_id}' not found.")
        record.status = status
        if incident_id is not None:
            record.incident_id = incident_id
        if error_message is not None:
            record.error_message = error_message
        self.session.flush()
        return record

    def create_dedup_candidate(
        self,
        raw_import_id: int,
        existing_incident_id: str,
        tier: int,
        similarity_score: float,
        match_rationale: str,
    ) -> DedupCandidateModel:
        """Queue a potential near-duplicate candidate for human review (DEC-P3-003)."""
        candidate = DedupCandidateModel(
            raw_import_id=raw_import_id,
            existing_incident_id=existing_incident_id,
            tier=tier,
            similarity_score=similarity_score,
            match_rationale=match_rationale,
            review_decision=None,
        )
        self.session.add(candidate)
        self.session.flush()
        return candidate

    def get_dedup_candidate(self, candidate_id: int) -> Optional[DedupCandidateModel]:
        """Fetch a deduplication candidate by ID."""
        return self.session.get(DedupCandidateModel, candidate_id)

    def list_pending_dedup_candidates(self) -> list[DedupCandidateModel]:
        """List all pending near-duplicate candidates awaiting human gatekeeper review."""
        stmt = (
            select(DedupCandidateModel)
            .where(DedupCandidateModel.review_decision.is_(None))
            .order_by(DedupCandidateModel.created_at.asc())
        )
        return list(self.session.execute(stmt).scalars().all())

    def resolve_dedup_candidate(
        self,
        candidate_id: int,
        decision: str,
        reviewed_by: str,
        notes: Optional[str] = None,
        audit_repo: Optional[AuditRepository] = None,
    ) -> DedupCandidateModel:
        """Record human gatekeeper review decision (CONFIRMED, REJECTED, DEFERRED) on a deduplication candidate.

        Enforces Constitutional Rules 14 & 16: Zero automated merging; generates an immutable audit trail.
        """
        candidate = self.get_dedup_candidate(candidate_id)
        if candidate is None:
            raise KeyError(f"Dedup candidate '{candidate_id}' not found.")
        norm_decision = decision.strip().upper()
        candidate.review_decision = norm_decision
        candidate.reviewed_by = reviewed_by
        candidate.reviewed_at = datetime.now(timezone.utc)
        self.session.flush()

        # Record immutable audit event for every deduplication decision
        auditor = audit_repo or AuditRepository(self.session)
        auditor.record_action(
            entity_type="DEDUP_CANDIDATE",
            entity_id=str(candidate.id),
            action=f"DEDUP_{norm_decision}",
            actor_id=reviewed_by,
            payload_after={
                "candidate_id": candidate.id,
                "existing_incident_id": candidate.existing_incident_id,
                "tier": candidate.tier,
                "similarity_score": candidate.similarity_score,
                "decision": norm_decision,
                "reviewed_by": reviewed_by,
                "notes": notes,
            },
        )
        self.session.flush()
        return candidate
