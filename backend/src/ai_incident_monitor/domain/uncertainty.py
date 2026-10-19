"""Uncertainty, disputed claims, and evidence gap representations.

Constitutional Rules 2, 3, 21:
- Unknowns must be explicitly captured and classified.
- Disputed facts must preserve both supporting and contradicting evidence.
- Missing evidence must not be converted into negative evidence.
"""

from typing import Optional

from pydantic import Field

from ai_incident_monitor.domain.common import BaseEntity, SchemaVersioned
from ai_incident_monitor.domain.identifiers import (
    EvidenceId,
    IncidentId,
    UncertaintyId,
)
from ai_incident_monitor.domain.vocabularies import UnresolvedReason


class DisputedFact(SchemaVersioned):
    """Specific factual assertion that is contested by one or more parties."""

    assertion: str = Field(min_length=5, description="The specific disputed factual claim")
    contesting_party: str = Field(min_length=2, description="Entity disputing the assertion")
    supporting_evidence_ids: list[EvidenceId] = Field(default_factory=list)
    contradicting_evidence_ids: list[EvidenceId] = Field(default_factory=list)


class UncertaintyRecord(SchemaVersioned):
    """Comprehensive disclosure of known facts, unknown variables, and evidentiary gaps."""

    id: UncertaintyId
    incident_id: IncidentId
    known_facts: list[str] = Field(default_factory=list)
    unknown_facts: list[str] = Field(default_factory=list)
    disputed_facts: list[DisputedFact] = Field(default_factory=list)
    missing_evidence: list[str] = Field(
        default_factory=list, description="Evidence known to exist but not yet publicly accessible"
    )
    conflicting_evidence: list[str] = Field(
        default_factory=list, description="Evidence items that directly contradict each other"
    )
    information_expected_later: Optional[str] = Field(
        default=None, description="Pending postmortems, regulatory findings, or court filings"
    )
    reason_unresolved: UnresolvedReason
    resolution_criteria: Optional[str] = None
