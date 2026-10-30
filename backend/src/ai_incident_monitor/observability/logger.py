"""Standard library structured logging sink for operational telemetry events.

Governing Charter: Project Constitution (Rules 1, 10, 11, 14, 16),
PRD §5 (TST-001, AUD-004), Phase 7B Plan.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Callable, Optional

from ai_incident_monitor.observability.models import OperationalEventSchema

LOGGER_NAME = "ai_incident_monitor.observability"
_logger = logging.getLogger(LOGGER_NAME)

# In-memory event listeners for tests and run metrics aggregation
_EVENT_LISTENERS: list[Callable[[OperationalEventSchema], None]] = []


def add_event_listener(listener: Callable[[OperationalEventSchema], None]) -> None:
    """Register an in-memory listener to observe operational events (e.g. for metrics/tests)."""
    if listener not in _EVENT_LISTENERS:
        _EVENT_LISTENERS.append(listener)


def remove_event_listener(listener: Callable[[OperationalEventSchema], None]) -> None:
    """Remove a registered in-memory event listener."""
    if listener in _EVENT_LISTENERS:
        _EVENT_LISTENERS.remove(listener)


def clear_event_listeners() -> None:
    """Remove all registered in-memory event listeners."""
    _EVENT_LISTENERS.clear()


def get_observability_logger() -> logging.Logger:
    """Return the configured standard library logger for operational events."""
    return _logger


def log_operational_event(event: OperationalEventSchema) -> None:
    """Emit a structured operational event to the logger.

    Logging Sink Failure Policy:
    Failures in the operational logging sink (e.g. disk full, broken pipe, formatting bug)
    are strictly NON-FATAL. Operational telemetry MUST NOT abort or rollback core business
    transactions or create false business results.

    Mandatory audit logs (governance_audit_logs) operate under a separate, fail-closed
    persistence architecture and remain untouched by this policy.
    """
    # 1. Notify any registered in-memory listeners
    for listener in list(_EVENT_LISTENERS):
        try:
            listener(event)
        except Exception as exc:
            # Non-fatal: listener errors must not disrupt logging or operations
            print(f"[WARN] In-memory observability listener error: {exc}", file=sys.stderr)

    # 2. Emit JSON line to logger
    try:
        payload_json = event.model_dump_json()
        _logger.info(payload_json)
    except Exception as exc:
        # Non-fatal: output fallback warning without crashing business caller
        print(f"[WARN] Operational log emission failure: {exc}", file=sys.stderr)
