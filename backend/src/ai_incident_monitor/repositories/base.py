"""Base generic repository providing transactional session access."""

from __future__ import annotations

from typing import Generic, Optional, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_incident_monitor.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Generic base repository encapsulating common persistence operations."""

    def __init__(self, session: Session, model_class: Type[ModelT]) -> None:
        self.session = session
        self.model_class = model_class

    def get_by_id(self, ident: str | int) -> Optional[ModelT]:
        """Fetch an entity by its primary key."""
        return self.session.get(self.model_class, ident)

    def add(self, entity: ModelT) -> ModelT:
        """Add an entity to the session."""
        self.session.add(entity)
        self.session.flush()
        return entity

    def delete(self, entity: ModelT) -> None:
        """Delete an entity from the session."""
        self.session.delete(entity)
        self.session.flush()
