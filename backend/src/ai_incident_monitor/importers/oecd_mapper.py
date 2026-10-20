"""OECD AIM export column mapper with missing-column tolerance and epistemic separation."""

from __future__ import annotations

from datetime import date, datetime, timezone
import re
from typing import Any, Optional
import uuid

from ai_incident_monitor.db.models.claim import ClaimRecordModel
from ai_incident_monitor.db.models.incident import IncidentModel
from ai_incident_monitor.db.models.source import SourceReferenceModel
from ai_incident_monitor.domain.identifiers import new_claim_id, new_incident_id, new_source_id
from ai_incident_monitor.domain.vocabularies import (
    AccessStatus,
    ClaimMateriality,
    ClaimType,
    ConfidenceLevel,
    EpistemicStatus,
    ReviewStatus,
    SourceAuthority,
    SourceIndependence,
    SourceType,
)

# Common column name aliases used in OECD AIM and international incident exports
COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "id": ("incident id", "id", "oecd id", "incident number", "incident_id"),
    "title": ("incident title", "title", "name", "headline"),
    "summary": ("description", "summary", "incident description", "details", "narrative"),
    "date": ("incident date", "date", "event date", "date of incident", "occurred_on"),
    "url": ("source url", "url", "link", "source", "article url", "news url"),
    "harm_type": ("harm type", "impact", "harm category", "damage type", "harm"),
    "ai_system": ("ai system implicated", "system", "ai system", "technology", "model"),
    "entity": ("deployer", "developer", "organization", "entity", "company"),
}


def _find_field_value(row: dict[str, Any], field_key: str) -> Optional[str]:
    """Search a row dictionary for field keys matching known column aliases."""
    raw_aliases = list(COLUMN_ALIASES.get(field_key, (field_key,)))
    if field_key not in raw_aliases:
        raw_aliases.append(field_key)

    expanded: set[str] = set()
    for a in raw_aliases:
        expanded.add(a.lower())
        expanded.add(a.lower().replace("_", " "))
        expanded.add(a.lower().replace(" ", "_"))

    norm_row = {str(k).strip().lower(): v for k, v in row.items()}
    for k, v in norm_row.items():
        if k in expanded or k.replace("_", " ") in expanded:
            if v is not None and str(v).strip():
                return str(v).strip()
    return None


def _parse_date_string(date_str: Optional[str]) -> tuple[str, Optional[date], Optional[int], Optional[int]]:
    """Parse date strings into (precision, exact_date, year, month).

    Missing, empty, or unparseable dates default to ('UNKNOWN', None, None, None)
    per Constitutional Rule 2 (Unknown is not coerced to zero or arbitrary dates).
    """
    if not date_str:
        return ("UNKNOWN", None, None, None)

    clean = date_str.strip()

    # Try ISO YYYY-MM-DD
    match_iso = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", clean)
    if match_iso:
        y, m, d = int(match_iso.group(1)), int(match_iso.group(2)), int(match_iso.group(3))
        try:
            return ("EXACT", date(y, m, d), y, m)
        except ValueError:
            pass

    # Try YYYY-MM
    match_ym = re.match(r"^(\d{4})-(\d{1,2})$", clean)
    if match_ym:
        y, m = int(match_ym.group(1)), int(match_ym.group(2))
        if 1 <= m <= 12:
            return ("MONTH", None, y, m)

    # Try YYYY
    match_y = re.match(r"^(\d{4})$", clean)
    if match_y:
        y = int(match_y.group(1))
        return ("YEAR", None, y, None)

    # Unparseable date format remains UNKNOWN (no guessing)
    return ("UNKNOWN", None, None, None)


class OECDIncidentMapper:
    """Transforms raw OECD export row dictionaries into internal relational models."""

    @classmethod
    def map_row(
        cls,
        row: dict[str, Any],
        batch_id: str,
        demonstration_notice: Optional[str] = None,
    ) -> tuple[IncidentModel, list[ClaimRecordModel], list[SourceReferenceModel]]:
        """Map a single sanitized row to an IncidentModel, ClaimRecordModel, and SourceReferenceModel.

        Constitutional Invariants Enforced:
        - Missing columns are tolerated and mapped to UNKNOWN/None (Gate 3).
        - OECD assertions are classified as UNVERIFIED_ALLEGATION (Gate 4, Rule 3).
        - Source URLs are extracted and linked with appropriate authority tagging.
        """
        raw_id = _find_field_value(row, "id")
        incident_id = f"INC-OECD-{raw_id}" if raw_id else new_incident_id()

        raw_title = _find_field_value(row, "title")
        title = raw_title if raw_title else (f"OECD Incident {raw_id}" if raw_id else "Untitled AI Incident")

        summary = _find_field_value(row, "summary") or "No detailed summary provided in OECD export."

        date_precision, exact_date, year, month = _parse_date_string(_find_field_value(row, "date"))

        # 1. Create IncidentModel
        incident = IncidentModel(
            id=incident_id,
            title=title,
            summary=summary,
            status="UNDER_INVESTIGATION",
            incident_date_precision=date_precision,
            incident_exact_date=exact_date,
            incident_date_year=year,
            incident_date_month=month,
            demonstration_notice=demonstration_notice,
            schema_version="1.0.0",
        )

        # 2. Create unverified ClaimRecordModel from OECD summary
        claim_id = new_claim_id()
        primary_claim = ClaimRecordModel(
            id=claim_id,
            incident_id=incident_id,
            claim_text=summary,
            claim_type=ClaimType.FACTUAL_EVENT.value,
            epistemic_status=EpistemicStatus.UNVERIFIED_ALLEGATION.value,  # Constitutional Rule 3 / Gate 4
            confidence=ConfidenceLevel.LOW.value,
            materiality=ClaimMateriality.CORE_IMPACT.value,
            review_status=ReviewStatus.DRAFT_UNREVIEWED.value,
            demonstration_notice=demonstration_notice,
            schema_version="1.0.0",
        )

        # 3. Create SourceReferenceModel if URL is present
        sources: list[SourceReferenceModel] = []
        raw_url = _find_field_value(row, "url")
        if raw_url and (raw_url.startswith("http://") or raw_url.startswith("https://")):
            source_id = new_source_id()
            source = SourceReferenceModel(
                id=source_id,
                title=title,
                publisher=_find_field_value(row, "entity") or "OECD AI Incident Monitor Export",
                url=raw_url,
                canonical_url=raw_url.split("?")[0],  # Strip query params for canonical
                source_type=SourceType.MAINSTREAM_NEWS.value,
                publication_date_precision=date_precision,
                publication_exact_date=exact_date,
                publication_date_year=year,
                publication_date_month=month,
                retrieval_date=datetime.now(timezone.utc),
                access_status=AccessStatus.OPEN_PUBLIC.value,
                authority=SourceAuthority.INDEPENDENT_RESEARCHER.value,
                reliability=ConfidenceLevel.MEDIUM.value,
                independence=SourceIndependence.INDEPENDENT_ORIGINAL.value,
                demonstration_notice=demonstration_notice,
                schema_version="1.0.0",
            )
            sources.append(source)

        return incident, [primary_claim], sources
