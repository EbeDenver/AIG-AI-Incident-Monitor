"""Governance mapping service layer orchestrating evaluation, persistence, and human review."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_incident_monitor.db.models.governance import (
    FrameworkControlModel,
    FrameworkReferenceSetModel,
    IncidentFrameworkMappingModel,
)
from ai_incident_monitor.domain.common import (
    ConstitutionalViolationError,
    ImmutabilityViolationError,
)
from ai_incident_monitor.governance.engine import GovernanceMappingEngine
from ai_incident_monitor.governance.enums import (
    FrameworkCode,
    MappingStatus,
)
from ai_incident_monitor.governance.models import (
    FrameworkReferenceSetSchema,
    GovernanceActorIdentity,
    IncidentFactContext,
    MappingCandidate,
)
from ai_incident_monitor.governance.reference_loader import (
    compute_file_sha256,
    load_reference_set,
)
class GovernanceMappingService:
    """Service orchestrating deterministic mapping generation, persistence, and HITL review."""

    def __init__(
        self,
        session: Session,
        frameworks_dir: Optional[Path] = None,
    ) -> None:
        from ai_incident_monitor.repositories.governance_repo import GovernanceRepository

        self.session = session
        self.repo = GovernanceRepository(session)
        self.frameworks_dir = frameworks_dir

        self._reference_schemas: dict[FrameworkCode, FrameworkReferenceSetSchema] = {}
        self._refset_db_cache: dict[FrameworkCode, FrameworkReferenceSetModel] = {}
        self._engine: Optional[GovernanceMappingEngine] = None

    def initialize_framework_reference(
        self,
        framework_code: FrameworkCode,
        yaml_file: Path,
    ) -> FrameworkReferenceSetModel:
        """Load, validate, and synchronize a framework reference set into the database."""
        ref_schema = load_reference_set(yaml_file)
        self._reference_schemas[framework_code] = ref_schema

        content_hash = compute_file_sha256(yaml_file)

        # Check if already present in database
        existing = self.session.execute(
            select(FrameworkReferenceSetModel).where(
                FrameworkReferenceSetModel.framework_code == framework_code.value,
                FrameworkReferenceSetModel.version == ref_schema.version,
            )
        ).scalar_one_or_none()

        if existing is not None:
            self._refset_db_cache[framework_code] = existing
            return existing

        created = self.repo.create_reference_set(ref_schema, content_hash=content_hash)
        self.session.flush()
        self._refset_db_cache[framework_code] = created
        return created

    def get_engine(self) -> GovernanceMappingEngine:
        """Get or initialize the mapping engine using cached reference schemas."""
        if self._engine is None:
            self._engine = GovernanceMappingEngine(reference_sets=self._reference_schemas)
        return self._engine

    def evaluate_mappings(
        self,
        context: IncidentFactContext,
    ) -> list[MappingCandidate]:
        """Run the deterministic mapping engine on the incident context."""
        engine = self.get_engine()
        return engine.map_incident(context)

    def persist_candidates(
        self,
        candidates: list[MappingCandidate],
        actor: GovernanceActorIdentity,
    ) -> list[IncidentFrameworkMappingModel]:
        """Persist mapping candidates to relational storage with evidence links and audit trail."""
        persisted: list[IncidentFrameworkMappingModel] = []

        for cand in candidates:
            # Locate reference set model
            refset_model = self._refset_db_cache.get(cand.framework_code)
            if refset_model is None:
                stmt = select(FrameworkReferenceSetModel).where(
                    FrameworkReferenceSetModel.framework_code == cand.framework_code.value,
                    FrameworkReferenceSetModel.version == cand.reference_set_version,
                )
                refset_model = self.session.execute(stmt).scalar_one_or_none()
                if refset_model is None:
                    raise ValueError(
                        f"Reference set '{cand.framework_code}' version '{cand.reference_set_version}' "
                        "not found in database. Must initialize reference set first."
                    )
                self._refset_db_cache[cand.framework_code] = refset_model

            # Find matching framework control in DB
            ctrl_stmt = select(FrameworkControlModel).where(
                FrameworkControlModel.reference_set_id == refset_model.id,
                FrameworkControlModel.external_identifier == cand.target_identifier,
            )
            ctrl_model = self.session.execute(ctrl_stmt).scalar_one_or_none()
            ctrl_id = ctrl_model.id if ctrl_model is not None else None

            mapping_dict: dict[str, Any] = {
                "incident_id": cand.incident_id,
                "framework_code": cand.framework_code.value,
                "reference_set_id": refset_model.id,
                "framework_control_id": ctrl_id,
                "mapping_level": cand.mapping_level.value,
                "applicability": cand.applicability,
                "confidence": cand.confidence.value,
                "mapping_status": cand.mapping_status.value,
                "rationale": cand.rationale,
                "known_facts": cand.known_facts,
                "unknowns": cand.unknowns,
                "disputed_facts": cand.disputed_facts,
                "evidence_ids": cand.evidence_ids,
                "recommended_control_or_follow_up": cand.recommended_control_or_follow_up,
                "rule_id": cand.rule_id,
                "rule_version": cand.rule_version,
                "generated_by": cand.generated_by,
                "generated_at": cand.generated_at,
            }

            mapping_model = self.repo.create_mapping(mapping_dict, actor=actor)

            # Create normalized evidence link records
            for ev_id in cand.evidence_ids:
                self.repo.add_evidence_link(
                    mapping_id=mapping_model.id,
                    evidence_id=ev_id,
                    claim_type="GOVERNANCE_ALIGNMENT",
                    relevance_note=f"Linked by rule {cand.rule_id} ({cand.target_identifier})",
                    actor=actor,
                )

            persisted.append(mapping_model)

        return persisted

    def approve_mapping(
        self,
        mapping_id: str,
        actor: GovernanceActorIdentity,
        rationale: str = "Human approval granted after evidentiary review.",
    ) -> IncidentFrameworkMappingModel:
        """Approve a mapping. Strictly enforces human primacy (Rule 12/13)."""
        if not actor.is_human:
            raise ConstitutionalViolationError(
                "Rule 12 Violation: Automated algorithms or LLMs cannot approve governance mappings. "
                "Approval strictly requires an authenticated human actor with is_human=True."
            )
        return self.repo.transition_mapping_status(
            mapping_id=mapping_id,
            new_status=MappingStatus.APPROVED,
            actor=actor,
            rationale=rationale,
        )

    def reject_mapping(
        self,
        mapping_id: str,
        actor: GovernanceActorIdentity,
        rationale: str,
    ) -> IncidentFrameworkMappingModel:
        """Reject a candidate mapping."""
        return self.repo.transition_mapping_status(
            mapping_id=mapping_id,
            new_status=MappingStatus.REJECTED,
            actor=actor,
            rationale=rationale,
        )

    def revise_mapping(
        self,
        mapping_id: str,
        updated_attributes: dict[str, Any],
        actor: GovernanceActorIdentity,
        rationale: str,
    ) -> IncidentFrameworkMappingModel:
        """Supersede a mapping with updated attributes, preserving prior record immutably."""
        return self.repo.supersede_mapping(
            original_mapping_id=mapping_id,
            updated_attributes=updated_attributes,
            actor=actor,
            rationale=rationale,
        )
