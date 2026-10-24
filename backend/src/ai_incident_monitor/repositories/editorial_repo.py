"""Repository managing persistence, state transitions, and audit chaining for editorial dossiers.

Enforces Constitutional Rules 1, 10, 11, 12, 14, 15, and 17:
- Relational transactional consistency across dossiers, entries, and review attestations.
- Immutability of approved dossiers; modifications trigger new versions or supersession.
- Append-only cryptographic audit logging with SHA-256 hash chaining.
- Source drift detection preventing stale or silent mutations before approval.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ai_incident_monitor.db.models.editorial import (
    EditorialDossierEntryModel,
    EditorialDossierModel,
    EditorialDossierReviewModel,
)
from ai_incident_monitor.db.models.governance import GovernanceAuditLogModel
from ai_incident_monitor.db.models.incident import IncidentModel
from ai_incident_monitor.domain.common import (
    ConstitutionalViolationError,
    ImmutabilityViolationError,
)
from ai_incident_monitor.editorial.enums import (
    EditorialAuditEventType,
    EditorialDossierStatus,
    EditorialEntryType,
    EditorialReviewAction,
    EditorialScopeType,
)
from ai_incident_monitor.editorial.models import (
    EditorialDossierEntrySchema,
    EditorialDossierSchema,
    EditorialDossierSummary,
    EditorialEntryDispute,
    EditorialEntryFact,
    EditorialEntryUnknown,
    EditorialReviewerAttestationSchema,
    EditorialValidationReport,
    canonical_sha256,
)
from ai_incident_monitor.editorial.review import EditorialReviewStateMachine
from ai_incident_monitor.repositories.base import BaseRepository


def _normalize_iso_timestamp(dt: datetime) -> str:
    """Normalize datetime to UTC ISO 8601 string with 'Z' suffix and microsecond precision."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


class EditorialRepository(BaseRepository[EditorialDossierModel]):
    """Transactional repository managing editorial dossiers, entries, and review attestations."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, EditorialDossierModel)

    def _model_to_schema(self, model: EditorialDossierModel) -> EditorialDossierSchema:
        """Convert an ORM model to a validated Pydantic domain schema."""
        entries: list[EditorialDossierEntrySchema] = []
        for em in sorted(model.entries, key=lambda e: e.entry_order):
            c_json = em.content_json or {}
            known_facts = [
                EditorialEntryFact(**f) for f in c_json.get("known_facts", [])
            ]
            unknowns = [
                EditorialEntryUnknown(**u) for u in c_json.get("unknowns", [])
            ]
            disputed_claims = [
                EditorialEntryDispute(**d) for d in c_json.get("disputed_claims", [])
            ]

            entry_schema = EditorialDossierEntrySchema(
                entry_id=c_json.get("entry_id", em.id),
                incident_id=em.incident_id,
                entry_order=em.entry_order,
                entry_type=EditorialEntryType(em.entry_type),
                incident_title=c_json.get("incident_title", ""),
                incident_summary=c_json.get("incident_summary", ""),
                incident_date_str=c_json.get("incident_date_str"),
                source_evidence_ids=em.source_evidence_ids or [],
                source_version_hash=em.source_version_hash,
                primary_source_url=c_json.get("primary_source_url"),
                primary_source_publisher=c_json.get("primary_source_publisher"),
                primary_source_published_date=c_json.get("primary_source_published_date"),
                known_facts=known_facts,
                unknowns=unknowns,
                disputed_claims=disputed_claims,
                severity_tier=c_json.get("severity_tier"),
                severity_score=c_json.get("severity_score"),
                eu_screen_id=em.eu_screen_id,
                eu_screen_status=em.eu_screen_status,
                eu_commentary=c_json.get("eu_commentary"),
                omitted_eu_reason=c_json.get("omitted_eu_reason"),
            )
            entries.append(entry_schema)

        summary_data = model.summary_json or {}
        summary = EditorialDossierSummary(
            executive_summary=summary_data.get("executive_summary", ""),
            key_themes=summary_data.get("key_themes", []),
            total_incidents=summary_data.get("total_incidents", len(entries)),
            total_evidence_links=summary_data.get("total_evidence_links", 0),
            disputed_incident_count=summary_data.get("disputed_incident_count", 0),
            learning_and_prevention_themes=summary_data.get("learning_and_prevention_themes", []),
        )

        start = model.coverage_period_start
        if start and start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        end = model.coverage_period_end
        if end and end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)

        return EditorialDossierSchema(
            id=model.id,
            version=model.version,
            title=model.title,
            scope_type=EditorialScopeType(model.scope_type),
            coverage_period_start=start,
            coverage_period_end=end,
            status=EditorialDossierStatus(model.status),
            content_hash=model.content_hash,
            disclaimer_version=model.disclaimer_version,
            disclaimer_text=model.disclaimer_text,
            methodology_notes=model.methodology_notes,
            summary=summary,
            entries=entries,
            metadata_json=model.metadata_json or {},
            generated_by=model.generated_by,
            reviewed_by=model.reviewed_by,
            reviewed_at=model.reviewed_at,
            supersedes_dossier_id=model.supersedes_dossier_id,
            superseded_by_id=model.superseded_by_id,
            rejection_reason=model.rejection_reason,
        )

    def record_audit_event(
        self,
        dossier_id: str,
        transition_type: EditorialAuditEventType,
        actor_id: str,
        is_human: bool,
        before_state: Optional[dict[str, Any]],
        after_state: dict[str, Any],
        actor_role: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> GovernanceAuditLogModel:
        """Record an append-only audit event with cryptographic hash chaining in governance_audit_logs."""
        event_id = f"ed_evt_{uuid.uuid4().hex[:16]}"
        now = datetime.now(timezone.utc)

        # Retrieve latest event for this dossier to get previous_event_hash
        stmt = (
            select(GovernanceAuditLogModel)
            .where(
                GovernanceAuditLogModel.entity_type == "EDITORIAL_DOSSIER",
                GovernanceAuditLogModel.entity_id == dossier_id,
            )
            .order_by(GovernanceAuditLogModel.created_at.desc(), GovernanceAuditLogModel.id.desc())
            .limit(1)
        )
        latest_event = self.session.execute(stmt).scalar_one_or_none()
        previous_event_hash = latest_event.event_hash if latest_event else None

        before_state_digest = (
            canonical_sha256(before_state) if before_state is not None else None
        )
        after_state_digest = canonical_sha256(after_state)

        event_payload = {
            "entity_type": "EDITORIAL_DOSSIER",
            "entity_id": dossier_id,
            "transition_type": transition_type.value,
            "actor_id": actor_id,
            "is_human": is_human,
            "timestamp_utc": _normalize_iso_timestamp(now),
            "before_state_digest": before_state_digest,
            "after_state_digest": after_state_digest,
            "previous_event_hash": previous_event_hash,
            "details": details or {},
        }
        event_hash = canonical_sha256(event_payload)

        log_model = GovernanceAuditLogModel(
            id=event_id,
            entity_type="EDITORIAL_DOSSIER",
            entity_id=dossier_id,
            transition_type=transition_type.value,
            actor_id=actor_id,
            is_human=is_human,
            actor_role=actor_role,
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

    def verify_audit_chain(self, dossier_id: str) -> tuple[bool, list[str]]:
        """Verify the integrity of the append-only cryptographic audit chain for a dossier."""
        stmt = (
            select(GovernanceAuditLogModel)
            .where(
                GovernanceAuditLogModel.entity_type == "EDITORIAL_DOSSIER",
                GovernanceAuditLogModel.entity_id == dossier_id,
            )
            .order_by(GovernanceAuditLogModel.created_at.asc(), GovernanceAuditLogModel.id.asc())
        )
        events = list(self.session.execute(stmt).scalars().all())
        if not events:
            return True, []

        anomalies: list[str] = []
        expected_prev_hash: Optional[str] = None

        for idx, evt in enumerate(events):
            if evt.previous_event_hash != expected_prev_hash:
                anomalies.append(
                    f"Event {evt.id} at index {idx} has previous_event_hash '{evt.previous_event_hash}', "
                    f"expected '{expected_prev_hash}'."
                )

            # Recompute expected event hash
            event_payload = {
                "entity_type": evt.entity_type,
                "entity_id": evt.entity_id,
                "transition_type": evt.transition_type,
                "actor_id": evt.actor_id,
                "is_human": evt.is_human,
                "timestamp_utc": _normalize_iso_timestamp(evt.timestamp_utc),
                "before_state_digest": evt.before_state_digest,
                "after_state_digest": evt.after_state_digest,
                "previous_event_hash": evt.previous_event_hash,
                "details": evt.details_json or {},
            }
            computed_hash = canonical_sha256(event_payload)
            if computed_hash != evt.event_hash:
                anomalies.append(
                    f"Event {evt.id} hash tampered or corrupted. Computed '{computed_hash}', stored '{evt.event_hash}'."
                )

            expected_prev_hash = evt.event_hash

        return len(anomalies) == 0, anomalies

    def save_dossier(
        self,
        dossier: EditorialDossierSchema,
        actor_id: str,
        is_human: bool,
        actor_role: Optional[str] = None,
    ) -> EditorialDossierSchema:
        """Create or update a dossier in DRAFT or ASSEMBLED status."""
        existing = (
            self.session.execute(
                select(EditorialDossierModel)
                .options(selectinload(EditorialDossierModel.entries))
                .where(EditorialDossierModel.id == dossier.id)
            )
            .scalars()
            .first()
        )

        before_state: Optional[dict[str, Any]] = None
        if existing:
            EditorialReviewStateMachine.check_mutation_allowed(
                EditorialDossierStatus(existing.status)
            )
            before_state = {
                "id": existing.id,
                "status": existing.status,
                "version": existing.version,
                "content_hash": existing.content_hash,
            }
            existing.title = dossier.title
            existing.scope_type = dossier.scope_type.value
            existing.coverage_period_start = dossier.coverage_period_start
            existing.coverage_period_end = dossier.coverage_period_end
            existing.status = dossier.status.value
            existing.content_hash = dossier.content_hash
            existing.disclaimer_version = dossier.disclaimer_version
            existing.disclaimer_text = dossier.disclaimer_text
            existing.methodology_notes = dossier.methodology_notes
            existing.summary_json = dossier.summary.canonical_dict()
            existing.metadata_json = dossier.metadata_json
            dossier_model = existing

            # Replace entries
            self.session.execute(
                EditorialDossierEntryModel.__table__.delete().where(
                    EditorialDossierEntryModel.dossier_id == existing.id
                )
            )
        else:
            dossier_model = EditorialDossierModel(
                id=dossier.id,
                version=dossier.version,
                title=dossier.title,
                scope_type=dossier.scope_type.value,
                coverage_period_start=dossier.coverage_period_start,
                coverage_period_end=dossier.coverage_period_end,
                status=dossier.status.value,
                content_hash=dossier.content_hash,
                disclaimer_version=dossier.disclaimer_version,
                disclaimer_text=dossier.disclaimer_text,
                methodology_notes=dossier.methodology_notes,
                summary_json=dossier.summary.canonical_dict(),
                metadata_json=dossier.metadata_json,
                generated_by=dossier.generated_by,
                reviewed_by=dossier.reviewed_by,
                reviewed_at=dossier.reviewed_at,
                supersedes_dossier_id=dossier.supersedes_dossier_id,
                superseded_by_id=dossier.superseded_by_id,
                rejection_reason=dossier.rejection_reason,
            )
            self.session.add(dossier_model)

        # Add entries
        now = datetime.now(timezone.utc)
        for entry in dossier.entries:
            db_entry_id = (
                entry.entry_id
                if entry.entry_id.startswith(f"{dossier.id}_")
                else f"{dossier.id[:31]}_{entry.entry_id}"[:64]
            )
            entry_model = EditorialDossierEntryModel(
                id=db_entry_id,
                dossier_id=dossier.id,
                incident_id=entry.incident_id,
                entry_order=entry.entry_order,
                entry_type=entry.entry_type.value,
                source_evidence_ids=entry.source_evidence_ids,
                source_version_hash=entry.source_version_hash,
                eu_screen_id=entry.eu_screen_id,
                eu_screen_status=entry.eu_screen_status,
                content_json=entry.canonical_dict(),
                created_at=now,
            )
            self.session.add(entry_model)

        self.session.flush()

        after_state = {
            "id": dossier_model.id,
            "status": dossier_model.status,
            "version": dossier_model.version,
            "content_hash": dossier_model.content_hash,
            "entry_count": len(dossier.entries),
        }

        evt_type = (
            EditorialAuditEventType.ASSEMBLE_DOSSIER
            if dossier.status == EditorialDossierStatus.ASSEMBLED
            else EditorialAuditEventType.CREATE_DOSSIER
        )
        self.record_audit_event(
            dossier_id=dossier.id,
            transition_type=evt_type,
            actor_id=actor_id,
            is_human=is_human,
            before_state=before_state,
            after_state=after_state,
            actor_role=actor_role,
        )

        return self.get_dossier(dossier.id)  # type: ignore[return-value]

    def get_dossier(self, dossier_id: str) -> Optional[EditorialDossierSchema]:
        """Fetch a complete editorial dossier domain schema by ID."""
        stmt = (
            select(EditorialDossierModel)
            .options(
                selectinload(EditorialDossierModel.entries),
                selectinload(EditorialDossierModel.reviews),
            )
            .where(EditorialDossierModel.id == dossier_id)
        )
        model = self.session.execute(stmt).scalars().first()
        if not model:
            return None
        return self._model_to_schema(model)

    def list_dossiers(
        self,
        status: Optional[EditorialDossierStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[EditorialDossierSchema]:
        """List dossiers with optional status filter."""
        stmt = (
            select(EditorialDossierModel)
            .options(selectinload(EditorialDossierModel.entries))
            .order_by(EditorialDossierModel.created_at.desc())
        )
        if status:
            stmt = stmt.where(EditorialDossierModel.status == status.value)
        stmt = stmt.limit(limit).offset(offset)

        models = list(self.session.execute(stmt).scalars().all())
        return [self._model_to_schema(m) for m in models]

    def check_source_drift(self, dossier: EditorialDossierSchema) -> tuple[bool, list[str]]:
        """Verify whether underlying source records have drifted since dossier assembly."""
        anomalies: list[str] = []

        for entry in dossier.entries:
            inc = (
                self.session.execute(
                    select(IncidentModel)
                    .options(
                        selectinload(IncidentModel.claims),
                    )
                    .where(IncidentModel.id == entry.incident_id)
                )
                .scalars()
                .first()
            )
            if not inc:
                anomalies.append(
                    f"Underlying incident '{entry.incident_id}' no longer exists in repository."
                )
                continue

            current_digest_payload = {
                "incident_id": inc.id,
                "title": inc.title,
                "summary": inc.summary,
                "evidence_ids": entry.source_evidence_ids,
                "claim_count": len(inc.claims),
            }
            current_hash = hashlib.sha256(
                json.dumps(current_digest_payload, sort_keys=True).encode("utf-8")
            ).hexdigest()

            if current_hash != entry.source_version_hash:
                anomalies.append(
                    f"Source drift on incident '{entry.incident_id}': recorded hash '{entry.source_version_hash}', "
                    f"current hash '{current_hash}'."
                )

        return len(anomalies) > 0, anomalies

    def submit_for_review(
        self,
        dossier_id: str,
        actor_id: str,
        is_human: bool,
        actor_role: Optional[str] = None,
    ) -> EditorialDossierSchema:
        """Transition dossier from ASSEMBLED to PENDING_REVIEW."""
        dossier = self.get_dossier(dossier_id)
        if not dossier:
            raise KeyError(f"Dossier '{dossier_id}' not found.")

        EditorialReviewStateMachine.validate_submission_for_review(dossier)

        model = (
            self.session.execute(
                select(EditorialDossierModel).where(EditorialDossierModel.id == dossier_id)
            )
            .scalars()
            .first()
        )
        before_state = {"id": model.id, "status": model.status}

        model.status = EditorialDossierStatus.PENDING_REVIEW.value
        self.session.flush()

        after_state = {"id": model.id, "status": model.status}
        self.record_audit_event(
            dossier_id=dossier_id,
            transition_type=EditorialAuditEventType.SUBMIT_FOR_REVIEW,
            actor_id=actor_id,
            is_human=is_human,
            before_state=before_state,
            after_state=after_state,
            actor_role=actor_role,
        )

        return self.get_dossier(dossier_id)  # type: ignore[return-value]

    def approve_dossier(
        self,
        dossier_id: str,
        attestation: EditorialReviewerAttestationSchema,
        validation_report: EditorialValidationReport,
    ) -> EditorialDossierSchema:
        """Approve an editorial dossier under human sign-off."""
        dossier = self.get_dossier(dossier_id)
        if not dossier:
            raise KeyError(f"Dossier '{dossier_id}' not found.")

        has_drift, drift_details = self.check_source_drift(dossier)
        EditorialReviewStateMachine.validate_approval(
            dossier=dossier,
            attestation=attestation,
            validation_report=validation_report,
            source_drift_detected=has_drift,
        )

        model = (
            self.session.execute(
                select(EditorialDossierModel).where(EditorialDossierModel.id == dossier_id)
            )
            .scalars()
            .first()
        )
        before_state = {
            "id": model.id,
            "status": model.status,
            "reviewed_by": model.reviewed_by,
        }

        now = attestation.attested_at
        model.status = EditorialDossierStatus.APPROVED_INFORMATIONAL.value
        model.reviewed_by = attestation.reviewer_id
        model.reviewed_at = now
        model.content_hash = attestation.content_hash

        # Create review record
        review_record = EditorialDossierReviewModel(
            id=f"rev_{uuid.uuid4().hex[:12]}",
            dossier_id=dossier_id,
            dossier_version=dossier.version,
            content_hash=attestation.content_hash,
            reviewer_id=attestation.reviewer_id,
            reviewer_name=attestation.reviewer_name,
            reviewer_role=attestation.reviewer_role,
            is_human=attestation.is_human,
            statement_confirmed=attestation.statement_confirmed,
            attestation_statement=attestation.attestation_statement,
            action=EditorialReviewAction.APPROVE.value,
            rationale="Approved following forensic editorial review.",
            attestation_json=attestation.model_dump(mode="json"),
            reviewed_at=now,
            created_at=now,
        )
        self.session.add(review_record)
        self.session.flush()

        after_state = {
            "id": model.id,
            "status": model.status,
            "reviewed_by": model.reviewed_by,
            "content_hash": model.content_hash,
        }
        self.record_audit_event(
            dossier_id=dossier_id,
            transition_type=EditorialAuditEventType.APPROVE_DOSSIER,
            actor_id=attestation.reviewer_id,
            is_human=True,
            before_state=before_state,
            after_state=after_state,
            actor_role=attestation.reviewer_role,
            details={"review_id": review_record.id},
        )

        return self.get_dossier(dossier_id)  # type: ignore[return-value]

    def reject_dossier(
        self,
        dossier_id: str,
        reviewer_id: str,
        is_human: bool,
        rejection_reason: str,
        reviewer_name: Optional[str] = None,
        reviewer_role: Optional[str] = None,
    ) -> EditorialDossierSchema:
        """Reject an editorial dossier with documented rationale."""
        dossier = self.get_dossier(dossier_id)
        if not dossier:
            raise KeyError(f"Dossier '{dossier_id}' not found.")

        EditorialReviewStateMachine.validate_rejection(
            dossier=dossier,
            reviewer_id=reviewer_id,
            is_human=is_human,
            rejection_reason=rejection_reason,
        )

        model = (
            self.session.execute(
                select(EditorialDossierModel).where(EditorialDossierModel.id == dossier_id)
            )
            .scalars()
            .first()
        )
        before_state = {
            "id": model.id,
            "status": model.status,
            "rejection_reason": model.rejection_reason,
        }

        now = datetime.now(timezone.utc)
        model.status = EditorialDossierStatus.REJECTED.value
        model.rejection_reason = rejection_reason

        review_record = EditorialDossierReviewModel(
            id=f"rev_{uuid.uuid4().hex[:12]}",
            dossier_id=dossier_id,
            dossier_version=dossier.version,
            content_hash=dossier.content_hash or "unhashed",
            reviewer_id=reviewer_id,
            reviewer_name=reviewer_name,
            reviewer_role=reviewer_role,
            is_human=is_human,
            statement_confirmed=False,
            attestation_statement="Dossier rejected with documented rationale.",
            action=EditorialReviewAction.REJECT.value,
            rationale=rejection_reason,
            attestation_json={"rejection_reason": rejection_reason},
            reviewed_at=now,
            created_at=now,
        )
        self.session.add(review_record)
        self.session.flush()

        after_state = {
            "id": model.id,
            "status": model.status,
            "rejection_reason": model.rejection_reason,
        }
        self.record_audit_event(
            dossier_id=dossier_id,
            transition_type=EditorialAuditEventType.REJECT_DOSSIER,
            actor_id=reviewer_id,
            is_human=is_human,
            before_state=before_state,
            after_state=after_state,
            actor_role=reviewer_role,
            details={"rejection_reason": rejection_reason},
        )

        return self.get_dossier(dossier_id)  # type: ignore[return-value]

    def supersede_dossier(
        self,
        old_dossier_id: str,
        new_dossier_id: str,
        actor_id: str,
        is_human: bool,
        rationale: Optional[str] = None,
    ) -> EditorialDossierSchema:
        """Supersede an approved dossier with a newer version."""
        old_model = (
            self.session.execute(
                select(EditorialDossierModel).where(EditorialDossierModel.id == old_dossier_id)
            )
            .scalars()
            .first()
        )
        if not old_model:
            raise KeyError(f"Prior dossier '{old_dossier_id}' not found.")

        new_model = (
            self.session.execute(
                select(EditorialDossierModel).where(EditorialDossierModel.id == new_dossier_id)
            )
            .scalars()
            .first()
        )
        if not new_model:
            raise KeyError(f"New dossier '{new_dossier_id}' not found.")

        before_state = {
            "id": old_model.id,
            "status": old_model.status,
            "superseded_by_id": old_model.superseded_by_id,
        }

        old_model.status = EditorialDossierStatus.SUPERSEDED.value
        old_model.superseded_by_id = new_dossier_id
        new_model.supersedes_dossier_id = old_dossier_id
        self.session.flush()

        after_state = {
            "id": old_model.id,
            "status": old_model.status,
            "superseded_by_id": old_model.superseded_by_id,
        }
        self.record_audit_event(
            dossier_id=old_dossier_id,
            transition_type=EditorialAuditEventType.SUPERSEDE_DOSSIER,
            actor_id=actor_id,
            is_human=is_human,
            before_state=before_state,
            after_state=after_state,
            details={
                "superseded_by_id": new_dossier_id,
                "rationale": rationale or "Superseded by updated revision.",
            },
        )

        return self.get_dossier(old_dossier_id)  # type: ignore[return-value]
