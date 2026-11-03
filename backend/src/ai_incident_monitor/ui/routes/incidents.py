"""Incident Explorer routes: paginated listing and detailed epistemic claim inspection.

Governing Charter: Project Constitution (Rules 1, 2, 3, 4, 10, 14, 15, 16),
PRD §2 (UIX-001, UIX-003, AUD-001, AUD-002), Phase 8A Plan.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ai_incident_monitor.db.models.claim import ClaimRecordModel
from ai_incident_monitor.db.models.enrichment import IncidentEnrichmentModel
from ai_incident_monitor.db.models.evidence import ClaimEvidenceLinkModel, EvidenceRecordModel, QuoteSpanModel
from ai_incident_monitor.db.models.governance import EULegalRelevanceScreenModel
from ai_incident_monitor.db.models.incident import IncidentModel
from ai_incident_monitor.db.models.severity import SeverityAssessmentModel
from ai_incident_monitor.db.models.source import SourceReferenceModel
from ai_incident_monitor.domain.taxonomy import (
    CATEGORY_REGISTRY,
    IncidentCategory,
    get_category_metadata,
)
from ai_incident_monitor.ui.auth import SESSION_COOKIE_NAME, ServerSessionManager

router = APIRouter(tags=["incidents"])

ID_REGEX = re.compile(r"^[a-zA-Z0-9_\-]+$")


def sanitize_url(url: Optional[str]) -> Optional[str]:
    """Allow only safe http: and https: URL schemes, rejecting dangerous schemes."""
    if not url:
        return None
    trimmed = url.strip()
    lower = trimmed.lower()
    if lower.startswith("http://") or lower.startswith("https://"):
        return trimmed
    return None


@router.get("/incidents", response_class=HTMLResponse)
async def list_incidents(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    category_filter: Optional[str] = Query(default=None, alias="category"),
) -> Response:
    """Render paginated incident list with status filtering, category taxonomy, and epistemic badges."""
    sess_mgr: ServerSessionManager = request.app.state.session_manager
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    session = sess_mgr.get_session(session_cookie)
    if not session:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    engine = request.app.state.db_engine
    templates = request.app.state.templates

    with Session(engine) as db_session:
        # Base count query with status & category filtering
        count_stmt = select(func.count(IncidentModel.id))
        if status_filter:
            count_stmt = count_stmt.where(IncidentModel.status == status_filter.strip())
        if category_filter:
            count_stmt = count_stmt.where(IncidentModel.primary_category == category_filter.strip().upper())
        total_items = db_session.execute(count_stmt).scalar() or 0

        total_pages = max(1, math.ceil(total_items / page_size))
        current_page = min(page, total_pages)

        # Paginated items query with stable ordering
        items_stmt = select(IncidentModel)
        if status_filter:
            items_stmt = items_stmt.where(IncidentModel.status == status_filter.strip())
        if category_filter:
            items_stmt = items_stmt.where(IncidentModel.primary_category == category_filter.strip().upper())
        items_stmt = items_stmt.order_by(
            IncidentModel.created_at.desc(),
            IncidentModel.id.asc(),
        ).offset((current_page - 1) * page_size).limit(page_size)

        raw_incidents = db_session.execute(items_stmt).scalars().all()
        incident_ids = [inc.id for inc in raw_incidents]

        # Gather claim counts per incident
        claim_counts: dict[str, int] = {}
        if incident_ids:
            claim_count_stmt = (
                select(ClaimRecordModel.incident_id, func.count(ClaimRecordModel.id))
                .where(ClaimRecordModel.incident_id.in_(incident_ids))
                .group_by(ClaimRecordModel.incident_id)
            )
            for inc_id, count in db_session.execute(claim_count_stmt).all():
                claim_counts[inc_id] = count

        # Gather severity assessments per incident
        severity_map: dict[str, str] = {}
        if incident_ids:
            sev_stmt = (
                select(SeverityAssessmentModel.incident_id, SeverityAssessmentModel.actual_tier)
                .where(SeverityAssessmentModel.incident_id.in_(incident_ids))
            )
            for inc_id, tier in db_session.execute(sev_stmt).all():
                severity_map[inc_id] = tier

        # Gather enrichment statuses per incident
        enrichment_map: dict[str, str] = {}
        if incident_ids:
            enr_stmt = (
                select(IncidentEnrichmentModel.incident_id, IncidentEnrichmentModel.status)
                .where(IncidentEnrichmentModel.incident_id.in_(incident_ids))
            )
            for inc_id, enr_status in db_session.execute(enr_stmt).all():
                enrichment_map[inc_id] = enr_status

        # Gather primary publisher names per incident
        publisher_map: dict[str, str] = {}
        if incident_ids:
            pub_stmt = (
                select(ClaimRecordModel.incident_id, SourceReferenceModel.publisher)
                .join(ClaimEvidenceLinkModel, ClaimRecordModel.id == ClaimEvidenceLinkModel.claim_id)
                .join(EvidenceRecordModel, ClaimEvidenceLinkModel.evidence_id == EvidenceRecordModel.id)
                .join(SourceReferenceModel, EvidenceRecordModel.source_id == SourceReferenceModel.id)
                .where(ClaimRecordModel.incident_id.in_(incident_ids))
            )
            for inc_id, pub in db_session.execute(pub_stmt).all():
                if inc_id not in publisher_map:
                    publisher_map[inc_id] = pub

        # Assemble rich incident view items
        incidents = []
        for inc in raw_incidents:
            cat_meta = get_category_metadata(inc.primary_category)
            event_date_str = str(inc.incident_exact_date) if inc.incident_exact_date else (
                str(inc.incident_date_year) if inc.incident_date_year else "Date Unknown"
            )
            incidents.append({
                "id": inc.id,
                "title": inc.title,
                "summary": inc.summary,
                "status": inc.status,
                "event_date": event_date_str,
                "primary_category": inc.primary_category,
                "category_meta": cat_meta,
                "severity_tier": severity_map.get(inc.id, "NOT_ASSESSED"),
                "enrichment_status": enrichment_map.get(inc.id, "NOT_GENERATED"),
                "publisher": publisher_map.get(inc.id, "Syndicated Source"),
                "claim_count": claim_counts.get(inc.id, 0),
            })

    return templates.TemplateResponse(
        request=request,
        name="incidents/list.html",
        context={
            "session": session,
            "incidents": incidents,
            "page": current_page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": total_pages,
            "status_filter": status_filter,
            "category_filter": category_filter,
            "categories": list(CATEGORY_REGISTRY.values()),
            "csrf_token": session.csrf_token,
        },
    )


@router.get("/incidents/{incident_id}", response_class=HTMLResponse)
async def incident_detail(
    request: Request,
    incident_id: str,
) -> Response:
    """Render incident detail with full epistemic tri-state decomposition, intelligence, and preparedness."""
    sess_mgr: ServerSessionManager = request.app.state.session_manager
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    session = sess_mgr.get_session(session_cookie)
    if not session:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    if not ID_REGEX.match(incident_id) or len(incident_id) > 64:
        raise HTTPException(status_code=404, detail="Invalid incident identifier format.")

    engine = request.app.state.db_engine
    templates = request.app.state.templates

    with Session(engine) as db_session:
        incident = db_session.execute(
            select(IncidentModel).where(IncidentModel.id == incident_id)
        ).scalar_one_or_none()

        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found.")

        cat_meta = get_category_metadata(incident.primary_category)

        # Query claims for this incident
        claims = db_session.execute(
            select(ClaimRecordModel)
            .where(ClaimRecordModel.incident_id == incident_id)
            .order_by(ClaimRecordModel.created_at.asc(), ClaimRecordModel.id.asc())
        ).scalars().all()

        # Collect claim-evidence links
        claim_ids = [c.id for c in claims]
        evidence_by_claim: dict[str, list[dict[str, Any]]] = {cid: [] for cid in claim_ids}
        primary_source: Optional[dict[str, Any]] = None

        if claim_ids:
            links_stmt = (
                select(ClaimEvidenceLinkModel, EvidenceRecordModel, SourceReferenceModel)
                .join(EvidenceRecordModel, ClaimEvidenceLinkModel.evidence_id == EvidenceRecordModel.id)
                .join(SourceReferenceModel, EvidenceRecordModel.source_id == SourceReferenceModel.id)
                .where(ClaimEvidenceLinkModel.claim_id.in_(claim_ids))
            )
            for link, ev, src in db_session.execute(links_stmt).all():
                safe_link_url = sanitize_url(src.url)
                evidence_info = {
                    "evidence_id": ev.id,
                    "evidence_type": ev.evidence_type,
                    "summary": ev.short_summary,
                    "source_title": src.title,
                    "publisher": src.publisher,
                    "source_url": safe_link_url,
                    "content_hash": src.content_hash,
                }
                evidence_by_claim[link.claim_id].append(evidence_info)
                if not primary_source:
                    primary_source = evidence_info

        # Categorize claims into epistemic buckets
        facts = []
        allegations = []
        uncertainties = []
        disputes = []

        for c in claims:
            c_info = {
                "id": c.id,
                "text": c.claim_text,
                "type": c.claim_type,
                "epistemic_status": c.epistemic_status,
                "confidence": c.confidence,
                "materiality": c.materiality,
                "is_causal": c.is_causal_claim,
                "evidence_links": evidence_by_claim.get(c.id, []),
            }
            status_upper = str(c.epistemic_status).upper()
            type_upper = str(c.claim_type).upper()

            if "DISPUTED" in status_upper or "CONTESTED" in status_upper or "DISPUTED" in type_upper:
                disputes.append(c_info)
            elif "UNCERTAINTY" in status_upper or "UNKNOWN" in status_upper or "UNCERTAINTY" in type_upper:
                uncertainties.append(c_info)
            elif status_upper in ("CONFIRMED_FACT", "VERIFIED") or (status_upper.startswith("CONFIRMED") and "UNVERIFIED" not in status_upper):
                facts.append(c_info)
            else:
                allegations.append(c_info)

        # Query severity assessment if available
        severity = db_session.execute(
            select(SeverityAssessmentModel)
            .where(SeverityAssessmentModel.incident_id == incident_id)
            .order_by(SeverityAssessmentModel.created_at.desc())
        ).scalars().first()

        # Query optional EU screen if available
        eu_screen = db_session.execute(
            select(EULegalRelevanceScreenModel)
            .where(EULegalRelevanceScreenModel.incident_id == incident_id)
        ).scalars().first()

        # Query LLM enrichment analysis if available
        raw_enrichment = db_session.execute(
            select(IncidentEnrichmentModel)
            .where(IncidentEnrichmentModel.incident_id == incident_id)
        ).scalar_one_or_none()

        enrichment_data: Optional[dict[str, Any]] = None
        if raw_enrichment:
            dossier_dict: Optional[dict[str, Any]] = None
            if getattr(raw_enrichment, "payload_json", None):
                try:
                    dossier_dict = json.loads(raw_enrichment.payload_json)
                except Exception:
                    dossier_dict = None

            enrichment_data = {
                "id": raw_enrichment.id,
                "status": raw_enrichment.status,
                "assessment_status": getattr(raw_enrichment, "assessment_status", "COMPLETE"),
                "prompt_version": raw_enrichment.prompt_version,
                "model_name": raw_enrichment.model_name,
                "prompt_digest": raw_enrichment.prompt_digest,
                "evidence_sufficiency": raw_enrichment.evidence_sufficiency,
                "executive_summary": raw_enrichment.executive_summary,
                "event_chronology": json.loads(raw_enrichment.event_chronology or "[]"),
                "ai_system_role": raw_enrichment.ai_system_role,
                "affected_stakeholders": json.loads(raw_enrichment.affected_stakeholders or "[]"),
                "documented_consequences": json.loads(raw_enrichment.documented_consequences or "[]"),
                "unknowns_and_disputes": json.loads(raw_enrichment.unknowns_and_disputes or "[]"),
                "evidence_limitations": raw_enrichment.evidence_limitations,
                "applicable_profiles": json.loads(raw_enrichment.applicable_profiles or "[]"),
                "early_warning_indicators": json.loads(raw_enrichment.early_warning_indicators or "[]"),
                "preventive_controls": json.loads(raw_enrichment.preventive_controls or "[]"),
                "detection_mechanisms": json.loads(raw_enrichment.detection_mechanisms or "[]"),
                "incident_response_actions": json.loads(raw_enrichment.incident_response_actions or "[]"),
                "responsible_functions": json.loads(raw_enrichment.responsible_functions or "[]"),
                "validation_methods": json.loads(raw_enrichment.validation_methods or "[]"),
                "token_count_input": raw_enrichment.token_count_input,
                "token_count_output": raw_enrichment.token_count_output,
                "latency_seconds": raw_enrichment.latency_seconds,
                "estimated_cost_usd": raw_enrichment.estimated_cost_usd,
                "error_message": raw_enrichment.error_message,
                "created_at": raw_enrichment.created_at,
                "dossier": dossier_dict,
            }

    return templates.TemplateResponse(
        request=request,
        name="incidents/detail.html",
        context={
            "session": session,
            "incident": incident,
            "category_meta": cat_meta,
            "primary_source": primary_source,
            "enrichment": enrichment_data,
            "facts": facts,
            "allegations": allegations,
            "uncertainties": uncertainties,
            "disputes": disputes,
            "severity": severity,
            "eu_screen": eu_screen,
            "csrf_token": session.csrf_token,
        },
    )
