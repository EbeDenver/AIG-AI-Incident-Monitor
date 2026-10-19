"""Source repository managing external source references and deduplication lookups."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_incident_monitor.db.models.source import SourceReferenceModel
from ai_incident_monitor.repositories.base import BaseRepository


class SourceRepository(BaseRepository[SourceReferenceModel]):
    """Repository managing source references, URLs, and cryptographic digests."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, SourceReferenceModel)

    def create(self, source: SourceReferenceModel) -> SourceReferenceModel:
        """Persist a new source reference."""
        return self.add(source)

    def get(self, source_id: str) -> Optional[SourceReferenceModel]:
        """Fetch a source by its identifier."""
        return self.get_by_id(source_id)

    def find_by_canonical_url(self, canonical_url: str) -> Optional[SourceReferenceModel]:
        """Look up a source reference by its exact canonical URL."""
        stmt = select(SourceReferenceModel).where(
            SourceReferenceModel.canonical_url == canonical_url
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def find_by_url(self, url: str) -> Optional[SourceReferenceModel]:
        """Look up a source reference by its primary URL."""
        stmt = select(SourceReferenceModel).where(SourceReferenceModel.url == url)
        return self.session.execute(stmt).scalar_one_or_none()

    def find_by_content_hash(self, content_hash: str) -> Optional[SourceReferenceModel]:
        """Look up a source reference by its SHA-256 payload digest."""
        stmt = select(SourceReferenceModel).where(
            SourceReferenceModel.content_hash == content_hash.strip().lower()
        )
        return self.session.execute(stmt).scalar_one_or_none()
