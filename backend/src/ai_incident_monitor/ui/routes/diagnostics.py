"""Operational diagnostics and automated ingestion status routes.

Governing Charter: Project Constitution (Rules 1, 10, 11, 14, 16),
PRD §2 (UIX-001, UIX-003, AUD-001, AUD-002), Phase 8A/8C/8D Plan.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Optional
import uuid

from fastapi import APIRouter, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from ai_incident_monitor.diagnostics.runner import LocalDiagnosticsRunner
from ai_incident_monitor.ingestion.checkpoints import CheckpointStore
from ai_incident_monitor.ingestion.cycle import load_latest_summary
from ai_incident_monitor.ingestion.lock import IngestionLock, is_process_alive
from ai_incident_monitor.ingestion.scheduler import DEFAULT_JOB_LABEL
from ai_incident_monitor.ingestion.sources import load_source_configs
from ai_incident_monitor.ui.auth import SESSION_COOKIE_NAME, SessionRecord, ServerSessionManager

router = APIRouter(tags=["diagnostics"])


def _get_authenticated_session(request: Request) -> Optional[SessionRecord]:
    """Retrieve verified active session from cookie."""
    sess_mgr: ServerSessionManager = request.app.state.session_manager
    cookie_token = request.cookies.get(SESSION_COOKIE_NAME)
    return sess_mgr.get_session(cookie_token)


def _verify_csrf(request: Request, candidate_csrf: Optional[str]) -> bool:
    """Validate candidate CSRF token against session token."""
    session = _get_authenticated_session(request)
    if not session:
        return False
    sess_mgr: ServerSessionManager = request.app.state.session_manager
    return sess_mgr.validate_csrf(session, candidate_csrf)


@router.get("/diagnostics", response_class=HTMLResponse)
async def diagnostics_page(request: Request) -> Response:
    """Execute safe read-only operational diagnostics and render health status cards."""
    session = _get_authenticated_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    engine = request.app.state.db_engine
    repo_root = getattr(request.app.state, "repo_root", Path("."))
    templates = request.app.state.templates

    # Run system diagnostics
    runner = LocalDiagnosticsRunner(engine=engine, repo_root=repo_root)
    report = runner.run_all_checks()

    # Ingestion operations status
    sources = load_source_configs(repo_root / "config" / "sources.json")
    checkpoint_store = CheckpointStore(repo_root / ".data" / "ingestion_checkpoints.json")
    checkpoints = checkpoint_store.load_all()
    latest_summary = load_latest_summary(repo_root)

    # Concurrency and active lock check
    lock = IngestionLock(trigger="status_check", run_id="", lock_file_path=repo_root / ".data" / "ingestion.lock")
    active_info = lock.read_active_info()
    is_active = active_info is not None and is_process_alive(active_info.pid)

    # launchd scheduler status check
    user_plist = Path.home() / "Library" / "LaunchAgents" / f"{DEFAULT_JOB_LABEL}.plist"
    scheduler_installed = user_plist.exists()
    scheduler_status = "INSTALLED" if scheduler_installed else "NOT_INSTALLED"

    return templates.TemplateResponse(
        request=request,
        name="diagnostics.html",
        context={
            "session": session,
            "report": report,
            "csrf_token": session.csrf_token,
            "sources": sources,
            "checkpoints": checkpoints,
            "latest_summary": latest_summary,
            "active_run": active_info if is_active else None,
            "scheduler_status": scheduler_status,
            "configured_frequency": "60 minutes (3600 seconds)",
        },
    )


@router.post("/diagnostics/refresh")
async def trigger_refresh(
    request: Request,
    csrf_token: Optional[str] = Form(default=None),
) -> Response:
    """Trigger an immediate background collection cycle via authenticated admin action."""
    session = _get_authenticated_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    if not _verify_csrf(request, csrf_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")

    repo_root = getattr(request.app.state, "repo_root", Path("."))
    lock = IngestionLock(trigger="portal", run_id="", lock_file_path=repo_root / ".data" / "ingestion.lock")
    active_info = lock.read_active_info()

    if active_info and is_process_alive(active_info.pid):
        # Already running: redirect back with conflict notice
        return RedirectResponse(
            url=f"/diagnostics?refresh=conflict&run_id={active_info.run_id}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    run_id = f"run_{uuid.uuid4().hex[:12]}"

    # Execute in detached background subprocess
    # Uses sys.executable to ensure the exact same virtualenv Python interpreter
    python_bin = sys.executable
    cmd = [
        python_bin,
        "-m",
        "ai_incident_monitor.ingestion.cycle",
        "--trigger",
        "portal",
        "--run-id",
        run_id,
    ]

    subprocess.Popen(
        cmd,
        cwd=str(repo_root),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    return RedirectResponse(
        url=f"/diagnostics?refresh=started&run_id={run_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/api/ingestion/status", response_class=JSONResponse)
async def api_ingestion_status(request: Request) -> JSONResponse:
    """JSON status API for operational ingestion monitoring."""
    session = _get_authenticated_session(request)
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    repo_root = getattr(request.app.state, "repo_root", Path("."))
    checkpoint_store = CheckpointStore(repo_root / ".data" / "ingestion_checkpoints.json")
    checkpoints = checkpoint_store.load_all()
    latest_summary = load_latest_summary(repo_root)

    lock = IngestionLock(trigger="api_check", run_id="", lock_file_path=repo_root / ".data" / "ingestion.lock")
    active_info = lock.read_active_info()
    is_active = active_info is not None and is_process_alive(active_info.pid)

    sources = load_source_configs(repo_root / "config" / "sources.json")

    return JSONResponse({
        "active_run": asdict(active_info) if (active_info and is_active) else None,
        "latest_summary": latest_summary,
        "checkpoints": {k: v.model_dump() for k, v in checkpoints.items()},
        "sources": [s.model_dump() for s in sources],
    })


@router.post("/api/ingestion/refresh", response_class=JSONResponse)
async def api_ingestion_refresh(
    request: Request,
    csrf_token: Optional[str] = Form(default=None),
) -> JSONResponse:
    """JSON endpoint for initiating ingestion cycle with CSRF protection."""
    session = _get_authenticated_session(request)
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    if not _verify_csrf(request, csrf_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")

    repo_root = getattr(request.app.state, "repo_root", Path("."))
    lock = IngestionLock(trigger="portal", run_id="", lock_file_path=repo_root / ".data" / "ingestion.lock")
    active_info = lock.read_active_info()

    if active_info and is_process_alive(active_info.pid):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "status": "conflict",
                "message": f"Ingestion cycle '{active_info.run_id}' already in progress.",
                "active_run": asdict(active_info),
            },
        )

    run_id = f"run_{uuid.uuid4().hex[:12]}"
    cmd = [
        sys.executable,
        "-m",
        "ai_incident_monitor.ingestion.cycle",
        "--trigger",
        "portal",
        "--run-id",
        run_id,
    ]
    subprocess.Popen(
        cmd,
        cwd=str(repo_root),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    return JSONResponse({
        "status": "started",
        "run_id": run_id,
        "trigger": "portal",
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
    })
