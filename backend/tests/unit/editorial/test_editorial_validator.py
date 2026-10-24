"""Unit tests for EditorialValidator verifying forensic integrity and safety checks."""

from __future__ import annotations

import pytest

from ai_incident_monitor.editorial.enums import (
    EditorialValidationCode,
    EditorialValidationSeverity,
)
from ai_incident_monitor.editorial.models import (
    EDITORIAL_DISCLAIMER_TEXT,
    EDITORIAL_DISCLAIMER_VERSION,
    EditorialDossierEntrySchema,
    EditorialDossierSchema,
    EditorialDossierSummary,
    EditorialEntryFact,
    EditorialEntryUnknown,
)
from ai_incident_monitor.editorial.validator import EditorialValidator
from tests.unit.editorial.test_editorial_models import (
    create_sample_dossier,
    create_sample_entry,
)


class TestEditorialValidator:
    def test_valid_dossier_passes_cleanly(self) -> None:
        validator = EditorialValidator()
        dossier = create_sample_dossier()
        report = validator.validate_dossier(dossier)

        assert report.is_valid is True
        assert report.blocking_count == 0
        assert report.total_findings == 0

    def test_disclaimer_preserves_compliance_terms_without_false_positive(self) -> None:
        """Requirement: Exact trusted disclaimer text must not fail solely because of words like compliance."""
        validator = EditorialValidator()
        dossier = create_sample_dossier()
        # Verify EDITORIAL_DISCLAIMER_TEXT contains 'compliance or noncompliance'
        assert "compliance or noncompliance" in EDITORIAL_DISCLAIMER_TEXT
        report = validator.validate_dossier(dossier)
        assert report.is_valid is True

    def test_missing_or_mismatched_disclaimer_blocked(self) -> None:
        validator = EditorialValidator()
        dossier = create_sample_dossier()

        # Missing disclaimer
        d_missing = dossier.model_copy(update={"disclaimer_text": ""})
        rep_missing = validator.validate_dossier(d_missing)
        assert rep_missing.is_valid is False
        assert any(f.finding_code == EditorialValidationCode.BLOCKED_MISSING_DISCLAIMER for f in rep_missing.findings)

        # Mismatched disclaimer text
        d_mismatch_txt = dossier.model_copy(update={"disclaimer_text": "Modified disclaimer text."})
        rep_mismatch_txt = validator.validate_dossier(d_mismatch_txt)
        assert rep_mismatch_txt.is_valid is False
        assert any(f.finding_code == EditorialValidationCode.BLOCKED_DISCLAIMER_MISMATCH for f in rep_mismatch_txt.findings)

        # Mismatched version
        d_mismatch_ver = dossier.model_copy(update={"disclaimer_version": "v999"})
        rep_mismatch_ver = validator.validate_dossier(d_mismatch_ver)
        assert rep_mismatch_ver.is_valid is False
        assert any(f.finding_code == EditorialValidationCode.BLOCKED_DISCLAIMER_MISMATCH for f in rep_mismatch_ver.findings)

    def test_prohibited_legal_conclusion_in_title_blocks(self) -> None:
        validator = EditorialValidator()
        dossier = create_sample_dossier().model_copy(
            update={"title": "Severe Incident Constitutes a Violation of the Law"}
        )
        report = validator.validate_dossier(dossier)
        assert report.is_valid is False
        assert any(f.finding_code == EditorialValidationCode.BLOCKED_PROHIBITED_TERM for f in report.findings)

    def test_prohibited_legal_conclusion_in_incident_summary_blocks(self) -> None:
        validator = EditorialValidator()
        entry = create_sample_entry()
        bad_entry = entry.model_copy(
            update={"incident_summary": "The vendor was illegal and violated the statute."}
        )
        dossier = create_sample_dossier().model_copy(update={"entries": [bad_entry]})
        report = validator.validate_dossier(dossier)
        assert report.is_valid is False
        assert any("incident_summary" in f.field_path for f in report.findings)

    def test_prohibited_legal_conclusion_in_fact_statement_blocks(self) -> None:
        validator = EditorialValidator()
        bad_fact = EditorialEntryFact(
            statement="The company is guilty of negligence.",
            source_id="ev_1",
            evidence_id="ev_1",
            attribution="Police Report",
        )
        entry = create_sample_entry().model_copy(update={"known_facts": [bad_fact]})
        dossier = create_sample_dossier().model_copy(update={"entries": [entry]})
        report = validator.validate_dossier(dossier)
        assert report.is_valid is False
        assert any("known_facts" in f.field_path for f in report.findings)

    def test_qualified_language_allowlist_passes(self) -> None:
        """Phrases like 'alleged violation', 'reported breach', 'potential noncompliance' must pass."""
        validator = EditorialValidator()
        hedged_entry = create_sample_entry().model_copy(
            update={
                "incident_summary": (
                    "Regulator published report regarding an alleged violation and reported breach. "
                    "Notice concerns potential noncompliance in secondary processing."
                )
            }
        )
        dossier = create_sample_dossier().model_copy(update={"entries": [hedged_entry]})
        report = validator.validate_dossier(dossier)
        assert report.is_valid is True
        assert report.blocking_count == 0

    def test_missing_evidence_in_entry_blocks(self) -> None:
        validator = EditorialValidator()
        no_ev_entry = create_sample_entry().model_copy(update={"source_evidence_ids": []})
        dossier = create_sample_dossier().model_copy(update={"entries": [no_ev_entry]})
        report = validator.validate_dossier(dossier)
        assert report.is_valid is False
        assert any(f.finding_code == EditorialValidationCode.BLOCKED_MISSING_EVIDENCE for f in report.findings)

    def test_unapproved_eu_screen_commentary_blocks(self) -> None:
        validator = EditorialValidator()
        entry_with_bad_eu = create_sample_entry().model_copy(
            update={
                "eu_commentary": "Informational relevance screen indicates high risk.",
                "eu_screen_status": "DRAFT",  # Not APPROVED_INFORMATIONAL!
            }
        )
        dossier = create_sample_dossier().model_copy(update={"entries": [entry_with_bad_eu]})
        report = validator.validate_dossier(dossier)
        assert report.is_valid is False
        assert any(f.finding_code == EditorialValidationCode.BLOCKED_UNAPPROVED_EU_SCREEN for f in report.findings)

    def test_empty_dossier_entries_blocks(self) -> None:
        validator = EditorialValidator()
        empty_dossier = create_sample_dossier().model_copy(update={"entries": []})
        report = validator.validate_dossier(empty_dossier)
        assert report.is_valid is False
        assert any(f.finding_code == EditorialValidationCode.BLOCKED_EMPTY_DOSSIER for f in report.findings)
