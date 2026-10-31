"""FastAPI application factory, security middleware, and template configuration for the local operator UI.

Governing Charter: Project Constitution (Rules 1, 10, 14, 15, 16),
PRD §2 (UIX-001, UIX-003, AUD-001, AUD-002), Phase 8A Plan.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional, Set

from fastapi import FastAPI, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import Engine
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from ai_incident_monitor.db.session import get_engine, get_repo_root
from ai_incident_monitor.ui.auth import (
    LocalCredentialManager,
    LoginRateLimiter,
    ServerSessionManager,
    SESSION_COOKIE_NAME,
)

logger = logging.getLogger("ai_incident_monitor.ui")

DEFAULT_ALLOWED_HOSTS: Set[str] = {
    "127.0.0.1:8000",
    "127.0.0.1",
    "localhost:8000",
    "localhost",
    "[::1]:8000",
    "[::1]",
    "testserver",  # Starlette TestClient standard Host header
}

MAX_REQUEST_BODY_BYTES = 1024 * 1024  # 1 MB


class LocalSecurityMiddleware(BaseHTTPMiddleware):
    """Enforces host allowlisting, request body limits, and strict browser security headers."""

    def __init__(self, app: Any, allowed_hosts: Optional[Set[str]] = None) -> None:
        super().__init__(app)
        self.allowed_hosts = allowed_hosts or DEFAULT_ALLOWED_HOSTS

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # 1. Validate Host header
        host_header = request.headers.get("host", "").lower().strip()
        if not host_header or host_header not in self.allowed_hosts:
            return PlainTextResponse(
                f"Forbidden: Host header '{host_header}' is not in the local allowlist.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # 2. Validate request body size limit
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > MAX_REQUEST_BODY_BYTES:
                    return PlainTextResponse(
                        "Payload Too Large: Maximum allowed request size is 1MB.",
                        status_code=getattr(status, "HTTP_413_CONTENT_TOO_LARGE", 413),
                    )
            except ValueError:
                return PlainTextResponse(
                    "Bad Request: Invalid Content-Length header.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

        # 3. Explicit Origin verification for state-changing HTTP methods
        if request.method in ("POST", "PUT", "DELETE", "PATCH"):
            origin = request.headers.get("origin")
            if origin:
                # Strip scheme (http://, https://)
                origin_host = origin.split("://")[-1].lower().strip()
                if origin_host not in self.allowed_hosts:
                    return PlainTextResponse(
                        f"Forbidden: Origin '{origin}' is not authorized for local state changes.",
                        status_code=status.HTTP_403_FORBIDDEN,
                    )

        # 4. Process request
        response = await call_next(request)

        # 5. Inject defensive security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; "
            "img-src 'self' data:; "
            "frame-ancestors 'none';"
        )
        return response


def create_app(
    db_engine: Optional[Engine] = None,
    repo_root: Optional[Path] = None,
    credential_manager: Optional[LocalCredentialManager] = None,
    session_manager: Optional[ServerSessionManager] = None,
    rate_limiter: Optional[LoginRateLimiter] = None,
    allowed_hosts: Optional[Set[str]] = None,
) -> FastAPI:
    """Create and configure the local operator FastAPI application."""
    root = repo_root or get_repo_root()
    engine = db_engine or get_engine()

    cred_mgr = credential_manager or LocalCredentialManager(
        storage_path=root / ".data" / ".operator_credential"
    )
    sess_mgr = session_manager or ServerSessionManager()
    limiter = rate_limiter or LoginRateLimiter()

    app = FastAPI(
        title="AI Incident Monitor — Local Operator Explorer",
        description="Local inspection interface for AI incidents, epistemic claims, and diagnostics.",
        version="0.2.0",
        docs_url=None,       # Disable Swagger UI in local operator tool
        redoc_url=None,      # Disable ReDoc
        openapi_url=None,    # Disable OpenAPI schema discovery
    )

    # Attach shared dependencies to app state
    app.state.db_engine = engine
    app.state.repo_root = root
    app.state.credential_manager = cred_mgr
    app.state.session_manager = sess_mgr
    app.state.rate_limiter = limiter

    # Security middleware
    app.add_middleware(LocalSecurityMiddleware, allowed_hosts=allowed_hosts)

    # Template and static paths
    pkg_dir = Path(__file__).parent
    template_dir = pkg_dir / "templates"
    static_dir = pkg_dir / "static"

    templates = Jinja2Templates(directory=str(template_dir))
    app.state.templates = templates

    # Static assets
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Import and register route modules
    from ai_incident_monitor.ui.routes.auth import router as auth_router
    from ai_incident_monitor.ui.routes.incidents import router as incidents_router
    from ai_incident_monitor.ui.routes.diagnostics import router as diagnostics_router

    app.include_router(auth_router)
    app.include_router(incidents_router)
    app.include_router(diagnostics_router)

    # Root landing redirect
    @app.get("/", response_class=HTMLResponse)
    async def index_redirect(request: Request) -> Response:
        cookie_val = request.cookies.get(SESSION_COOKIE_NAME)
        session = sess_mgr.get_session(cookie_val)
        if session:
            return RedirectResponse(url="/incidents", status_code=status.HTTP_303_SEE_OTHER)
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    # Custom clean exception handlers to prevent debug tracebacks containing sensitive data
    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc: Any) -> Response:
        return PlainTextResponse("404 Not Found: The requested resource does not exist.", status_code=404)

    @app.exception_handler(500)
    async def internal_error_handler(request: Request, exc: Any) -> Response:
        logger.error(f"Internal server error on {request.method} {request.url.path}: {exc}")
        return PlainTextResponse(
            "500 Internal Server Error: An unexpected error occurred. Consult local logs.",
            status_code=500,
        )

    return app
