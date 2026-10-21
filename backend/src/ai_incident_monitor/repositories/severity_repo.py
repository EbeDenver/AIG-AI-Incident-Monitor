"""Severity assessment repository managing versioned, auditable AIG-ISI records."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ai_incident_monitor.db.models.severity import SeverityAssessmentModel
from ai_incident_monitor.repositories.audit_repo import AuditRepository
from ai_incident_monitor.repositories.base import BaseRepository
from ai_incident_monitor.scoring.enums import HumanReviewState, SeverityTier
from ai_incident_monitor.scoring.models import AIGISIScoreResult, ScoreOverride


class SeverityRepository(BaseRepository[SeverityAssessmentModel]):
    """Repository managing versioned, auditable AIG-ISI severity records."""

    def __init__(self, session: Session, audit_repo: Optional[AuditRepository] = None) -> None:
        super().__init__(session, SeverityAssessmentModel)
        self.audit_repo = audit_repo or AuditRepository(session)

    def save_assessment(
        self,
        assessment: AIGISIScoreResult,
        actor_id: str = "system",
        supersedes_id: Optional[str] = None,
    ) -> SeverityAssessmentModel:
        """Persist a new versioned AIG-ISI assessment record."""
        # Convert dimensions to JSON-serializable dictionaries
        dimension_scores_payload = {
            "actual": {
                dim.value: dim_score.model_dump()
                for dim, dim_score in assessment.actual_impact.dimension_scores.items()
            },
            "potential": {
                dim.value: dim_score.model_dump()
                for dim, dim_score in assessment.potential_impact.dimension_scores.items()
            },
        }

        gates_payload = [gate.model_dump() for gate in assessment.review_gates]
        overrides_payload = [o.model_dump(mode="json") for o in assessment.overrides]

        model = SeverityAssessmentModel(
            id=assessment.assessment_id,
            incident_id=assessment.incident_id,
            methodology_version=assessment.methodology_version,
            actual_raw_score=assessment.actual_impact.lower_bound,
            actual_normalized_score=assessment.actual_impact.final_score,
            actual_lower_bound=assessment.actual_impact.lower_bound,
            actual_upper_bound=assessment.actual_impact.upper_bound,
            actual_completeness_pct=assessment.actual_impact.completeness_pct,
            actual_tier=assessment.actual_impact.tier.value,
            actual_confidence=assessment.actual_impact.confidence.value,
            potential_raw_score=assessment.potential_impact.lower_bound,
            potential_normalized_score=assessment.potential_impact.final_score,
            potential_lower_bound=assessment.potential_impact.lower_bound,
            potential_upper_bound=assessment.potential_impact.upper_bound,
            potential_completeness_pct=assessment.potential_impact.completeness_pct,
            potential_tier=assessment.potential_impact.tier.value,
            potential_confidence=assessment.potential_impact.confidence.value,
            dimension_scores=dimension_scores_payload,
            review_state=assessment.review_state.value,
            review_gates_triggered=gates_payload,
            is_pending_review=assessment.is_pending_review,
            has_disputed_facts=assessment.has_disputed_facts,
            overrides=overrides_payload,
            supersedes_assessment_id=supersedes_id,
            superseded_by_id=None,
        )

        saved = self.add(model)

        # If this supersedes an older assessment, mark the older one
        if supersedes_id:
            prior = self.get_by_id(supersedes_id)
            if prior:
                prior.superseded_by_id = saved.id
                prior.review_state = HumanReviewState.SUPERSEDED.value

        self.audit_repo.record_action(
            entity_type="SeverityAssessment",
            entity_id=saved.id,
            action="CREATE_ASSESSMENT" if not supersedes_id else "SUPERSEDE_ASSESSMENT",
            actor_id=actor_id,
            payload_after={
                "incident_id": saved.incident_id,
                "actual_tier": saved.actual_tier,
                "actual_normalized_score": saved.actual_normalized_score,
                "potential_tier": saved.potential_tier,
                "potential_normalized_score": saved.potential_normalized_score,
                "review_state": saved.review_state,
                "is_pending_review": saved.is_pending_review,
            },
        )
        return saved

    def get_by_id(self, assessment_id: str) -> Optional[SeverityAssessmentModel]:
        """Fetch a specific severity assessment by its unique ID."""
        stmt = select(SeverityAssessmentModel).where(SeverityAssessmentModel.id == assessment_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_latest_for_incident(self, incident_id: str) -> Optional[SeverityAssessmentModel]:
        """Fetch the latest active (non-superseded) assessment for an incident."""
        stmt = (
            select(SeverityAssessmentModel)
            .where(
                SeverityAssessmentModel.incident_id == incident_id,
                SeverityAssessmentModel.superseded_by_id.is_(None),
            )
            .order_by(desc(SeverityAssessmentModel.created_at))
            .limit(1)
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def list_for_incident(self, incident_id: str) -> list[SeverityAssessmentModel]:
        """Fetch all historical and current assessments for an incident."""
        stmt = (
            select(SeverityAssessmentModel)
            .where(SeverityAssessmentModel.incident_id == incident_id)
            .order_by(desc(SeverityAssessmentModel.created_at))
        )
        return list(self.session.execute(stmt).scalars().all())

    def apply_override(
        self,
        assessment_id: str,
        override: ScoreOverride,
        actor_id: str,
    ) -> SeverityAssessmentModel:
        """Apply an auditable manual score override to an assessment."""
        assessment = self.get_by_id(assessment_id)
        if not assessment:
            raise ValueError(f"Severity assessment '{assessment_id}' not found.")

        payload_before = {
            "actual_normalized_score": assessment.actual_normalized_score,
            "actual_tier": assessment.actual_tier,
            "potential_normalized_score": assessment.potential_normalized_score,
            "potential_tier": assessment.potential_tier,
            "overrides_count": len(assessment.overrides),
        }

        # Update target
        if override.target in ("actual_impact", "actual"):
            assessment.actual_normalized_score = override.overridden_score
            assessment.actual_tier = override.overridden_tier.value
        elif override.target in ("potential_impact", "potential"):
            assessment.potential_normalized_score = override.overridden_score
            assessment.potential_tier = override.overridden_tier.value

        current_overrides = list(assessment.overrides)
        current_overrides.append(override.model_dump(mode="json"))
        assessment.overrides = current_overrides

        # Overrides always require human review
        assessment.is_pending_review = True
        if assessment.review_state not in (HumanReviewState.APPROVED.value, HumanReviewState.REJECTED.value):
            assessment.review_state = HumanReviewState.PENDING_REVIEW.value

        self.audit_repo.record_action(
            entity_type="SeverityAssessment",
            entity_id=assessment.id,
            action="APPLY_OVERRIDE",
            actor_id=actor_id,
            payload_before=payload_before,
            payload_after={
                "target": override.target,
                "overridden_score": override.overridden_score,
                "overridden_tier": override.overridden_tier.value,
                "rationale": override.rationale,
                "applied_by_id": override.applied_by_id,
            },
        )
        self.session.flush()
        return assessment

    def update_review_state(
        self,
        assessment_id: str,
        new_state: HumanReviewState,
        actor_id: str,
        rationale: Optional[str] = None,
    ) -> SeverityAssessmentModel:
        """Update review state (e.g. approve or reject) with mandatory audit logging."""
        assessment = self.get_by_id(assessment_id)
        if not assessment:
            raise ValueError(f"Severity assessment '{assessment_id}' not found.")

        state_before = assessment.review_state
        assessment.review_state = new_state.value
        if new_state in (HumanReviewState.APPROVED, HumanReviewState.REJECTED):
            assessment.is_pending_review = False

        self.audit_repo.record_action(
            entity_type="SeverityAssessment",
            entity_id=assessment.id,
            action="UPDATE_REVIEW_STATE",
            actor_id=actor_id,
            payload_before={"review_state": state_before},
            payload_after={
                "review_state": new_state.value,
                "rationale": rationale,
            },
        )
        self.session.flush()
        return assessment
