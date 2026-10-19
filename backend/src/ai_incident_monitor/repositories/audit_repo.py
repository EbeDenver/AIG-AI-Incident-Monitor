"""Immutable append-only audit repository enforcing Constitutional Rule 16."""

from __future__ import annotations

from typing import Any, NoReturn, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_incident_monitor.db.models.audit import AuditLogModel
from ai_incident_monitor.domain.common import ImmutabilityViolationError
from ai_incident_monitor.repositories.base import BaseRepository


class AuditRepository(BaseRepository[AuditLogModel]):
    """Repository managing immutable, append-only audit trail records."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, AuditLogModel)

    def record_action(
        self,
        entity_type: str,
        entity_id: str,
        action: str,
        actor_id: str,
        is_model_generated: bool = False,
        model_id: Optional[str] = None,
        prompt_version: Optional[str] = None,
        prompt_hash: Optional[str] = None,
        temperature: Optional[float] = None,
        payload_before: Optional[dict[str, Any]] = None,
        payload_after: Optional[dict[str, Any]] = None,
    ) -> AuditLogModel:
        """Append a new audit log record to the immutable audit trail."""
        log_entry = AuditLogModel(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor_id=actor_id,
            is_model_generated=is_model_generated,
            model_id=model_id,
            prompt_version=prompt_version,
            prompt_hash=prompt_hash,
            temperature=temperature,
            payload_before=payload_before,
            payload_after=payload_after,
        )
        return self.add(log_entry)

    def get_audit_trail(self, entity_id: str) -> list[AuditLogModel]:
        """Retrieve full chronological audit trail for a specific entity."""
        stmt = (
            select(AuditLogModel)
            .where(AuditLogModel.entity_id == entity_id)
            .order_by(AuditLogModel.recorded_at.asc(), AuditLogModel.id.asc())
        )
        return list(self.session.execute(stmt).scalars().all())

    def list_recent_logs(self, limit: int = 100, offset: int = 0) -> list[AuditLogModel]:
        """List audit logs ordered by recorded_at descending."""
        stmt = (
            select(AuditLogModel)
            .order_by(AuditLogModel.recorded_at.desc(), AuditLogModel.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.execute(stmt).scalars().all())

    def delete(self, entity: AuditLogModel) -> NoReturn:
        """Constitutional Rule 16: Audit records are strictly immutable and cannot be deleted."""
        raise ImmutabilityViolationError(
            "Audit records are append-only. Deletion of audit log entries is strictly forbidden "
            "by Constitutional Rule 16."
        )

    def update(self, *args: Any, **kwargs: Any) -> NoReturn:
        """Constitutional Rule 16: Audit records cannot be modified."""
        raise ImmutabilityViolationError(
            "Audit records are append-only. Modification of audit log entries is strictly forbidden "
            "by Constitutional Rule 16."
        )
