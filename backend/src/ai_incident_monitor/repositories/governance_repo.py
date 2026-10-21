"""Typed repository for governance reference sets, controls, mappings, and audit events."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_incident_monitor.db.models.governance import (
    EULegalRelevanceScreenModel,
    FrameworkControlModel,
    FrameworkReferenceSetModel,
    GovernanceAuditLogModel,
    IncidentFrameworkMappingModel,
    MappingEvidenceLinkModel,
)
from ai_incident_monitor.domain.common import (
    ConstitutionalViolationError,
    ImmutabilityViolationError,
)
from ai_incident_monitor.governance.enums import (
    GovernanceAuditEventType,
    MappingStatus,
)
from ai_incident_monitor.governance.models import (
    EU_AI_ACT_STATUTORY_DISCLAIMER,
    FrameworkReferenceSetSchema,
    GovernanceActorIdentity,
)


def _canonical_json(obj: Any) -> str:
    """Deterministic JSON serialization (UTF-8, sorted keys, no whitespace)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _normalize_iso_timestamp(dt: datetime) -> str:
    """Normalize datetime to UTC ISO 8601 string with 'Z' suffix and microsecond precision."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _sha256_canonical(obj: Any) -> str:
    """Compute SHA-256 over canonical JSON representation."""
    canonical_bytes = _canonical_json(obj).encode("utf-8")
    return hashlib.sha256(canonical_bytes).hexdigest()


class GovernanceRepository:
    """Repository managing governance reference libraries, evidence mappings, and audit chains."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # --------------------------------------------------------------------------
    # Reference Sets & Controls
    # --------------------------------------------------------------------------

    def create_reference_set(
        self,
        ref_schema: FrameworkReferenceSetSchema,
        content_hash: str,
    ) -> FrameworkReferenceSetModel:
        """Persist a validated framework reference set and its child controls."""
        ref_set_id = f"refset_{uuid.uuid4().hex[:16]}"
        ref_model = FrameworkReferenceSetModel(
            id=ref_set_id,
            framework_code=ref_schema.framework_code.value,
            framework_name=ref_schema.framework_name,
            version=ref_schema.version,
            source_url=ref_schema.source_url,
            publisher=ref_schema.publisher,
            retrieved_at=ref_schema.retrieved_at_utc,
            verified_at=ref_schema.verified_at_utc,
            verified_by=ref_schema.verified_by,
            content_hash=content_hash,
            license_notes=ref_schema.license_notes,
            status=ref_schema.status.value,
            supersedes_reference_set_id=ref_schema.supersedes_reference_set_id,
            metadata_json={},
        )
        self.session.add(ref_model)

        for ctrl in ref_schema.controls:
            ctrl_id = f"ctrl_{uuid.uuid4().hex[:16]}"
            ctrl_model = FrameworkControlModel(
                id=ctrl_id,
                reference_set_id=ref_set_id,
                external_identifier=ctrl.external_identifier,
                parent_identifier=ctrl.parent_identifier,
                title=ctrl.title,
                description=ctrl.description,
                control_level=ctrl.control_level.value,
                framework_function=ctrl.framework_function,
                category=ctrl.category,
                subcategory=ctrl.subcategory,
                article_number=ctrl.article_number,
                effective_date=ctrl.effective_date,
                applicability_notes=ctrl.applicability_notes,
                source_locator=ctrl.source_locator,
                status=ctrl.status.value,
                metadata_json=ctrl.metadata,
            )
            self.session.add(ctrl_model)

        self.session.flush()
        return ref_model

    def get_reference_set(self, ref_set_id: str) -> Optional[FrameworkReferenceSetModel]:
        """Fetch a reference set by ID."""
        return self.session.get(FrameworkReferenceSetModel, ref_set_id)

    def get_reference_set_by_code_and_version(
        self,
        framework_code: str,
        version: str,
    ) -> Optional[FrameworkReferenceSetModel]:
        """Fetch a reference set by code and version string."""
        stmt = select(FrameworkReferenceSetModel).where(
            FrameworkReferenceSetModel.framework_code == framework_code,
            FrameworkReferenceSetModel.version == version,
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def get_control(self, control_id: str) -> Optional[FrameworkControlModel]:
        """Fetch a framework control node by ID."""
        return self.session.get(FrameworkControlModel, control_id)

    def get_control_by_external_id(
        self,
        ref_set_id: str,
        external_id: str,
    ) -> Optional[FrameworkControlModel]:
        """Fetch a framework control node by external identifier within a reference set."""
        stmt = select(FrameworkControlModel).where(
            FrameworkControlModel.reference_set_id == ref_set_id,
            FrameworkControlModel.external_identifier == external_id,
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def list_controls_for_reference_set(self, ref_set_id: str) -> list[FrameworkControlModel]:
        """List all controls in a given reference set."""
        stmt = select(FrameworkControlModel).where(
            FrameworkControlModel.reference_set_id == ref_set_id
        ).order_by(FrameworkControlModel.external_identifier)
        return list(self.session.execute(stmt).scalars().all())

    # --------------------------------------------------------------------------
    # Incident Framework Mappings
    # --------------------------------------------------------------------------

    def create_mapping(
        self,
        mapping_data: dict[str, Any],
        actor: GovernanceActorIdentity,
    ) -> IncidentFrameworkMappingModel:
        """Create a new incident-framework mapping record and record audit event."""
        mapping_id = f"map_{uuid.uuid4().hex[:16]}"
        now = datetime.now(timezone.utc)

        mapping = IncidentFrameworkMappingModel(
            id=mapping_id,
            incident_id=mapping_data["incident_id"],
            framework_code=mapping_data["framework_code"],
            reference_set_id=mapping_data["reference_set_id"],
            framework_control_id=mapping_data.get("framework_control_id"),
            mapping_level=mapping_data["mapping_level"],
            applicability=mapping_data["applicability"],
            confidence=mapping_data.get("confidence", "INSUFFICIENT"),
            mapping_status=mapping_data.get("mapping_status", MappingStatus.DRAFT.value),
            rationale=mapping_data["rationale"],
            known_facts=mapping_data.get("known_facts", []),
            unknowns=mapping_data.get("unknowns", []),
            disputed_facts=mapping_data.get("disputed_facts", []),
            evidence_ids=mapping_data.get("evidence_ids", []),
            recommended_control_or_follow_up=mapping_data.get("recommended_control_or_follow_up"),
            generated_by=mapping_data.get("generated_by", actor.actor_id),
            reviewed_by=mapping_data.get("reviewed_by"),
            generated_at=mapping_data.get("generated_at", now),
            reviewed_at=mapping_data.get("reviewed_at"),
            supersedes_mapping_id=mapping_data.get("supersedes_mapping_id"),
            superseded_by_id=None,
        )
        self.session.add(mapping)
        self.session.flush()

        # Audit event
        after_state = self._serialize_mapping_state(mapping)
        self.record_governance_audit_event(
            entity_type="incident_framework_mappings",
            entity_id=mapping.id,
            transition_type=GovernanceAuditEventType.CREATE_MAPPING,
            actor=actor,
            before_state=None,
            after_state=after_state,
            details={"action": "created_initial_mapping"},
        )

        return mapping

    def get_mapping(self, mapping_id: str) -> Optional[IncidentFrameworkMappingModel]:
        """Fetch a mapping by ID."""
        return self.session.get(IncidentFrameworkMappingModel, mapping_id)

    def list_mappings_for_incident(
        self,
        incident_id: str,
        include_superseded: bool = False,
    ) -> list[IncidentFrameworkMappingModel]:
        """List framework mappings for an incident."""
        stmt = select(IncidentFrameworkMappingModel).where(
            IncidentFrameworkMappingModel.incident_id == incident_id
        )
        if not include_superseded:
            stmt = stmt.where(IncidentFrameworkMappingModel.superseded_by_id.is_(None))
        return list(self.session.execute(stmt).scalars().all())

    def transition_mapping_status(
        self,
        mapping_id: str,
        new_status: MappingStatus,
        actor: GovernanceActorIdentity,
        rationale: str = "",
    ) -> IncidentFrameworkMappingModel:
        """Transition the review state of a mapping.

        Constitutional Rule 12 & 13: An automated model/LLM can NEVER approve an assessment.
        Setting status to APPROVED strictly requires actor.is_human == True.
        """
        mapping = self.session.get(IncidentFrameworkMappingModel, mapping_id)
        if mapping is None:
            raise ValueError(f"Mapping not found: {mapping_id}")

        if mapping.mapping_status == MappingStatus.APPROVED.value:
            raise ImmutabilityViolationError(
                f"Cannot mutate approved mapping '{mapping_id}' in place. Reviewer edits must create "
                "a superseding mapping record (Binding Correction 7)."
            )

        if new_status == MappingStatus.APPROVED and not actor.is_human:
            raise ConstitutionalViolationError(
                "Automated self-approval forbidden (Rule 12). Only authenticated human reviewer "
                "with is_human=True can approve mappings."
            )

        before_state = self._serialize_mapping_state(mapping)
        now = datetime.now(timezone.utc)

        mapping.mapping_status = new_status.value
        mapping.reviewed_by = actor.actor_id
        mapping.reviewed_at = now
        self.session.flush()

        after_state = self._serialize_mapping_state(mapping)
        self.record_governance_audit_event(
            entity_type="incident_framework_mappings",
            entity_id=mapping.id,
            transition_type=GovernanceAuditEventType.TRANSITION_STATE,
            actor=actor,
            before_state=before_state,
            after_state=after_state,
            details={"rationale": rationale, "new_status": new_status.value},
        )

        return mapping

    def supersede_mapping(
        self,
        original_mapping_id: str,
        updated_attributes: dict[str, Any],
        actor: GovernanceActorIdentity,
        rationale: str,
    ) -> IncidentFrameworkMappingModel:
        """Create a superseding mapping record, preserving the prior record immutably.

        Enforces Binding Correction 7 and Rule 16.
        """
        original = self.session.get(IncidentFrameworkMappingModel, original_mapping_id)
        if original is None:
            raise ValueError(f"Original mapping not found: {original_mapping_id}")

        if original.superseded_by_id is not None:
            raise ValueError(f"Mapping '{original_mapping_id}' has already been superseded by '{original.superseded_by_id}'.")

        new_mapping_id = f"map_{uuid.uuid4().hex[:16]}"
        now = datetime.now(timezone.utc)

        # Merge base attributes with updates
        merged_data: dict[str, Any] = {
            "incident_id": original.incident_id,
            "framework_code": original.framework_code,
            "reference_set_id": original.reference_set_id,
            "framework_control_id": original.framework_control_id,
            "mapping_level": original.mapping_level,
            "applicability": original.applicability,
            "confidence": original.confidence,
            "mapping_status": MappingStatus.CANDIDATE.value if actor.is_human else MappingStatus.DRAFT.value,
            "rationale": original.rationale,
            "known_facts": list(original.known_facts),
            "unknowns": list(original.unknowns),
            "disputed_facts": list(original.disputed_facts),
            "evidence_ids": list(original.evidence_ids),
            "recommended_control_or_follow_up": original.recommended_control_or_follow_up,
            "generated_by": actor.actor_id,
            "reviewed_by": actor.actor_id if actor.is_human else None,
            "generated_at": now,
            "reviewed_at": now if actor.is_human else None,
            "supersedes_mapping_id": original.id,
        }
        merged_data.update(updated_attributes)

        new_mapping = IncidentFrameworkMappingModel(
            id=new_mapping_id,
            incident_id=merged_data["incident_id"],
            framework_code=merged_data["framework_code"],
            reference_set_id=merged_data["reference_set_id"],
            framework_control_id=merged_data.get("framework_control_id"),
            mapping_level=merged_data["mapping_level"],
            applicability=merged_data["applicability"],
            confidence=merged_data["confidence"],
            mapping_status=merged_data["mapping_status"],
            rationale=merged_data["rationale"],
            known_facts=merged_data["known_facts"],
            unknowns=merged_data["unknowns"],
            disputed_facts=merged_data["disputed_facts"],
            evidence_ids=merged_data["evidence_ids"],
            recommended_control_or_follow_up=merged_data.get("recommended_control_or_follow_up"),
            generated_by=merged_data["generated_by"],
            reviewed_by=merged_data.get("reviewed_by"),
            generated_at=merged_data["generated_at"],
            reviewed_at=merged_data.get("reviewed_at"),
            supersedes_mapping_id=original.id,
            superseded_by_id=None,
        )
        self.session.add(new_mapping)

        # Mark original as superseded
        original_before = self._serialize_mapping_state(original)
        original.superseded_by_id = new_mapping_id
        original.mapping_status = MappingStatus.SUPERSEDED.value
        self.session.flush()

        original_after = self._serialize_mapping_state(original)
        self.record_governance_audit_event(
            entity_type="incident_framework_mappings",
            entity_id=original.id,
            transition_type=GovernanceAuditEventType.SUPERSEDE_MAPPING,
            actor=actor,
            before_state=original_before,
            after_state=original_after,
            details={"superseded_by": new_mapping_id, "rationale": rationale},
        )

        new_after = self._serialize_mapping_state(new_mapping)
        self.record_governance_audit_event(
            entity_type="incident_framework_mappings",
            entity_id=new_mapping.id,
            transition_type=GovernanceAuditEventType.CREATE_MAPPING,
            actor=actor,
            before_state=None,
            after_state=new_after,
            details={"supersedes_mapping_id": original.id, "rationale": rationale},
        )

        return new_mapping

    # --------------------------------------------------------------------------
    # EU Legal Relevance Screens
    # --------------------------------------------------------------------------

    def create_eu_screen(
        self,
        screen_data: dict[str, Any],
        actor: GovernanceActorIdentity,
    ) -> EULegalRelevanceScreenModel:
        """Create a new EU AI Act informational relevance screen."""
        screen_id = f"euscreen_{uuid.uuid4().hex[:16]}"
        now = datetime.now(timezone.utc)

        screen = EULegalRelevanceScreenModel(
            id=screen_id,
            incident_id=screen_data["incident_id"],
            reference_set_id=screen_data["reference_set_id"],
            territorial_nexus=screen_data.get("territorial_nexus", "INSUFFICIENT_INFORMATION"),
            ai_system_relevance=screen_data.get("ai_system_relevance", "INSUFFICIENT_INFORMATION"),
            actor_roles=screen_data.get("actor_roles", []),
            risk_class=screen_data.get("risk_class", "INSUFFICIENT_INFORMATION"),
            serious_incident_relevance=screen_data.get("serious_incident_relevance", "INSUFFICIENT_INFORMATION"),
            potentially_relevant_articles=screen_data.get("potentially_relevant_articles", []),
            operational_obligations=screen_data.get("operational_obligations", []),
            applicability_date_assessment=screen_data.get("applicability_date_assessment", "Pending factual evaluation"),
            missing_facts=screen_data.get("missing_facts", []),
            confidence=screen_data.get("confidence", "INSUFFICIENT"),
            status=screen_data.get("status", MappingStatus.DRAFT.value),
            disclaimer_text=EU_AI_ACT_STATUTORY_DISCLAIMER,
            generated_by=screen_data.get("generated_by", actor.actor_id),
            reviewed_by=screen_data.get("reviewed_by"),
            generated_at=screen_data.get("generated_at", now),
            reviewed_at=screen_data.get("reviewed_at"),
            supersedes_screen_id=screen_data.get("supersedes_screen_id"),
            superseded_by_id=None,
        )
        self.session.add(screen)
        self.session.flush()

        after_state = self._serialize_screen_state(screen)
        self.record_governance_audit_event(
            entity_type="eu_legal_relevance_screens",
            entity_id=screen.id,
            transition_type=GovernanceAuditEventType.CREATE_EU_SCREEN,
            actor=actor,
            before_state=None,
            after_state=after_state,
            details={"action": "created_initial_eu_screen"},
        )

        return screen

    def get_eu_screen(self, screen_id: str) -> Optional[EULegalRelevanceScreenModel]:
        """Fetch an EU legal relevance screen by ID."""
        return self.session.get(EULegalRelevanceScreenModel, screen_id)

    def list_eu_screens_for_incident(
        self,
        incident_id: str,
        include_superseded: bool = False,
    ) -> list[EULegalRelevanceScreenModel]:
        """List EU legal relevance screens for an incident."""
        stmt = select(EULegalRelevanceScreenModel).where(
            EULegalRelevanceScreenModel.incident_id == incident_id
        )
        if not include_superseded:
            stmt = stmt.where(EULegalRelevanceScreenModel.superseded_by_id.is_(None))
        return list(self.session.execute(stmt).scalars().all())

    def supersede_eu_screen(
        self,
        original_screen_id: str,
        updated_attributes: dict[str, Any],
        actor: GovernanceActorIdentity,
        rationale: str,
    ) -> EULegalRelevanceScreenModel:
        """Create a superseding EU legal screen, preserving prior record immutably."""
        original = self.session.get(EULegalRelevanceScreenModel, original_screen_id)
        if original is None:
            raise ValueError(f"Original EU screen not found: {original_screen_id}")

        if original.superseded_by_id is not None:
            raise ValueError(f"Screen '{original_screen_id}' has already been superseded by '{original.superseded_by_id}'.")

        new_screen_id = f"euscreen_{uuid.uuid4().hex[:16]}"
        now = datetime.now(timezone.utc)

        merged_data: dict[str, Any] = {
            "incident_id": original.incident_id,
            "reference_set_id": original.reference_set_id,
            "territorial_nexus": original.territorial_nexus,
            "ai_system_relevance": original.ai_system_relevance,
            "actor_roles": list(original.actor_roles),
            "risk_class": original.risk_class,
            "serious_incident_relevance": original.serious_incident_relevance,
            "potentially_relevant_articles": list(original.potentially_relevant_articles),
            "operational_obligations": list(original.operational_obligations),
            "applicability_date_assessment": original.applicability_date_assessment,
            "missing_facts": list(original.missing_facts),
            "confidence": original.confidence,
            "status": MappingStatus.CANDIDATE.value if actor.is_human else MappingStatus.DRAFT.value,
            "disclaimer_text": EU_AI_ACT_STATUTORY_DISCLAIMER,
            "generated_by": actor.actor_id,
            "reviewed_by": actor.actor_id if actor.is_human else None,
            "generated_at": now,
            "reviewed_at": now if actor.is_human else None,
            "supersedes_screen_id": original.id,
        }
        merged_data.update(updated_attributes)

        new_screen = EULegalRelevanceScreenModel(
            id=new_screen_id,
            incident_id=merged_data["incident_id"],
            reference_set_id=merged_data["reference_set_id"],
            territorial_nexus=merged_data["territorial_nexus"],
            ai_system_relevance=merged_data["ai_system_relevance"],
            actor_roles=merged_data["actor_roles"],
            risk_class=merged_data["risk_class"],
            serious_incident_relevance=merged_data["serious_incident_relevance"],
            potentially_relevant_articles=merged_data["potentially_relevant_articles"],
            operational_obligations=merged_data["operational_obligations"],
            applicability_date_assessment=merged_data["applicability_date_assessment"],
            missing_facts=merged_data["missing_facts"],
            confidence=merged_data["confidence"],
            status=merged_data["status"],
            disclaimer_text=EU_AI_ACT_STATUTORY_DISCLAIMER,
            generated_by=merged_data["generated_by"],
            reviewed_by=merged_data.get("reviewed_by"),
            generated_at=merged_data["generated_at"],
            reviewed_at=merged_data.get("reviewed_at"),
            supersedes_screen_id=original.id,
            superseded_by_id=None,
        )
        self.session.add(new_screen)

        original_before = self._serialize_screen_state(original)
        original.superseded_by_id = new_screen_id
        original.status = MappingStatus.SUPERSEDED.value
        self.session.flush()

        original_after = self._serialize_screen_state(original)
        self.record_governance_audit_event(
            entity_type="eu_legal_relevance_screens",
            entity_id=original.id,
            transition_type=GovernanceAuditEventType.SUPERSEDE_EU_SCREEN,
            actor=actor,
            before_state=original_before,
            after_state=original_after,
            details={"superseded_by": new_screen_id, "rationale": rationale},
        )

        new_after = self._serialize_screen_state(new_screen)
        self.record_governance_audit_event(
            entity_type="eu_legal_relevance_screens",
            entity_id=new_screen.id,
            transition_type=GovernanceAuditEventType.CREATE_EU_SCREEN,
            actor=actor,
            before_state=None,
            after_state=new_after,
            details={"supersedes_screen_id": original.id, "rationale": rationale},
        )

        return new_screen

    # --------------------------------------------------------------------------
    # Evidence Links
    # --------------------------------------------------------------------------

    def add_evidence_link(
        self,
        mapping_id: Optional[str],
        screen_id: Optional[str],
        evidence_id: str,
        claim_type: str,
        relevance_note: Optional[str] = None,
        actor: Optional[GovernanceActorIdentity] = None,
    ) -> MappingEvidenceLinkModel:
        """Connect an evidence record to a framework mapping or EU legal screen."""
        if (mapping_id is None and screen_id is None) or (mapping_id is not None and screen_id is not None):
            raise ValueError("Exactly one of mapping_id or screen_id must be provided (XOR).")

        link_id = f"maplink_{uuid.uuid4().hex[:16]}"
        now = datetime.now(timezone.utc)

        link = MappingEvidenceLinkModel(
            id=link_id,
            incident_framework_mapping_id=mapping_id,
            eu_legal_relevance_screen_id=screen_id,
            evidence_id=evidence_id,
            claim_type=claim_type,
            relevance_note=relevance_note,
            created_at=now,
        )
        self.session.add(link)
        self.session.flush()

        if actor is not None:
            entity_type = "incident_framework_mappings" if mapping_id else "eu_legal_relevance_screens"
            entity_id = mapping_id if mapping_id else screen_id
            self.record_governance_audit_event(
                entity_type=entity_type,
                entity_id=entity_id,  # type: ignore[arg-type]
                transition_type=GovernanceAuditEventType.ADD_EVIDENCE_LINK,
                actor=actor,
                before_state=None,
                after_state={"link_id": link_id, "evidence_id": evidence_id, "claim_type": claim_type},
                details={"relevance_note": relevance_note},
            )

        return link

    # --------------------------------------------------------------------------
    # Cryptographic Audit Trail Chaining
    # --------------------------------------------------------------------------

    def record_governance_audit_event(
        self,
        entity_type: str,
        entity_id: str,
        transition_type: GovernanceAuditEventType,
        actor: GovernanceActorIdentity,
        before_state: Optional[dict[str, Any]],
        after_state: dict[str, Any],
        details: Optional[dict[str, Any]] = None,
    ) -> GovernanceAuditLogModel:
        """Record an append-only audit event with cryptographic hash chaining."""
        event_id = f"govevt_{uuid.uuid4().hex[:16]}"
        now = datetime.now(timezone.utc)

        # Get latest event for this entity to fetch previous_event_hash
        stmt = (
            select(GovernanceAuditLogModel)
            .where(
                GovernanceAuditLogModel.entity_type == entity_type,
                GovernanceAuditLogModel.entity_id == entity_id,
            )
            .order_by(GovernanceAuditLogModel.created_at.desc(), GovernanceAuditLogModel.id.desc())
            .limit(1)
        )
        latest_event = self.session.execute(stmt).scalar_one_or_none()
        previous_event_hash = latest_event.event_hash if latest_event else None

        before_state_digest = _sha256_canonical(before_state) if before_state is not None else None
        after_state_digest = _sha256_canonical(after_state)

        event_payload = {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "transition_type": transition_type.value,
            "actor_id": actor.actor_id,
            "is_human": actor.is_human,
            "timestamp_utc": _normalize_iso_timestamp(now),
            "before_state_digest": before_state_digest,
            "after_state_digest": after_state_digest,
            "previous_event_hash": previous_event_hash,
            "details": details or {},
        }
        event_hash = _sha256_canonical(event_payload)

        log_model = GovernanceAuditLogModel(
            id=event_id,
            entity_type=entity_type,
            entity_id=entity_id,
            transition_type=transition_type.value,
            actor_id=actor.actor_id,
            is_human=actor.is_human,
            actor_role=actor.role,
            timestamp_utc=now,
            before_state_digest=before_state_digest,
            after_state_digest=after_state_digest,
            event_hash=event_hash,
            previous_event_hash=previous_event_hash,
            details_json=details or {},
            created_at=now,
        )
        self.session.add(log_model)
        self.session.flush()
        return log_model

    def verify_governance_audit_chain(
        self,
        entity_type: str,
        entity_id: str,
    ) -> tuple[bool, list[str]]:
        """Verify the cryptographic hash chain for a governance entity."""
        stmt = (
            select(GovernanceAuditLogModel)
            .where(
                GovernanceAuditLogModel.entity_type == entity_type,
                GovernanceAuditLogModel.entity_id == entity_id,
            )
            .order_by(GovernanceAuditLogModel.created_at.asc(), GovernanceAuditLogModel.id.asc())
        )
        events = list(self.session.execute(stmt).scalars().all())
        if not events:
            return True, []

        errors: list[str] = []
        expected_prev_hash: Optional[str] = None

        for idx, evt in enumerate(events):
            if evt.previous_event_hash != expected_prev_hash:
                errors.append(
                    f"Chain break at event {evt.id} (index {idx}): expected previous_event_hash "
                    f"'{expected_prev_hash}', got '{evt.previous_event_hash}'"
                )

            # Reconstruct and verify event_hash
            reconstructed_payload = {
                "entity_type": evt.entity_type,
                "entity_id": evt.entity_id,
                "transition_type": evt.transition_type,
                "actor_id": evt.actor_id,
                "is_human": evt.is_human,
                "timestamp_utc": _normalize_iso_timestamp(evt.timestamp_utc),
                "before_state_digest": evt.before_state_digest,
                "after_state_digest": evt.after_state_digest,
                "previous_event_hash": evt.previous_event_hash,
                "details": evt.details_json,
            }
            computed_hash = _sha256_canonical(reconstructed_payload)
            if computed_hash != evt.event_hash:
                errors.append(
                    f"Tampered event payload at event {evt.id}: recorded hash '{evt.event_hash}', "
                    f"computed '{computed_hash}'"
                )

            expected_prev_hash = evt.event_hash

        return len(errors) == 0, errors

    # --------------------------------------------------------------------------
    # State Serializers
    # --------------------------------------------------------------------------

    def _serialize_mapping_state(self, m: IncidentFrameworkMappingModel) -> dict[str, Any]:
        return {
            "id": m.id,
            "incident_id": m.incident_id,
            "framework_code": m.framework_code,
            "reference_set_id": m.reference_set_id,
            "framework_control_id": m.framework_control_id,
            "mapping_level": m.mapping_level,
            "applicability": m.applicability,
            "confidence": m.confidence,
            "mapping_status": m.mapping_status,
            "rationale": m.rationale,
            "known_facts": list(m.known_facts),
            "unknowns": list(m.unknowns),
            "disputed_facts": list(m.disputed_facts),
            "evidence_ids": list(m.evidence_ids),
            "supersedes_mapping_id": m.supersedes_mapping_id,
            "superseded_by_id": m.superseded_by_id,
        }

    def _serialize_screen_state(self, s: EULegalRelevanceScreenModel) -> dict[str, Any]:
        return {
            "id": s.id,
            "incident_id": s.incident_id,
            "reference_set_id": s.reference_set_id,
            "territorial_nexus": s.territorial_nexus,
            "ai_system_relevance": s.ai_system_relevance,
            "actor_roles": list(s.actor_roles),
            "risk_class": s.risk_class,
            "serious_incident_relevance": s.serious_incident_relevance,
            "potentially_relevant_articles": list(s.potentially_relevant_articles),
            "operational_obligations": list(s.operational_obligations),
            "status": s.status,
            "supersedes_screen_id": s.supersedes_screen_id,
            "superseded_by_id": s.superseded_by_id,
        }
