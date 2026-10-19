"""Immutable append-only audit log relational model."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from ai_incident_monitor.db.base import Base


class AuditLogModel(Base):
    """Append-only audit trail logging all lifecycle actions (Rule 16/17)."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)

    is_model_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    model_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    prompt_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    payload_before: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    payload_after: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
