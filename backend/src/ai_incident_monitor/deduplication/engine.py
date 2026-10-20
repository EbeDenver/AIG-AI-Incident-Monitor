"""4-tier deterministic deduplication waterfall engine enforcing DEC-P3-003."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_incident_monitor.db.models.claim import ClaimRecordModel
from ai_incident_monitor.db.models.evidence import ClaimEvidenceLinkModel, EvidenceRecordModel
from ai_incident_monitor.db.models.incident import IncidentModel
from ai_incident_monitor.db.models.source import SourceReferenceModel
from ai_incident_monitor.deduplication.normalizer import (
    calculate_title_similarity,
    normalize_title,
    normalize_url,
)

SIMILARITY_THRESHOLD: float = 0.90  # Tier 3 near-duplicate title similarity threshold
DATE_TOLERANCE_DAYS: int = 2  # Tier 3 temporal matching tolerance (+/- 2 days)


@dataclass
class DedupDecision:
    """Outcome of deduplication evaluation for a candidate incident record."""

    tier: int  # 1, 2, 3, or 4
    outcome: str  # "AUTO_LINK_ID", "AUTO_LINK_URL", "FLAG_FOR_REVIEW", "DISTINCT"
    matched_incident_id: Optional[str] = None
    candidate_incident_id: Optional[str] = None
    similarity_score: float = 0.0
    fields_compared: list[str] = field(default_factory=list)
    normalized_values: dict[str, Any] = field(default_factory=dict)
    date_window_result: Optional[str] = None
    decision_status: str = "PENDING"
    rationale: str = ""
    algorithm_version: str = "dedup-waterfall-v1.0"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class DeduplicationEngine:
    """Evaluates proposed incident records against existing database records.

    Enforces Constitutional Rule 14 & DEC-P3-003:
    - Tier 1: Exact external source ID -> Auto-link to existing incident.
    - Tier 2: Exact canonical URL -> Auto-link to existing incident.
    - Tier 3: Near-duplicate match (title similarity >= 0.90 and date within +/- 2 days)
              -> Queued for human gatekeeper review (POTENTIAL_DUPLICATE). Zero automated merges.
    - Tier 4: Distinct incident -> Allowed to create new dossier.
    """

    @classmethod
    def evaluate(
        cls,
        session: Session,
        proposed_incident_id: str,
        proposed_title: str,
        proposed_date: Optional[date],
        source_urls: list[str],
    ) -> DedupDecision:
        """Run the 4-tier waterfall evaluation against the active database session."""

        # -------------------------------------------------------------
        # Tier 1: Exact Source ID Match
        # -------------------------------------------------------------
        existing_by_id = session.get(IncidentModel, proposed_incident_id)
        if existing_by_id is not None:
            return DedupDecision(
                tier=1,
                outcome="AUTO_LINK_ID",
                matched_incident_id=existing_by_id.id,
                candidate_incident_id=proposed_incident_id,
                similarity_score=1.0,
                fields_compared=["incident_id"],
                normalized_values={
                    "proposed_id": proposed_incident_id,
                    "matched_id": existing_by_id.id,
                },
                date_window_result="NOT_APPLICABLE",
                decision_status="AUTO_LINKED",
                rationale=f"Exact incident identifier match: '{proposed_incident_id}'.",
            )

        # -------------------------------------------------------------
        # Tier 2: Exact Canonical URL Match
        # -------------------------------------------------------------
        for raw_url in source_urls:
            canonical = normalize_url(raw_url)
            if not canonical:
                continue

            # Check if canonical_url matches an existing source reference
            stmt = select(SourceReferenceModel).where(
                (SourceReferenceModel.canonical_url == canonical)
                | (SourceReferenceModel.url == canonical)
            )
            matched_source = session.execute(stmt).scalar_one_or_none()
            if matched_source is not None:
                # Find associated incident through evidence -> claims -> incident
                incident_id = cls._find_incident_for_source(session, matched_source.id)
                if incident_id:
                    return DedupDecision(
                        tier=2,
                        outcome="AUTO_LINK_URL",
                        matched_incident_id=incident_id,
                        candidate_incident_id=proposed_incident_id,
                        similarity_score=1.0,
                        fields_compared=["canonical_url"],
                        normalized_values={
                            "matched_canonical_url": canonical,
                            "raw_url": raw_url,
                        },
                        date_window_result="NOT_APPLICABLE",
                        decision_status="AUTO_LINKED",
                        rationale=f"Exact canonical source URL match: '{canonical}'.",
                    )

        # -------------------------------------------------------------
        # Tier 3: Near-Duplicate Similarity Matching (Human Review Queue)
        # -------------------------------------------------------------
        all_incidents = session.execute(select(IncidentModel)).scalars().all()
        for existing in all_incidents:
            sim = calculate_title_similarity(proposed_title, existing.title)
            if sim >= SIMILARITY_THRESHOLD:
                # Check date compatibility
                date_match = cls._dates_compatible(proposed_date, existing.incident_exact_date)
                date_window_str = (
                    "WITHIN_TOLERANCE"
                    if (proposed_date and existing.incident_exact_date and date_match)
                    else (
                        "UNKNOWN_TOLERATED"
                        if (proposed_date is None or existing.incident_exact_date is None)
                        else "OUTSIDE_TOLERANCE"
                    )
                )
                if date_match:
                    return DedupDecision(
                        tier=3,
                        outcome="FLAG_FOR_REVIEW",
                        matched_incident_id=existing.id,
                        candidate_incident_id=proposed_incident_id,
                        similarity_score=sim,
                        fields_compared=["title", "incident_date"],
                        normalized_values={
                            "proposed_title": normalize_title(proposed_title),
                            "existing_title": normalize_title(existing.title),
                            "proposed_date": str(proposed_date) if proposed_date else "UNKNOWN",
                            "existing_date": (
                                str(existing.incident_exact_date)
                                if existing.incident_exact_date
                                else "UNKNOWN"
                            ),
                        },
                        date_window_result=date_window_str,
                        decision_status="FLAGGED_FOR_REVIEW",
                        rationale=(
                            f"Title similarity {sim:.2f} >= {SIMILARITY_THRESHOLD} and dates "
                            f"compatible with existing incident '{existing.id}' ('{existing.title}')."
                        ),
                    )

        # -------------------------------------------------------------
        # Tier 4: Distinct Incident
        # -------------------------------------------------------------
        return DedupDecision(
            tier=4,
            outcome="DISTINCT",
            matched_incident_id=None,
            candidate_incident_id=proposed_incident_id,
            similarity_score=0.0,
            fields_compared=["incident_id", "canonical_url", "title", "incident_date"],
            normalized_values={
                "proposed_id": proposed_incident_id,
                "proposed_title": normalize_title(proposed_title),
            },
            date_window_result="NO_MATCH",
            decision_status="DISTINCT",
            rationale="No existing identifier, canonical URL, or near-duplicate title match found.",
        )

    @classmethod
    def _find_incident_for_source(cls, session: Session, source_id: str) -> Optional[str]:
        """Traverse source -> evidence -> claim -> incident to find associated incident ID."""
        stmt = (
            select(ClaimRecordModel.incident_id)
            .join(ClaimEvidenceLinkModel, ClaimEvidenceLinkModel.claim_id == ClaimRecordModel.id)
            .join(EvidenceRecordModel, EvidenceRecordModel.id == ClaimEvidenceLinkModel.evidence_id)
            .where(EvidenceRecordModel.source_id == source_id)
            .limit(1)
        )
        return session.execute(stmt).scalar_one_or_none()

    @classmethod
    def _dates_compatible(cls, date_a: Optional[date], date_b: Optional[date]) -> bool:
        """Evaluate if two incident dates fall within +/- 2 days, or if one/both are unknown."""
        if date_a is None or date_b is None:
            # Unknown is not assumed to contradict; allow review queue
            return True
        return abs((date_a - date_b).days) <= DATE_TOLERANCE_DAYS
