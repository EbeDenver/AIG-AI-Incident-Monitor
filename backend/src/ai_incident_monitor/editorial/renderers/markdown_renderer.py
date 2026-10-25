"""Deterministic Markdown renderer for editorial dossiers across presentation profiles.

Governing Charter: Project Constitution (Rules 1, 3, 10, 11, 12, 14, 15, 17),
ADR-001, ADR-014, ADR-020, ADR-021, PRD §4.7.
"""

from __future__ import annotations

import hashlib
from typing import Optional

from ai_incident_monitor.editorial.enums import (
    EditorialArtifactPurpose,
    EditorialDossierStatus,
    EditorialPresentationProfile,
)
from ai_incident_monitor.editorial.models import (
    EditorialDossierSchema,
    EditorialValidationReport,
)
from ai_incident_monitor.editorial.renderers.base import (
    BaseEditorialRenderer,
    escape_markdown_table_cell,
    escape_markdown_text,
    sanitize_url,
    strip_html_tags,
)


class EditorialMarkdownRenderer(BaseEditorialRenderer):
    """Deterministic, pure Markdown renderer supporting multiple presentation profiles.

    Produces editorially structured drafts for manual review and transfer.
    Guarantees:
    - Pure programmatic generation (zero LLM or generative inference).
    - Bit-for-bit repeatability across runs for identical inputs.
    - Epistemic segregation of facts, allegations, disputes, and unknowns.
    - Strict differentiation of unapproved review copies from approved copies.
    """

    RENDERER_VERSION = "EditorialMarkdownRenderer/1.0"

    def render(
        self,
        dossier: EditorialDossierSchema,
        profile: EditorialPresentationProfile = EditorialPresentationProfile.DEEP_DIVE_DOSSIER,
        purpose: EditorialArtifactPurpose = EditorialArtifactPurpose.INTERNAL_REVIEW_COPY,
        validation_report: Optional[EditorialValidationReport] = None,
    ) -> tuple[str, str]:
        """Render the dossier into deterministic Markdown.

        Returns:
            tuple[str, str]: (rendered_markdown, canonical_payload_hash)
        """
        # Enforce approved copy preconditions
        if purpose == EditorialArtifactPurpose.APPROVED_EDITORIAL_COPY:
            if dossier.status != EditorialDossierStatus.APPROVED_INFORMATIONAL:
                raise ValueError(
                    f"Cannot render APPROVED_EDITORIAL_COPY: dossier '{dossier.id}' is in "
                    f"status '{dossier.status.value}', expected 'APPROVED_INFORMATIONAL'."
                )
            computed_hash = dossier.compute_content_hash()
            if dossier.content_hash and dossier.content_hash != computed_hash:
                raise ValueError(
                    f"Cannot render APPROVED_EDITORIAL_COPY: dossier content hash mismatch "
                    f"(recorded='{dossier.content_hash}', computed='{computed_hash}')."
                )
            if validation_report and validation_report.blocking_count > 0:
                raise ValueError(
                    f"Cannot render APPROVED_EDITORIAL_COPY: dossier has "
                    f"{validation_report.blocking_count} blocking validation finding(s)."
                )

        lines: list[str] = []

        # 1. Header & Artifact Purpose Banner
        if purpose == EditorialArtifactPurpose.INTERNAL_REVIEW_COPY:
            lines.append("> **[UNAPPROVED — INTERNAL EDITORIAL REVIEW COPY — NOT FOR PUBLICATION]**")
            lines.append(
                "> *Notice: This document is an unapproved internal working draft prepared for "
                "editorial verification, fact-checking, and tone review. Do not distribute externally.*"
            )
            lines.append("")
        else:
            lines.append("> **[AI GUARDIANS RESEARCH DOSSIER — APPROVED PUBLICATION DRAFT]**")
            lines.append(
                f"> *Formal human editorial review completed by {dossier.reviewed_by or 'editorial board'}. "
                "Approved for manual publication.*"
            )
            lines.append("")

        # 2. Main Title and Scope
        lines.append(f"# {escape_markdown_text(dossier.title)}")
        lines.append("")

        meta_parts: list[str] = [f"**Scope**: `{dossier.scope_type.value}`"]
        if dossier.coverage_period_start and dossier.coverage_period_end:
            start_str = dossier.coverage_period_start.strftime("%Y-%m-%d")
            end_str = dossier.coverage_period_end.strftime("%Y-%m-%d")
            meta_parts.append(f"**Coverage Period**: {start_str} to {end_str}")
        meta_parts.append(f"**Dossier Version**: `v{dossier.version}`")
        if purpose == EditorialArtifactPurpose.APPROVED_EDITORIAL_COPY and dossier.reviewed_by:
            meta_parts.append(f"**Reviewed By**: `{dossier.reviewed_by}`")
        lines.append(" | ".join(meta_parts))
        lines.append("")

        # 3. Profile-Specific Body
        if profile == EditorialPresentationProfile.DEEP_DIVE_DOSSIER:
            self._render_deep_dive_body(lines, dossier, purpose)
        elif profile == EditorialPresentationProfile.EXECUTIVE_BRIEF:
            self._render_executive_brief_body(lines, dossier, purpose)
        elif profile == EditorialPresentationProfile.RAPID_ALERT:
            self._render_rapid_alert_body(lines, dossier, purpose)
        else:
            raise ValueError(f"Unsupported presentation profile: {profile}")

        # 4. Mandatory Disclaimer Section
        lines.append("---")
        lines.append("## Mandatory Research Disclaimer")
        lines.append(f"*{escape_markdown_text(dossier.disclaimer_text)}*")
        lines.append("")
        lines.append(f"*Disclaimer Version: `{dossier.disclaimer_version}` | Generator: `{self.RENDERER_VERSION}`*")
        lines.append("")

        # 5. Internal Review Findings (INTERNAL_REVIEW_COPY Only)
        if purpose == EditorialArtifactPurpose.INTERNAL_REVIEW_COPY and validation_report:
            val_status_str = "PASSED" if validation_report.is_valid else "FAILED"
            lines.append("---")
            lines.append("## Internal Review Notes & Validation Findings")
            lines.append(
                f"*Validation Status: `{val_status_str}` | "
                f"Blocking Findings: `{validation_report.blocking_count}` | "
                f"Warnings: `{validation_report.warning_count}`*"
            )
            lines.append("")
            if validation_report.findings:
                lines.append("| Severity | Code | Field Path | Message |")
                lines.append("|:---|:---|:---|:---|")
                for f in validation_report.findings:
                    sev = escape_markdown_table_cell(f.severity.value)
                    code = escape_markdown_table_cell(f.finding_code.value)
                    field = escape_markdown_table_cell(f.field_path)
                    msg = escape_markdown_table_cell(f.message)
                    lines.append(f"| {sev} | `{code}` | `{field}` | {msg} |")
                lines.append("")
            else:
                lines.append("*(No active validation findings detected for this draft.)*")
                lines.append("")

        rendered_text = "\n".join(lines).strip() + "\n"
        canonical_payload_hash = hashlib.sha256(rendered_text.encode("utf-8")).hexdigest()
        return rendered_text, canonical_payload_hash

    # -------------------------------------------------------------------------
    # Internal Profile Builders
    # -------------------------------------------------------------------------

    def _render_deep_dive_body(
        self,
        lines: list[str],
        dossier: EditorialDossierSchema,
        purpose: EditorialArtifactPurpose,
    ) -> None:
        """Render full forensic breakdown for the DEEP_DIVE_DOSSIER profile."""
        # Executive Summary & Forensic Metrics
        lines.append("## Executive Summary")
        lines.append(escape_markdown_text(dossier.summary.executive_summary))
        lines.append("")

        lines.append("### Forensic Monitoring Overview")
        lines.append("| Metric | Count |")
        lines.append("|:---|:---|")
        lines.append(f"| Total Incidents Included | {dossier.summary.total_incidents} |")
        lines.append(f"| Corroborating Evidence Links | {dossier.summary.total_evidence_links} |")
        lines.append(f"| Contested / Disputed Incidents | {dossier.summary.disputed_incident_count} |")
        lines.append("")

        if dossier.summary.key_themes:
            lines.append("### Key Incident Themes")
            for theme in sorted(dossier.summary.key_themes):
                lines.append(f"- {escape_markdown_text(theme)}")
            lines.append("")

        # Detailed Incident Entries
        lines.append("---")
        lines.append("## Forensic Incident Dossiers")
        lines.append("")

        for idx, entry in enumerate(dossier.entries, start=1):
            lines.append(f"### {idx}. {escape_markdown_text(entry.incident_title)}")

            # Entry Metadata line
            entry_meta: list[str] = [f"**Incident ID**: `{entry.incident_id}`"]
            if entry.incident_date_str:
                entry_meta.append(f"**Date**: {entry.incident_date_str}")
            if entry.severity_tier:
                score_str = f" ({entry.severity_score:.1f})" if entry.severity_score is not None else ""
                entry_meta.append(f"**Severity**: `{entry.severity_tier}`{score_str}")
            lines.append(" | ".join(entry_meta))
            lines.append("")

            # Primary source attribution
            if entry.primary_source_publisher or entry.primary_source_url:
                pub = escape_markdown_text(entry.primary_source_publisher or "Reporting Source")
                safe_url = sanitize_url(entry.primary_source_url)
                if safe_url:
                    lines.append(f"**Primary Reporting Source**: [{pub}]({safe_url})")
                else:
                    lines.append(f"**Primary Reporting Source**: {pub}")
                lines.append("")

            # Narrative Summary
            lines.append(f"> {escape_markdown_text(entry.incident_summary)}")
            lines.append("")

            # 1. Established Facts
            facts = [f for f in entry.known_facts if not f.is_allegation]
            if facts:
                lines.append("#### Established Empirical Facts")
                lines.append("| # | Factual Assertion | Source / Attribution | Evidence ID |")
                lines.append("|:---|:---|:---|:---|")
                for f_idx, f in enumerate(facts, start=1):
                    stmt = escape_markdown_table_cell(f.statement)
                    attr = escape_markdown_table_cell(f.attribution)
                    ev_id = escape_markdown_table_cell(f.evidence_id)
                    lines.append(f"| {f_idx} | {stmt} | {attr} | `{ev_id}` |")
                lines.append("")

            # 2. Attributed Allegations
            allegations = [f for f in entry.known_facts if f.is_allegation]
            if allegations:
                lines.append("#### Attributed Allegations & Unproven Claims")
                for a in allegations:
                    stmt = escape_markdown_text(a.statement)
                    attr = escape_markdown_text(a.attribution)
                    lines.append(f"> **[ALLEGATION]** \"{stmt}\"")
                    lines.append(f"> *Attribution: {attr} (Evidence `{a.evidence_id}`)*")
                    lines.append("> *Status: Contested / subject to ongoing inquiry; unadjudicated.*")
                    lines.append("")

            # 3. Material Disputes
            if entry.disputed_claims:
                lines.append("#### Material Disputes & Conflicting Statements")
                for d in entry.disputed_claims:
                    topic = escape_markdown_text(d.topic)
                    pos_a = escape_markdown_text(d.position_a)
                    src_a = escape_markdown_text(d.source_a)
                    pos_b = escape_markdown_text(d.position_b)
                    src_b = escape_markdown_text(d.source_b)
                    lines.append(f"- **Dispute Topic**: {topic}")
                    lines.append(f"  - **Position A** ({src_a}): \"{pos_a}\"")
                    lines.append(f"  - **Position B** ({src_b}): \"{pos_b}\"")
                lines.append("")

            # 4. Unresolved Uncertainties
            if entry.unknowns:
                lines.append("#### Critical Uncertainties & Open Questions")
                for u in entry.unknowns:
                    q = escape_markdown_text(u.question)
                    domain_str = f" [{u.domain}]" if u.domain else ""
                    impact_str = f" *(Impact: {u.impact})*" if u.impact else ""
                    lines.append(f"- [ ] **Question**{domain_str}: {q}{impact_str}")
                lines.append("")

            # 5. Optional EU Regulatory Relevance (Informational Only)
            if entry.eu_screen_status == "APPROVED_INFORMATIONAL" and entry.eu_commentary:
                lines.append("#### EU AI Act Regulatory Context (Informational Only)")
                lines.append(f"> {escape_markdown_text(entry.eu_commentary)}")
                lines.append("> *Note: Informational relevance screening only. Does not constitute formal compliance certification.*")
                lines.append("")
            elif entry.omitted_eu_reason and purpose == EditorialArtifactPurpose.INTERNAL_REVIEW_COPY:
                lines.append(f"> *(Internal Note: EU regulatory commentary omitted: {entry.omitted_eu_reason})*")
                lines.append("")

            lines.append("")

        # Learning & Prevention Themes
        if dossier.summary.learning_and_prevention_themes:
            lines.append("---")
            lines.append("## Learning & Prevention Themes")
            for theme in sorted(dossier.summary.learning_and_prevention_themes):
                lines.append(f"- {escape_markdown_text(theme)}")
            lines.append("")

        # Methodology Notes
        if dossier.methodology_notes:
            lines.append("---")
            lines.append("## Methodology & Safe-Harbor Notes")
            lines.append(escape_markdown_text(dossier.methodology_notes))
            lines.append("")

    def _render_executive_brief_body(
        self,
        lines: list[str],
        dossier: EditorialDossierSchema,
        purpose: EditorialArtifactPurpose,
    ) -> None:
        """Render high-level executive summary for the EXECUTIVE_BRIEF profile."""
        lines.append("## Executive Brief")
        lines.append(escape_markdown_text(dossier.summary.executive_summary))
        lines.append("")

        lines.append("### Key Macro Metrics")
        lines.append(
            f"- **Monitored Incidents**: `{dossier.summary.total_incidents}` | "
            f"**Evidence Links**: `{dossier.summary.total_evidence_links}` | "
            f"**Contested Incidents**: `{dossier.summary.disputed_incident_count}`"
        )
        lines.append("")

        if dossier.summary.key_themes:
            lines.append("### Strategic Safety Themes")
            for theme in sorted(dossier.summary.key_themes):
                lines.append(f"- **{escape_markdown_text(theme)}**")
            lines.append("")

        lines.append("---")
        lines.append("## Incident Summaries")
        lines.append("")

        for idx, entry in enumerate(dossier.entries, start=1):
            sev_str = f" [{entry.severity_tier}]" if entry.severity_tier else ""
            lines.append(f"### {idx}. {escape_markdown_text(entry.incident_title)}{sev_str}")

            pub = escape_markdown_text(entry.primary_source_publisher or "Reporting Source")
            safe_url = sanitize_url(entry.primary_source_url)
            citation = f"([source: {pub}]({safe_url}))" if safe_url else f"([source: {pub}])"
            lines.append(f"{escape_markdown_text(entry.incident_summary)} {citation}")
            lines.append("")

            # High-level highlights of allegations or disputes
            allegations = [f for f in entry.known_facts if f.is_allegation]
            if allegations:
                lines.append(f"- *Attributed Claim*: {escape_markdown_text(allegations[0].statement)} *(unproven allegation)*")
            if entry.disputed_claims:
                lines.append(f"- *Contested Assertion*: Dispute regarding {escape_markdown_text(entry.disputed_claims[0].topic)}.")
            lines.append("")

        if dossier.summary.learning_and_prevention_themes:
            lines.append("---")
            lines.append("## Key Organizational Learnings")
            for theme in sorted(dossier.summary.learning_and_prevention_themes):
                lines.append(f"- {escape_markdown_text(theme)}")
            lines.append("")

    def _render_rapid_alert_body(
        self,
        lines: list[str],
        dossier: EditorialDossierSchema,
        purpose: EditorialArtifactPurpose,
    ) -> None:
        """Render concise technical briefing for the RAPID_ALERT profile."""
        lines.append("## Incident Alert Briefing")
        lines.append(
            "> *Editorial Notice: This briefing compiles preliminary public reporting concerning an "
            "emerging AI safety event. It does not imply real-time detection, external notification dispatch, "
            "or confirmed statutory liability.*"
        )
        lines.append("")

        for idx, entry in enumerate(dossier.entries, start=1):
            lines.append(f"### {escape_markdown_text(entry.incident_title)}")

            date_str = f"**Date**: {entry.incident_date_str} | " if entry.incident_date_str else ""
            tier_str = f"**Severity**: `{entry.severity_tier}`" if entry.severity_tier else ""
            if date_str or tier_str:
                lines.append(f"{date_str}{tier_str}".strip(" | "))
                lines.append("")

            lines.append(f"> {escape_markdown_text(entry.incident_summary)}")
            lines.append("")

            # Preliminary reported facts
            facts = [f for f in entry.known_facts if not f.is_allegation]
            if facts:
                lines.append("#### Initial Verified Points")
                for f in facts:
                    lines.append(f"- {escape_markdown_text(f.statement)} *(Source: {escape_markdown_text(f.attribution)})*")
                lines.append("")

            # Allegations
            allegations = [f for f in entry.known_facts if f.is_allegation]
            if allegations:
                lines.append("#### Initial Attributed Allegations")
                for a in allegations:
                    lines.append(f"- **[ALLEGATION]** {escape_markdown_text(a.statement)} *(Attribution: {escape_markdown_text(a.attribution)})*")
                lines.append("")

            # Unknowns
            if entry.unknowns:
                lines.append("#### Immediate Open Questions")
                for u in entry.unknowns:
                    lines.append(f"- [ ] {escape_markdown_text(u.question)}")
                lines.append("")

            # Sources
            if entry.primary_source_publisher or entry.primary_source_url:
                pub = escape_markdown_text(entry.primary_source_publisher or "Reporting Source")
                safe_url = sanitize_url(entry.primary_source_url)
                if safe_url:
                    lines.append(f"**Primary Reporting**: [{pub}]({safe_url})")
                else:
                    lines.append(f"**Primary Reporting**: {pub}")
                lines.append("")
