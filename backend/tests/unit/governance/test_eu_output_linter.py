"""Unit tests for the EU AI Act output linter (EUOutputLinter).

Enforces Constitutional Rules 10, 11, 14 & 15 and LGL-001/LGL-002:
- Detects and blocks prohibited legal-conclusion language across all structured fields.
- Verifies bypass resistance (casing, punctuation, hyphenation, whitespace, inflection).
- Validates narrow qualified allowlist preservation (zero false positives).
- Validates structural checks (status, disclaimer, evidence, reference set).
"""

from __future__ import annotations

import pytest

from ai_incident_monitor.governance.enums import (
    EUScreenStatus,
    EUTimingAssessment,
    FrameworkCode,
    FrameworkStatus,
)
from ai_incident_monitor.governance.eu_output_linter import (
    EULinterFinding,
    EULinterReport,
    EULinterResult,
    EUOutputLinter,
)
from ai_incident_monitor.governance.models import (
    EU_AI_ACT_DISCLAIMER_V2,
    EU_AI_ACT_DISCLAIMER_VERSION,
    EULegalRelevanceScreenSchema,
    FrameworkReferenceSetSchema,
)


@pytest.fixture
def linter() -> EUOutputLinter:
    """Fixture providing a fresh default EUOutputLinter instance."""
    return EUOutputLinter()


@pytest.fixture
def clean_screen_schema() -> EULegalRelevanceScreenSchema:
    """Fixture providing a valid, neutral, approved EU screen schema."""
    return EULegalRelevanceScreenSchema(
        incident_id="inc_clean_001",
        reference_set_id="eu-ai-act-2024-1689",
        status=EUScreenStatus.APPROVED_INFORMATIONAL,
        rationale="Incident evidence indicates machine-based biometric processing in public spaces.",
        known_facts=["System utilized CCTV camera streams in a retail facility."],
        unknowns=["Specific vendor and model architecture are unverified."],
        disputed_facts=[],
        missing_facts=["Whether facial recognition inferencing occurred in real time."],
        follow_up_questions=["Was remote biometric identification conducted in publicly accessible spaces?"],
        timing_assessment=EUTimingAssessment.REFERENCE_METADATA_ALIGNS,
        disclaimer_version=EU_AI_ACT_DISCLAIMER_VERSION,
        disclaimer_text=EU_AI_ACT_DISCLAIMER_V2,
        evidence_ids=["ev_101"],
        reviewed_by="senior_reviewer_01",
        metadata_json={
            "reviewer_notes": "Neutral factual assessment based strictly on verified records.",
            "conceptual_findings": [
                {
                    "control_id": "EU-ART-5.1.h",
                    "finding_rationale": "Evidence indicates potential conceptual correspondence to public biometric identification.",
                    "matched_facts": ["CCTV stream used for facial tracking."],
                }
            ],
        },
    )


class TestEUOutputLinterTextRules:
    """Test individual text linting and regex matching rules."""

    def test_clean_text_passes(self, linter: EUOutputLinter) -> None:
        """Neutral technical language passes with zero findings."""
        findings = linter.lint_text(
            "The incident facts document automated facial recognition deployed in a transportation hub.",
            "rationale",
        )
        assert len(findings) == 0

    @pytest.mark.parametrize(
        "prohibited_term,matched_substr",
        [
            ("The deployment was a direct violation of European law.", "violation"),
            ("The organization violates regulatory provisions.", "violates"),
            ("The company violated user safety standards.", "violated"),
            ("We observed actions violating privacy protections.", "violating"),
            ("This represents an infringement of fundamental rights.", "infringement"),
            ("The practice infringes on civil liberties.", "infringes"),
            ("The system caused a major breach of security obligations.", "breach"),
            ("The provider breached their legal commitments.", "breached"),
            ("The facial recognition system is illegal.", "illegal"),
            ("Operating without authorization is unlawful.", "unlawful"),
            ("The system is non-compliant with requirements.", "non-compliant"),
            ("The system is noncompliant with standards.", "noncompliant"),
            ("A serious compliance failure occurred.", "compliance failure"),
            ("A statutory duty applies to this operator.", "statutory duty"),
            ("A legal duty applies to the provider.", "legal duty applies"),
            ("The operator has a duty applies to mitigate risk.", "duty applies"),
            ("The entity is required to report this incident immediately.", "required to report"),
            ("The provider must report to the supervisory authority.", "must report"),
            ("This incident is reportable under Union law.", "incident is reportable"),
            ("This is a legally high-risk deployment.", "legally high-risk"),
            ("The model is classified as high-risk under the EU AI Act.", "high-risk under the EU AI Act"),
            ("The company operated a prohibited practice in the EU.", "prohibited practice"),
            ("The company operated a prohibited AI system in public.", "prohibited AI system"),
            ("The EU AI Act applies directly to this product.", "EU AI Act applies"),
            ("A statutory obligation applies to the deployer.", "obligation applies"),
            ("The provider bears legal liability for the harm.", "legal liability"),
            ("The vendor is liable for damages incurred.", "liable for"),
        ],
    )
    def test_prohibited_terms_detected(
        self, linter: EUOutputLinter, prohibited_term: str, matched_substr: str
    ) -> None:
        """Every mandatory prohibited legal-conclusion phrase is detected and blocked."""
        findings = linter.lint_text(prohibited_term, "test_field")
        assert len(findings) >= 1
        assert any(f.finding_code == EULinterResult.BLOCKED_PROHIBITED_TERM.value for f in findings)
        assert any(f.blocked_boolean is True for f in findings)

    @pytest.mark.parametrize(
        "casing_variant",
        [
            "VIOLATION of regulations",
            "A clear BreAch occurred",
            "This was an ILLEGAL deployment",
            "System is Non-Compliant",
            "Company MUST REPORT the failure",
            "System is a Prohibited Practice",
        ],
    )
    def test_case_insensitivity(self, linter: EUOutputLinter, casing_variant: str) -> None:
        """Linter is robust against arbitrary capitalization variants."""
        findings = linter.lint_text(casing_variant, "test_field")
        assert len(findings) >= 1
        assert findings[0].finding_code == EULinterResult.BLOCKED_PROHIBITED_TERM.value

    @pytest.mark.parametrize(
        "bypass_attempt",
        [
            "Evidence shows violation; in the market.",
            "A serious (breach) of protocol.",
            "This action is illegal!",
            "System is non - compliant with standards.",
            "System is non   compliant with standards.",
            "System is non_compliant with standards.",
            "Identified as high - risk  ai  system in deployment.",
            "Identified as high_risk ai system in deployment.",
            "Identified as high--risk ai system in deployment.",
            "The deployer has statutory   duty to respond.",
        ],
    )
    def test_bypass_resistance_punctuation_and_whitespace(
        self, linter: EUOutputLinter, bypass_attempt: str
    ) -> None:
        """Linter detects prohibited phrases despite punctuation delimiters and whitespace padding."""
        findings = linter.lint_text(bypass_attempt, "test_field")
        assert len(findings) >= 1
        assert any(f.finding_code == EULinterResult.BLOCKED_PROHIBITED_TERM.value for f in findings)

    @pytest.mark.parametrize(
        "allowlisted_phrase",
        [
            "not legal advice, a legal determination, or a finding of compliance or noncompliance.",
            "Applicability depends on compliance or noncompliance context.",
            "News sources cited an alleged violation reported by former employees.",
            "Regulators received an alleged breach notification from a competitor.",
            "Complainants submitted a reported violation to the data protection agency.",
            "System exhibits potential high-risk area correspondence under Annex III.",
            "Demonstrates potential conceptual relevance to high-risk areas in recruitment.",
            "Preliminary screen indicates conceptual relevance to Article 5 concepts.",
            "Facts demonstrate serious incident reporting relevance under Article 3(49).",
            "Identified serious incident reporting context in hospital records.",
        ],
    )
    def test_qualified_allowlist_preserves_permitted_phrases(
        self, linter: EUOutputLinter, allowlisted_phrase: str
    ) -> None:
        """Permitted qualified phrases do not trigger false-positive blocks."""
        findings = linter.lint_text(allowlisted_phrase, "rationale")
        assert len(findings) == 0, f"False positive triggered on: {allowlisted_phrase}"

    def test_allowlist_does_not_mask_surrounding_violations(
        self, linter: EUOutputLinter
    ) -> None:
        """An allowlisted phrase in one clause does not mask a true violation in another clause."""
        compound_text = (
            "Complainants noted an alleged violation by the provider. "
            "However, the company committed an illegal breach of privacy rules."
        )
        findings = linter.lint_text(compound_text, "rationale")
        assert len(findings) >= 1
        matched_texts = [f.matched_text.lower() for f in findings if f.matched_text]
        assert "illegal" in matched_texts or "breach" in matched_texts

    def test_blank_and_null_values_safe(self, linter: EUOutputLinter) -> None:
        """Empty strings, whitespace, and None cleanly return zero findings."""
        assert linter.lint_text(None, "empty_field") == []
        assert linter.lint_text("", "empty_field") == []
        assert linter.lint_text("   \n\t  ", "empty_field") == []


class TestEUOutputLinterScreenTraversal:
    """Test full screen structural and nested field linting."""

    def test_clean_screen_passes_linter(
        self, linter: EUOutputLinter, clean_screen_schema: EULegalRelevanceScreenSchema
    ) -> None:
        """A properly formatted, neutral, approved screen passes all linter checks."""
        report = linter.lint_screen(clean_screen_schema)
        assert report.is_clean is True
        assert report.overall_result == EULinterResult.PASS.value
        assert len(report.findings) == 0
        assert report.inspected_fields_count > 0

    def test_top_level_rationale_violation_blocked(
        self, linter: EUOutputLinter, clean_screen_schema: EULegalRelevanceScreenSchema
    ) -> None:
        """Prohibited language in top-level rationale blocks the screen."""
        data = clean_screen_schema.model_dump()
        data["rationale"] = "The system committed an unlawful breach of safety regulations."

        report = linter.lint_screen(data)
        assert report.is_clean is False
        assert report.overall_result == EULinterResult.BLOCKED_PROHIBITED_TERM.value
        assert any(f.field_name == "rationale" for f in report.findings)

    @pytest.mark.parametrize(
        "fact_field",
        ["known_facts", "unknowns", "disputed_facts", "missing_facts", "follow_up_questions"],
    )
    def test_fact_lists_violations_blocked(
        self,
        linter: EUOutputLinter,
        clean_screen_schema: EULegalRelevanceScreenSchema,
        fact_field: str,
    ) -> None:
        """Prohibited language in any fact or inquiry list item blocks the screen."""
        data = clean_screen_schema.model_dump()
        data[fact_field] = ["System was verified to be in illegal non-compliance."]

        report = linter.lint_screen(data)
        assert report.is_clean is False
        assert any(fact_field in f.field_name for f in report.findings)

    def test_nested_conceptual_findings_violation_blocked(
        self, linter: EUOutputLinter, clean_screen_schema: EULegalRelevanceScreenSchema
    ) -> None:
        """Prohibited language nested inside metadata_json conceptual findings is detected and blocked."""
        data = clean_screen_schema.model_dump()
        data["metadata_json"]["conceptual_findings"][0]["finding_rationale"] = (
            "System operates as a prohibited AI system under statutory mandates."
        )

        report = linter.lint_screen(data)
        assert report.is_clean is False
        assert any("conceptual_findings[0].finding_rationale" in f.field_name for f in report.findings)

    def test_reviewer_notes_violation_blocked(
        self, linter: EUOutputLinter, clean_screen_schema: EULegalRelevanceScreenSchema
    ) -> None:
        """Prohibited language entered by a human reviewer in reviewer notes is detected and blocked."""
        data = clean_screen_schema.model_dump()
        data["metadata_json"]["reviewer_notes"] = "In my view this is a clear violation."

        report = linter.lint_screen(data)
        assert report.is_clean is False
        assert any("reviewer_notes" in f.field_name for f in report.findings)

    def test_unapproved_status_blocked(
        self, linter: EUOutputLinter, clean_screen_schema: EULegalRelevanceScreenSchema
    ) -> None:
        """Screen with status other than APPROVED_INFORMATIONAL is blocked for output."""
        data = clean_screen_schema.model_dump()
        data["status"] = EUScreenStatus.PENDING_REVIEW

        report = linter.lint_screen(data)
        assert report.is_clean is False
        assert any(f.finding_code == EULinterResult.BLOCKED_UNAPPROVED_STATUS.value for f in report.findings)

    def test_altered_disclaimer_text_blocked(
        self, linter: EUOutputLinter, clean_screen_schema: EULegalRelevanceScreenSchema
    ) -> None:
        """Screen with altered or truncated disclaimer text is blocked."""
        data = clean_screen_schema.model_dump()
        data["disclaimer_text"] = "Informational governance screen only."

        report = linter.lint_screen(data)
        assert report.is_clean is False
        assert any(f.finding_code == EULinterResult.BLOCKED_MISSING_DISCLAIMER.value for f in report.findings)

    def test_stale_or_superseded_reference_set_blocked(
        self, linter: EUOutputLinter, clean_screen_schema: EULegalRelevanceScreenSchema
    ) -> None:
        """Screen evaluated against a superseded framework reference set is blocked."""
        superseded_ref = {
            "id": "eu-ai-act-2024-1689-legacy",
            "framework_code": FrameworkCode.EU_AI_ACT,
            "status": FrameworkStatus.SUPERSEDED,
        }
        report = linter.lint_screen(clean_screen_schema, reference_set=superseded_ref)
        assert report.is_clean is False
        assert any(f.finding_code == EULinterResult.BLOCKED_STALE_REFERENCE_SET.value for f in report.findings)

    def test_invalid_reference_set_blocked(
        self, linter: EUOutputLinter, clean_screen_schema: EULegalRelevanceScreenSchema
    ) -> None:
        """Screen evaluated against a non-EU AI Act reference set is blocked."""
        oecd_ref = {
            "id": "oecd-principles-2024",
            "framework_code": FrameworkCode.OECD_AI_PRINCIPLES,
            "status": FrameworkStatus.ACTIVE,
        }
        report = linter.lint_screen(clean_screen_schema, reference_set=oecd_ref)
        assert report.is_clean is False
        assert any(f.finding_code == EULinterResult.BLOCKED_INVALID_REFERENCE.value for f in report.findings)

    def test_missing_evidence_links_blocked(
        self, linter: EUOutputLinter, clean_screen_schema: EULegalRelevanceScreenSchema
    ) -> None:
        """Screen with zero primary evidence links is blocked."""
        data = clean_screen_schema.model_dump()
        data["evidence_ids"] = []

        report = linter.lint_screen(data, evidence_links=[])
        assert report.is_clean is False
        assert any(f.finding_code == EULinterResult.BLOCKED_MISSING_EVIDENCE.value for f in report.findings)

    def test_report_helper_methods(
        self, linter: EUOutputLinter, clean_screen_schema: EULegalRelevanceScreenSchema
    ) -> None:
        """Verify has_violations and block_reasons convenience methods on EULinterReport."""
        data = clean_screen_schema.model_dump()
        data["rationale"] = "The operator committed a breach."

        report = linter.lint_screen(data)
        assert report.has_violations is True
        reasons = report.block_reasons()
        assert len(reasons) >= 1
        assert any("breach" in r for r in reasons)
