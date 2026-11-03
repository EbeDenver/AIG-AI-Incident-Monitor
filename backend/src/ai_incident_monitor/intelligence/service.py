"""Incident LLM enrichment orchestration service.

Governing Charter: Project Constitution (Rules 1, 2, 3, 4, 11, 14, 16),
ADR-011, AUD-005, OPS-004, Ai-incident-manager-guide.pdf (§1–§3),
amended by Section B (No-Approval Amendment: advisory quality warnings only).
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Optional, Sequence
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_incident_monitor.db.models.audit import AuditLogModel
from ai_incident_monitor.db.models.claim import ClaimRecordModel
from ai_incident_monitor.db.models.enrichment import IncidentEnrichmentModel
from ai_incident_monitor.db.models.incident import IncidentModel
from ai_incident_monitor.intelligence.client import (
    BaseLLMClient,
    MockLLMClient,
    PilotBudgetGuard,
    get_llm_client,
)
from ai_incident_monitor.intelligence.prompts import (
    PROMPT_VERSION,
    build_evidence_package,
    render_enrichment_prompt,
)
from ai_incident_monitor.intelligence.schemas import (
    AssessmentStatus,
    ControlType,
    IncidentEnrichmentDossier,
)
from ai_incident_monitor.intelligence.validator import EnrichmentValidator

logger = logging.getLogger(__name__)


class EnrichmentService:
    """Manages idempotent, audit-logged LLM enrichment of AI incidents."""

    def __init__(
        self,
        default_client: Optional[BaseLLMClient] = None,
        validator: Optional[EnrichmentValidator] = None,
        budget_guard: Optional[PilotBudgetGuard] = None,
    ) -> None:
        self.default_client = default_client or get_llm_client()
        self.validator = validator or EnrichmentValidator()
        self.budget_guard = budget_guard

    def enrich_incident(
        self,
        session: Session,
        incident_id: str,
        *,
        force: bool = False,
        client: Optional[BaseLLMClient] = None,
        budget_guard: Optional[PilotBudgetGuard] = None,
    ) -> IncidentEnrichmentModel:
        """Enrich a single incident dossier with full evidence-grounded intelligence.

        Idempotent: Uses content_hash and prompt_version to prevent duplicate runs
        unless force=True is explicitly passed.
        """
        active_client = client or self.default_client
        active_guard = budget_guard or self.budget_guard

        incident = session.execute(
            select(IncidentModel).where(IncidentModel.id == incident_id)
        ).scalar_one_or_none()

        if not incident:
            raise ValueError(f"Incident '{incident_id}' not found.")

        # Compute content hash of the raw incident data
        content_sig = f"{incident.title}|{incident.summary}"
        content_hash = hashlib.sha256(content_sig.encode("utf-8")).hexdigest()

        # Compute cache key
        model_name = getattr(active_client, "model_name", "generic-llm")
        cache_key = hashlib.sha256(
            f"{content_hash}|{PROMPT_VERSION}|{model_name}".encode("utf-8")
        ).hexdigest()

        # Check existing enrichment
        enrichment = session.execute(
            select(IncidentEnrichmentModel).where(IncidentEnrichmentModel.incident_id == incident_id)
        ).scalar_one_or_none()

        if not force and enrichment and enrichment.status == "COMPLETED" and enrichment.cache_key == cache_key and enrichment.payload_json:
            logger.info(f"Returning cached enrichment for incident '{incident_id}'.")
            return enrichment

        # Retrieve claims and evidence excerpts for grounding
        claims = session.execute(
            select(ClaimRecordModel).where(ClaimRecordModel.incident_id == incident_id)
        ).scalars().all()
        evidence_excerpts = [c.claim_text for c in claims if c.claim_text]

        source_url = getattr(incident, "source_url", None)
        evidence_package = build_evidence_package(
            incident_id=incident.id,
            title=incident.title,
            summary=incident.summary,
            source_url=source_url,
            evidence_excerpts=evidence_excerpts,
        )

        prompt_body, prompt_digest = render_enrichment_prompt(
            incident_id=incident.id,
            title=incident.title,
            summary=incident.summary,
            category=incident.primary_category,
            evidence_excerpts=evidence_excerpts,
            source_url=source_url,
        )

        model_provider = "mock"
        provider_hint = getattr(active_client, "provider_id", "").lower()
        if "claude" in model_name.lower() or "claude" in provider_hint or "anthropic" in provider_hint:
            model_provider = "claude"
        elif "gemini" in model_name.lower() or "gemini" in provider_hint or "google" in provider_hint:
            model_provider = "gemini"

        if not enrichment:
            enrichment = IncidentEnrichmentModel(
                id=f"enr_{uuid.uuid4().hex[:12]}",
                incident_id=incident_id,
                status="RUNNING",
                prompt_version=PROMPT_VERSION,
                model_provider=model_provider,
                model_name=model_name,
                prompt_digest=prompt_digest,
                content_hash=content_hash,
                cache_key=cache_key,
                assessment_status=AssessmentStatus.COMPLETE.value,
                executive_summary="Generating AI analysis...",
                ai_system_role="Pending analysis...",
            )
            session.add(enrichment)
        else:
            enrichment.status = "RUNNING"
            enrichment.prompt_version = PROMPT_VERSION
            enrichment.model_provider = model_provider
            enrichment.model_name = model_name
            enrichment.prompt_digest = prompt_digest
            enrichment.content_hash = content_hash
            enrichment.cache_key = cache_key
            enrichment.error_message = None

        session.flush()

        # Guard: Check and reserve spending allocation before dispatch
        if active_guard:
            # Realistic ceiling bound for comprehensive structured dossier: 10,000 input, 6,000 output
            estimated_call_cost = active_client.calculate_cost(10000, 6000)
            active_guard.check_and_reserve(estimated_call_cost)

        try:
            dossier, in_tok, out_tok, latency, model_id = active_client.generate_dossier(
                prompt_body,
                incident_id=incident.id,
                title=incident.title,
                summary=incident.summary,
                category=incident.primary_category,
                evidence_package=evidence_package,
            )

            # Persist master dossier and synchronized relational columns
            enrichment.status = "COMPLETED"
            enrichment.model_name = model_id
            enrichment.model_provider = model_provider
            enrichment.assessment_status = dossier.assessment_status.value
            enrichment.payload_json = dossier.model_dump_json()

            # Backwards-compatible fields
            enrichment.evidence_sufficiency = (
                "COMPLETE"
                if dossier.assessment_status == AssessmentStatus.COMPLETE
                else (
                    "PARTIAL"
                    if dossier.assessment_status == AssessmentStatus.PARTIAL
                    else "LIMITED_EVIDENCE"
                )
            )
            enrichment.executive_summary = dossier.incident_summary.reported_event
            enrichment.event_chronology = json.dumps([
                f"Reported event: {dossier.incident_summary.reported_event}",
                f"Verified outcome: {dossier.incident_summary.verified_outcome or 'Pending independent verification'}",
            ])
            enrichment.ai_system_role = dossier.ai_involvement.assessment
            enrichment.affected_stakeholders = json.dumps(
                dossier.incident_summary.affected_entities or ["Impacted parties"]
            )
            enrichment.documented_consequences = json.dumps(
                dossier.causal_assessment.observed_outcomes or ["Public incident report"]
            )
            enrichment.unknowns_and_disputes = json.dumps(
                [u.question for u in dossier.uncertainties]
            )
            enrichment.evidence_limitations = (
                dossier.provenance[0].limitations if dossier.provenance else "Syndicated feed reporting"
            )

            enrichment.applicable_profiles = json.dumps([incident.primary_category])
            enrichment.early_warning_indicators = json.dumps(
                dossier.causal_assessment.reported_mechanisms or ["Anomalous AI output"]
            )
            enrichment.preventive_controls = json.dumps(
                [c.control for c in dossier.organizational_controls if c.control_type == ControlType.PREVENTIVE]
            )
            enrichment.detection_mechanisms = json.dumps(
                [c.control for c in dossier.organizational_controls if c.control_type == ControlType.DETECTIVE]
            )
            enrichment.incident_response_actions = json.dumps(
                [c.control for c in dossier.organizational_controls if c.control_type == ControlType.CORRECTIVE]
            )
            enrichment.responsible_functions = json.dumps(
                ["AI Safety Engineering", "Enterprise Risk Management"]
            )
            enrichment.validation_methods = json.dumps(
                [c.validation_test for c in dossier.organizational_controls]
            )

            enrichment.token_count_input = in_tok
            enrichment.token_count_output = out_tok
            enrichment.latency_seconds = latency
            actual_cost = active_client.calculate_cost(in_tok, out_tok)
            enrichment.estimated_cost_usd = actual_cost
            enrichment.error_message = None

            if active_guard:
                active_guard.record_actual(actual_cost, success=True)

            # Record audit entry (AUD-005)
            audit_entry = AuditLogModel(
                entity_type="INCIDENT_ENRICHMENT",
                entity_id=enrichment.id,
                action="GENERATE_ENRICHMENT",
                actor_id=f"intelligence:{model_provider}:{model_id}",
                payload_after={
                    "incident_id": incident_id,
                    "prompt_version": PROMPT_VERSION,
                    "prompt_digest": prompt_digest,
                    "model_provider": model_provider,
                    "model_name": model_id,
                    "assessment_status": dossier.assessment_status.value,
                    "claims_count": len(dossier.claims),
                    "controls_count": len(dossier.organizational_controls),
                    "input_tokens": in_tok,
                    "output_tokens": out_tok,
                    "latency_seconds": latency,
                    "estimated_cost_usd": actual_cost,
                    "advisory_review_flag": dossier.quality_review.advisory_human_review_flag,
                },
            )
            session.add(audit_entry)
            session.commit()
            return enrichment

        except Exception as exc:
            logger.error(f"Enrichment generation failed for incident '{incident_id}': {exc}")
            if active_guard:
                active_guard.record_actual(0.0, success=False)
            session.rollback()
            try:
                fail_enr = session.execute(
                    select(IncidentEnrichmentModel).where(IncidentEnrichmentModel.incident_id == incident_id)
                ).scalar_one_or_none()
                if not fail_enr:
                    fail_enr = IncidentEnrichmentModel(
                        id=f"enr_{uuid.uuid4().hex[:12]}",
                        incident_id=incident_id,
                        status="FAILED",
                        prompt_version=PROMPT_VERSION,
                        model_provider=model_provider,
                        model_name=model_name,
                        prompt_digest=prompt_digest,
                        content_hash=content_hash,
                        cache_key=cache_key,
                        assessment_status=AssessmentStatus.ADVISORY_REVIEW.value,
                        executive_summary="Failed to generate AI analysis.",
                        ai_system_role="Failed to generate AI analysis.",
                        error_message=str(exc),
                    )
                    session.add(fail_enr)
                else:
                    fail_enr.status = "FAILED"
                    fail_enr.error_message = str(exc)
                session.commit()
                return fail_enr
            except Exception:
                session.rollback()
                raise

    def enrich_batch(
        self,
        session: Session,
        incident_ids: Sequence[str] | None = None,
        *,
        limit: Optional[int] = None,
        force: bool = False,
        client: Optional[BaseLLMClient] = None,
        budget_guard: Optional[PilotBudgetGuard] = None,
    ) -> list[IncidentEnrichmentModel]:
        """Enrich a batch of incidents serially, respecting limit and budget boundaries."""
        if incident_ids is None:
            # Select un-enriched incidents
            subq = select(IncidentEnrichmentModel.incident_id).where(
                IncidentEnrichmentModel.status == "COMPLETED"
            )
            query = select(IncidentModel.id).where(~IncidentModel.id.in_(subq)).order_by(
                IncidentModel.created_at.desc()
            )
            if limit:
                query = query.limit(limit)
            target_ids = list(session.execute(query).scalars().all())
        else:
            target_ids = list(incident_ids)[:limit] if limit else list(incident_ids)

        active_guard = budget_guard or self.budget_guard

        results: list[IncidentEnrichmentModel] = []
        for inc_id in target_ids:
            enr = self.enrich_incident(
                session, inc_id, force=force, client=client, budget_guard=active_guard
            )
            results.append(enr)
        return results
