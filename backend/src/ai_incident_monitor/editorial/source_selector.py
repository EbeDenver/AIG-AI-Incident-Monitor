"""Editorial source selector evaluating candidate incidents for dossier assembly.

Enforces:
- Rule 1 & Rule 4: Mandatory evidence grounding and provenance verification.
- Authoritative Workflow: Ordinary attributed reporting enters draft dossiers WITHOUT human approval.
- Optional EU Commentary: Unapproved or ineligible EU screens are cleanly omitted without blocking
  ordinary incident reporting.
- Epistemic Integrity: Conflicting reports and disputed facts are preserved, not silently flattened.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ai_incident_monitor.db.models.claim import ClaimRecordModel
from ai_incident_monitor.db.models.evidence import EvidenceRecordModel
from ai_incident_monitor.db.models.governance import EULegalRelevanceScreenModel
from ai_incident_monitor.db.models.incident import IncidentModel
from ai_incident_monitor.db.models.severity import SeverityAssessmentModel
from ai_incident_monitor.db.models.uncertainty import UncertaintyRecordModel
from ai_incident_monitor.editorial.models import EditorialCandidate


class EditorialSourceSelector:
    """Evaluates candidate incidents and sources for deterministic dossier assembly."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def evaluate_candidate_incident(
        self,
        incident: IncidentModel,
        include_eu_commentary_if_eligible: bool = True,
    ) -> EditorialCandidate:
        """Evaluate a single incident for inclusion in an editorial dossier.

        Determines eligibility based strictly on concrete data integrity (evidence presence,
        clean payloads, non-empty text). Does NOT require human approval for ordinary reporting.
        """
        exclusion_reasons: list[str] = []

        # 1. Basic text integrity checks
        if not incident.title or not incident.title.strip():
            exclusion_reasons.append("Incident title is empty or missing.")
        if not incident.summary or not incident.summary.strip():
            exclusion_reasons.append("Incident summary is empty or missing.")

        # 2. Collect evidence IDs across claims and uncertainties
        evidence_ids_set: set[str] = set()
        primary_source_url: Optional[str] = None
        primary_source_publisher: Optional[str] = None
        primary_source_date: Optional[str] = None

        known_facts: list[dict[str, Any]] = []
        disputed_claims: list[dict[str, Any]] = []
        unknowns: list[dict[str, Any]] = []

        # Process claims
        for claim in incident.claims:
            is_allegation = claim.epistemic_status.upper() in {
                "UNVERIFIED",
                "DISPUTED",
                "ALLEGATION",
                "INVESTIGATIVE_REPORT",
                "REPORTED_ALLEGATION",
            }
            attribution_text = (
                f"Reported assertion ({claim.epistemic_status})"
                if is_allegation
                else "Documented factual assertion"
            )

            for link in claim.evidence_links:
                ev_id = link.evidence_id
                evidence_ids_set.add(ev_id)
                known_facts.append(
                    {
                        "statement": claim.claim_text,
                        "source_id": ev_id,
                        "source_title": claim.claim_type,
                        "evidence_id": ev_id,
                        "is_allegation": is_allegation,
                        "attribution": attribution_text,
                    }
                )

        # Process uncertainties and disputed facts
        for unc in incident.uncertainties:
            for unk_fact in unc.unknown_facts:
                unknowns.append(
                    {
                        "question": unk_fact,
                        "domain": unc.reason_unresolved,
                        "impact": "Unresolved empirical factor",
                    }
                )
            for disp in unc.disputed_facts:
                disputed_claims.append(
                    {
                        "topic": disp.assertion,
                        "position_a": f"Contested by {disp.contesting_party}",
                        "source_a": (
                            disp.supporting_evidence_ids[0]
                            if disp.supporting_evidence_ids
                            else "Source A"
                        ),
                        "position_b": "Alternative account / disputed status",
                        "source_b": (
                            disp.contradicting_evidence_ids[0]
                            if disp.contradicting_evidence_ids
                            else "Source B"
                        ),
                    }
                )
                evidence_ids_set.update(disp.supporting_evidence_ids)
                evidence_ids_set.update(disp.contradicting_evidence_ids)

        evidence_ids = sorted(evidence_ids_set)

        # Fail closed on missing evidence (Constitutional Rule 1)
        if len(evidence_ids) == 0:
            exclusion_reasons.append(
                "Incident lacks primary or observational evidence records (Rule 1 violation)."
            )

        # Retrieve primary source metadata if available
        if evidence_ids:
            first_ev = (
                self.session.execute(
                    select(EvidenceRecordModel).where(EvidenceRecordModel.id == evidence_ids[0])
                )
                .scalars()
                .first()
            )
            if first_ev and first_ev.source:
                primary_source_url = first_ev.source.url
                primary_source_publisher = first_ev.source.publisher
                if first_ev.source.publication_exact_date:
                    primary_source_date = first_ev.source.publication_exact_date.isoformat()
                elif first_ev.source.publication_date_year:
                    primary_source_date = str(first_ev.source.publication_date_year)

        # Compute deterministic source version hash
        source_digest_payload = {
            "incident_id": incident.id,
            "title": incident.title,
            "summary": incident.summary,
            "evidence_ids": evidence_ids,
            "claim_count": len(incident.claims),
        }
        source_version_hash = hashlib.sha256(
            json.dumps(source_digest_payload, sort_keys=True).encode("utf-8")
        ).hexdigest()

        # 3. Process optional severity assessment
        severity_tier: Optional[str] = None
        severity_score: Optional[float] = None
        latest_sev = (
            self.session.execute(
                select(SeverityAssessmentModel)
                .where(SeverityAssessmentModel.incident_id == incident.id)
                .order_by(SeverityAssessmentModel.created_at.desc())
            )
            .scalars()
            .first()
        )
        if latest_sev:
            severity_tier = latest_sev.actual_tier
            severity_score = latest_sev.actual_normalized_score

        # 4. Process optional EU screen (with strict unapproved barrier)
        eu_screen_id: Optional[str] = None
        eu_screen_status: Optional[str] = None
        eu_screen_eligible: bool = False
        eu_commentary: Optional[str] = None
        omitted_eu_reason: Optional[str] = None

        latest_eu = (
            self.session.execute(
                select(EULegalRelevanceScreenModel)
                .where(EULegalRelevanceScreenModel.incident_id == incident.id)
                .order_by(EULegalRelevanceScreenModel.created_at.desc())
            )
            .scalars()
            .first()
        )

        if latest_eu:
            eu_screen_id = latest_eu.id
            eu_screen_status = latest_eu.status
            if latest_eu.status == "APPROVED_INFORMATIONAL":
                eu_screen_eligible = True
                if include_eu_commentary_if_eligible:
                    eu_commentary = (
                        f"EU AI Act Informational Relevance: Level={latest_eu.relevance_level}, "
                        f"Nexus={latest_eu.nexus_assessment}. Disclaimer: {latest_eu.disclaimer_version}."
                    )
            else:
                eu_screen_eligible = False
                omitted_eu_reason = (
                    f"EU screen exists with status '{latest_eu.status}' (not APPROVED_INFORMATIONAL); "
                    "omitted to prevent unapproved governance commentary leakage."
                )
        else:
            omitted_eu_reason = (
                "No EU screen associated with incident; ordinary incident reporting retained."
            )

        is_eligible = len(exclusion_reasons) == 0

        # Construct candidate date representation
        incident_date_str: Optional[str] = None
        if incident.incident_exact_date:
            incident_date_str = incident.incident_exact_date.isoformat()
        elif incident.incident_start_date:
            incident_date_str = incident.incident_start_date.isoformat()
        elif incident.incident_date_year:
            incident_date_str = str(incident.incident_date_year)

        return EditorialCandidate(
            incident_id=incident.id,
            title=incident.title,
            summary=incident.summary,
            incident_date_str=incident_date_str,
            evidence_ids=evidence_ids,
            primary_source_url=primary_source_url,
            primary_source_publisher=primary_source_publisher,
            primary_source_date=primary_source_date,
            source_version_hash=source_version_hash,
            severity_tier=severity_tier,
            severity_score=severity_score,
            known_facts=known_facts,
            unknowns=unknowns,
            disputed_claims=disputed_claims,
            eu_screen_id=eu_screen_id,
            eu_screen_status=eu_screen_status,
            eu_screen_eligible=eu_screen_eligible,
            eu_commentary=eu_commentary,
            omitted_eu_reason=omitted_eu_reason,
            is_eligible=is_eligible,
            exclusion_reasons=exclusion_reasons,
        )

    def select_candidates(
        self,
        incident_ids: Optional[list[str]] = None,
        limit: int = 50,
        only_eligible: bool = True,
        include_eu_commentary: bool = True,
    ) -> list[EditorialCandidate]:
        """Query and evaluate candidate incidents from the database."""
        stmt = (
            select(IncidentModel)
            .options(
                selectinload(IncidentModel.claims).selectinload(ClaimRecordModel.evidence_links),
                selectinload(IncidentModel.uncertainties).selectinload(
                    UncertaintyRecordModel.disputed_facts
                ),
            )
            .order_by(IncidentModel.created_at.desc())
        )

        if incident_ids:
            stmt = stmt.where(IncidentModel.id.in_(incident_ids))
        stmt = stmt.limit(limit)

        incidents = list(self.session.execute(stmt).scalars().all())
        candidates: list[EditorialCandidate] = []

        for inc in incidents:
            candidate = self.evaluate_candidate_incident(
                inc, include_eu_commentary_if_eligible=include_eu_commentary
            )
            if only_eligible and not candidate.is_eligible:
                continue
            candidates.append(candidate)

        return candidates
