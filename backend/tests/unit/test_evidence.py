"""Tests for EvidenceRecord, QuoteSpan, and ProvenanceRecord."""

import pytest

from ai_incident_monitor.domain.evidence import EvidenceRecord, ProvenanceRecord, QuoteSpan
from ai_incident_monitor.domain.sources import ContentHash
from ai_incident_monitor.domain.vocabularies import (
    CorroborationStatus,
    EvidenceDirectness,
    EvidenceSpecificity,
    EvidenceType,
)


def test_valid_evidence_record(sample_evidence_record):
    assert sample_evidence_record.id.startswith("EVD-")
    assert len(sample_evidence_record.quote_spans) == 1
    assert sample_evidence_record.provenance.payload_hash.digest is not None


def test_quote_span_valid():
    qs = QuoteSpan(
        quote_text="model weights were modified without authorization",
        start_char_offset=50,
        end_char_offset=99,
    )
    assert qs.start_char_offset == 50
    assert qs.end_char_offset == 99


def test_quote_span_inverted_offsets_rejected():
    with pytest.raises(ValueError, match="end_char_offset .* must be strictly greater than start_char_offset"):
        QuoteSpan(
            quote_text="invalid offsets",
            start_char_offset=100,
            end_char_offset=50,
        )


def test_quote_span_zero_length_rejected():
    with pytest.raises(ValueError, match="end_char_offset .* must be strictly greater than start_char_offset"):
        QuoteSpan(
            quote_text="same offset",
            start_char_offset=25,
            end_char_offset=25,
        )


def test_empty_summary_rejected():
    with pytest.raises(ValueError):
        EvidenceRecord(
            id="EVD-test-01",
            source_id="SRC-source-01",
            short_summary="",  # Empty summary
            evidence_type=EvidenceType.MEDIA_REPORT,
            directness=EvidenceDirectness.SECONDARY_DERIVED,
            specificity=EvidenceSpecificity.MODERATELY_SPECIFIC,
            corroboration_status=CorroborationStatus.SINGLE_SOURCE_UNCONTESTED,
            provenance=ProvenanceRecord(
                ingested_at="2026-01-01T00:00:00Z",
                payload_hash=ContentHash(
                    algorithm="sha256",
                    digest="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                ),
            ),
        )
