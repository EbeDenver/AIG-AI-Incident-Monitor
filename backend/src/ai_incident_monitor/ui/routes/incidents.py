"""Incident Explorer routes: paginated listing and detailed epistemic claim inspection.

Governing Charter: Project Constitution (Rules 1, 2, 3, 4, 10, 14, 15, 16),
PRD §2 (UIX-001, UIX-003, AUD-001, AUD-002), Phase 8A Plan.
"""

from __future__ import annotations

import math
import re
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from ai_incident_monitor.db.models.claim import ClaimRecordModel
from ai_incident_monitor.db.models.evidence import ClaimEvidenceLinkModel, EvidenceRecordModel, QuoteSpanModel
from ai_incident_monitor.db.models.governance import EULegalRelevanceScreenModel
from ai_incident_monitor.db.models.incident import IncidentModel
from ai_incident_monitor.db.models.severity import SeverityAssessmentModel
from ai_incident_monitor.db.models.source import SourceReferenceModel
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
) -> Response:
    """Render paginated incident list with status filtering and epistemic badges."""
    sess_mgr: ServerSessionManager = request.app.state.session_manager
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    session = sess_mgr.get_session(session_cookie)
    if not session:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    engine = request.app.state.db_engine
    templates = request.app.state.templates

    with Session(engine) as db_session:
        # Base count query
        count_stmt = select(func.count(IncidentModel.id))
        if status_filter:
            count_stmt = count_stmt.where(IncidentModel.status == status_filter.strip())
        total_items = db_session.execute(count_stmt).scalar() or 0

        total_pages = max(1, math.ceil(total_items / page_size))
        current_page = min(page, total_pages)

        # Paginated items query with stable ordering
        items_stmt = select(IncidentModel)
        if status_filter:
            items_stmt = items_stmt.where(IncidentModel.status == status_filter.strip())
        items_stmt = items_stmt.order_by(
            IncidentModel.created_at.desc(),
            IncidentModel.id.asc(),
        ).offset((current_page - 1) * page_size).limit(page_size)

        incidents = db_session.execute(items_stmt).scalars().all()

        # Gather claim counts per incident
        incident_ids = [inc.id for inc in incidents]
        claim_counts: dict[str, int] = {}
        if incident_ids:
            claim_count_stmt = (
                select(ClaimRecordModel.incident_id, func.count(ClaimRecordModel.id))
                .where(ClaimRecordModel.incident_id.in_(incident_ids))
                .group_by(ClaimRecordModel.incident_id)
            )
            for inc_id, count in db_session.execute(claim_count_stmt).all():
                claim_counts[inc_id] = count

    return templates.TemplateResponse(
        request=request,
        name="incidents/list.html",
        context={
            "session": session,
            "incidents": incidents,
            "claim_counts": claim_counts,
            "page": current_page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": total_pages,
            "status_filter": status_filter,
            "csrf_token": session.csrf_token,
        },
    )


@router.get("/incidents/{incident_id}", response_class=HTMLResponse)
async def incident_detail(
    request: Request,
    incident_id: str,
) -> Response:
    """Render incident detail with full epistemic tri-state decomposition and safe evidence links."""
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

        # Query claims for this incident
        claims = db_session.execute(
            select(ClaimRecordModel)
            .where(ClaimRecordModel.incident_id == incident_id)
            .order_by(ClaimRecordModel.created_at.asc(), ClaimRecordModel.id.asc())
        ).scalars().all()

        # Collect claim-evidence links
        claim_ids = [c.id for c in claims]
        evidence_by_claim: dict[str, list[dict[str, Any]]] = {cid: [] for cid in claim_ids}

        if claim_ids:
            links_stmt = (
                select(ClaimEvidenceLinkModel, EvidenceRecordModel, SourceReferenceModel)
                .join(EvidenceRecordModel, ClaimEvidenceLinkModel.evidence_id == EvidenceRecordModel.id)
                .join(SourceReferenceModel, EvidenceRecordModel.source_id == SourceReferenceModel.id)
                .where(ClaimEvidenceLinkModel.claim_id.in_(claim_ids))
            )
            for link, ev, src in db_session.execute(links_stmt).all():
                safe_link_url = sanitize_url(src.url)
                evidence_by_claim[link.claim_id].append({
                    "evidence_id": ev.id,
                    "evidence_type": ev.evidence_type,
                    "summary": ev.short_summary,
                    "source_title": src.title,
                    "publisher": src.publisher,
                    "source_url": safe_link_url,
                    "content_hash": src.content_hash,
                })

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
            elif "CONFIRMED" in status_upper or "FACT" in type_upper:
                facts.append(c_info)
            elif "UNCERTAINTY" in type_upper or "UNKNOWN" in status_upper:
                uncertainties.append(c_info)
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

    return templates.TemplateResponse(
        request=request,
        name="incidents/detail.html",
        context={
            "session": session,
            "incident": incident,
            "facts": facts,
            "allegations": allegations,
            "uncertainties": uncertainties,
            "disputes": disputes,
            "severity": severity,
            "eu_screen": eu_screen,
            "csrf_token": session.csrf_token,
        },
    )
