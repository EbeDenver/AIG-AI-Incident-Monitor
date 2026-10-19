"""Tests for SourceReference and ContentHash."""

from datetime import datetime, timezone
import pytest

from ai_incident_monitor.domain.dates import DateWithPrecision
from ai_incident_monitor.domain.sources import ContentHash, SourceReference
from ai_incident_monitor.domain.vocabularies import (
    AccessStatus,
    ConfidenceLevel,
    DatePrecision,
    SourceAuthority,
    SourceIndependence,
    SourceType,
)


def test_valid_source_reference(sample_source_reference):
    assert sample_source_reference.id.startswith("SRC-")
    assert sample_source_reference.title == "Official Safety Investigation Report 101"
    assert sample_source_reference.authority == SourceAuthority.REGULATORY_JUDICIAL_AUTHORITY


def test_invalid_url_scheme_rejected():
    with pytest.raises(ValueError, match="URL must have 'http' or 'https' scheme"):
        SourceReference(
            id="SRC-test-01",
            title="Test Source",
            publisher="Test Publisher",
            url="ftp://invalid.com/file.pdf",
            source_type=SourceType.MAINSTREAM_NEWS,
            publication_date=DateWithPrecision(precision=DatePrecision.EXACT, exact_date="2026-01-01"),
            retrieval_date=datetime.now(timezone.utc),
            access_status=AccessStatus.OPEN_PUBLIC,
            authority=SourceAuthority.ACCREDITED_JOURNALIST,
            reliability=ConfidenceLevel.HIGH,
            independence=SourceIndependence.INDEPENDENT_ORIGINAL,
        )


def test_syndicated_source_without_origin_rejected():
    # Constitutional Rule 13: Syndicated copy must declare syndication_origin
    with pytest.raises(ValueError, match="Sources with independence status SYNDICATED_COPY must specify syndication_origin"):
        SourceReference(
            id="SRC-test-02",
            title="Syndicated Repost",
            publisher="Mirror Site",
            url="https://mirror.com/repost",
            source_type=SourceType.MAINSTREAM_NEWS,
            publication_date=DateWithPrecision(precision=DatePrecision.EXACT, exact_date="2026-01-01"),
            retrieval_date=datetime.now(timezone.utc),
            access_status=AccessStatus.OPEN_PUBLIC,
            authority=SourceAuthority.ACCREDITED_JOURNALIST,
            reliability=ConfidenceLevel.MEDIUM,
            independence=SourceIndependence.SYNDICATED_COPY,
            syndication_origin=None,  # Missing origin
        )


def test_content_hash_valid():
    h = ContentHash(
        algorithm="sha256",
        digest="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    )
    assert h.digest == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_content_hash_invalid_length_rejected():
    with pytest.raises(ValueError, match="SHA-256 digest must be a 64-character hexadecimal string"):
        ContentHash(algorithm="sha256", digest="tooshort")
