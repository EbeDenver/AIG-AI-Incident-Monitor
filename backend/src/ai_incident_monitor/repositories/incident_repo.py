"""Incident repository providing query and mutation operations for incidents."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ai_incident_monitor.db.models.incident import IncidentModel
from ai_incident_monitor.repositories.base import BaseRepository


class IncidentRepository(BaseRepository[IncidentModel]):
    """Repository managing incident persistence, queries, and status updates."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, IncidentModel)

    def create(self, incident: IncidentModel) -> IncidentModel:
        """Persist a new incident entity."""
        return self.add(incident)

    def get(self, incident_id: str, load_relations: bool = False) -> Optional[IncidentModel]:
        """Fetch an incident by its unique identifier."""
        if not load_relations:
            return self.get_by_id(incident_id)

        stmt = (
            select(IncidentModel)
            .where(IncidentModel.id == incident_id)
            .options(
                selectinload(IncidentModel.claims),
                selectinload(IncidentModel.uncertainties),
                selectinload(IncidentModel.ai_involvements),
            )
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def list_incidents(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[IncidentModel]:
        """List incidents with optional status filter and pagination."""
        stmt = select(IncidentModel)
        if status:
            stmt = stmt.where(IncidentModel.status == status)
        stmt = stmt.order_by(IncidentModel.created_at.desc()).limit(limit).offset(offset)
        return list(self.session.execute(stmt).scalars().all())

    def update_status(self, incident_id: str, new_status: str) -> IncidentModel:
        """Update an incident's lifecycle status."""
        incident = self.get_by_id(incident_id)
        if incident is None:
            raise KeyError(f"Incident '{incident_id}' not found.")
        incident.status = new_status
        self.session.flush()
        return incident
