"""Tests for HumanReviewRecord and ReviewerIdentity."""

import pytest

from ai_incident_monitor.domain.reviews import HumanReviewRecord, ReviewerIdentity
from ai_incident_monitor.domain.vocabularies import ReviewDecision, ReviewStatus


def test_valid_human_review_record():
    rev = HumanReviewRecord(
        id="REV-101",
        reviewer=ReviewerIdentity(
            reviewer_id="USR-42",
            full_name="Jane Doe",
            email="jdoe@aiguardians.com",
            role="Lead Safety Auditor",
            is_human=True,
        ),
        review_status=ReviewStatus.HUMAN_APPROVED,
        review_decision=ReviewDecision.APPROVED,
        rationale="All 10 points of the gatekeeper review checklist verified.",
        reviewed_at="2026-06-01T12:00:00Z",
    )
    assert rev.review_decision == ReviewDecision.APPROVED


def test_reviewer_identity_rejects_non_human():
    # Constitutional Rule 14: Automated agents cannot act as human reviewers
    with pytest.raises(ValueError, match="ReviewerIdentity requires is_human=True"):
        ReviewerIdentity(
            reviewer_id="AGENT-LLM-01",
            full_name="Automated Agent Reviewer",
            email="agent@internal",
            role="LLM Evaluator",
            is_human=False,
        )


def test_human_review_record_rejects_draft_status():
    with pytest.raises(ValueError, match="HumanReviewRecord review_status must be a human decision"):
        HumanReviewRecord(
            id="REV-102",
            reviewer=ReviewerIdentity(
                reviewer_id="USR-42",
                full_name="Jane Doe",
                email="jdoe@aiguardians.com",
                role="Lead Safety Auditor",
                is_human=True,
            ),
            review_status=ReviewStatus.DRAFT_UNREVIEWED,  # Invalid status for human record
            review_decision=ReviewDecision.APPROVED,
            rationale="Review completed.",
            reviewed_at="2026-06-01T12:00:00Z",
        )
