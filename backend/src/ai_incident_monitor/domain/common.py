"""Common base classes, constitutional exceptions, and lifecycle models.

All domain models inherit from BaseEntity with frozen=True, extra="forbid",
and str_strip_whitespace=True to guarantee immutability, data hygiene,
and prevention of silent errors.
"""

from datetime import datetime, timezone
import re
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ConstitutionalViolationError(ValueError):
    """Raised when data violates one of the Project Constitution's non-negotiable rules."""


class EpistemicIntegrityError(ConstitutionalViolationError):
    """Raised when facts, allegations, analysis, or uncertainties are conflated."""


class UngroundedClaimError(ConstitutionalViolationError):
    """Raised when a factual, material numeric, or causal claim lacks required evidence."""


class UnverifiedLegalConclusionError(ConstitutionalViolationError):
    """Raised when an unadjudicated legal claim is marked confirmed without human review."""


class InvalidMonetaryStateError(ConstitutionalViolationError):
    """Raised when unknown monetary amounts are coerced to zero or lack required evidence."""


class ImmutabilityViolationError(ConstitutionalViolationError):
    """Raised when an attempt is made to mutate or silently overwrite historical records."""


class BaseEntity(BaseModel):
    """Base model for all domain entities.

    Enforces strict immutability (frozen=True), forbids unexpected extra attributes,
    and strips leading/trailing whitespace from string inputs.
    """

    demonstration_notice: Optional[str] = Field(
        default=None,
        description="Mandatory disclaimer banner for test demonstration data",
    )

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


SEMVER_REGEX = re.compile(r"^\d+\.\d+\.\d+$")


class SchemaVersioned(BaseEntity):
    """Mixin enforcing semantic versioning on domain entities."""

    schema_version: str = Field(
        default="1.0.0",
        description="Semantic version of the model schema (MAJOR.MINOR.PATCH)",
    )

    @field_validator("schema_version")
    @classmethod
    def validate_semver(cls, v: str) -> str:
        if not SEMVER_REGEX.match(v):
            raise ValueError(f"Invalid schema_version '{v}'. Must follow semver (e.g. '1.0.0').")
        return v


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)
