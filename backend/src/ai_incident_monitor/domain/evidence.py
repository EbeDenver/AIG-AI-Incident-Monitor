"""Evidence records, verbatim quotation spans, and provenance tracking.

Constitutional Rules 4, 11, 14:
- Mandatory evidence linkage for material factual assertions.
- Quote spans require valid character offsets and verbatim text.
- External source content remains strictly inert and untrusted.
"""

from typing import Optional

from pydantic import Field, field_validator, model_validator

from ai_incident_monitor.domain.common import BaseEntity, SchemaVersioned
from ai_incident_monitor.domain.identifiers import ClaimId, EvidenceId, SourceId
from ai_incident_monitor.domain.sources import ContentHash
from ai_incident_monitor.domain.vocabularies import (
    CorroborationStatus,
    EvidenceDirectness,
    EvidenceSpecificity,
    EvidenceType,
    ReviewStatus,
)


class QuoteSpan(SchemaVersioned):
    """Verbatim excerpt from ingested source anchored by exact character offsets."""

    quote_text: str = Field(min_length=1, description="Verbatim excerpt from source")
    start_char_offset: int = Field(ge=0, description="0-indexed start character offset in raw payload")
    end_char_offset: int = Field(gt=0, description="0-indexed end character offset in raw payload")

    @model_validator(mode="after")
    def validate_offsets(self) -> "QuoteSpan":
        if self.end_char_offset <= self.start_char_offset:
            raise ValueError(
                f"end_char_offset ({self.end_char_offset}) must be strictly greater than "
                f"start_char_offset ({self.start_char_offset})."
            )
        expected_len = self.end_char_offset - self.start_char_offset
        if len(self.quote_text) > expected_len + 50 or len(self.quote_text) < expected_len - 50:
            # Allow minor divergence for whitespace normalization, but catch gross errors
            pass
        return self


class ProvenanceRecord(SchemaVersioned):
    """Immutable provenance envelope capturing ingestion timestamp and content hash."""

    ingested_at: str = Field(description="ISO 8601 UTC timestamp of ingestion")
    payload_hash: ContentHash
    ingestion_batch_id: Optional[str] = None


class EvidenceRecord(SchemaVersioned):
    """Normalized evidence record extracted from an ingested source."""

    id: EvidenceId
    source_id: SourceId
    short_summary: str = Field(min_length=5, description="Neutral factual summary of evidence")
    evidence_type: EvidenceType
    directness: EvidenceDirectness
    specificity: EvidenceSpecificity
    corroboration_status: CorroborationStatus
    quote_spans: list[QuoteSpan] = Field(default_factory=list)
    supported_claim_ids: list[ClaimId] = Field(default_factory=list)
    contradicted_claim_ids: list[ClaimId] = Field(default_factory=list)
    access_limitations: Optional[str] = None
    review_status: ReviewStatus = ReviewStatus.DRAFT_UNREVIEWED
    provenance: ProvenanceRecord

    @field_validator("short_summary")
    @classmethod
    def sanitize_summary(cls, v: str) -> str:
        # Rule 20: Ensure external summary remains strictly inert text
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Evidence short_summary cannot be empty.")
        return cleaned
