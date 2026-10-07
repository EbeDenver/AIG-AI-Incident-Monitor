"""Tests for strongly typed domain identifiers."""

import pytest

from ai_incident_monitor.domain.identifiers import (
    new_claim_id,
    new_evidence_id,
    new_incident_id,
    new_review_id,
    new_source_id,
    new_uncertainty_id,
    validate_claim_id,
    validate_evidence_id,
    validate_incident_id,
    validate_review_id,
    validate_source_id,
    validate_uncertainty_id,
)


def test_valid_identifier_generation():
    assert new_source_id().startswith("SRC-")
    assert new_evidence_id().startswith("EVD-")
    assert new_claim_id().startswith("CLM-")
    assert new_incident_id().startswith("INC-")
    assert new_review_id().startswith("REV-")
    assert new_uncertainty_id().startswith("UNC-")


def test_valid_identifier_validation():
    assert validate_source_id("SRC-12345") == "SRC-12345"
    assert validate_evidence_id("EVD-abc_def") == "EVD-abc_def"
    assert validate_claim_id("CLM-uuid.1") == "CLM-uuid.1"
    assert validate_incident_id("INC-2026-001") == "INC-2026-001"
    assert validate_review_id("REV-reviewer99") == "REV-reviewer99"
    assert validate_uncertainty_id("UNC-xyz") == "UNC-xyz"


def test_invalid_identifier_prefix_rejection():
    with pytest.raises(ValueError, match="Must match prefix 'SRC-'"):
        validate_source_id("EVD-12345")

    with pytest.raises(ValueError, match="Must match prefix 'EVD-'"):
        validate_evidence_id("SRC-12345")

    with pytest.raises(ValueError, match="Must match prefix 'CLM-'"):
        validate_claim_id("INVALID-123")

    with pytest.raises(ValueError, match="Must match prefix 'INC-'"):
        validate_incident_id("INC")

    with pytest.raises(ValueError, match="Must match prefix 'REV-'"):
        validate_review_id("123-REV")
