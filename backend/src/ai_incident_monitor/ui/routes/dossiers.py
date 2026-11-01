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
    EditorialDossierStatus,
    EditorialScopeType,
)
from ai_incident_monitor.editorial.models import (
    EDITORIAL_ATTESTATION_STATEMENT,
    EDITORIAL_DISCLAIMER_TEXT,
    EDITORIAL_DISCLAIMER_VERSION,
    EditorialDossierSchema,
    EditorialReviewerAttestationSchema,
)
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
            "csrf_token": session.csrf_token,
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


@router.post("/dossiers/{dossier_id}/submit", response_class=HTMLResponse)
async def submit_dossier_for_review(
    request: Request,
    dossier_id: str,
    csrf_token: str = Form(...),
) -> Response:
    """Transition dossier from DRAFT/ASSEMBLED to PENDING_REVIEW."""
    session = _get_authenticated_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    if not _verify_csrf(request, csrf_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: Invalid CSRF token.")

    engine = request.app.state.db_engine
    with Session(engine) as db_session:
        repo = EditorialRepository(db_session)
        try:
            repo.submit_for_review(
                dossier_id=dossier_id,
                actor_id=session.actor_id,
                is_human=session.is_human,
                actor_role=session.role,
            )
            db_session.commit()
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Dossier '{dossier_id}' not found.")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    return RedirectResponse(url=f"/dossiers/{dossier_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/dossiers/{dossier_id}/review", response_class=HTMLResponse)
async def review_attestation_page(request: Request, dossier_id: str) -> Response:
    """Review and attestation screen for human reviewer approval."""
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

        if dossier.status != EditorialDossierStatus.PENDING_REVIEW:
            return RedirectResponse(url=f"/dossiers/{dossier_id}", status_code=status.HTTP_303_SEE_OTHER)

        validator = EditorialValidator()
        validation_report = validator.validate_dossier(dossier)
        has_drift, drift_details = repo.check_source_drift(dossier)

    current_hash = dossier.compute_content_hash()

    return templates.TemplateResponse(
        request=request,
        name="dossiers/review.html",
        context={
            "session": session,
            "dossier": dossier,
            "current_content_hash": current_hash,
            "validation_report": validation_report,
            "has_drift": has_drift,
            "drift_details": drift_details,
            "attestation_statement": EDITORIAL_ATTESTATION_STATEMENT,
            "disclaimer_text": EDITORIAL_DISCLAIMER_TEXT,
            "disclaimer_version": EDITORIAL_DISCLAIMER_VERSION,
            "csrf_token": session.csrf_token,
            "error": None,
        },
    )


@router.post("/dossiers/{dossier_id}/approve", response_class=HTMLResponse)
async def approve_dossier_route(
    request: Request,
    dossier_id: str,
    reviewer_id: str = Form(...),
    reviewer_key: str = Form(...),
    expected_version: int = Form(...),
    expected_content_hash: str = Form(...),
    statement_confirmed: bool = Form(default=False),
    csrf_token: str = Form(...),
) -> Response:
    """Step-up reviewer approval verifying reviewer key, exact content hash, and drift."""
    session = _get_authenticated_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    if not _verify_csrf(request, csrf_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: Invalid CSRF token.")

    client_ip = request.client.host if request.client else "127.0.0.1"
    rate_limiter: ReviewerRateLimiter = request.app.state.reviewer_rate_limiter
    keystore: ReviewerKeystore = request.app.state.reviewer_keystore

    # 1. Rate limiter check
    is_blocked, cooldown = rate_limiter.is_blocked(f"{client_ip}:{reviewer_id}")
    if is_blocked:
        return _render_review_error(
            request,
            dossier_id,
            f"Too many failed approval attempts. Reviewer locked for {int(cooldown)} seconds.",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    # 2. Verify reviewer credentials via keystore
    is_valid, err_reason, reviewer_record = keystore.verify_reviewer_key(
        reviewer_id=reviewer_id,
        candidate_key=reviewer_key,
    )
    if not is_valid or not reviewer_record:
        rate_limiter.record_failure(f"{client_ip}:{reviewer_id}")
        return _render_review_error(
            request,
            dossier_id,
            err_reason or "Invalid reviewer credentials or inactive reviewer.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    # 3. Statement confirmation check
    if not statement_confirmed:
        return _render_review_error(
            request,
            dossier_id,
            "You must explicitly confirm the editorial attestation statement.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    engine = request.app.state.db_engine
    with Session(engine) as db_session:
        repo = EditorialRepository(db_session)
        dossier = repo.get_dossier(dossier_id)
        if not dossier:
            raise HTTPException(status_code=404, detail=f"Dossier '{dossier_id}' not found.")

        # 4. State check
        if dossier.status != EditorialDossierStatus.PENDING_REVIEW:
            return _render_review_error(
                request,
                dossier_id,
                f"Cannot approve dossier in status '{dossier.status.value}'. Must be PENDING_REVIEW.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # 5. Stale-page / Concurrency check: Exact version and content hash match
        current_hash = dossier.compute_content_hash()
        if dossier.version != expected_version:
            return _render_review_error(
                request,
                dossier_id,
                f"Stale page: Dossier version changed (displayed version {expected_version}, current version {dossier.version}).",
                status_code=status.HTTP_409_CONFLICT,
            )

        if current_hash != expected_content_hash.strip():
            return _render_review_error(
                request,
                dossier_id,
                "Stale page: Dossier content hash changed since review page was rendered. Please refresh.",
                status_code=status.HTTP_409_CONFLICT,
            )

        # 6. Source drift check
        has_drift, drift_details = repo.check_source_drift(dossier)
        if has_drift:
            return _render_review_error(
                request,
                dossier_id,
                f"Cannot approve: Underlying source records have drifted: {'; '.join(drift_details)}",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # 7. Validation report check
        validator = EditorialValidator()
        validation_report = validator.validate_dossier(dossier)
        if not validation_report.is_valid or validation_report.blocking_count > 0:
            blocking_reasons = [
                f"{f.field_path}: {f.message}"
                for f in validation_report.findings
                if f.severity.value == "BLOCKING"
            ]
            return _render_review_error(
                request,
                dossier_id,
                f"Cannot approve: {validation_report.blocking_count} blocking validation finding(s): {'; '.join(blocking_reasons)}",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # 8. Construct validated attestation schema with server-side identity injection
        attestation = EditorialReviewerAttestationSchema(
            reviewer_id=reviewer_record.reviewer_id,
            reviewer_name=reviewer_record.reviewer_name,
            reviewer_role=reviewer_record.reviewer_role,
            is_human=True,
            statement_confirmed=True,
            content_hash=current_hash,
            dossier_id=dossier_id,
            dossier_version=dossier.version,
            attested_at=datetime.now(timezone.utc),
            source_snapshots_verified=True,
            editorial_standards_verified=True,
        )

        # 9. Commit atomic approval
        repo.approve_dossier(
            dossier_id=dossier_id,
            attestation=attestation,
            validation_report=validation_report,
        )
        db_session.commit()

    # Reset failed attempts upon successful approval
    rate_limiter.reset(f"{client_ip}:{reviewer_id}")

    return RedirectResponse(url=f"/dossiers/{dossier_id}", status_code=status.HTTP_303_SEE_OTHER)


def _render_review_error(
    request: Request,
    dossier_id: str,
    error_msg: str,
    status_code: int = 400,
) -> Response:
    """Helper to render review page with error."""
    session = _get_authenticated_session(request)
    engine = request.app.state.db_engine
    templates = request.app.state.templates

    with Session(engine) as db_session:
        repo = EditorialRepository(db_session)
        dossier = repo.get_dossier(dossier_id)
        if not dossier:
            raise HTTPException(status_code=404, detail="Dossier not found.")
        validator = EditorialValidator()
        validation_report = validator.validate_dossier(dossier)
        has_drift, drift_details = repo.check_source_drift(dossier)

    current_hash = dossier.compute_content_hash()

    return templates.TemplateResponse(
        request=request,
        name="dossiers/review.html",
        context={
            "session": session,
            "dossier": dossier,
            "current_content_hash": current_hash,
            "validation_report": validation_report,
            "has_drift": has_drift,
            "drift_details": drift_details,
            "attestation_statement": EDITORIAL_ATTESTATION_STATEMENT,
            "disclaimer_text": EDITORIAL_DISCLAIMER_TEXT,
            "disclaimer_version": EDITORIAL_DISCLAIMER_VERSION,
            "csrf_token": session.csrf_token,
            "error": error_msg,
        },
        status_code=status_code,
    )


@router.post("/dossiers/{dossier_id}/reject", response_class=HTMLResponse)
async def reject_dossier_route(
    request: Request,
    dossier_id: str,
    rejection_reason: str = Form(...),
    reviewer_id: Optional[str] = Form(default=None),
    csrf_token: str = Form(...),
) -> Response:
    """Reject a dossier with mandatory documented rationale."""
    session = _get_authenticated_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    if not _verify_csrf(request, csrf_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: Invalid CSRF token.")

    reason_clean = rejection_reason.strip()
    if not reason_clean or len(reason_clean) < 5:
        raise HTTPException(
            status_code=400,
            detail="Rejection reason must be at least 5 characters long.",
        )

    r_id = reviewer_id.strip() if reviewer_id and reviewer_id.strip() else session.actor_id

    engine = request.app.state.db_engine
    with Session(engine) as db_session:
        repo = EditorialRepository(db_session)
        try:
            repo.reject_dossier(
                dossier_id=dossier_id,
                reviewer_id=r_id,
                is_human=True,
                rejection_reason=reason_clean,
                reviewer_role=session.role,
            )
            db_session.commit()
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    return RedirectResponse(url=f"/dossiers/{dossier_id}", status_code=status.HTTP_303_SEE_OTHER)


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
