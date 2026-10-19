"""Strongly typed identifiers for domain entities.

Enforces deterministic prefix conventions:
- SourceId:      SRC-<uuid or identifier>
- EvidenceId:    EVD-<uuid or identifier>
- ClaimId:       CLM-<uuid or identifier>
- IncidentId:    INC-<uuid or identifier>
- ReviewId:      REV-<uuid or identifier>
- UncertaintyId: UNC-<uuid or identifier>
"""

import re
from typing import Annotated
import uuid

from pydantic import AfterValidator


def _validate_prefix(val: str, prefix: str) -> str:
    if not isinstance(val, str):
        raise ValueError(f"Identifier must be a string, got {type(val).__name__}")
    cleaned = val.strip()
    pattern = rf"^{prefix}-[A-Za-z0-9_\-\.]+$"
    if not re.match(pattern, cleaned):
        raise ValueError(
            f"Invalid identifier '{val}'. Must match prefix '{prefix}-' followed by alphanumeric characters."
        )
    return cleaned


def validate_source_id(v: str) -> str:
    return _validate_prefix(v, "SRC")


def validate_evidence_id(v: str) -> str:
    return _validate_prefix(v, "EVD")


def validate_claim_id(v: str) -> str:
    return _validate_prefix(v, "CLM")


def validate_incident_id(v: str) -> str:
    return _validate_prefix(v, "INC")


def validate_review_id(v: str) -> str:
    return _validate_prefix(v, "REV")


def validate_uncertainty_id(v: str) -> str:
    return _validate_prefix(v, "UNC")


SourceId = Annotated[str, AfterValidator(validate_source_id)]
EvidenceId = Annotated[str, AfterValidator(validate_evidence_id)]
ClaimId = Annotated[str, AfterValidator(validate_claim_id)]
IncidentId = Annotated[str, AfterValidator(validate_incident_id)]
ReviewId = Annotated[str, AfterValidator(validate_review_id)]
UncertaintyId = Annotated[str, AfterValidator(validate_uncertainty_id)]


def new_source_id() -> str:
    return f"SRC-{uuid.uuid4()}"


def new_evidence_id() -> str:
    return f"EVD-{uuid.uuid4()}"


def new_claim_id() -> str:
    return f"CLM-{uuid.uuid4()}"


def new_incident_id() -> str:
    return f"INC-{uuid.uuid4()}"


def new_review_id() -> str:
    return f"REV-{uuid.uuid4()}"


def new_uncertainty_id() -> str:
    return f"UNC-{uuid.uuid4()}"
