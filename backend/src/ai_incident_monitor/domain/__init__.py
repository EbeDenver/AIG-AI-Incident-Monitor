"""Domain layer for AI Incident Monitor (AI Guardians LLC).

Exports all domain models, value objects, controlled vocabularies,
and constitutional validation exceptions.
"""

from ai_incident_monitor.domain.audit import AuditMetadata, ModelInferenceMetadata
from ai_incident_monitor.domain.causality import AIInvolvementAssessment, CausalAssessment
from ai_incident_monitor.domain.claims import ClaimRecord
from ai_incident_monitor.domain.common import (
    BaseEntity,
    ConstitutionalViolationError,
    EpistemicIntegrityError,
    ImmutabilityViolationError,
    InvalidMonetaryStateError,
    SchemaVersioned,
    UngroundedClaimError,
    UnverifiedLegalConclusionError,
    utc_now,
)
from ai_incident_monitor.domain.dates import DateRange, DateWithPrecision
from ai_incident_monitor.domain.evidence import EvidenceRecord, ProvenanceRecord, QuoteSpan
from ai_incident_monitor.domain.export_schemas import export_json_schemas_to_dir, get_all_json_schemas
from ai_incident_monitor.domain.identifiers import (
    ClaimId,
    EvidenceId,
    IncidentId,
    ReviewId,
    SourceId,
    UncertaintyId,
    new_claim_id,
    new_evidence_id,
    new_incident_id,
    new_review_id,
    new_source_id,
    new_uncertainty_id,
)
from ai_incident_monitor.domain.money import CurrencyConversionRecord, MonetaryAmount
from ai_incident_monitor.domain.reviews import HumanReviewRecord, ReviewerIdentity
from ai_incident_monitor.domain.sources import ContentHash, CopyrightRestriction, SourceReference
from ai_incident_monitor.domain.uncertainty import DisputedFact, UncertaintyRecord
from ai_incident_monitor.domain.vocabularies import (
    AccessStatus,
    AIComponentType,
    AIInvolvementStatus,
    AssessmentLifecycleStatus,
    CausalAttributionStatus,
    ClaimMateriality,
    ClaimType,
    ConfidenceLevel,
    CorroborationStatus,
    DatePrecision,
    EpistemicStatus,
    EvidenceDirectness,
    EvidenceSpecificity,
    EvidenceType,
    MonetaryAmountStatus,
    ReviewDecision,
    ReviewStatus,
    SourceAuthority,
    SourceIndependence,
    SourceType,
    SupersessionReason,
    UnresolvedReason,
)

__all__ = [
    # Common
    "BaseEntity",
    "SchemaVersioned",
    "ConstitutionalViolationError",
    "EpistemicIntegrityError",
    "UngroundedClaimError",
    "UnverifiedLegalConclusionError",
    "InvalidMonetaryStateError",
    "ImmutabilityViolationError",
    "utc_now",
    # Identifiers
    "SourceId",
    "EvidenceId",
    "ClaimId",
    "IncidentId",
    "ReviewId",
    "UncertaintyId",
    "new_source_id",
    "new_evidence_id",
    "new_claim_id",
    "new_incident_id",
    "new_review_id",
    "new_uncertainty_id",
    # Vocabularies
    "EpistemicStatus",
    "ClaimType",
    "ClaimMateriality",
    "EvidenceType",
    "EvidenceDirectness",
    "EvidenceSpecificity",
    "SourceType",
    "SourceAuthority",
    "SourceIndependence",
    "CorroborationStatus",
    "ConfidenceLevel",
    "AccessStatus",
    "ReviewStatus",
    "ReviewDecision",
    "CausalAttributionStatus",
    "AIInvolvementStatus",
    "AIComponentType",
    "MonetaryAmountStatus",
    "DatePrecision",
    "AssessmentLifecycleStatus",
    "SupersessionReason",
    "UnresolvedReason",
    # Dates
    "DateWithPrecision",
    "DateRange",
    # Money
    "MonetaryAmount",
    "CurrencyConversionRecord",
    # Sources
    "SourceReference",
    "ContentHash",
    "CopyrightRestriction",
    # Evidence
    "EvidenceRecord",
    "QuoteSpan",
    "ProvenanceRecord",
    # Claims
    "ClaimRecord",
    # Causality
    "CausalAssessment",
    "AIInvolvementAssessment",
    # Uncertainty
    "UncertaintyRecord",
    "DisputedFact",
    # Reviews
    "HumanReviewRecord",
    "ReviewerIdentity",
    # Audit
    "AuditMetadata",
    "ModelInferenceMetadata",
    # Schema Export
    "get_all_json_schemas",
    "export_json_schemas_to_dir",
]
