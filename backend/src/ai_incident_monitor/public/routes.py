"""FastAPI router for the public read-only API.

Governing Principles:
1. Strict segregation of mock data: Records with model_provider == 'mock' are excluded
   or clearly flagged, ensuring external clients never mistake synthetic templates for live intelligence.
2. Read-only allowlist: Only pre-approved public DTOs are returned; internal relational IDs,
   database paths, reviewer keys, and audit digests are never leaked.
3. High-contrast WCAG-compliant styling tokens returned with category metadata.
4. HTTP caching headers (Cache-Control: public, max-age=300) and permissive CORS headers.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ai_incident_monitor.config import allow_mock_opt_in, is_production_environment
from ai_incident_monitor.db.models.claim import ClaimRecordModel
from ai_incident_monitor.db.models.compliance import EUAIActComplianceAssessmentModel
from ai_incident_monitor.db.models.enrichment import IncidentEnrichmentModel
from ai_incident_monitor.db.models.evidence import (
    ClaimEvidenceLinkModel,
    EvidenceRecordModel,
    QuoteSpanModel,
)
from ai_incident_monitor.db.models.governance import EULegalRelevanceScreenModel
from ai_incident_monitor.db.models.incident import IncidentModel
from ai_incident_monitor.db.models.severity import SeverityAssessmentModel
from ai_incident_monitor.db.models.source import SourceReferenceModel
from ai_incident_monitor.db.models.uncertainty import UncertaintyRecordModel
from ai_incident_monitor.domain.taxonomy import (
    CATEGORY_REGISTRY,
    IncidentCategory,
    get_category_metadata,
)
from ai_incident_monitor.public.schemas import (
    CatalogFreshnessDTO,
    PublicAIInvolvementDTO,
    PublicAtomicClaimDTO,
    PublicCategoryDTO,
    PublicCausalAssessmentDTO,
    PublicDecisionMakerGuidanceDTO,
    PublicEUAIActDTO,
    PublicEUAIActGapDTO,
    PublicIncidentDetailDTO,
    PublicIncidentListResponse,
    PublicIncidentSummaryDTO,
    PublicIntelligenceDTO,
    PublicOrganizationalControlDTO,
    PublicPractitionerGuidanceDTO,
    PublicSourceReferenceDTO,
)

router = APIRouter(prefix="/api/v1/public", tags=["public"])

ID_REGEX = re.compile(r"^[a-zA-Z0-9_\-]+$")
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With",
    "Access-Control-Max-Age": "86400",
}


def sanitize_public_url(url: Optional[str]) -> Optional[str]:
    """Allow safe http and https URLs only."""
    if not url:
        return None
    trimmed = url.strip()
    lower = trimmed.lower()
    if lower.startswith("http://") or lower.startswith("https://"):
        return trimmed
    return None


@router.options("/{rest_of_path:path}")
async def preflight_handler(rest_of_path: str) -> Response:
    """Handle CORS pre-flight requests for all public endpoints."""
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers=CORS_HEADERS)


@router.get("/categories", response_model=list[PublicCategoryDTO])
async def list_categories(response: Response) -> list[PublicCategoryDTO]:
    """Retrieve full incident category taxonomy with accessible WCAG AAA/AA color tokens."""
    for k, v in CORS_HEADERS.items():
        response.headers[k] = v
    response.headers["Cache-Control"] = "public, max-age=3600"

    results: list[PublicCategoryDTO] = []
    for cat in CATEGORY_REGISTRY.values():
        results.append(
            PublicCategoryDTO(
                category_key=cat.category.value,
                display_name=cat.display_name,
                short_label=cat.short_label,
                icon=cat.icon,
                text_symbol=cat.text_symbol,
                description=cat.description,
                border_hex=cat.border_hex,
                bg_hex=cat.bg_hex,
                text_hex=cat.text_hex,
            )
        )
    return results


@router.get("/incidents", response_model=PublicIncidentListResponse)
async def list_public_incidents(
    request: Request,
    response: Response,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    q: Optional[str] = Query(default=None, description="Catalog-wide search matching title, summary, or ID."),
    category: Optional[str] = Query(default=None, description="Filter by primary category key (e.g. CYBERSECURITY)."),
    severity: Optional[str] = Query(default=None, description="Filter by severity tier (CRITICAL, HIGH, MEDIUM, LOW)."),
    sort_by: str = Query(default="discovered_date", description="Sort field: 'discovered_date', 'event_date', or 'title'."),
    sort_order: str = Query(default="desc", description="Sort order: 'desc' or 'asc'."),
    has_enrichment: Optional[bool] = Query(default=None),
    include_mock: bool = Query(
        default=False,
        description="Whether to include synthetic mock intelligence. Default False guarantees mock segregation.",
    ),
) -> PublicIncidentListResponse:
    """Retrieve paginated incident summaries with accessible category styling and mock-isolated intelligence status."""
    for k, v in CORS_HEADERS.items():
        response.headers[k] = v
    response.headers["Cache-Control"] = "public, max-age=300"

    if include_mock and not allow_mock_opt_in():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Synthetic mock intelligence opt-in ('include_mock=true') is strictly forbidden in production.",
        )

    mock_allowed = allow_mock_opt_in() and include_mock

    engine = request.app.state.db_engine

    with Session(engine) as db_session:
        # Build canonical filter conditions applied before count, sort, and pagination
        filter_conditions = []

        if category and category.strip():
            filter_conditions.append(IncidentModel.primary_category == category.strip().upper())

        if q and q.strip():
            term = f"%{q.strip()}%"
            filter_conditions.append(
                IncidentModel.title.ilike(term) | IncidentModel.summary.ilike(term) | IncidentModel.id.ilike(term)
            )

        # Deterministic effective latest severity subquery
        latest_sev_sub = (
            select(SeverityAssessmentModel.actual_tier)
            .where(SeverityAssessmentModel.incident_id == IncidentModel.id)
            .order_by(SeverityAssessmentModel.created_at.desc(), SeverityAssessmentModel.id.desc())
            .limit(1)
            .scalar_subquery()
        )
        effective_severity = func.coalesce(latest_sev_sub, "NOT_ASSESSED")

        if severity and severity.strip():
            filter_conditions.append(func.upper(effective_severity) == severity.strip().upper())

        # Effective has_enrichment condition reflecting environment mock suppression
        enr_conditions = [
            IncidentEnrichmentModel.incident_id == IncidentModel.id,
            IncidentEnrichmentModel.status == "COMPLETED",
        ]
        if not mock_allowed:
            enr_conditions.append(IncidentEnrichmentModel.model_provider != "mock")

        has_enr_clause = select(1).where(*enr_conditions).exists()

        if has_enrichment is not None:
            if has_enrichment:
                filter_conditions.append(has_enr_clause)
            else:
                filter_conditions.append(~has_enr_clause)

        # 1. Total matching count across identical canonical filtered set
        count_stmt = select(func.count(IncidentModel.id))
        if filter_conditions:
            count_stmt = count_stmt.where(*filter_conditions)
        total_items = db_session.execute(count_stmt).scalar() or 0

        # Deterministic total pages calculation
        total_pages = math.ceil(total_items / page_size) if total_items > 0 else 0

        # 2. Sorting clause with stable incident ID tie-breaker
        norm_sort_by = (sort_by or "discovered_date").strip().lower()
        norm_sort_order = (sort_order or "desc").strip().lower()

        if norm_sort_by == "event_date":
            date_col = IncidentModel.incident_exact_date
            primary_order = date_col.asc() if norm_sort_order == "asc" else date_col.desc()
        elif norm_sort_by == "title":
            title_col = IncidentModel.title
            primary_order = title_col.asc() if norm_sort_order == "asc" else title_col.desc()
        else:  # discovered_date
            created_col = IncidentModel.created_at
            primary_order = created_col.asc() if norm_sort_order == "asc" else created_col.desc()

        tie_breaker = IncidentModel.id.asc()

        # 3. Paginated query on canonical filtered set
        offset = (page - 1) * page_size
        query = select(IncidentModel)
        if filter_conditions:
            query = query.where(*filter_conditions)
        query = query.order_by(primary_order, tie_breaker).offset(offset).limit(page_size)

        raw_incidents = db_session.execute(query).scalars().all()
        incident_ids = [inc.id for inc in raw_incidents]

        # Gather severity map for retrieved page
        severity_map: dict[str, str] = {}
        if incident_ids:
            sev_stmt = (
                select(SeverityAssessmentModel.incident_id, SeverityAssessmentModel.actual_tier)
                .where(SeverityAssessmentModel.incident_id.in_(incident_ids))
                .order_by(SeverityAssessmentModel.created_at.desc(), SeverityAssessmentModel.id.desc())
            )
            for row in db_session.execute(sev_stmt):
                if row[0] not in severity_map:
                    severity_map[row[0]] = row[1]

        # Gather enrichment map for retrieved page
        enrichment_map: dict[str, tuple[str, str]] = {}  # incident_id -> (status, model_provider)
        if incident_ids:
            enr_stmt = (
                select(
                    IncidentEnrichmentModel.incident_id,
                    IncidentEnrichmentModel.status,
                    IncidentEnrichmentModel.model_provider,
                )
                .where(IncidentEnrichmentModel.incident_id.in_(incident_ids))
                .order_by(IncidentEnrichmentModel.created_at.desc(), IncidentEnrichmentModel.id.desc())
            )
            for row in db_session.execute(enr_stmt):
                if row[0] not in enrichment_map:
                    enrichment_map[row[0]] = (row[1], row[2])

        # Gather source counts
        source_count_map: dict[str, int] = {}
        if incident_ids:
            cnt_stmt = (
                select(ClaimRecordModel.incident_id, func.count(ClaimRecordModel.id))
                .where(ClaimRecordModel.incident_id.in_(incident_ids))
                .group_by(ClaimRecordModel.incident_id)
            )
            for row in db_session.execute(cnt_stmt):
                source_count_map[row[0]] = row[1]

        items: list[PublicIncidentSummaryDTO] = []
        for inc in raw_incidents:
            cat_meta = get_category_metadata(inc.primary_category)
            sev = severity_map.get(inc.id, "NOT_ASSESSED")

            enr_info = enrichment_map.get(inc.id)
            has_intel = False
            intel_status = "NOT_ENRICHED"
            is_mock = False

            if enr_info:
                enr_status, model_provider = enr_info
                is_mock = model_provider == "mock"
                if is_mock and not mock_allowed:
                    has_intel = False
                    intel_status = "PENDING_ANALYSIS"
                    is_mock = False
                else:
                    has_intel = enr_status == "COMPLETED"
                    intel_status = "SYNTHETIC_MOCK" if is_mock else "LIVE_ENRICHED"

            event_date_str = None
            if inc.incident_exact_date:
                event_date_str = str(inc.incident_exact_date)
            elif inc.incident_date_year:
                event_date_str = f"{inc.incident_date_year}"

            discovered_date_str = inc.created_at.isoformat() if inc.created_at else None

            items.append(
                PublicIncidentSummaryDTO(
                    incident_id=inc.id,
                    title=inc.title,
                    summary=inc.summary,
                    event_date=event_date_str,
                    discovered_date=discovered_date_str,
                    primary_category=inc.primary_category,
                    category_display_name=cat_meta.display_name,
                    category_color=cat_meta.border_hex,
                    category_bg_color=cat_meta.bg_hex,
                    severity=sev,
                    status=inc.status,
                    has_intelligence=has_intel,
                    intelligence_status=intel_status,
                    is_synthetic_mock=is_mock,
                    sources_count=source_count_map.get(inc.id, 0),
                )
            )

        # Gather freshness metadata
        latest_created = db_session.execute(select(func.max(IncidentModel.created_at))).scalar()
        total_sources = db_session.execute(select(func.count(SourceReferenceModel.id))).scalar() or 0
        freshness = CatalogFreshnessDTO(
            latest_ingestion_time=latest_created.isoformat() if latest_created else None,
            total_sources_count=total_sources,
            catalog_version="2.0.0",
            database_environment="production" if is_production_environment() else "development",
        )

        return PublicIncidentListResponse(
            items=items,
            total=total_items,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            freshness=freshness,
        )


@router.get("/incidents/{incident_id}", response_model=PublicIncidentDetailDTO)
async def get_public_incident_detail(
    incident_id: str,
    request: Request,
    response: Response,
    include_mock: bool = Query(
        default=False,
        description="Whether to include synthetic mock intelligence. Default False guarantees mock segregation.",
    ),
) -> PublicIncidentDetailDTO:
    """Retrieve comprehensive incident detail including evidence, intelligence dossier, and regulatory status."""
    for k, v in CORS_HEADERS.items():
        response.headers[k] = v
    response.headers["Cache-Control"] = "public, max-age=300"

    if include_mock and not allow_mock_opt_in():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Synthetic mock intelligence opt-in ('include_mock=true') is strictly forbidden in production.",
        )

    if not ID_REGEX.match(incident_id) or len(incident_id) > 64:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invalid incident identifier format: '{incident_id}'",
        )

    engine = request.app.state.db_engine

    with Session(engine) as db_session:
        incident = db_session.execute(
            select(IncidentModel).where(IncidentModel.id == incident_id)
        ).scalar_one_or_none()

        if not incident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incident '{incident_id}' not found.",
            )

        cat_meta = get_category_metadata(incident.primary_category)

        # Severity
        latest_sev = db_session.execute(
            select(SeverityAssessmentModel)
            .where(SeverityAssessmentModel.incident_id == incident_id)
            .order_by(SeverityAssessmentModel.created_at.desc())
        ).scalars().first()
        severity = latest_sev.actual_tier if latest_sev else "NOT_ASSESSED"

        # Sources & Claims
        sources: list[PublicSourceReferenceDTO] = []
        claims = db_session.execute(
            select(ClaimRecordModel)
            .where(ClaimRecordModel.incident_id == incident_id)
            .order_by(ClaimRecordModel.created_at.asc())
        ).scalars().all()

        claim_ids = [c.id for c in claims]
        if claim_ids:
            links = db_session.execute(
                select(ClaimEvidenceLinkModel, EvidenceRecordModel, SourceReferenceModel)
                .join(EvidenceRecordModel, ClaimEvidenceLinkModel.evidence_id == EvidenceRecordModel.id)
                .join(SourceReferenceModel, EvidenceRecordModel.source_id == SourceReferenceModel.id)
                .where(ClaimEvidenceLinkModel.claim_id.in_(claim_ids))
            ).all()

            seen_sources: set[str] = set()
            for _link, ev, src in links:
                if src.id not in seen_sources:
                    seen_sources.add(src.id)
                    retrieval_str = src.retrieval_date.isoformat() if hasattr(src, "retrieval_date") and src.retrieval_date else None

                    # Check for quote spans associated with this evidence record
                    qs = db_session.execute(
                        select(QuoteSpanModel)
                        .where(QuoteSpanModel.evidence_id == ev.id)
                        .order_by(QuoteSpanModel.start_char_offset.asc())
                    ).scalars().first()
                    loc = f"char_offset:{qs.start_char_offset}-{qs.end_char_offset}" if qs else None

                    sources.append(
                        PublicSourceReferenceDTO(
                            source_id=src.id,
                            source_name=src.publisher,
                            url=sanitize_public_url(src.url),
                            epistemic_role=src.source_type,
                            published_at=str(src.publication_exact_date) if src.publication_exact_date else None,
                            retrieval_date=retrieval_str,
                            content_hash=getattr(src, "content_hash", None),
                            locator=loc,
                        )
                    )

        # Unknowns & Uncertainties
        uncertainties = db_session.execute(
            select(UncertaintyRecordModel)
            .where(UncertaintyRecordModel.incident_id == incident_id)
            .order_by(UncertaintyRecordModel.created_at.asc())
        ).scalars().all()
        unknowns = [u.uncertainty_statement for u in uncertainties if u.uncertainty_statement]

        # Intelligence Dossier
        intelligence: Optional[PublicIntelligenceDTO] = None
        has_intel = False
        intel_status = "NOT_ENRICHED"
        is_mock = False

        enrichment = db_session.execute(
            select(IncidentEnrichmentModel).where(IncidentEnrichmentModel.incident_id == incident_id)
        ).scalar_one_or_none()

        if enrichment:
            is_mock = enrichment.model_provider == "mock"

            if is_mock and not include_mock:
                has_intel = False
                intel_status = "PENDING_ANALYSIS"
                intelligence = None
            else:
                has_intel = enrichment.status == "COMPLETED"
                intel_status = "SYNTHETIC_MOCK" if is_mock else "LIVE_ENRICHED"

                ai_inv = None
                causal = None
                atomic_claims: list[PublicAtomicClaimDTO] = []
                controls: list[PublicOrganizationalControlDTO] = []
                dm_guidance = None
                pract_guidance = None

                # Parse detailed payload JSON if available
                if enrichment.payload_json:
                    try:
                        pdata = json.loads(enrichment.payload_json)
                        # AI involvement
                        ai_data = pdata.get("ai_involvement", {})
                        if ai_data:
                            ai_inv = PublicAIInvolvementDTO(
                                role=ai_data.get("role", "NOT_ESTABLISHED"),
                                autonomy=ai_data.get("autonomy_level") or ai_data.get("autonomy", "UNKNOWN"),
                                human_oversight=ai_data.get("human_oversight", "UNKNOWN"),
                                assessment=ai_data.get("assessment", "Assessment details unavailable."),
                            )

                        # Causal assessment
                        cdata = pdata.get("causal_assessment", {})
                        if cdata:
                            causal = PublicCausalAssessmentDTO(
                                causal_status=cdata.get("causal_status", "CAUSALITY_NOT_ESTABLISHED"),
                                confidence=cdata.get("confidence", "LOW"),
                                observed_outcomes=cdata.get("observed_outcomes", []),
                                reported_mechanisms=cdata.get("reported_mechanisms", []),
                                supported_causal_links=cdata.get("supported_causal_links", []),
                                alternative_explanations=cdata.get("alternative_explanations", []),
                            )

                        # Atomic claims (supports both 'claims' and legacy 'atomic_claims')
                        raw_claims = pdata.get("claims") or pdata.get("atomic_claims") or []
                        prov_items = pdata.get("provenance", [])
                        prov_map = {p.get("evidence_id"): p.get("excerpt") for p in prov_items if isinstance(p, dict)}

                        for cl in raw_claims:
                            sup_ids = cl.get("supporting_evidence_ids", [])
                            excerpts = [prov_map[eid] for eid in sup_ids if eid in prov_map and prov_map[eid]]
                            atomic_claims.append(
                                PublicAtomicClaimDTO(
                                    claim_id=cl.get("claim_id", "CLM-UNKNOWN"),
                                    assertion=cl.get("statement") or cl.get("assertion", ""),
                                    classification=cl.get("classification", "ATTRIBUTED_ALLEGATION"),
                                    verification_status=cl.get("verification_status", "UNVERIFIED"),
                                    confidence=cl.get("confidence", "LOW"),
                                    supporting_evidence_ids=sup_ids,
                                    evidence_excerpts=excerpts,
                                    reasoning_summary=cl.get("reasoning_summary"),
                                )
                            )

                        # Controls
                        for ctl in pdata.get("organizational_controls", []):
                            controls.append(
                                PublicOrganizationalControlDTO(
                                    risk=ctl.get("risk", ""),
                                    control=ctl.get("control", ""),
                                    control_type=ctl.get("control_type", "PREVENTIVE"),
                                    incident_specific=ctl.get("incident_specific", False),
                                )
                            )

                        # Decision Maker Guidance (Guide §3 & legacy compatible)
                        dmg = pdata.get("decision_maker_guidance", {})
                        if dmg:
                            dm_guidance = PublicDecisionMakerGuidanceDTO(
                                executive_summary=dmg.get("executive_summary", "") or (dmg.get("key_implications", [""])[0] if dmg.get("key_implications") else ""),
                                board_briefing=dmg.get("board_briefing", "") or (" ".join(dmg.get("decisions_to_consider", []))),
                                strategic_priorities=dmg.get("strategic_priorities", []) or dmg.get("decisions_to_consider", []),
                                budget_allocation_recommendations=dmg.get("budget_allocation_recommendations", []) or dmg.get("effectiveness_measures", []),
                                key_implications=dmg.get("key_implications", []),
                                decisions_to_consider=dmg.get("decisions_to_consider", []),
                                evidence_required=dmg.get("evidence_required", []),
                                effectiveness_measures=dmg.get("effectiveness_measures", []),
                            )

                        # Practitioner / Consultant Guidance (Guide §3 & legacy compatible)
                        prg = pdata.get("consultant_guidance") or pdata.get("practitioner_guidance") or {}
                        if prg:
                            pract_guidance = PublicPractitionerGuidanceDTO(
                                immediate_actions=prg.get("immediate_actions", []) or prg.get("assessment_activities", []),
                                short_term_hardening=prg.get("short_term_hardening", []) or prg.get("implementation_controls", []),
                                architectural_guidance=prg.get("architectural_guidance", []) or prg.get("architecture_considerations", []),
                                testing_requirements=prg.get("testing_requirements", []) or prg.get("acceptance_criteria", []),
                                discovery_questions=prg.get("discovery_questions", []),
                                assessment_activities=prg.get("assessment_activities", []),
                                architecture_considerations=prg.get("architecture_considerations", []),
                                implementation_controls=prg.get("implementation_controls", []),
                                acceptance_criteria=prg.get("acceptance_criteria", []),
                            )

                        # Quality Review
                        qr = pdata.get("quality_review", {})
                        assessment_status = pdata.get("assessment_status", enrichment.assessment_status or "COMPLETE")
                        advisory_review_flag = qr.get("advisory_human_review_flag", False)
                        review_reasons = qr.get("review_reasons", [])
                    except Exception:
                        pass

                inc_sum = pdata.get("incident_summary", {}) if pdata and isinstance(pdata.get("incident_summary"), dict) else {}
                intel_summary = (
                    inc_sum.get("reported_event")
                    or inc_sum.get("summary")
                    or enrichment.executive_summary
                    or incident.summary
                )

                intelligence = PublicIntelligenceDTO(
                    is_available=has_intel,
                    model_provider=enrichment.model_provider,
                    model_name=enrichment.model_name,
                    generated_at=enrichment.created_at.isoformat() if enrichment.created_at else None,
                    is_synthetic_mock=is_mock,
                    assessment_status=assessment_status if "assessment_status" in locals() else (enrichment.assessment_status or "COMPLETE"),
                    advisory_review_flag=advisory_review_flag if "advisory_review_flag" in locals() else False,
                    review_reasons=review_reasons if "review_reasons" in locals() else [],
                    summary=intel_summary,
                    ai_involvement=ai_inv,
                    causal_assessment=causal,
                    atomic_claims=atomic_claims,
                    organizational_controls=controls,
                    decision_maker_guidance=dm_guidance,
                    practitioner_guidance=pract_guidance,
                )

        # EU AI Act Compliance Assessment
        eu_compliance: Optional[PublicEUAIActDTO] = None

        # Check comprehensive assessment model first
        eu_assessment_model = db_session.execute(
            select(EUAIActComplianceAssessmentModel)
            .where(EUAIActComplianceAssessmentModel.incident_id == incident_id)
        ).scalar_one_or_none()

        if eu_assessment_model and eu_assessment_model.payload_json:
            try:
                eu_data = json.loads(eu_assessment_model.payload_json)
                gaps: list[PublicEUAIActGapDTO] = []
                for g in eu_data.get("compliance_gaps", []):
                    gaps.append(
                        PublicEUAIActGapDTO(
                            article=g.get("article", ""),
                            gap_status=g.get("gap_status", "POTENTIAL_GAP"),
                            finding=g.get("finding", ""),
                        )
                    )
                eu_compliance = PublicEUAIActDTO(
                    is_available=True,
                    jurisdiction_status=eu_data.get("territorial_scope", {}).get("jurisdiction", eu_assessment_model.jurisdiction_status),
                    classification=eu_data.get("system_classification", eu_assessment_model.system_classification),
                    annex_reference=eu_assessment_model.annex_reference,
                    article_73_serious_incident=eu_data.get("serious_incident"),
                    enforcement_status=eu_data.get("overall_enforcement_status", eu_assessment_model.enforcement_status),
                    enforcement_notes=eu_data.get("timeline_notes", ""),
                    assessment_date=eu_assessment_model.created_at.isoformat() if eu_assessment_model.created_at else None,
                    legal_framework_version="EU Regulation 2024/1689 (AI Act) - November 2026 Baseline",
                    governance_sources=eu_data.get("regulatory_references", [
                        "Regulation (EU) 2024/1689",
                        "Article 2 (Scope & Exclusions)",
                        "Article 5 (Prohibitions)",
                        "Article 6 (High-Risk Systems)",
                        "Article 50 (Transparency Duties)",
                        "Article 73 (Serious Incident Reporting)",
                    ]),
                    qualifications_and_limitations=eu_data.get("epistemic_limitations", [
                        "Automated statutory screening based on open incident filings.",
                        "Deployer technical documentation and conformity declarations not independently verified.",
                    ]),
                    review_status="AUTOMATED_STATUTORY_TRIAGE",
                    missing_facts=eu_data.get("missing_facts", [
                        "Whether system was placed on the EU market, deployed in the Union, or produced output affecting natural persons in the Union is unverified in available filings.",
                        "Deployer technical documentation, operational autonomy levels, and real-time oversight telemetry are not publicly disclosed.",
                    ]),
                    identified_gaps=gaps,
                    disclaimer=eu_data.get("disclaimer", (
                        "This automated regulatory impact assessment is generated for technical research "
                        "and compliance preparedness only. It does not constitute formal legal advice, "
                        "regulatory determination, or EU conformity certification."
                    )),
                )
            except Exception:
                pass

        if not eu_compliance:
            # Fallback to Phase 5 informational screen if present
            eu_screen = db_session.execute(
                select(EULegalRelevanceScreenModel)
                .where(EULegalRelevanceScreenModel.incident_id == incident_id)
                .order_by(EULegalRelevanceScreenModel.created_at.desc())
            ).scalars().first()

            if eu_screen:
                gaps = []
                for obl in eu_screen.operational_obligations:
                    gaps.append(
                        PublicEUAIActGapDTO(
                            article="EU AI Act Obligation",
                            gap_status="POTENTIAL_GAP",
                            finding=str(obl),
                        )
                    )

                jurisdiction = "APPLICABLE" if eu_screen.in_scope else "NOT_APPLICABLE"

                eu_compliance = PublicEUAIActDTO(
                    is_available=True,
                    jurisdiction_status=jurisdiction,
                    classification=eu_screen.qualification_status,
                    annex_reference=None,
                    article_73_serious_incident={
                        "determination": "POTENTIAL_SERIOUS_INCIDENT" if eu_screen.in_scope else "NOT_ASSESSABLE",
                        "rationale": eu_screen.rationale or "Evaluated under informational factual screen.",
                    },
                    enforcement_status="ACTIVE_LAW" if eu_screen.qualification_status == "PROHIBITED_PRACTICE" else "NOT_YET_APPLICABLE",
                    enforcement_notes=eu_screen.applicability_date_assessment or "Evaluated against November 2026 phased enforcement timeline.",
                    missing_facts=[
                        "Informational screening only; deployer operational logs and technical files not verified.",
                    ],
                    identified_gaps=gaps,
                    disclaimer=eu_screen.disclaimer_text or (
                        "This automated regulatory impact assessment is generated for technical research "
                        "and compliance preparedness only. It does not constitute formal legal advice, "
                        "regulatory determination, or EU conformity certification."
                    ),
                )

        event_date_str = None
        if incident.incident_exact_date:
            event_date_str = str(incident.incident_exact_date)
        elif incident.incident_date_year:
            event_date_str = f"{incident.incident_date_year}"

        discovered_date_str = incident.created_at.isoformat() if incident.created_at else None

        return PublicIncidentDetailDTO(
            incident_id=incident.id,
            title=incident.title,
            summary=incident.summary,
            event_date=event_date_str,
            discovered_date=discovered_date_str,
            primary_category=incident.primary_category,
            category_display_name=cat_meta.display_name,
            category_color=cat_meta.border_hex,
            category_bg_color=cat_meta.bg_hex,
            severity=severity,
            status=incident.status,
            has_intelligence=has_intel,
            intelligence_status=intel_status,
            is_synthetic_mock=is_mock,
            sources_count=len(sources),
            sources=sources,
            unknowns=unknowns,
            intelligence=intelligence,
            eu_ai_act_compliance=eu_compliance,
        )
