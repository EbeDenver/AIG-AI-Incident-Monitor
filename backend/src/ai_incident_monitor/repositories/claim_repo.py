"""Claim repository managing assertion persistence, evidence linking, and supersession."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ai_incident_monitor.db.models.claim import ClaimRecordModel
from ai_incident_monitor.db.models.evidence import ClaimEvidenceLinkModel
from ai_incident_monitor.repositories.base import BaseRepository


class ClaimRepository(BaseRepository[ClaimRecordModel]):
    """Repository handling claim records, evidence junctions, and version lineage."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, ClaimRecordModel)

    def create(self, claim: ClaimRecordModel) -> ClaimRecordModel:
        """Persist a new claim record."""
        return self.add(claim)

    def get(self, claim_id: str, load_relations: bool = False) -> Optional[ClaimRecordModel]:
        """Fetch a claim by ID."""
        if not load_relations:
            return self.get_by_id(claim_id)

        stmt = (
            select(ClaimRecordModel)
            .where(ClaimRecordModel.id == claim_id)
            .options(
                selectinload(ClaimRecordModel.evidence_links),
                selectinload(ClaimRecordModel.causal_assessment),
                selectinload(ClaimRecordModel.human_review),
            )
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def list_for_incident(self, incident_id: str) -> list[ClaimRecordModel]:
        """List all claims belonging to an incident."""
        stmt = (
            select(ClaimRecordModel)
            .where(ClaimRecordModel.incident_id == incident_id)
            .order_by(ClaimRecordModel.created_at.asc())
        )
        return list(self.session.execute(stmt).scalars().all())

    def link_evidence(
        self,
        claim_id: str,
        evidence_id: str,
        link_type: str = "SUPPORTING",
    ) -> ClaimEvidenceLinkModel:
        """Link an evidence record to a claim."""
        link = ClaimEvidenceLinkModel(
            claim_id=claim_id,
            evidence_id=evidence_id,
            link_type=link_type,
        )
        self.session.add(link)
        self.session.flush()
        return link

    def supersede_claim(
        self,
        old_claim_id: str,
        new_claim: ClaimRecordModel,
        reason: str,
    ) -> ClaimRecordModel:
        """Supersede an existing claim with a new version, preserving bidirectional lineage."""
        old_claim = self.get_by_id(old_claim_id)
        if old_claim is None:
            raise KeyError(f"Claim '{old_claim_id}' to supersede was not found.")

        new_claim.supersedes = old_claim.id
        new_claim.supersession_reason = reason
        new_claim.lifecycle_status = "INITIAL_ASSESSMENT"

        self.session.add(new_claim)
        self.session.flush()

        old_claim.lifecycle_status = "SUPERSEDED"
        old_claim.superseded_by = new_claim.id
        self.session.flush()

        return new_claim
