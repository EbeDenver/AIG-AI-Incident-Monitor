"""Operational diagnostics route integrating LocalDiagnosticsRunner.

Governing Charter: Project Constitution (Rules 1, 10, 11, 14, 16),
PRD §2 (UIX-001, UIX-003, AUD-001, AUD-002), Phase 8A Plan.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse

from ai_incident_monitor.diagnostics.runner import LocalDiagnosticsRunner
from ai_incident_monitor.ui.auth import SESSION_COOKIE_NAME, ServerSessionManager

router = APIRouter(tags=["diagnostics"])


@router.get("/diagnostics", response_class=HTMLResponse)
async def diagnostics_page(request: Request) -> Response:
    """Execute safe read-only operational diagnostics and render health status cards."""
    sess_mgr: ServerSessionManager = request.app.state.session_manager
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    session = sess_mgr.get_session(session_cookie)
    if not session:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    engine = request.app.state.db_engine
    repo_root = request.app.state.repo_root
    templates = request.app.state.templates

    runner = LocalDiagnosticsRunner(engine=engine, repo_root=repo_root)
    report = runner.run_all_checks()

    return templates.TemplateResponse(
        request=request,
        name="diagnostics.html",
        context={
            "session": session,
            "report": report,
            "csrf_token": session.csrf_token,
        },
    )
