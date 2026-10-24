"""Review state machine and human-in-the-loop governance for editorial dossiers.

Enforces Constitutional Rules 12, 14, and 15:
- Rule 12 & 14: Automated algorithms, agents, and LLMs cannot self-approve.
- Rule 15: Single human editorial sign-off covers the assembled dossier version.
- Content Immutability: Approved dossiers cannot be edited in place. Any change creates a new version.
- Rejection History: Rejection records reasons and preserves history.
"""

from __future__ import annotations

from typing import Optional

from ai_incident_monitor.domain.common import (
    ConstitutionalViolationError,
    ImmutabilityViolationError,
)
from ai_incident_monitor.editorial.enums import (
    EditorialDossierStatus,
    EditorialReviewAction,
)
from ai_incident_monitor.editorial.models import (
    EditorialDossierSchema,
    EditorialReviewerAttestationSchema,
    EditorialValidationReport,
)


class EditorialReviewStateMachine:
    """Controls lifecycle state transitions and attestation enforcement for editorial dossiers."""

    VALID_TRANSITIONS: dict[EditorialDossierStatus, set[EditorialDossierStatus]] = {
        EditorialDossierStatus.DRAFT: {
            EditorialDossierStatus.ASSEMBLED,
        },
        EditorialDossierStatus.ASSEMBLED: {
            EditorialDossierStatus.PENDING_REVIEW,
            EditorialDossierStatus.DRAFT,
        },
        EditorialDossierStatus.PENDING_REVIEW: {
            EditorialDossierStatus.APPROVED_INFORMATIONAL,
            EditorialDossierStatus.REJECTED,
            EditorialDossierStatus.ASSEMBLED,
        },
        EditorialDossierStatus.APPROVED_INFORMATIONAL: {
            EditorialDossierStatus.SUPERSEDED,
        },
        EditorialDossierStatus.REJECTED: {
            EditorialDossierStatus.DRAFT,
            EditorialDossierStatus.PENDING_REVIEW,
        },
        EditorialDossierStatus.SUPERSEDED: set(),  # Terminal historical state
    }

    @classmethod
    def can_transition(
        cls, current_status: EditorialDossierStatus, target_status: EditorialDossierStatus
    ) -> bool:
        """Check if a status transition is permitted by the state machine."""
        return target_status in cls.VALID_TRANSITIONS.get(current_status, set())

    @classmethod
    def validate_submission_for_review(
        cls,
        dossier: EditorialDossierSchema,
        validation_report: Optional[EditorialValidationReport] = None,
    ) -> None:
        """Validate that a dossier is ready for human review queue."""
        if dossier.status not in {
            EditorialDossierStatus.ASSEMBLED,
            EditorialDossierStatus.REJECTED,
        }:
            raise ValueError(
                f"Cannot submit dossier in status '{dossier.status.value}' for review. "
                f"Must be ASSEMBLED or REJECTED."
            )

        if len(dossier.entries) == 0:
            raise ValueError("Cannot submit empty dossier with zero entries for review.")

    @classmethod
    def validate_approval(
        cls,
        dossier: EditorialDossierSchema,
        attestation: EditorialReviewerAttestationSchema,
        validation_report: EditorialValidationReport,
        source_drift_detected: bool = False,
    ) -> None:
        """Validate that an editorial dossier satisfies all criteria for human approval.

        Fails closed if any gate fails:
        1. Current status must be PENDING_REVIEW.
        2. Reviewer must be authenticated human (is_human=True, Rule 14).
        3. Attestation must be confirmed and match dossier content hash.
        4. Validation report must have zero blocking findings.
        5. Underlying source content must not have drifted since assembly.
        """
        # 1. Status check
        if dossier.status != EditorialDossierStatus.PENDING_REVIEW:
            raise ValueError(
                f"Cannot approve dossier in status '{dossier.status.value}'. "
                f"Dossier must be submitted and in PENDING_REVIEW status."
            )

        # 2. Human reviewer check (Rule 14)
        if not attestation.is_human:
            raise ConstitutionalViolationError(
                "Review approval strictly requires an authenticated human reviewer (Rule 14). "
                "Automated self-approval is forbidden."
            )

        if not attestation.reviewer_id or not attestation.reviewer_id.strip():
            raise ValueError("Reviewer ID cannot be empty.")

        # 3. Attestation confirmation and content hash binding
        if not attestation.statement_confirmed:
            raise ValueError(
                "Reviewer attestation statement was not confirmed. Explicit confirmation required."
            )

        current_content_hash = dossier.compute_content_hash()
        if attestation.content_hash != current_content_hash:
            raise ValueError(
                f"Attestation content hash '{attestation.content_hash}' does not match "
                f"canonical dossier content hash '{current_content_hash}'. "
                f"Dossier content may have been modified."
            )

        if dossier.content_hash and dossier.content_hash != current_content_hash:
            raise ValueError(
                f"Dossier content hash mismatch: recorded='{dossier.content_hash}', "
                f"current='{current_content_hash}'."
            )

        # 4. Validation report clearance
        if not validation_report.is_valid or validation_report.blocking_count > 0:
            blocking_reasons = [
                f"{f.field_path}: {f.message}"
                for f in validation_report.findings
                if f.severity.value == "BLOCKING"
            ]
            raise ValueError(
                f"Cannot approve dossier with {validation_report.blocking_count} blocking validation "
                f"finding(s): {'; '.join(blocking_reasons)}"
            )

        # 5. Source drift check
        if source_drift_detected:
            raise ValueError(
                "Underlying source records have drifted since dossier assembly. "
                "Re-assembly and re-validation required before approval."
            )

    @classmethod
    def validate_rejection(
        cls,
        dossier: EditorialDossierSchema,
        reviewer_id: str,
        is_human: bool,
        rejection_reason: str,
    ) -> None:
        """Validate rejection preconditions."""
        if dossier.status != EditorialDossierStatus.PENDING_REVIEW:
            raise ValueError(
                f"Cannot reject dossier in status '{dossier.status.value}'. "
                f"Dossier must be in PENDING_REVIEW status."
            )

        if not is_human:
            raise ConstitutionalViolationError(
                "Rejection decision must be made by a human reviewer (Rule 14)."
            )

        if not reviewer_id or not reviewer_id.strip():
            raise ValueError("Reviewer ID cannot be empty.")

        if not rejection_reason or not rejection_reason.strip():
            raise ValueError("Rejection requires a non-empty rationale/reason.")

    @classmethod
    def check_mutation_allowed(cls, dossier_status: EditorialDossierStatus) -> None:
        """Enforce immutability of approved editorial dossiers."""
        if dossier_status in {
            EditorialDossierStatus.APPROVED_INFORMATIONAL,
            EditorialDossierStatus.SUPERSEDED,
        }:
            raise ImmutabilityViolationError(
                f"Cannot mutate editorial dossier in status '{dossier_status.value}'. "
                f"Approved content is strictly immutable. Create a new revision/superseding dossier."
            )
