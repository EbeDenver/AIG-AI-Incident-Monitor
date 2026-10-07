"""Audit metadata and LLM inference provenance.

Constitutional Rules 14, 16, 17, 19:
- Every generative inference call preserves model ID and prompt hash.
- Machine generation is strictly separated from human review credentials.
- Historical assessments are append-only.
"""

from typing import Optional

from pydantic import Field, model_validator

from ai_incident_monitor.domain.common import BaseEntity, SchemaVersioned
from ai_incident_monitor.domain.identifiers import ReviewId
from ai_incident_monitor.domain.sources import ContentHash


class ModelInferenceMetadata(SchemaVersioned):
    """Provenance tracking for automated model recommendations."""

    model_id: str = Field(min_length=2, description="Specific model identifier")
    prompt_version: str = Field(min_length=1, description="Version tag of system prompt template")
    prompt_hash: ContentHash = Field(description="SHA-256 digest of prompt template")
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    execution_timestamp: str = Field(description="ISO 8601 UTC execution timestamp")


class AuditMetadata(SchemaVersioned):
    """Complete provenance envelope for any generated or reviewed artifact."""

    created_by: str = Field(min_length=2, description="Authoring user or agent identifier")
    is_model_generated: bool = Field(description="True if artifact was produced by LLM inference")
    model_metadata: Optional[ModelInferenceMetadata] = None
    created_at: str = Field(description="ISO 8601 UTC creation timestamp")
    updated_at: str = Field(description="ISO 8601 UTC update timestamp")
    reviewed_by: Optional[str] = None
    human_review_id: Optional[ReviewId] = None
    reviewed_at: Optional[str] = None
    supersedes_id: Optional[str] = None

    @model_validator(mode="after")
    def validate_audit_integrity(self) -> "AuditMetadata":
        # Rule 19: If model generated, inference metadata is mandatory
        if self.is_model_generated and self.model_metadata is None:
            raise ValueError(
                "Model-generated records must include complete ModelInferenceMetadata."
            )

        # Rule 18: Machine recommendations cannot claim human approval without human review
        if self.reviewed_by is not None:
            if self.human_review_id is None or self.reviewed_at is None:
                raise ValueError(
                    "Declaring 'reviewed_by' requires attaching both 'human_review_id' and 'reviewed_at'."
                )

        return self
