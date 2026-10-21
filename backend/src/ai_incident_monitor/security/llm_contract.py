"""Formal boundary contract governing future LLM analysis of untrusted content.

Governing Charter: Project Constitution (Rules 1, 3, 10, 11, 12, 13),
ADR-008, ADR-011, SEC-001, SEC-002.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from ai_incident_monitor.security.envelope import UntrustedSourceContentEnvelope


class LLMBoundaryViolationError(Exception):
    """Raised when external untrusted content attempts to violate the LLM boundary contract."""


class QuarantinedContentError(LLMBoundaryViolationError):
    """Raised when quarantined content is passed to an LLM without human review."""


class PrivilegedActionBlockedError(LLMBoundaryViolationError):
    """Raised when an automated process attempts a privileged or self-approving action."""


# Forbidden actions that models or untrusted content can NEVER execute
FORBIDDEN_AUTOMATED_ACTIONS: frozenset[str] = frozenset({
    "publish_incident",
    "finalize_high_severity",
    "modify_connector_policy",
    "modify_source_allowlist",
    "modify_system_prompt",
    "alter_audit_history",
    "delete_incident_dossier",
    "execute_shell_command",
    "arbitrary_network_request",
})


@dataclass(frozen=True)
class StaticPromptTemplate:
    """Immutable, source-controlled prompt template."""

    template_id: str
    version: str
    template_sha256: str
    static_instruction: str


def validate_envelope_for_model_ingestion(
    envelope: UntrustedSourceContentEnvelope,
    human_override_token: Optional[str] = None,
) -> None:
    """Validate that an untrusted envelope meets the LLM ingestion boundary contract.

    Enforces:
    1. Envelope must be a valid UntrustedSourceContentEnvelope instance.
    2. Quarantined envelopes strictly cannot be consumed by an LLM without
       an explicit human override token (Rule 12, Rule 13).
    3. Content must have a valid content_sha256 digest.
    """
    if not isinstance(envelope, UntrustedSourceContentEnvelope):
        raise LLMBoundaryViolationError("Model input must be an UntrustedSourceContentEnvelope instance")

    if envelope.quarantined and not human_override_token:
        raise QuarantinedContentError(
            f"Content for record '{envelope.source_record_id}' is QUARANTINED due to injection signals "
            f"({envelope.injection_signal_codes}). Human review is strictly required before LLM consumption."
        )

    if not envelope.content_sha256:
        raise LLMBoundaryViolationError("Envelope lacks valid cryptographic content_sha256")


def assert_privileged_action_forbidden(action_name: str) -> None:
    """Verify that a proposed action does not violate the non-delegable authority boundary."""
    if action_name.lower() in FORBIDDEN_AUTOMATED_ACTIONS:
        raise PrivilegedActionBlockedError(
            f"Action '{action_name}' is a privileged operation requiring explicit Human-in-the-Loop "
            f"sign-off (Constitutional Rules 12 and 13). Automated execution is strictly forbidden."
        )
