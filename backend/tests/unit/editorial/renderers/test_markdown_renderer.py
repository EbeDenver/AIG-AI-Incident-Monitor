"""Unit tests for EditorialMarkdownRenderer verifying deterministic output, profiles, and safety."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from ai_incident_monitor.editorial.enums import (
    EditorialArtifactPurpose,
    EditorialDossierStatus,
    EditorialEntryType,
    EditorialPresentationProfile,
    EditorialScopeType,
    EditorialValidationCode,
    EditorialValidationSeverity,
)
from ai_incident_monitor.editorial.models import (
    EDITORIAL_DISCLAIMER_TEXT,
    EDITORIAL_DISCLAIMER_VERSION,
    EditorialDossierEntrySchema,
    EditorialDossierSchema,
    EditorialDossierSummary,
    EditorialEntryDispute,
    EditorialEntryFact,
    EditorialEntryUnknown,
    EditorialValidationFinding,
    EditorialValidationReport,
)
from ai_incident_monitor.editorial.renderers.markdown_renderer import EditorialMarkdownRenderer
from tests.unit.editorial.test_editorial_models import create_sample_dossier, create_sample_entry


class TestEditorialMarkdownRenderer:
    def test_deterministic_rendering_identical_hashes(self) -> None:
        dossier = create_sample_dossier()
        renderer = EditorialMarkdownRenderer()

        md1, hash1 = renderer.render(
            dossier,
            profile=EditorialPresentationProfile.DEEP_DIVE_DOSSIER,
            purpose=EditorialArtifactPurpose.INTERNAL_REVIEW_COPY,
        )
        md2, hash2 = renderer.render(
            dossier,
            profile=EditorialPresentationProfile.DEEP_DIVE_DOSSIER,
            purpose=EditorialArtifactPurpose.INTERNAL_REVIEW_COPY,
        )

        assert md1 == md2
        assert hash1 == hash2
        assert len(hash1) == 64

    def test_render_deep_dive_profile_content(self) -> None:
        dossier = create_sample_dossier()
        renderer = EditorialMarkdownRenderer()

        md, _ = renderer.render(
            dossier,
            profile=EditorialPresentationProfile.DEEP_DIVE_DOSSIER,
            purpose=EditorialArtifactPurpose.INTERNAL_REVIEW_COPY,
        )

        assert "# Weekly AI Safety Incident Dossier" in md
        assert "## Executive Summary" in md
        assert "### Forensic Monitoring Overview" in md
        assert "| Total Incidents Included | 1 |" in md
        assert "### Key Incident Themes" in md
        assert "Autonomous Systems" in md
        assert "## Forensic Incident Dossiers" in md
        assert "Autonomous Agent Database Purge" in md
        assert "#### Established Empirical Facts" in md
        assert "Agent deleted table 'users' at 04:15 UTC." in md
        assert "#### Material Disputes & Conflicting Statements" in md
        assert "Advance test execution" in md
        assert "## Learning & Prevention Themes" in md
        assert EDITORIAL_DISCLAIMER_TEXT in md
        assert f"Disclaimer Version: `{EDITORIAL_DISCLAIMER_VERSION}`" in md

    def test_render_executive_brief_profile(self) -> None:
        dossier = create_sample_dossier()
        renderer = EditorialMarkdownRenderer()

        md, _ = renderer.render(
            dossier,
            profile=EditorialPresentationProfile.EXECUTIVE_BRIEF,
            purpose=EditorialArtifactPurpose.INTERNAL_REVIEW_COPY,
        )

        assert "## Executive Brief" in md
        assert "### Key Macro Metrics" in md
        assert "### Strategic Safety Themes" in md
        assert "## Incident Summaries" in md
        assert "Autonomous Agent Database Purge" in md
        assert "## Key Organizational Learnings" in md
        assert EDITORIAL_DISCLAIMER_TEXT in md

    def test_render_rapid_alert_profile(self) -> None:
        dossier = create_sample_dossier()
        renderer = EditorialMarkdownRenderer()

        md, _ = renderer.render(
            dossier,
            profile=EditorialPresentationProfile.RAPID_ALERT,
            purpose=EditorialArtifactPurpose.INTERNAL_REVIEW_COPY,
        )

        assert "## Incident Alert Briefing" in md
        assert "does not imply real-time detection, external notification dispatch" in md
        assert "Autonomous Agent Database Purge" in md
        assert "#### Initial Verified Points" in md
        assert "#### Immediate Open Questions" in md
        assert EDITORIAL_DISCLAIMER_TEXT in md

    def test_epistemic_segregation_allegations_vs_facts(self) -> None:
        fact = EditorialEntryFact(
            statement="System crashed following unhandled exception.",
            source_id="ev_001",
            evidence_id="ev_001",
            is_allegation=False,
            attribution="Engineering Log",
        )
        allegation = EditorialEntryFact(
            statement="Whistleblower asserts supervisor disabled safety kill switch.",
            source_id="ev_002",
            evidence_id="ev_002",
            is_allegation=True,
            attribution="Whistleblower Affidavit",
        )

        entry = create_sample_entry()
        entry_with_both = entry.model_copy(update={"known_facts": [fact, allegation]})
        dossier = create_sample_dossier().model_copy(update={"entries": [entry_with_both]})
        dossier = dossier.model_copy(update={"content_hash": dossier.compute_content_hash()})

        renderer = EditorialMarkdownRenderer()
        md, _ = renderer.render(
            dossier,
            profile=EditorialPresentationProfile.DEEP_DIVE_DOSSIER,
            purpose=EditorialArtifactPurpose.INTERNAL_REVIEW_COPY,
        )

        assert "#### Established Empirical Facts" in md
        assert "System crashed following unhandled exception." in md

        assert "#### Attributed Allegations & Unproven Claims" in md
        assert "> **[ALLEGATION]** \"Whistleblower asserts supervisor disabled safety kill switch.\"" in md
        assert "*Attribution: Whistleblower Affidavit (Evidence `ev_002`)*" in md
        assert "unadjudicated" in md

    def test_approved_copy_requires_approved_informational_status(self) -> None:
        dossier = create_sample_dossier()  # Status is ASSEMBLED
        renderer = EditorialMarkdownRenderer()

        with pytest.raises(ValueError) as exc:
            renderer.render(
                dossier,
                purpose=EditorialArtifactPurpose.APPROVED_EDITORIAL_COPY,
            )
        assert "expected 'APPROVED_INFORMATIONAL'" in str(exc.value)

    def test_approved_copy_fails_on_hash_mismatch(self) -> None:
        dossier = create_sample_dossier().model_copy(
            update={
                "status": EditorialDossierStatus.APPROVED_INFORMATIONAL,
                "reviewed_by": "human_reviewer",
                "content_hash": "f" * 64,  # Corrupt hash
            }
        )
        renderer = EditorialMarkdownRenderer()

        with pytest.raises(ValueError) as exc:
            renderer.render(
                dossier,
                purpose=EditorialArtifactPurpose.APPROVED_EDITORIAL_COPY,
            )
        assert "content hash mismatch" in str(exc.value)

    def test_approved_copy_fails_on_blocking_findings(self) -> None:
        dossier = create_sample_dossier().model_copy(
            update={
                "status": EditorialDossierStatus.APPROVED_INFORMATIONAL,
                "reviewed_by": "human_reviewer",
            }
        )
        dossier = dossier.model_copy(update={"content_hash": dossier.compute_content_hash()})

        v_report = EditorialValidationReport(
            is_valid=False,
            dossier_id=dossier.id,
            dossier_version=dossier.version,
            content_hash=dossier.content_hash,
            total_findings=1,
            blocking_count=1,
            warning_count=0,
            findings=[
                EditorialValidationFinding(
                    severity=EditorialValidationSeverity.BLOCKING,
                    finding_code=EditorialValidationCode.BLOCKED_PROHIBITED_TERM,
                    field_path="title",
                    message="Prohibited term found.",
                )
            ],
        )

        renderer = EditorialMarkdownRenderer()
        with pytest.raises(ValueError) as exc:
            renderer.render(
                dossier,
                purpose=EditorialArtifactPurpose.APPROVED_EDITORIAL_COPY,
                validation_report=v_report,
            )
        assert "blocking validation finding" in str(exc.value)

    def test_internal_review_copy_includes_unapproved_banner_and_findings(self) -> None:
        dossier = create_sample_dossier()
        v_report = EditorialValidationReport(
            is_valid=False,
            dossier_id=dossier.id,
            dossier_version=dossier.version,
            content_hash=dossier.compute_content_hash(),
            total_findings=2,
            blocking_count=1,
            warning_count=1,
            findings=[
                EditorialValidationFinding(
                    severity=EditorialValidationSeverity.BLOCKING,
                    finding_code=EditorialValidationCode.BLOCKED_PROHIBITED_TERM,
                    field_path="entries[0].title",
                    message="Unadjudicated legal claim.",
                ),
                EditorialValidationFinding(
                    severity=EditorialValidationSeverity.WARNING,
                    finding_code=EditorialValidationCode.PASS,
                    field_path="entries[0].summary",
                    message="Source date missing.",
                ),
            ],
        )

        renderer = EditorialMarkdownRenderer()
        md, _ = renderer.render(
            dossier,
            purpose=EditorialArtifactPurpose.INTERNAL_REVIEW_COPY,
            validation_report=v_report,
        )

        assert "> **[UNAPPROVED — INTERNAL EDITORIAL REVIEW COPY — NOT FOR PUBLICATION]**" in md
        assert "## Internal Review Notes & Validation Findings" in md
        assert "Unadjudicated legal claim." in md
        assert "BLOCKED_PROHIBITED_TERM" in md

    def test_render_cleanly_handles_missing_optional_fields(self) -> None:
        bare_entry = EditorialDossierEntrySchema(
            entry_id="bare_entry_01",
            incident_id="inc_bare_01",
            entry_order=1,
            incident_title="Minimal Incident",
            incident_summary="Summary of bare incident without optional fields.",
            source_version_hash="b" * 64,
            known_facts=[],
            unknowns=[],
            disputed_claims=[],
        )
        bare_summary = EditorialDossierSummary(
            executive_summary="Overview without themes.",
            key_themes=[],
            total_incidents=1,
            total_evidence_links=0,
            disputed_incident_count=0,
            learning_and_prevention_themes=[],
        )
        bare_dossier = EditorialDossierSchema(
            id="dos_bare_01",
            version=1,
            title="Bare Incident Dossier",
            summary=bare_summary,
            entries=[bare_entry],
        )

        renderer = EditorialMarkdownRenderer()
        md, _ = renderer.render(bare_dossier)

        assert "# Bare Incident Dossier" in md
        assert "Minimal Incident" in md
        assert EDITORIAL_DISCLAIMER_TEXT in md

    def test_optional_eu_commentary_included_when_approved(self) -> None:
        entry = create_sample_entry().model_copy(
            update={
                "eu_screen_status": "APPROVED_INFORMATIONAL",
                "eu_commentary": "Relevance: DIRECT_SYSTEM_RELEVANCE. Non-binding analysis.",
            }
        )
        dossier = create_sample_dossier().model_copy(update={"entries": [entry]})
        renderer = EditorialMarkdownRenderer()

        md, _ = renderer.render(dossier)
        assert "#### EU AI Act Regulatory Context (Informational Only)" in md
        assert "Relevance: DIRECT_SYSTEM_RELEVANCE" in md

    def test_optional_eu_commentary_omitted_when_unapproved(self) -> None:
        entry = create_sample_entry().model_copy(
            update={
                "eu_screen_status": "DRAFT",
                "eu_commentary": None,
                "omitted_eu_reason": "Screen in DRAFT status; unapproved regulatory commentary suppressed.",
            }
        )
        dossier = create_sample_dossier().model_copy(update={"entries": [entry]})
        renderer = EditorialMarkdownRenderer()

        # Review copy displays internal note
        md_review, _ = renderer.render(
            dossier, purpose=EditorialArtifactPurpose.INTERNAL_REVIEW_COPY
        )
        assert "EU regulatory commentary omitted: Screen in DRAFT status" in md_review

    def test_link_scheme_validation_sanitizes_dangerous_urls(self) -> None:
        entry = create_sample_entry().model_copy(
            update={
                "primary_source_url": "javascript:alert(document.cookie)",
                "primary_source_publisher": "Malicious Publisher",
            }
        )
        dossier = create_sample_dossier().model_copy(update={"entries": [entry]})
        renderer = EditorialMarkdownRenderer()

        md, _ = renderer.render(dossier)
        # Should NOT render active [Malicious Publisher](javascript:...) link
        assert "[Malicious Publisher](javascript:" not in md
        assert "**Primary Reporting Source**: Malicious Publisher" in md

    def test_active_html_stripped_from_content(self) -> None:
        entry = create_sample_entry().model_copy(
            update={
                "incident_summary": "Injected payload <script>evil()</script><iframe src='https://evil.com'></iframe>clean text.",
            }
        )
        dossier = create_sample_dossier().model_copy(update={"entries": [entry]})
        renderer = EditorialMarkdownRenderer()

        md, _ = renderer.render(dossier)
        assert "<script>" not in md
        assert "<iframe>" not in md
        assert "clean text." in md

    def test_table_pipe_characters_escaped_cleanly(self) -> None:
        fact = EditorialEntryFact(
            statement="Expression A | Expression B failed parsing.",
            source_id="ev_101",
            evidence_id="ev_101",
            is_allegation=False,
            attribution="Parser Report",
        )
        entry = create_sample_entry().model_copy(update={"known_facts": [fact]})
        dossier = create_sample_dossier().model_copy(update={"entries": [entry]})
        renderer = EditorialMarkdownRenderer()

        md, _ = renderer.render(dossier)
        assert "Expression A \\| Expression B failed parsing." in md
