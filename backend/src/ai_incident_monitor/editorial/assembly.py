"""Deterministic assembly engine for editorial dossiers.

Enforces:
- Rule 1 & Rule 3: Zero fabrication, dispassionate tone, and factual grounding.
- Deterministic Assembly: Identical inputs produce identical canonical content and SHA-256 digests.
- Zero LLM Inference: Structured templates and pure programmatic transformation.
- Epistemic Tri-State: Distinct handling of facts, allegations, unknowns, and disputes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
import uuid

from ai_incident_monitor.editorial.enums import (
    EditorialDossierStatus,
    EditorialEntryType,
    EditorialScopeType,
)
from ai_incident_monitor.editorial.models import (
    EDITORIAL_DISCLAIMER_TEXT,
    EDITORIAL_DISCLAIMER_VERSION,
    EditorialCandidate,
    EditorialDossierEntrySchema,
    EditorialDossierSchema,
    EditorialDossierSummary,
    EditorialEntryDispute,
    EditorialEntryFact,
    EditorialEntryUnknown,
)

DEFAULT_METHODOLOGY_NOTES: str = (
    "This editorial dossier was compiled using the AI Incident Monitor deterministic assembly engine. "
    "All reported incidents are grounded in recorded primary evidence and observational public reporting. "
    "Allegations, disputed facts, and open questions are maintained without editorial distortion. "
    "Statutory and regulatory references represent technical research context rather than formal legal advice."
)


class EditorialDossierAssembler:
    """Assembles structured, deterministic editorial dossiers from validated candidate incidents."""

    def assemble(
        self,
        candidates: list[EditorialCandidate],
        title: str,
        scope_type: EditorialScopeType = EditorialScopeType.CUSTOM,
        coverage_period_start: Optional[datetime] = None,
        coverage_period_end: Optional[datetime] = None,
        methodology_notes: Optional[str] = None,
        executive_summary: Optional[str] = None,
        dossier_id: Optional[str] = None,
    ) -> EditorialDossierSchema:
        """Deterministically assemble an editorial dossier from candidate incidents."""
        # Validate that candidates are eligible
        eligible_candidates = [c for c in candidates if c.is_eligible]
        if not eligible_candidates:
            raise ValueError(
                "Cannot assemble dossier: zero eligible candidate incidents provided (Rule 1)."
            )

        # Deterministic ordering: primary entries first, sorted by severity score descending, then incident ID ascending
        def sort_key(c: EditorialCandidate) -> tuple[float, str]:
            score = c.severity_score if c.severity_score is not None else -1.0
            return (-score, c.incident_id)

        sorted_candidates = sorted(eligible_candidates, key=sort_key)

        entries: list[EditorialDossierEntrySchema] = []
        total_evidence_links = 0
        disputed_incident_count = 0
        all_themes: set[str] = set()

        for idx, cand in enumerate(sorted_candidates, start=1):
            entry_id = f"entry_{cand.incident_id}_{idx}"
            total_evidence_links += len(cand.evidence_ids)

            if len(cand.disputed_claims) > 0:
                disputed_incident_count += 1

            # Convert facts
            entry_facts = [
                EditorialEntryFact(
                    statement=f["statement"],
                    source_id=f["source_id"],
                    source_title=f.get("source_title"),
                    evidence_id=f["evidence_id"],
                    is_allegation=f.get("is_allegation", False),
                    attribution=f["attribution"],
                )
                for f in cand.known_facts
            ]

            # Convert unknowns
            entry_unknowns = [
                EditorialEntryUnknown(
                    question=u["question"],
                    domain=u.get("domain"),
                    impact=u.get("impact"),
                )
                for u in cand.unknowns
            ]

            # Convert disputed claims
            entry_disputes = [
                EditorialEntryDispute(
                    topic=d["topic"],
                    position_a=d["position_a"],
                    source_a=d["source_a"],
                    position_b=d["position_b"],
                    source_b=d["source_b"],
                )
                for d in cand.disputed_claims
            ]

            # Deduce entry themes
            if cand.severity_tier:
                all_themes.add(f"Severity Tier: {cand.severity_tier}")
            if cand.eu_screen_status == "APPROVED_INFORMATIONAL":
                all_themes.add("EU AI Act Regulatory Screening")

            entry = EditorialDossierEntrySchema(
                entry_id=entry_id,
                incident_id=cand.incident_id,
                entry_order=idx,
                entry_type=EditorialEntryType.PRIMARY,
                incident_title=cand.title,
                incident_summary=cand.summary,
                incident_date_str=cand.incident_date_str,
                source_evidence_ids=cand.evidence_ids,
                source_version_hash=cand.source_version_hash,
                primary_source_url=cand.primary_source_url,
                primary_source_publisher=cand.primary_source_publisher,
                primary_source_published_date=cand.primary_source_date,
                known_facts=entry_facts,
                unknowns=entry_unknowns,
                disputed_claims=entry_disputes,
                severity_tier=cand.severity_tier,
                severity_score=cand.severity_score,
                eu_screen_id=cand.eu_screen_id,
                eu_screen_status=cand.eu_screen_status,
                eu_commentary=cand.eu_commentary,
                omitted_eu_reason=(
                    cand.omitted_eu_reason
                    if not cand.eu_commentary
                    else None
                ),
            )
            entries.append(entry)

        # Build summary
        default_exec_summary = (
            f"Forensic monitoring dossier covering {len(entries)} incident(s) with "
            f"{total_evidence_links} verified evidence linkages. "
            f"Disputed assertions identified in {disputed_incident_count} incident(s)."
        )

        learning_themes: list[str] = [
            "Continuous verification of empirical source records",
            "Epistemic separation of allegations from established facts",
        ]
        if disputed_incident_count > 0:
            learning_themes.append("Explicit preservation of conflicting accounts and unresolved claims")

        summary = EditorialDossierSummary(
            executive_summary=executive_summary or default_exec_summary,
            key_themes=sorted(all_themes),
            total_incidents=len(entries),
            total_evidence_links=total_evidence_links,
            disputed_incident_count=disputed_incident_count,
            learning_and_prevention_themes=sorted(learning_themes),
        )

        resolved_dossier_id = dossier_id or f"dossier_{uuid.uuid4().hex[:12]}"
        notes = methodology_notes or DEFAULT_METHODOLOGY_NOTES

        # Construct unhashed schema
        dossier = EditorialDossierSchema(
            id=resolved_dossier_id,
            version=1,
            title=title,
            scope_type=scope_type,
            coverage_period_start=coverage_period_start,
            coverage_period_end=coverage_period_end,
            status=EditorialDossierStatus.ASSEMBLED,
            disclaimer_version=EDITORIAL_DISCLAIMER_VERSION,
            disclaimer_text=EDITORIAL_DISCLAIMER_TEXT,
            methodology_notes=notes,
            summary=summary,
            entries=entries,
            metadata_json={
                "assembled_at": datetime.now(timezone.utc).isoformat(),
                "entry_count": len(entries),
            },
            generated_by="EditorialDossierAssembler/1.0",
        )

        # Compute canonical content hash
        content_hash = dossier.compute_content_hash()

        # Return schema with locked content_hash
        return dossier.model_copy(update={"content_hash": content_hash})
