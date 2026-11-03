"""Incident LLM enrichment orchestration service.

Governing Charter: Project Constitution (Rules 1, 2, 3, 4, 11, 14, 16),
ADR-011, AUD-005, OPS-004.
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
from ai_incident_monitor.intelligence.client import BaseLLMClient, MockLLMClient
from ai_incident_monitor.intelligence.prompts import PROMPT_VERSION, render_enrichment_prompt

logger = logging.getLogger(__name__)


class EnrichmentService:
    """Manages idempotent, audit-logged LLM enrichment of AI incidents."""

    def __init__(self, default_client: Optional[BaseLLMClient] = None) -> None:
        self.default_client = default_client or MockLLMClient()

    def enrich_incident(
        self,
        session: Session,
        incident_id: str,
        *,
        force: bool = False,
        client: Optional[BaseLLMClient] = None,
    ) -> IncidentEnrichmentModel:
        """Enrich a single incident dossier with explanation and preparedness guidance.

        Idempotent: Uses content_hash and prompt_version to prevent duplicate runs
        unless force=True is explicitly passed.
        """
        active_client = client or self.default_client

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

        if not force and enrichment and enrichment.status == "COMPLETED" and enrichment.cache_key == cache_key:
            logger.info(f"Returning cached enrichment for incident '{incident_id}'.")
            return enrichment

        # Retrieve claims and evidence excerpts for grounding
        claims = session.execute(
            select(ClaimRecordModel).where(ClaimRecordModel.incident_id == incident_id)
        ).scalars().all()
        evidence_excerpts = [c.claim_text for c in claims if c.claim_text]

        prompt_body, prompt_digest = render_enrichment_prompt(
            incident_id=incident.id,
            title=incident.title,
            summary=incident.summary,
            category=incident.primary_category,
            evidence_excerpts=evidence_excerpts,
        )

        if not enrichment:
            enrichment = IncidentEnrichmentModel(
                id=f"enr_{uuid.uuid4().hex[:12]}",
                incident_id=incident_id,
                status="RUNNING",
                prompt_version=PROMPT_VERSION,
                model_provider="mock" if isinstance(active_client, MockLLMClient) else "external",
                model_name=model_name,
                prompt_digest=prompt_digest,
                content_hash=content_hash,
                cache_key=cache_key,
                executive_summary="Generating AI analysis...",
                ai_system_role="Pending analysis...",
            )
            session.add(enrichment)
        else:
            enrichment.status = "RUNNING"
            enrichment.prompt_version = PROMPT_VERSION
            enrichment.model_name = model_name
            enrichment.prompt_digest = prompt_digest
            enrichment.content_hash = content_hash
            enrichment.cache_key = cache_key
            enrichment.error_message = None

        session.flush()

        try:
            payload, in_tok, out_tok, latency, model_id = active_client.generate_enrichment(
                prompt_body,
                incident_id=incident.id,
                title=incident.title,
                summary=incident.summary,
                category=incident.primary_category,
            )

            enrichment.status = "COMPLETED"
            enrichment.model_name = model_id
            enrichment.evidence_sufficiency = payload.explanation.sufficiency.value
            enrichment.executive_summary = payload.explanation.executive_summary
            enrichment.event_chronology = json.dumps(payload.explanation.event_chronology)
            enrichment.ai_system_role = payload.explanation.ai_system_role
            enrichment.affected_stakeholders = json.dumps(payload.explanation.affected_stakeholders)
            enrichment.documented_consequences = json.dumps(payload.explanation.documented_consequences)
            enrichment.unknowns_and_disputes = json.dumps(payload.explanation.unknowns_and_disputes)
            enrichment.evidence_limitations = payload.explanation.evidence_limitations

            enrichment.applicable_profiles = json.dumps(payload.preparedness.applicable_profiles)
            enrichment.early_warning_indicators = json.dumps(payload.preparedness.early_warning_indicators)
            enrichment.preventive_controls = json.dumps(payload.preparedness.prioritized_preventive_controls)
            enrichment.detection_mechanisms = json.dumps(payload.preparedness.detection_mechanisms)
            enrichment.incident_response_actions = json.dumps(payload.preparedness.incident_response_actions)
            enrichment.responsible_functions = json.dumps(payload.preparedness.responsible_functions)
            enrichment.validation_methods = json.dumps(payload.preparedness.validation_methods)

            enrichment.token_count_input = in_tok
            enrichment.token_count_output = out_tok
            enrichment.latency_seconds = latency
            enrichment.estimated_cost_usd = round(
                (in_tok * 0.00000125) + (out_tok * 0.00001000), 6
            )  # pricing basis
            enrichment.error_message = None

            # Record audit entry (AUD-005)
            audit_entry = AuditLogModel(
                entity_type="INCIDENT_ENRICHMENT",
                entity_id=enrichment.id,
                action="GENERATE_ENRICHMENT",
                actor_id=f"intelligence:{model_id}",
                payload_after={
                    "incident_id": incident_id,
                    "prompt_version": PROMPT_VERSION,
                    "prompt_digest": prompt_digest,
                    "model_name": model_id,
                    "input_tokens": in_tok,
                    "output_tokens": out_tok,
                    "latency_seconds": latency,
                    "sufficiency": payload.explanation.sufficiency.value,
                },
            )
            session.add(audit_entry)
            session.commit()
            return enrichment

        except Exception as exc:
            logger.error(f"Enrichment generation failed for incident '{incident_id}': {exc}")
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
                        model_name=model_name,
                        prompt_digest=prompt_digest,
                        content_hash=content_hash,
                        cache_key=cache_key,
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
    ) -> list[IncidentEnrichmentModel]:
        """Enrich a batch of incidents respecting limit boundaries."""
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

        results: list[IncidentEnrichmentModel] = []
        for inc_id in target_ids:
            enr = self.enrich_incident(session, inc_id, force=force, client=client)
            results.append(enr)
        return results
