"""External source representations with cryptographic provenance and copyright boundaries.

Constitutional Rules 12, 13, 16:
- Sources track SHA-256 digests and canonical URLs.
- Syndicated copies do not count as independent corroboration.
- Full-text copyrighted articles are excluded from Git.
"""

from datetime import datetime, timezone
import re
from typing import Optional
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator

from ai_incident_monitor.domain.common import BaseEntity, SchemaVersioned
from ai_incident_monitor.domain.dates import DateWithPrecision
from ai_incident_monitor.domain.identifiers import SourceId
from ai_incident_monitor.domain.vocabularies import (
    AccessStatus,
    ConfidenceLevel,
    SourceAuthority,
    SourceIndependence,
    SourceType,
)

HEX_64_REGEX = re.compile(r"^[a-fA-F0-9]{64}$")


class ContentHash(SchemaVersioned):
    """Cryptographic hash verifying payload integrity without storing copyrighted text."""

    algorithm: str = Field(default="sha256", description="Hash algorithm, default sha256")
    digest: str = Field(description="64-character hexadecimal SHA-256 digest")

    @field_validator("digest")
    @classmethod
    def validate_digest(cls, v: str) -> str:
        clean = v.strip().lower()
        if not HEX_64_REGEX.match(clean):
            raise ValueError(
                f"Invalid digest '{v}'. SHA-256 digest must be a 64-character hexadecimal string."
            )
        return clean


class CopyrightRestriction(SchemaVersioned):
    """Explicit copyright and data retention constraints (Constitutional Rule 16)."""

    is_copyright_restricted: bool = True
    fair_use_quotation_only: bool = True
    full_text_git_excluded: bool = True
    retention_policy_days: Optional[int] = None


def _validate_url(url_str: str) -> str:
    cleaned = url_str.strip()
    parsed = urlparse(cleaned)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"URL must have 'http' or 'https' scheme, got '{parsed.scheme}'")
    if not parsed.netloc:
        raise ValueError(f"URL must have a valid host/domain, got '{url_str}'")
    return cleaned


class SourceReference(SchemaVersioned):
    """Complete source metadata record linking external reporting to evidence claims."""

    id: SourceId
    title: str = Field(min_length=3, description="Article or document title")
    publisher: str = Field(min_length=2, description="Publishing organization or domain")
    author: Optional[str] = None
    url: str = Field(description="Ingestion URL")
    canonical_url: Optional[str] = None
    source_type: SourceType
    publication_date: DateWithPrecision
    retrieval_date: datetime
    access_status: AccessStatus
    authority: SourceAuthority
    reliability: ConfidenceLevel
    independence: SourceIndependence
    syndication_origin: Optional[str] = None
    language: str = Field(default="en", description="ISO 639-1 language code")
    content_hash: Optional[ContentHash] = None
    copyright_restrictions: CopyrightRestriction = Field(default_factory=CopyrightRestriction)

    @field_validator("url")
    @classmethod
    def validate_primary_url(cls, v: str) -> str:
        return _validate_url(v)

    @field_validator("canonical_url")
    @classmethod
    def validate_canonical_url(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return _validate_url(v)
        return None

    @field_validator("retrieval_date")
    @classmethod
    def validate_tz(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v

    @model_validator(mode="after")
    def validate_syndication_origin(self) -> "SourceReference":
        # Rule 13: Syndicated copies must declare syndication_origin
        if self.independence == SourceIndependence.SYNDICATED_COPY:
            if not self.syndication_origin or not self.syndication_origin.strip():
                raise ValueError(
                    "Sources with independence status SYNDICATED_COPY must specify syndication_origin."
                )
        return self
