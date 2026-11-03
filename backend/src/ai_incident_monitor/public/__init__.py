"""Public API package exposing read-only endpoints and schemas for external consumers (e.g., Codex AI Guardians Portal)."""

from ai_incident_monitor.public.routes import router as public_router

__all__ = ["public_router"]
