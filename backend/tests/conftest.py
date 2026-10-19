"""Pytest fixtures and configuration for domain tests."""

from decimal import Decimal
from pathlib import Path
import pytest

from ai_incident_monitor.domain import (
    AccessStatus,
    ConfidenceLevel,
    ContentHash,
    CorroborationStatus,
    DatePrecision,
    DateWithPrecision,
    EvidenceDirectness,
    EvidenceRecord,
    EvidenceSpecificity,
    EvidenceType,
    MonetaryAmount,
    MonetaryAmountStatus,
    ProvenanceRecord,
    QuoteSpan,
    SourceAuthority,
    SourceIndependence,
    SourceReference,
    SourceType,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
GOLDEN_DIR = FIXTURES_DIR / "golden"
INVALID_DIR = FIXTURES_DIR / "invalid"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def golden_dir() -> Path:
    return GOLDEN_DIR


@pytest.fixture
def invalid_dir() -> Path:
    return INVALID_DIR


@pytest.fixture
def sample_source_reference() -> SourceReference:
    return SourceReference(
        id="SRC-f1e2d3c4-1111",
        title="Official Safety Investigation Report 101",
        publisher="National Transportation Safety Board",
        author="Lead Investigator Jane Doe",
        url="https://ntsb.gov/investigations/ai-101",
        source_type=SourceType.OFFICIAL_POSTMORTEM,
        publication_date=DateWithPrecision(
            precision=DatePrecision.EXACT,
            exact_date="2026-02-14",
            supporting_evidence_ids=[],
        ),
        retrieval_date="2026-02-15T08:00:00Z",
        access_status=AccessStatus.OPEN_PUBLIC,
        authority=SourceAuthority.REGULATORY_JUDICIAL_AUTHORITY,
        reliability=ConfidenceLevel.VERY_HIGH,
        independence=SourceIndependence.INDEPENDENT_ORIGINAL,
        content_hash=ContentHash(
            algorithm="sha256",
            digest="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        ),
    )


@pytest.fixture
def sample_evidence_record() -> EvidenceRecord:
    return EvidenceRecord(
        id="EVD-a1b2c3d4-2222",
        source_id="SRC-f1e2d3c4-1111",
        short_summary="Telemetry logs establish that the autonomous agent executed an unverified database wipe.",
        evidence_type=EvidenceType.TECHNICAL_POSTMORTEM,
        directness=EvidenceDirectness.PRIMARY_DIRECT,
        specificity=EvidenceSpecificity.HIGHLY_SPECIFIC,
        corroboration_status=CorroborationStatus.FULLY_CORROBORATED,
        quote_spans=[
            QuoteSpan(
                quote_text="unverified database wipe executed at 04:12 UTC",
                start_char_offset=120,
                end_char_offset=166,
            )
        ],
        provenance=ProvenanceRecord(
            ingested_at="2026-02-15T08:05:00Z",
            payload_hash=ContentHash(
                algorithm="sha256",
                digest="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            ),
        ),
    )


@pytest.fixture
def sample_monetary_amount() -> MonetaryAmount:
    return MonetaryAmount(
        amount_status=MonetaryAmountStatus.EXACT_KNOWN,
        exact_amount=Decimal("250000.00"),
        currency="USD",
        supporting_evidence_ids=["EVD-a1b2c3d4-2222"],
    )
