"""Independent application validation and quality review engine for incident dossiers.

Governing Specification: Ai-incident-manager-guide.pdf (§1–§3),
Project Constitution (Rules 1, 2, 3, 4, 11, 14, 16),
amended by Section B (No-Approval Amendment: advisory quality warnings only,
no workflow gates, no reviewer keys, no attestations).
"""

from __future__ import annotations

import logging
from typing import Sequence

from ai_incident_monitor.intelligence.schemas import (
    AssessmentStatus,
    CausalStatus,
    ClaimClassification,
    ConfidenceTier,
    IncidentEnrichmentDossier,
    MaterialityLevel,
    ProvenanceItem,
    QualityReview,
    VerificationStatus,
)

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when an incident dossier violates structural integrity."""


class EnrichmentValidator:
    """Independent application validator for Stage 3 of the intelligence workflow.

    Enforces:
    1. Citation Integrity Gate: Verifies all cited evidence IDs exist in provenance package.
    2. Epistemic Consistency Gate: Enforces separation of allegation and verified fact.
    3. Causal Discipline Gate: Verifies causal claims are substantiated by empirical evidence.
    4. Independent Quality Calculation: Computes quality review metrics independently rather
       than accepting model self-certification.
    5. No-Approval Amendment: Generates advisory warnings, never publication blocks.
    """

    def validate_and_certify(
        self,
        dossier: IncidentEnrichmentDossier,
        *,
        evidence_package: Sequence[ProvenanceItem] | None = None,
    ) -> IncidentEnrichmentDossier:
        """Validate, sanitize, and independently compute quality review for a dossier."""
        # 1. Catalog valid evidence IDs
        provenance_sources = evidence_package or dossier.provenance
        valid_evidence_ids = {p.evidence_id for p in provenance_sources}

        # Merge any provenance items from the dossier into the valid pool
        for p in dossier.provenance:
            valid_evidence_ids.add(p.evidence_id)

        review_reasons: list[str] = []
        unresolved_evidence_gaps: list[str] = []
        unsupported_claims = 0

        # 2. Epistemic Consistency & Citation Integrity on Claims
        for claim in dossier.claims:
            # Check citations
            invalid_citations = [
                eid for eid in claim.supporting_evidence_ids if eid not in valid_evidence_ids
            ]
            if invalid_citations:
                unsupported_claims += 1
                msg = f"Claim '{claim.claim_id}' cites non-existent evidence IDs: {invalid_citations}"
                unresolved_evidence_gaps.append(msg)
                logger.warning(msg)
                # Filter out fabricated IDs
                claim.supporting_evidence_ids = [
                    eid for eid in claim.supporting_evidence_ids if eid in valid_evidence_ids
                ]

            if not claim.supporting_evidence_ids:
                unsupported_claims += 1
                unresolved_evidence_gaps.append(
                    f"Claim '{claim.claim_id}' lacks supporting evidence citations."
                )

            # Epistemic Gate: Rule 2 & 3 - Never allow UNVERIFIED claims to be marked CONFIRMED_FACT
            if (
                claim.classification == ClaimClassification.CONFIRMED_FACT
                and claim.verification_status != VerificationStatus.VERIFIED
            ):
                logger.warning(
                    f"Epistemic violation in claim '{claim.claim_id}': CONFIRMED_FACT with status "
                    f"'{claim.verification_status.value}'. Reclassifying to ATTRIBUTED_ALLEGATION."
                )
                claim.classification = ClaimClassification.ATTRIBUTED_ALLEGATION
                claim.advisory_review_flag = True
                review_reasons.append(
                    f"Claim '{claim.claim_id}' reclassified from CONFIRMED_FACT to ATTRIBUTED_ALLEGATION "
                    f"due to unverified status."
                )

            # Flag unverified allegations or low-confidence claims for advisory review
            if (
                claim.classification == ClaimClassification.ATTRIBUTED_ALLEGATION
                and claim.verification_status == VerificationStatus.UNVERIFIED
            ):
                claim.advisory_review_flag = True

            if claim.advisory_review_flag:
                reason = f"Advisory flag on claim '{claim.claim_id}': {claim.statement[:80]}..."
                if reason not in review_reasons:
                    review_reasons.append(reason)

        # 3. Citation Check on AI Involvement
        invalid_ai_cites = [
            eid for eid in dossier.ai_involvement.supporting_evidence_ids if eid not in valid_evidence_ids
        ]
        if invalid_ai_cites:
            unresolved_evidence_gaps.append(
                f"AI involvement cites non-existent evidence IDs: {invalid_ai_cites}"
            )
            dossier.ai_involvement.supporting_evidence_ids = [
                eid for eid in dossier.ai_involvement.supporting_evidence_ids if eid in valid_evidence_ids
            ]

        # 4. Causal Assessment Discipline
        invalid_causal_cites = [
            eid for eid in dossier.causal_assessment.evidence_ids if eid not in valid_evidence_ids
        ]
        if invalid_causal_cites:
            unresolved_evidence_gaps.append(
                f"Causal assessment cites non-existent evidence IDs: {invalid_causal_cites}"
            )
            dossier.causal_assessment.evidence_ids = [
                eid for eid in dossier.causal_assessment.evidence_ids if eid in valid_evidence_ids
            ]

        # If causal status is CONFIRMED_CAUSE but no evidence is cited or verification is lacking
        if (
            dossier.causal_assessment.causal_status == CausalStatus.CONFIRMED_CAUSE
            and not dossier.causal_assessment.evidence_ids
        ):
            logger.warning(
                "Causal discipline violation: CONFIRMED_CAUSE without verified evidence. "
                "Adjusting to POSSIBLE_CONTRIBUTOR."
            )
            dossier.causal_assessment.causal_status = CausalStatus.POSSIBLE_CONTRIBUTOR
            review_reasons.append(
                "Causal connection adjusted to POSSIBLE_CONTRIBUTOR due to lack of direct postmortem evidence."
            )

        # 5. High-materiality uncertainties
        for unc in dossier.uncertainties:
            if unc.materiality == MaterialityLevel.HIGH:
                reason = f"Material uncertainty: {unc.question[:80]} (Evidence needed: {unc.evidence_needed[:60]})"
                review_reasons.append(reason)

        # 6. Disputed facts
        for disp in dossier.disputed_facts:
            reason = f"Disputed fact on claim '{disp.claim_id}': {disp.assertion[:80]}"
            review_reasons.append(reason)

        # 7. Citation Check on Controls
        for ctrl in dossier.organizational_controls:
            ctrl.evidence_ids = [eid for eid in ctrl.evidence_ids if eid in valid_evidence_ids]

        # 8. Compute Independent Quality Review Metrics
        advisory_review_flag = bool(review_reasons or unsupported_claims > 0)

        # Determine AssessmentStatus
        if advisory_review_flag:
            assessment_status = AssessmentStatus.ADVISORY_REVIEW
        elif len(provenance_sources) <= 1 and (
            not dossier.claims or all(c.confidence == ConfidenceTier.LOW for c in dossier.claims)
        ):
            assessment_status = AssessmentStatus.PARTIAL
        else:
            assessment_status = AssessmentStatus.COMPLETE

        dossier.assessment_status = assessment_status
        dossier.quality_review = QualityReview(
            unsupported_claim_count=unsupported_claims,
            unresolved_evidence_gaps=unresolved_evidence_gaps,
            advisory_human_review_flag=advisory_review_flag,
            review_reasons=review_reasons,
        )

        return dossier
