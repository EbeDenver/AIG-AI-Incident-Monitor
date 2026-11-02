"""UI route modules for authentication, incidents, diagnostics, and editorial dossiers."""

from ai_incident_monitor.ui.routes.auth import router as auth_router
from ai_incident_monitor.ui.routes.diagnostics import router as diagnostics_router
from ai_incident_monitor.ui.routes.dossiers import router as dossiers_router
from ai_incident_monitor.ui.routes.incidents import router as incidents_router
from ai_incident_monitor.ui.routes.packages import router as packages_router

__all__ = [
    "auth_router",
    "diagnostics_router",
    "dossiers_router",
    "incidents_router",
    "packages_router",
]
