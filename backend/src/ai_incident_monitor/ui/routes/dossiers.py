"""Editorial Dossier Workbench and Review Routes.

Implements Phase 8B web routes:
- Browse and list dossiers with status filtering and pagination (GET /dossiers)
- Candidate incident workbench & selection (GET /dossiers/new)
- Assemble draft dossier (POST /dossiers)
- Inspect dossier details, claims breakdown, findings, drift, and history (GET /dossiers/{id})
- On-demand validation (POST /dossiers/{id}/validate)
- Submit dossier for review (POST /dossiers/{id}/submit)
- Review & attestation interface (GET /dossiers/{id}/review)
- Step-up reviewer approval with exact-hash and drift verification (POST /dossiers/{id}/approve)
- Reject dossier with reason (POST /dossiers/{id}/reject)
- Supersede approved/rejected dossier (POST /dossiers/{id}/supersede)
"""

from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any, Optional
import uuid

from fastapi import APIRouter, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ai_incident_monitor.db.models.editorial import (
    EditorialDossierModel,
    EditorialDossierReviewModel,
)
from ai_incident_monitor.db.models.governance import GovernanceAuditLogModel
from ai_incident_monitor.db.models.incident import IncidentModel
from ai_incident_monitor.editorial.assembly import (
    DEFAULT_METHODOLOGY_NOTES,
    EditorialDossierAssembler,
)
from ai_incident_monitor.editorial.enums import (
    EditorialArtifactPurpose,
    EditorialDossierStatus,
    EditorialExportFormat,
    EditorialPresentationProfile,
    EditorialScopeType,
)
from ai_incident_monitor.editorial.models import (
    EDITORIAL_ATTESTATION_STATEMENT,
    EDITORIAL_DISCLAIMER_TEXT,
    EDITORIAL_DISCLAIMER_VERSION,
    EditorialDossierSchema,
    EditorialReviewerAttestationSchema,
)
from ai_incident_monitor.editorial.renderers.json_renderer import EditorialJSONRenderer
from ai_incident_monitor.editorial.renderers.markdown_renderer import EditorialMarkdownRenderer
from ai_incident_monitor.editorial.review import EditorialReviewStateMachine
from ai_incident_monitor.editorial.source_selector import EditorialSourceSelector
from ai_incident_monitor.editorial.validator import EditorialValidator
from ai_incident_monitor.repositories.editorial_repo import EditorialRepository
from ai_incident_monitor.ui.auth import SESSION_COOKIE_NAME, ServerSessionManager
from ai_incident_monitor.ui.reviewer_auth import (
    ReviewerKeystore,
    ReviewerRateLimiter,
)


router = APIRouter(tags=["editorial-dossiers"])


def _get_authenticated_session(request: Request) -> Any:
    """Validate and return active server-side session or None."""
    sess_mgr: ServerSessionManager = request.app.state.session_manager
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    return sess_mgr.get_session(session_cookie)


def _verify_csrf(request: Request, candidate_csrf: Optional[str]) -> bool:
    """Validate candidate CSRF token against session token."""
    session = _get_authenticated_session(request)
    if not session:
        return False
    sess_mgr: ServerSessionManager = request.app.state.session_manager
    return sess_mgr.validate_csrf(session, candidate_csrf)


@router.get("/dossiers", response_class=HTMLResponse)
async def list_dossiers(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    status_filter: Optional[str] = Query(default=None, alias="status"),
) -> Response:
    """List editorial dossiers with status filtering and pagination."""
    session = _get_authenticated_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    engine = request.app.state.db_engine
    templates = request.app.state.templates

    filter_enum: Optional[EditorialDossierStatus] = None
    if status_filter and status_filter.strip():
        try:
            filter_enum = EditorialDossierStatus(status_filter.strip().upper())
        except ValueError:
            filter_enum = None

    with Session(engine) as db_session:
        repo = EditorialRepository(db_session)
        # Count query
        count_stmt = select(func.count(EditorialDossierModel.id))
        if filter_enum:
            count_stmt = count_stmt.where(EditorialDossierModel.status == filter_enum.value)
        total_items = db_session.execute(count_stmt).scalar() or 0

        total_pages = max(1, math.ceil(total_items / page_size))
        current_page = min(page, total_pages)
        offset = (current_page - 1) * page_size

        dossiers = repo.list_dossiers(status=filter_enum, limit=page_size, offset=offset)

    return templates.TemplateResponse(
        request=request,
        name="dossiers/list.html",
        context={
            "session": session,
            "dossiers": dossiers,
            "current_page": current_page,
            "total_pages": total_pages,
            "total_items": total_items,
            "page_size": page_size,
            "status_filter": status_filter or "",
            "statuses": [s.value for s in EditorialDossierStatus],
            "csrf_token": session.csrf_token,
        },
    )


@router.get("/dossiers/new", response_class=HTMLResponse)
async def new_dossier_form(request: Request) -> Response:
    """Candidate incident selector and dossier creation workbench."""
    session = _get_authenticated_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    engine = request.app.state.db_engine
    templates = request.app.state.templates

    with Session(engine) as db_session:
        selector = EditorialSourceSelector(db_session)
        all_candidates = selector.select_candidates(limit=100, only_eligible=False)

    eligible_candidates = [c for c in all_candidates if c.is_eligible]
    ineligible_candidates = [c for c in all_candidates if not c.is_eligible]

    return templates.TemplateResponse(
        request=request,
        name="dossiers/new.html",
        context={
            "session": session,
            "eligible_candidates": eligible_candidates,
            "ineligible_candidates": ineligible_candidates,
            "scope_types": [s.value for s in EditorialScopeType],
            "default_methodology": DEFAULT_METHODOLOGY_NOTES,
            "csrf_token": session.csrf_token,
            "error": None,
        },
    )


@router.post("/dossiers", response_class=HTMLResponse)
async def create_dossier(
    request: Request,
    title: str = Form(...),
    scope_type: str = Form(default=EditorialScopeType.CUSTOM.value),
    incident_ids: list[str] = Form(...),
    methodology_notes: Optional[str] = Form(default=None),
    csrf_token: str = Form(...),
) -> Response:
    """Assemble and persist a new draft editorial dossier."""
    session = _get_authenticated_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    if not _verify_csrf(request, csrf_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Invalid or expired CSRF token.",
        )

    t_clean = title.strip()
    if not t_clean:
        return _render_new_with_error(request, session, "Dossier title is required.")

    if not incident_ids:
        return _render_new_with_error(request, session, "At least one candidate incident must be selected.")

    try:
        scope_enum = EditorialScopeType(scope_type.strip().upper())
    except ValueError:
        scope_enum = EditorialScopeType.CUSTOM

    engine = request.app.state.db_engine
    with Session(engine) as db_session:
        selector = EditorialSourceSelector(db_session)
        candidates = selector.select_candidates(incident_ids=incident_ids, only_eligible=True)

        if not candidates:
            return _render_new_with_error(
                request, session, "Selected incidents contain zero eligible entries (evidence linkage required)."
            )

        assembler = EditorialDossierAssembler()
        dossier_schema = assembler.assemble(
            candidates=candidates,
            title=t_clean,
            scope_type=scope_enum,
            methodology_notes=methodology_notes.strip() if methodology_notes else None,
        )

        repo = EditorialRepository(db_session)
        saved = repo.save_dossier(
            dossier=dossier_schema,
            actor_id=session.actor_id,
            is_human=session.is_human,
            actor_role=session.role,
        )
        db_session.commit()
        dossier_id = saved.id

    return RedirectResponse(url=f"/dossiers/{dossier_id}", status_code=status.HTTP_303_SEE_OTHER)


def _render_new_with_error(request: Request, session: Any, error_msg: str) -> Response:
    """Helper to re-render new dossier form with error."""
    engine = request.app.state.db_engine
    templates = request.app.state.templates
    with Session(engine) as db_session:
        selector = EditorialSourceSelector(db_session)
        all_candidates = selector.select_candidates(limit=100, only_eligible=False)

    eligible_candidates = [c for c in all_candidates if c.is_eligible]
    ineligible_candidates = [c for c in all_candidates if not c.is_eligible]

    return templates.TemplateResponse(
        request=request,
        name="dossiers/new.html",
        context={
            "session": session,
            "eligible_candidates": eligible_candidates,
            "ineligible_candidates": ineligible_candidates,
            "scope_types": [s.value for s in EditorialScopeType],
            "default_methodology": DEFAULT_METHODOLOGY_NOTES,
            "csrf_token": session.csrf_token,
            "error": error_msg,
        },
        status_code=status.HTTP_400_BAD_REQUEST,
    )


@router.get("/dossiers/{dossier_id}", response_class=HTMLResponse)
async def dossier_detail(request: Request, dossier_id: str) -> Response:
    """Inspect dossier details, entries, claims, validation report, and history."""
    session = _get_authenticated_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    engine = request.app.state.db_engine
    templates = request.app.state.templates

    with Session(engine) as db_session:
        repo = EditorialRepository(db_session)
        dossier = repo.get_dossier(dossier_id)
        if not dossier:
            raise HTTPException(status_code=404, detail=f"Dossier '{dossier_id}' not found.")

        # On-demand validation report
        validator = EditorialValidator()
        validation_report = validator.validate_dossier(dossier)

        # Source drift check
        has_drift, drift_details = repo.check_source_drift(dossier)

        # Audit events and review records
        audit_stmt = (
            select(GovernanceAuditLogModel)
            .where(
                GovernanceAuditLogModel.entity_type == "EDITORIAL_DOSSIER",
                GovernanceAuditLogModel.entity_id == dossier_id,
            )
            .order_by(GovernanceAuditLogModel.created_at.desc(), GovernanceAuditLogModel.id.desc())
        )
        audit_events = list(db_session.execute(audit_stmt).scalars().all())
        reviews_stmt = (
            select(EditorialDossierReviewModel)
            .where(EditorialDossierReviewModel.dossier_id == dossier_id)
            .order_by(EditorialDossierReviewModel.created_at.desc())
        )
        reviews = list(db_session.execute(reviews_stmt).scalars().all())

    current_hash = dossier.compute_content_hash()

    return templates.TemplateResponse(
        request=request,
        name="dossiers/detail.html",
        context={
            "session": session,
            "dossier": dossier,
            "current_content_hash": current_hash,
            "validation_report": validation_report,
            "has_drift": has_drift,
            "drift_details": drift_details,
            "audit_events": audit_events,
            "reviews": reviews,
            "profiles": [p.value for p in EditorialPresentationProfile],
            "formats": [f.value for f in EditorialExportFormat],
            "purposes": [p.value for p in EditorialArtifactPurpose],
            "csrf_token": session.csrf_token,
        },
    )


@router.get("/dossiers/{dossier_id}/preview", response_class=HTMLResponse)
async def preview_dossier_artifact(
    request: Request,
    dossier_id: str,
    profile: str = Query(default=EditorialPresentationProfile.DEEP_DIVE_DOSSIER.value),
    format: str = Query(default="markdown"),
) -> Response:
    """In-browser preview of rendered dossier artifact across presentation profiles."""
    session = _get_authenticated_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    try:
        profile_enum = EditorialPresentationProfile(profile.strip().upper())
    except ValueError:
        profile_enum = EditorialPresentationProfile.DEEP_DIVE_DOSSIER

    format_clean = format.strip().lower()
    if format_clean not in ("markdown", "json"):
        format_clean = "markdown"

    engine = request.app.state.db_engine
    templates = request.app.state.templates

    with Session(engine) as db_session:
        repo = EditorialRepository(db_session)
        dossier = repo.get_dossier(dossier_id)
        if not dossier:
            raise HTTPException(status_code=404, detail=f"Dossier '{dossier_id}' not found.")

        validator = EditorialValidator()
        v_report = validator.validate_dossier(dossier)

        # Render preview using neutral EXPORTED_SNAPSHOT
        is_approved = (dossier.status == EditorialDossierStatus.APPROVED_INFORMATIONAL)
        purpose = EditorialArtifactPurpose.EXPORTED_SNAPSHOT

        audit_records = []
        if format_clean == "json":
            stmt = (
                select(GovernanceAuditLogModel)
                .where(
                    GovernanceAuditLogModel.entity_type == "EDITORIAL_DOSSIER",
                    GovernanceAuditLogModel.entity_id == dossier_id,
                )
                .order_by(GovernanceAuditLogModel.created_at.asc())
            )
            logs = list(db_session.execute(stmt).scalars().all())
            audit_records = [
                {
                    "id": l.id,
                    "transition_type": l.transition_type,
                    "timestamp_utc": l.timestamp_utc,
                    "event_hash": l.event_hash,
                    "actor_role": l.actor_role,
                    "is_human": l.is_human,
                }
                for l in logs
            ]
            renderer = EditorialJSONRenderer()
            rendered_content, payload_hash = renderer.render(
                dossier=dossier,
                profile=profile_enum,
                purpose=purpose,
                validation_report=v_report,
                audit_records=audit_records,
            )
        else:
            md_renderer = EditorialMarkdownRenderer()
            rendered_content, payload_hash = md_renderer.render(
                dossier=dossier,
                profile=profile_enum,
                purpose=purpose,
                validation_report=v_report,
            )

    return templates.TemplateResponse(
        request=request,
        name="dossiers/preview.html",
        context={
            "session": session,
            "dossier": dossier,
            "profile": profile_enum.value,
            "profiles": [p.value for p in EditorialPresentationProfile],
            "format": format_clean,
            "rendered_content": rendered_content,
            "payload_hash": payload_hash,
            "canonical_content_hash": dossier.content_hash or dossier.compute_content_hash(),
            "is_approved": is_approved,
            "purpose": purpose.value,
        },
    )


@router.post("/dossiers/{dossier_id}/validate", response_class=HTMLResponse)
async def validate_dossier_route(
    request: Request,
    dossier_id: str,
    csrf_token: str = Form(...),
) -> Response:
    """Trigger on-demand validation and redirect back to detail view."""
    session = _get_authenticated_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    if not _verify_csrf(request, csrf_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: Invalid CSRF token.")

    return RedirectResponse(url=f"/dossiers/{dossier_id}", status_code=status.HTTP_303_SEE_OTHER)


RETIRED_APPROVAL_DETAIL = (
    "The editorial review and approval workflow has been retired under design correction. "
    "Dossiers are directly usable, previewable, and exportable without approval."
)


@router.post("/dossiers/{dossier_id}/submit")
async def submit_dossier_for_review(request: Request, dossier_id: str) -> Response:
    """Retired editorial workflow endpoint (returns 410 Gone)."""
    session = _get_authenticated_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    raise HTTPException(status_code=status.HTTP_410_GONE, detail=RETIRED_APPROVAL_DETAIL)


@router.get("/dossiers/{dossier_id}/review")
async def review_attestation_page(request: Request, dossier_id: str) -> Response:
    """Retired editorial workflow endpoint (returns 410 Gone)."""
    session = _get_authenticated_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    raise HTTPException(status_code=status.HTTP_410_GONE, detail=RETIRED_APPROVAL_DETAIL)


@router.post("/dossiers/{dossier_id}/approve")
async def approve_dossier_route(request: Request, dossier_id: str) -> Response:
    """Retired editorial workflow endpoint (returns 410 Gone)."""
    session = _get_authenticated_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    raise HTTPException(status_code=status.HTTP_410_GONE, detail=RETIRED_APPROVAL_DETAIL)


@router.post("/dossiers/{dossier_id}/reject")
async def reject_dossier_route(request: Request, dossier_id: str) -> Response:
    """Retired editorial workflow endpoint (returns 410 Gone)."""
    session = _get_authenticated_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    raise HTTPException(status_code=status.HTTP_410_GONE, detail=RETIRED_APPROVAL_DETAIL)


@router.post("/dossiers/{dossier_id}/supersede", response_class=HTMLResponse)
async def supersede_dossier_route(
    request: Request,
    dossier_id: str,
    rationale: Optional[str] = Form(default=None),
    csrf_token: str = Form(...),
) -> Response:
    """Create a new draft version superseding an approved or rejected dossier."""
    session = _get_authenticated_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    if not _verify_csrf(request, csrf_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: Invalid CSRF token.")

    engine = request.app.state.db_engine
    with Session(engine) as db_session:
        repo = EditorialRepository(db_session)
        old_dossier = repo.get_dossier(dossier_id)
        if not old_dossier:
            raise HTTPException(status_code=404, detail=f"Dossier '{dossier_id}' not found.")

        # Create new version
        new_id = f"dos_{uuid.uuid4().hex[:12]}"
        new_dossier = EditorialDossierSchema(
            id=new_id,
            title=f"{old_dossier.title} (Rev {old_dossier.version + 1})",
            scope_type=old_dossier.scope_type,
            coverage_period_start=old_dossier.coverage_period_start,
            coverage_period_end=old_dossier.coverage_period_end,
            status=EditorialDossierStatus.DRAFT,
            version=old_dossier.version + 1,
            entries=old_dossier.entries,
            summary=old_dossier.summary,
            disclaimer_version=old_dossier.disclaimer_version,
            disclaimer_text=old_dossier.disclaimer_text,
            methodology_notes=old_dossier.methodology_notes,
            supersedes_dossier_id=dossier_id,
            content_hash=None,
        )

        repo.save_dossier(
            dossier=new_dossier,
            actor_id=session.actor_id,
            is_human=True,
            actor_role=session.role,
        )
        repo.supersede_dossier(
            old_dossier_id=dossier_id,
            new_dossier_id=new_id,
            actor_id=session.actor_id,
            is_human=True,
            rationale=rationale.strip() if rationale else None,
        )
        db_session.commit()

    return RedirectResponse(url=f"/dossiers/{new_id}", status_code=status.HTTP_303_SEE_OTHER)
