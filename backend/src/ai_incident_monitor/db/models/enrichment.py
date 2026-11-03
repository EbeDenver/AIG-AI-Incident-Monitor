"""Incident LLM enrichment relational model.

Governing Charter: Project Constitution (Rules 1, 2, 3, 4, 11, 14, 16),
ADR-011 (Untrusted Source Envelopes), AUD-005, OPS-004.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ai_incident_monitor.db.base import Base
from ai_incident_monitor.db.models.common import TimestampMixin

if TYPE_CHECKING:
    from ai_incident_monitor.db.models.incident import IncidentModel


class IncidentEnrichmentModel(Base, TimestampMixin):
    """Relational model for structured LLM enrichment analysis of an incident."""

    __tablename__ = "incident_enrichments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    incident_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="PENDING", index=True
    )  # PENDING, RUNNING, COMPLETED, FAILED, STALE

    prompt_version: Mapped[str] = mapped_column(String(30), nullable=False, default="1.0.0")
    model_provider: Mapped[str] = mapped_column(String(50), nullable=False, default="mock")
    model_name: Mapped[str] = mapped_column(String(100), nullable=False, default="mock-intelligence-v1")
    prompt_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    cache_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    evidence_sufficiency: Mapped[str] = mapped_column(
        String(30), nullable=False, default="LIMITED_EVIDENCE"
    )  # COMPLETE, PARTIAL, LIMITED_EVIDENCE

    # Factual Explanation components
    executive_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    event_chronology: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON list
    ai_system_role: Mapped[str] = mapped_column(Text, nullable=False, default="")
    affected_stakeholders: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON list
    documented_consequences: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON list
    unknowns_and_disputes: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON list
    evidence_limitations: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Practical Company Preparedness Guidance components
    applicable_profiles: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON list
    early_warning_indicators: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON list
    preventive_controls: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON list
    detection_mechanisms: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON list
    incident_response_actions: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON list
    responsible_functions: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON list
    validation_methods: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON list

    # Telemetry and Audit
    token_count_input: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    token_count_output: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    latency_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    schema_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0.0")

    # Relationship
    incident: Mapped[IncidentModel] = relationship(
        "IncidentModel",
        back_populates="enrichment",
    )
