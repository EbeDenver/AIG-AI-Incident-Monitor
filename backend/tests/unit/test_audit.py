"""Tests for AuditMetadata, ModelInferenceMetadata, and historical immutability."""

import pytest

from ai_incident_monitor.domain.audit import AuditMetadata, ModelInferenceMetadata
from ai_incident_monitor.domain.sources import ContentHash


def test_valid_audit_metadata():
    audit = AuditMetadata(
        created_by="analyst-john",
        is_model_generated=False,
        created_at="2026-06-01T10:00:00Z",
        updated_at="2026-06-01T10:00:00Z",
    )
    assert not audit.is_model_generated


def test_model_generated_missing_metadata_rejected():
    # Constitutional Rule 19: Model generated records require inference metadata
    with pytest.raises(ValueError, match="Model-generated records must include complete ModelInferenceMetadata"):
        AuditMetadata(
            created_by="agent:extraction",
            is_model_generated=True,
            model_metadata=None,  # Missing
            created_at="2026-06-01T10:00:00Z",
            updated_at="2026-06-01T10:00:00Z",
        )


def test_claimed_approval_without_review_record_rejected():
    # Constitutional Rule 18: Machine cannot claim human approval without human review ID
    with pytest.raises(ValueError, match="Declaring 'reviewed_by' requires attaching both 'human_review_id'"):
        AuditMetadata(
            created_by="analyst-john",
            is_model_generated=False,
            created_at="2026-06-01T10:00:00Z",
            updated_at="2026-06-01T10:00:00Z",
            reviewed_by="auditor-jane",
            human_review_id=None,  # Missing review ID
            reviewed_at=None,
        )


def test_historical_immutability():
    # Constitutional Rule 17 & 24: Historical records are immutable (frozen=True)
    audit = AuditMetadata(
        created_by="analyst-john",
        is_model_generated=False,
        created_at="2026-06-01T10:00:00Z",
        updated_at="2026-06-01T10:00:00Z",
    )
    with pytest.raises(Exception):  # FrozenInstanceError / ValidationError on mutation
        audit.created_by = "mutated-name"
