"""Controlled enumerations for local operational diagnostics.

Governing Charter: Project Constitution (Rules 1, 10, 11, 14, 16),
PRD §5 (TST-001, AUD-004), Phase 7B Plan.
"""

from __future__ import annotations

from enum import Enum


class CheckStatus(str, Enum):
    """Health status of an individual diagnostic check or overall report."""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"


class CheckCategory(str, Enum):
    """Category of operational environment check."""

    CONFIGURATION = "CONFIGURATION"
    DATABASE = "DATABASE"
    SCHEMA = "SCHEMA"
    REFERENCE_LIBRARY = "REFERENCE_LIBRARY"
    STORAGE_PATHS = "STORAGE_PATHS"
    PIPELINE_COMPONENTS = "PIPELINE_COMPONENTS"
