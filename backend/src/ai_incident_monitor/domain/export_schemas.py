"""Utility to export JSON Schemas (Draft 2020-12) for all core domain models."""

import json
from pathlib import Path
from typing import Any, Optional

from ai_incident_monitor.domain.audit import AuditMetadata, ModelInferenceMetadata
from ai_incident_monitor.domain.causality import AIInvolvementAssessment, CausalAssessment
from ai_incident_monitor.domain.claims import ClaimRecord
from ai_incident_monitor.domain.dates import DateRange, DateWithPrecision
from ai_incident_monitor.domain.evidence import EvidenceRecord, QuoteSpan
from ai_incident_monitor.domain.money import CurrencyConversionRecord, MonetaryAmount
from ai_incident_monitor.domain.reviews import HumanReviewRecord, ReviewerIdentity
from ai_incident_monitor.domain.sources import ContentHash, CopyrightRestriction, SourceReference
from ai_incident_monitor.domain.uncertainty import DisputedFact, UncertaintyRecord

DOMAIN_MODELS = {
    "SourceReference": SourceReference,
    "EvidenceRecord": EvidenceRecord,
    "ClaimRecord": ClaimRecord,
    "CausalAssessment": CausalAssessment,
    "AIInvolvementAssessment": AIInvolvementAssessment,
    "UncertaintyRecord": UncertaintyRecord,
    "HumanReviewRecord": HumanReviewRecord,
    "AuditMetadata": AuditMetadata,
    "MonetaryAmount": MonetaryAmount,
    "DateWithPrecision": DateWithPrecision,
    "DateRange": DateRange,
    "ContentHash": ContentHash,
    "CopyrightRestriction": CopyrightRestriction,
    "QuoteSpan": QuoteSpan,
    "ReviewerIdentity": ReviewerIdentity,
    "ModelInferenceMetadata": ModelInferenceMetadata,
    "CurrencyConversionRecord": CurrencyConversionRecord,
    "DisputedFact": DisputedFact,
}


def get_all_json_schemas() -> dict[str, dict[str, Any]]:
    """Return JSON schema dicts for all domain entities."""
    return {name: model.model_json_schema() for name, model in DOMAIN_MODELS.items()}


def export_json_schemas_to_dir(output_dir: Path) -> dict[str, Path]:
    """Export each model's JSON Schema to a .json file in the target directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    exported_files: dict[str, Path] = {}

    for name, schema in get_all_json_schemas().items():
        file_path = output_dir / f"{name}.schema.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(schema, f, indent=2)
        exported_files[name] = file_path

    return exported_files
