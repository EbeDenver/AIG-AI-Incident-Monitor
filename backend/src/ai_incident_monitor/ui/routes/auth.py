"""Authentication routes: login, credential verification, and logout handling.

Governing Charter: Project Constitution (Rules 1, 10, 14, 15, 16),
PRD §2 (UIX-001, UIX-003, AUD-001, AUD-002), Phase 8A Plan.
"""

from __future__ import annotations

import hmac
import os
import secrets
from typing import Optional

from fastapi import APIRouter, Form, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse

from ai_incident_monitor.ui.auth import (
    SESSION_COOKIE_NAME,
    LocalCredentialManager,
    LoginRateLimiter,
    ServerSessionManager,
)

router = APIRouter(tags=["authentication"])

LOGIN_CSRF_COOKIE_NAME = "aig_login_csrf"


def is_cookie_secure() -> bool:
    """Return whether session cookies should enforce the Secure flag (default False for loopback HTTP)."""
    return os.environ.get("AIG_SESSION_COOKIE_SECURE", "false").lower() in ("true", "1", "yes")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> Response:
    """Render the local operator login page with CSRF protection."""
    sess_mgr: ServerSessionManager = request.app.state.session_manager
    existing_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if sess_mgr.get_session(existing_cookie):
        return RedirectResponse(url="/incidents", status_code=status.HTTP_303_SEE_OTHER)

    # Issue or retrieve anonymous login CSRF token
    csrf_token = request.cookies.get(LOGIN_CSRF_COOKIE_NAME) or secrets.token_urlsafe(32)

    templates = request.app.state.templates
    response = templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "csrf_token": csrf_token,
            "error": None,
            "blocked": False,
            "cooldown": 0,
        },
    )
    # Ensure login CSRF cookie is set
    response.set_cookie(
        key=LOGIN_CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=True,
        samesite="strict",
        secure=is_cookie_secure(),
        path="/login",
        max_age=3600,
    )
    return response


@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    credential: str = Form(...),
    csrf_token: str = Form(...),
) -> Response:
    """Validate submitted bootstrap credential, enforce rate-limiting, and initialize session."""
    cred_mgr: LocalCredentialManager = request.app.state.credential_manager
    sess_mgr: ServerSessionManager = request.app.state.session_manager
    rate_limiter: LoginRateLimiter = request.app.state.rate_limiter
    templates = request.app.state.templates

    client_ip = request.client.host if request.client else "127.0.0.1"

    # 1. Validate CSRF token against login cookie in constant time
    expected_csrf = request.cookies.get(LOGIN_CSRF_COOKIE_NAME)
    if not expected_csrf or not hmac.compare_digest(csrf_token.strip(), expected_csrf.strip()):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "csrf_token": secrets.token_urlsafe(32),
                "error": "Invalid or expired security token. Please refresh and try again.",
                "blocked": False,
                "cooldown": 0,
            },
            status_code=status.HTTP_403_FORBIDDEN,
        )

    # 2. Check login rate limiter
    is_blocked, cooldown = rate_limiter.is_blocked(client_ip)
    if is_blocked:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "csrf_token": expected_csrf,
                "error": f"Too many failed login attempts. Client blocked for {int(cooldown)} seconds.",
                "blocked": True,
                "cooldown": int(cooldown),
            },
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    # 3. Verify credential in constant time
    if not cred_mgr.verify_credential(credential):
        rate_limiter.record_failure(client_ip)
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "csrf_token": expected_csrf,
                "error": "Invalid operator credential. Check '.data/.operator_credential' on your local filesystem.",
                "blocked": False,
                "cooldown": 0,
            },
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    # 4. Successful login: reset failed attempts & create fresh session
    rate_limiter.reset(client_ip)
    session = sess_mgr.create_session(
        actor_id="local_operator",
        role="LOCAL_EXPLORER",
        is_human=True,
    )

    response = RedirectResponse(url="/incidents", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session.session_id,
        httponly=True,
        samesite="strict",
        secure=is_cookie_secure(),
        path="/",
        max_age=86400,  # 24 hours absolute ceiling
    )
    # Clear login CSRF cookie
    response.delete_cookie(LOGIN_CSRF_COOKIE_NAME, path="/login")
    return response


@router.post("/logout")
async def logout(
    request: Request,
    csrf_token: str = Form(...),
) -> Response:
    """Invalidate session in server-side registry and clear session cookie."""
    sess_mgr: ServerSessionManager = request.app.state.session_manager
    cookie_val = request.cookies.get(SESSION_COOKIE_NAME)
    session = sess_mgr.get_session(cookie_val)

    if session and sess_mgr.validate_csrf(session, csrf_token):
        sess_mgr.invalidate_session(session.session_id)

    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return response
