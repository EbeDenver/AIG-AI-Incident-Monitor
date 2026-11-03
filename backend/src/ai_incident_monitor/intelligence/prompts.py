"""Versioned prompt templates and envelope sanitizers for LLM enrichment.

Governing Specification: Ai-incident-manager-guide.pdf (§1–§3),
Project Constitution (Rules 1, 2, 3, 4, 11, 12, 14, 16), ADR-011, SEC-005,
amended by Section B (No-Approval Amendment: advisory quality warnings only,
no workflow gates, no reviewer keys, no attestations).
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import html
from typing import Sequence

from ai_incident_monitor.intelligence.schemas import (
    ProvenanceItem,
    SourceTypeCategory,
)

PROMPT_VERSION = "2.0.0"

SYSTEM_PROMPT = """AI Incident Manager — Evidence-Grounded Incident Enrichment

You are an AI Incident Analyst specializing in evidence-grounded incident analysis, root-cause assessment, and enterprise risk management. Your role is to analyze reported AI incidents and generate structured, verified incident intelligence dossiers.

You operate under strict evidential discipline: you must distinguish what is known from what is claimed, separate confirmed facts from attributed allegations, identify causal links versus correlations, and provide actionable, validated guidance for organizational decision-makers and consultants.

================================================================================
NON-NEGOTIABLE OPERATING RULES
================================================================================

1. GROUNDING IN PROVIDED EVIDENCE ONLY:
   Every factual assertion, claim, and finding must be grounded in and cited to specific items in the provided evidence package using their evidence_id (e.g., E001). Never introduce external claims, unverified assumptions, or speculative narratives not supported by the evidence package.

2. EPISTEMIC STATUS DISCIPLINE:
   Strictly classify every claim into exactly one of four epistemic categories:
   - CONFIRMED_FACT: Empirically verified by primary evidence, regulatory findings, or technical postmortems with high confidence.
   - ATTRIBUTED_ALLEGATION: Asserted by a named source (media, company spokesperson, researcher) but lacking independent technical or empirical verification.
   - TECHNICAL_UNCERTAINTY: A recognized question or gap where the evidence is insufficient to determine what occurred.
   - DISPUTED_FACT: Explicitly contradicted by competing sources or accounts within the evidence package.

3. SEPARATION OF CLASSIFICATION AND VERIFICATION:
   Claim classification and verification status are independent dimensions:
   - A claim may be an ATTRIBUTED_ALLEGATION and UNVERIFIED even if the attribution itself is high-confidence.
   - Never promote an unverified allegation to CONFIRMED_FACT simply because the reporting source is credible.
   - Valid verification_status values: VERIFIED, PARTIALLY_VERIFIED, UNVERIFIED, CONTESTED, NOT_ASSESSABLE.
   - Valid confidence tiers: LOW, MEDIUM, HIGH.

4. AI INVOLVEMENT CLASSIFICATION:
   Classify the AI system's role using only these standard categories:
   - PRIMARY: The AI system's direct output, decision, or autonomous action was the central driver of the incident.
   - CONTRIBUTING: The AI system was one of several factors that combined to produce the incident.
   - ENABLING: The AI system provided capabilities, tools, or data that facilitated the incident, but did not directly cause it.
   - INCIDENTAL: The AI system was present in the environment or workflow but had no meaningful causal connection to the incident.
   - ALLEGED: AI involvement has been claimed by sources but is not substantiated by technical evidence.
   - NOT_ESTABLISHED: Available evidence is insufficient to determine whether AI was involved.
   Always assess documented autonomy level (AUTONOMOUS_EXECUTION, HUMAN_DIRECTED, ASSISTIVE, UNKNOWN) and human oversight status (EFFECTIVE, DEFICIENT, ABSENT, UNKNOWN).

5. CAUSAL RIGOR:
   Distinguish correlation from causation. Identify:
   - Observed outcomes (what actually happened).
   - Reported mechanisms (how the AI system reportedly produced the outcome).
   - Supported causal links (links substantiated by evidence).
   - Hypotheses (plausible but unproven explanations).
   - Alternative explanations (non-AI factors, system configuration, human error, conventional software defects).
   Assign causal_status: CONFIRMED_CAUSE, PROBABLE_CONTRIBUTOR, POSSIBLE_CONTRIBUTOR, UNSUPPORTED_SPECULATION, or CAUSALITY_NOT_ESTABLISHED.

6. UNCERTAINTY TRANSPARENCY:
   Explicitly identify what is NOT known. For every material uncertainty, formulate:
   - The specific question.
   - Its materiality (LOW, MEDIUM, HIGH).
   - What evidence would be required to resolve it.

7. DISPUTED FACTS HANDLING:
   When evidence items present conflicting accounts:
   - Record the specific assertion in dispute.
   - Identify the conflicting sources and their respective evidence_ids.
   - Provide an objective analysis explaining the discrepancy without taking sides unless the evidence definitively resolves it.

8. PROVENANCE AND CITATION INTEGRITY:
   Every claim, control, and analytical finding must cite one or more valid evidence_ids from the provenance package.
   - Citations must be precise: cite only the evidence items that directly support the specific statement.
   - Never invent or fabricate evidence_ids.

9. ACTIONABLE, TESTABLE GUIDANCE:
   Organizational controls must be concrete, operational safeguards:
   - State the specific risk addressed.
   - Formulate the control with sufficient detail for engineering or governance implementation.
   - Classify control_type: PREVENTIVE, DETECTIVE, or CORRECTIVE.
   - Distinguish incident-specific controls from broad defense-in-depth measures.
   - Provide a concrete, testable validation_test for every control.
   Tailor separate guidance for decision-makers (strategic implications, governance decisions, required disclosures, effectiveness metrics) and consultants (diagnostic discovery questions, assessment activities, architecture considerations, implementation controls, acceptance criteria).

10. NO SPECULATIVE EXTRAPOLATION:
    If source evidence is limited to headlines, brief summaries, or wire notices, explicitly declare LIMITED_EVIDENCE or UNKNOWN. Never extrapolate detailed causal mechanisms or architecture details from sparse reporting.

================================================================================
AUTHORITATIVE NO-APPROVAL AMENDMENT
================================================================================
The AI Incident Monitor operates under an authoritative No-Approval Policy:
- No incident approvals, dossier approvals, reviewer keys, or attestations exist or may be required.
- Do NOT output blocking workflow gates or human review prerequisites.
- Any unresolved uncertainties, uncorroborated allegations, or citation gaps MUST be recorded advisory-only in quality_review (advisory_human_review_flag, review_reasons) and assessment_status (ADVISORY_REVIEW).
- Source incidents and enrichment analyses remain immediately accessible without publication gating.

================================================================================
ANALYSIS PROCEDURE (10-STEP WORKFLOW)
================================================================================
Step 1: Ingest and catalog all evidence items in the untrusted source payload.
Step 2: Extract atomic, independently verifiable claims.
Step 3: Classify each claim and assign verification status and confidence independently.
Step 4: Assess AI involvement, system role, documented capabilities, autonomy, and oversight.
Step 5: Perform causal assessment separating verified causal mechanisms from hypotheses and alternative explanations.
Step 6: Document technical uncertainties and disputed facts.
Step 7: Formulate organizational controls (preventive, detective, corrective) with concrete validation tests.
Step 8: Formulate strategic decision-maker guidance.
Step 9: Formulate actionable consultant diagnostic and implementation guidance.
Step 10: Produce quality review assessment and assign assessment_status (COMPLETE, PARTIAL, or ADVISORY_REVIEW).

================================================================================
OUTPUT FORMAT
================================================================================
You must respond EXCLUSIVELY with a single valid JSON object adhering strictly to the IncidentEnrichmentDossier schema. Do NOT include markdown code blocks, preamble, or commentary.
"""


def compute_prompt_digest(prompt_text: str) -> str:
    """Compute cryptographic SHA-256 digest of prompt template and input (SEC-005)."""
    return hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()


def escape_envelope_content(raw_text: str) -> str:
    """Escape XML special characters to prevent envelope escape attacks (ADR-011)."""
    if not raw_text:
        return ""
    escaped = html.escape(raw_text, quote=True)
    escaped = escaped.replace("<untrusted_source", "&lt;untrusted_source")
    escaped = escaped.replace("</untrusted_source>", "&lt;/untrusted_source&gt;")
    return escaped


def build_evidence_package(
    *,
    incident_id: str,
    title: str,
    summary: str,
    source_url: str | None = None,
    evidence_excerpts: Sequence[str] | None = None,
    source_records: Sequence[dict] | None = None,
) -> list[ProvenanceItem]:
    """Catalog available source evidence into a clean, indexed provenance package."""
    now_iso = datetime.now(timezone.utc).isoformat()
    package: list[ProvenanceItem] = []

    # E001 is always the primary syndicated record
    is_brief = len(summary.split()) < 20 or summary == title
    limitations = (
        "Syndicated incident report; technical postmortem telemetry not provided in source feed."
        if is_brief
        else "Primary incident monitoring feed record."
    )
    package.append(
        ProvenanceItem(
            evidence_id="E001",
            source_title=title,
            publisher="AI Incident Monitor Ingestion Feed",
            url=source_url or f"https://incidentdatabase.ai/cite/{incident_id}",
            published_at=None,
            retrieved_at=now_iso,
            source_type=SourceTypeCategory.AGGREGATOR,
            excerpt=summary if summary else title,
            locator="incident_record:root",
            limitations=limitations,
        )
    )

    # Add source records if provided
    if source_records:
        for idx, s in enumerate(source_records, start=2):
            eid = f"E{idx:03d}"
            package.append(
                ProvenanceItem(
                    evidence_id=eid,
                    source_title=s.get("title", f"Source {idx}"),
                    publisher=s.get("publisher", "External Source"),
                    url=s.get("url"),
                    published_at=s.get("published_at"),
                    retrieved_at=now_iso,
                    source_type=SourceTypeCategory.SECONDARY,
                    excerpt=s.get("excerpt", s.get("title", "")),
                    locator=s.get("locator"),
                    limitations=s.get("limitations", "External syndicated report."),
                )
            )

    # Add evidence excerpts if provided
    if evidence_excerpts:
        start_idx = len(package) + 1
        for idx, exc in enumerate(evidence_excerpts, start=start_idx):
            eid = f"E{idx:03d}"
            package.append(
                ProvenanceItem(
                    evidence_id=eid,
                    source_title=f"Extracted Citation {idx}",
                    publisher="Ingested Source Reference",
                    url=None,
                    published_at=None,
                    retrieved_at=now_iso,
                    source_type=SourceTypeCategory.SECONDARY,
                    excerpt=exc,
                    locator=f"citation_excerpt:{idx}",
                    limitations="Isolated excerpt cited in primary incident dossier.",
                )
            )

    return package


def render_enrichment_prompt(
    *,
    incident_id: str,
    title: str,
    summary: str,
    category: str,
    evidence_excerpts: Sequence[str] | None = None,
    source_url: str | None = None,
    source_records: Sequence[dict] | None = None,
) -> tuple[str, str]:
    """Render the versioned prompt and return (prompt_text, prompt_digest).

    Source text is wrapped strictly in <untrusted_source> envelopes per ADR-011.
    """
    safe_title = escape_envelope_content(title)
    safe_summary = escape_envelope_content(summary)

    package = build_evidence_package(
        incident_id=incident_id,
        title=title,
        summary=summary,
        source_url=source_url,
        evidence_excerpts=evidence_excerpts,
        source_records=source_records,
    )

    items_xml = ""
    for item in package:
        safe_excerpt = escape_envelope_content(item.excerpt)
        safe_pub = escape_envelope_content(item.publisher)
        safe_title_item = escape_envelope_content(item.source_title)
        items_xml += f"""  <untrusted_evidence_item id="{item.evidence_id}" source_type="{item.source_type.value}" publisher="{safe_pub}">
    <title>{safe_title_item}</title>
    <url>{escape_envelope_content(item.url or "")}</url>
    <excerpt>{safe_excerpt}</excerpt>
    <limitations>{escape_envelope_content(item.limitations)}</limitations>
  </untrusted_evidence_item>\n"""

    prompt_body = f"""{SYSTEM_PROMPT}

[PROMPT VERSION: {PROMPT_VERSION}]
[INCIDENT IDENTIFIER: {incident_id}]
[PRELIMINARY CATEGORY: {category}]

<untrusted_source_payload incident_id="{incident_id}">
  <untrusted_source type="headline">
{safe_title}
  </untrusted_source>
  <untrusted_source type="summary">
{safe_summary}
  </untrusted_source>
  <untrusted_source_evidence count="{len(package)}">
{items_xml}  </untrusted_source_evidence>
</untrusted_source_payload>

Analyze the untrusted source text above and produce a validated IncidentEnrichmentDossier JSON object adhering to the schema and operating rules.
"""
    digest = compute_prompt_digest(prompt_body)
    return prompt_body, digest
