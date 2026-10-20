"""Deduplication package providing URL/title normalization and 4-tier matching."""

from ai_incident_monitor.deduplication.engine import (
    DATE_TOLERANCE_DAYS,
    SIMILARITY_THRESHOLD,
    DedupDecision,
    DeduplicationEngine,
)
from ai_incident_monitor.deduplication.normalizer import (
    calculate_title_similarity,
    normalize_title,
    normalize_url,
)

__all__ = [
    "DATE_TOLERANCE_DAYS",
    "DedupDecision",
    "DeduplicationEngine",
    "SIMILARITY_THRESHOLD",
    "calculate_title_similarity",
    "normalize_title",
    "normalize_url",
]
