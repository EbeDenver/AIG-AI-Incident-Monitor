"""Maps normalized IngestedItems into database incident records with epistemic separation.

Governing Charter: Project Constitution (Rules 1, 2, 3, 4, 11, 14, 16),
ADR-008, AUD-004.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import email.utils
import hashlib
import json
import re
from typing import Optional, Tuple
import uuid

from sqlalchemy.orm import Session

from ai_incident_monitor.db.models.claim import ClaimRecordModel
from ai_incident_monitor.db.models.evidence import ClaimEvidenceLinkModel, EvidenceRecordModel
from ai_incident_monitor.db.models.incident import IncidentModel
from ai_incident_monitor.db.models.source import SourceReferenceModel
from ai_incident_monitor.deduplication.engine import DeduplicationEngine
from ai_incident_monitor.domain.identifiers import new_claim_id, new_evidence_id, new_source_id
from ai_incident_monitor.domain.taxonomy import classify_incident_category
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
from ai_incident_monitor.ingestion.models import IngestedItem
from ai_incident_monitor.ingestion.sources import SourceConfig, SourceRole
from ai_incident_monitor.repositories.claim_repo import ClaimRepository
from ai_incident_monitor.repositories.incident_repo import IncidentRepository
from ai_incident_monitor.repositories.source_repo import SourceRepository


def parse_date_string(date_str: Optional[str]) -> Tuple[str, Optional[date], Optional[int], Optional[int]]:
    """Parse date strings into (precision, exact_date, year, month).
    
    Adheres to Constitutional Rule 2: Unknown is not coerced to zero or arbitrary dates.
    """
    if not date_str:
        return ("UNKNOWN", None, None, None)

    clean = date_str.strip()

    # Try RFC 2822 (standard RSS pubDate)
    try:
        dt = email.utils.parsedate_to_datetime(clean)
        if dt is not None:
            return ("EXACT", dt.date(), dt.year, dt.month)
    except Exception:
        pass

    # Try ISO YYYY-MM-DD
    match_iso = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", clean)
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

    return ("UNKNOWN", None, None, None)


class IngestionIncidentMapper:
    """Transforms normalized IngestedItems into relational database entities."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.incident_repo = IncidentRepository(session)
        self.claim_repo = ClaimRepository(session)
        self.source_repo = SourceRepository(session)

    def process_item(
        self,
        item: IngestedItem,
        source_config: SourceConfig,
        manifest_id: Optional[str] = None,
    ) -> Tuple[Optional[str], str]:
        """Process an IngestedItem and persist entities if appropriate.
        
        Returns:
            Tuple of (incident_id, outcome_status)
            outcome_status: "CREATED", "AUTO_LINKED", "POTENTIAL_DUPLICATE", "RESEARCH_CONTEXT", "SKIPPED"
        """
        # 1. Epistemic Guard: Distinguish primary incident reports from research context
        if source_config.role == SourceRole.SUPPLEMENTARY_RESEARCH_CONTEXT or item.is_research_context:
            # Academic/research paper preprints are supplementary context, not primary incidents
            source_id = new_source_id()
            date_precision, exact_date, year, month = parse_date_string(item.published_date)
            source = SourceReferenceModel(
                id=source_id,
                title=item.title,
                publisher="arXiv AI Research (Context Feed)",
                url=item.canonical_url,
                canonical_url=item.canonical_url.split("?")[0],
                source_type=SourceType.ARXIV_PAPER.value,
                publication_date_precision=date_precision,
                publication_exact_date=exact_date,
                publication_date_year=year,
                publication_date_month=month,
                retrieval_date=datetime.now(timezone.utc),
                access_status=AccessStatus.OPEN_PUBLIC.value,
                authority=SourceAuthority.INDEPENDENT_RESEARCHER.value,
                reliability=ConfidenceLevel.HIGH.value,
                independence=SourceIndependence.INDEPENDENT_ORIGINAL.value,
                content_hash=item.content_sha256,
                is_copyright_restricted=True,
                fair_use_quotation_only=True,
                full_text_git_excluded=True,
                demonstration_notice="Supplementary research context signal (ADR-008, SEC-002)",
                schema_version="1.0.0",
            )
            self.source_repo.create(source)
            self.session.flush()
            return (None, "RESEARCH_CONTEXT")

        # 2. Evaluate deduplication for primary incident sources
        date_precision, exact_date, year, month = parse_date_string(item.published_date)
        decision = DeduplicationEngine.evaluate(
            session=self.session,
            proposed_incident_id=item.source_id,
            proposed_title=item.title,
            proposed_date=exact_date,
            source_urls=[item.canonical_url] if item.canonical_url else [],
        )

        if decision.outcome in ("AUTO_LINK_ID", "AUTO_LINK_URL"):
            # Existing incident already covers this event
            return (decision.matched_incident_id, "AUTO_LINKED")

        if decision.outcome == "FLAG_FOR_REVIEW":
            # Near duplicate flagged
            return (decision.matched_incident_id, "POTENTIAL_DUPLICATE")

        # Tier 4: Distinct new incident -> persist IncidentModel, ClaimRecordModel, SourceReferenceModel, EvidenceRecordModel
        # Generate formatted incident identifier
        year_str = str(year) if year else str(datetime.now(timezone.utc).year)
        inc_suffix = uuid.uuid4().hex[:6].upper()
        incident_id = f"INC-{year_str}-{inc_suffix}"

        # Classify category using source tags, level, and text heuristics
        raw_tags = item.raw_item_dict.get("tags", []) if isinstance(item.raw_item_dict, dict) else []
        raw_level = item.raw_item_dict.get("level") if isinstance(item.raw_item_dict, dict) else None
        cat_enum, matched_tags = classify_incident_category(
            item.title,
            item.summary_snippet,
            source_tags=raw_tags,
            level=raw_level,
        )

        incident = IncidentModel(
            id=incident_id,
            title=item.title[:255],
            summary=item.summary_snippet,
            status="NEW",
            primary_category=cat_enum.value,
            category_tags=json.dumps(matched_tags),
            incident_date_precision=date_precision,
            incident_exact_date=exact_date,
            incident_date_year=year,
            incident_date_month=month,
            schema_version="1.0.0",
        )
        self.incident_repo.create(incident)

        # Attributed source reference
        source_id = new_source_id()
        publisher_name = item.raw_item_dict.get("publisher") or item.connector_name
        source = SourceReferenceModel(
            id=source_id,
            title=item.title,
            publisher=str(publisher_name)[:255],
            url=item.canonical_url,
            canonical_url=item.canonical_url.split("?")[0],
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
            content_hash=item.content_sha256,
            is_copyright_restricted=True,
            fair_use_quotation_only=True,
            full_text_git_excluded=True,
            schema_version="1.0.0",
        )
        self.source_repo.create(source)

        # Evidence record linking to the source reference
        ev_id = new_evidence_id()
        evidence = EvidenceRecordModel(
            id=ev_id,
            source_id=source_id,
            short_summary=f"Feed excerpt: {item.title[:100]}",
            evidence_type="TECHNICAL_POSTMORTEM",
            directness="PRIMARY_DIRECT",
            specificity="HIGHLY_SPECIFIC",
            corroboration_status="UNVERIFIED",
            ingested_at=datetime.now(timezone.utc),
            payload_hash=item.content_sha256,
        )
        self.session.add(evidence)

        # Primary factual claim with epistemic classification
        claim_id = new_claim_id()
        claim = ClaimRecordModel(
            id=claim_id,
            incident_id=incident_id,
            claim_text=item.summary_snippet,
            claim_type=ClaimType.FACTUAL_EVENT.value,
            epistemic_status=EpistemicStatus.UNVERIFIED_ALLEGATION.value,
            confidence=ConfidenceLevel.LOW.value,
            materiality=ClaimMateriality.CORE_IMPACT.value,
            review_status=ReviewStatus.DRAFT_UNREVIEWED.value,
            schema_version="1.0.0",
        )
        self.claim_repo.create(claim)

        # Link claim to evidence
        link = ClaimEvidenceLinkModel(
            claim_id=claim_id,
            evidence_id=ev_id,
            link_type="SUPPORTING",
        )
        self.session.add(link)

        self.session.flush()
        return (incident_id, "CREATED")
