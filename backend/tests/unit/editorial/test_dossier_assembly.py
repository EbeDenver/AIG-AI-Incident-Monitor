"""Unit tests for EditorialDossierAssembler verifying deterministic assembly."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from ai_incident_monitor.editorial.assembly import (
    DEFAULT_METHODOLOGY_NOTES,
    EditorialDossierAssembler,
)
from ai_incident_monitor.editorial.enums import (
    EditorialDossierStatus,
    EditorialScopeType,
)
from ai_incident_monitor.editorial.models import (
    EDITORIAL_DISCLAIMER_TEXT,
    EDITORIAL_DISCLAIMER_VERSION,
    EditorialCandidate,
)


def make_candidate(
    incident_id: str,
    title: str,
    severity_score: float | None = None,
    severity_tier: str | None = None,
    evidence_count: int = 2,
    has_dispute: bool = False,
    is_eligible: bool = True,
    eu_status: str | None = None,
) -> EditorialCandidate:
    disputes = (
        [
            {
                "topic": "Claim dispute",
                "position_a": "Pos A",
                "source_a": "Src A",
                "position_b": "Pos B",
                "source_b": "Src B",
            }
        ]
        if has_dispute
        else []
    )
    return EditorialCandidate(
        incident_id=incident_id,
        title=title,
        summary=f"Summary for {incident_id}",
        incident_date_str="2026-03-01",
        evidence_ids=[f"ev_{incident_id}_{i}" for i in range(evidence_count)],
        primary_source_url=f"https://example.com/{incident_id}",
        primary_source_publisher="Tech Reporter",
        primary_source_date="2026-03-01",
        source_version_hash="1" * 64,
        severity_tier=severity_tier,
        severity_score=severity_score,
        known_facts=[
            {
                "statement": f"Fact about {incident_id}",
                "source_id": f"ev_{incident_id}_0",
                "evidence_id": f"ev_{incident_id}_0",
                "is_allegation": False,
                "attribution": "Primary Source",
            }
        ],
        unknowns=[
            {
                "question": f"Unknown open question for {incident_id}",
                "domain": "Technical",
                "impact": "Investigation",
            }
        ],
        disputed_claims=disputes,
        eu_screen_id=f"eu_{incident_id}" if eu_status else None,
        eu_screen_status=eu_status,
        eu_screen_eligible=(eu_status == "APPROVED_INFORMATIONAL"),
        eu_commentary="EU Informational Note" if eu_status == "APPROVED_INFORMATIONAL" else None,
        is_eligible=is_eligible,
        exclusion_reasons=[] if is_eligible else ["Excluded"],
    )


class TestEditorialDossierAssembly:
    def test_assembly_creates_assembled_status_and_content_hash(self) -> None:
        c1 = make_candidate("inc_001", "Severe Outage", severity_score=85.0, severity_tier="TIER_4_CRITICAL")
        c2 = make_candidate("inc_002", "Minor Glitch", severity_score=25.0, severity_tier="TIER_1_LOW")

        assembler = EditorialDossierAssembler()
        dossier = assembler.assemble(
            candidates=[c1, c2],
            title="Weekly Incident Dossier",
            scope_type=EditorialScopeType.WEEKLY,
        )

        assert dossier.status == EditorialDossierStatus.ASSEMBLED
        assert dossier.content_hash is not None
        assert len(dossier.content_hash) == 64
        assert dossier.disclaimer_version == EDITORIAL_DISCLAIMER_VERSION
        assert dossier.disclaimer_text == EDITORIAL_DISCLAIMER_TEXT
        assert len(dossier.entries) == 2

    def test_entry_ordering_is_deterministic_by_severity(self) -> None:
        c_low = make_candidate("inc_001", "Low Severity", severity_score=20.0)
        c_high = make_candidate("inc_002", "High Severity", severity_score=90.0)
        c_med = make_candidate("inc_003", "Medium Severity", severity_score=50.0)

        assembler = EditorialDossierAssembler()
        # Pass in scrambled order
        dossier = assembler.assemble(
            candidates=[c_low, c_high, c_med],
            title="Severity Ordered Dossier",
        )

        assert dossier.entries[0].incident_id == "inc_002"  # 90.0
        assert dossier.entries[0].entry_order == 1
        assert dossier.entries[1].incident_id == "inc_003"  # 50.0
        assert dossier.entries[1].entry_order == 2
        assert dossier.entries[2].incident_id == "inc_001"  # 20.0
        assert dossier.entries[2].entry_order == 3

    def test_repeated_assembly_yields_identical_content_hash(self) -> None:
        c1 = make_candidate("inc_001", "Event Alpha", severity_score=70.0)
        c2 = make_candidate("inc_002", "Event Beta", severity_score=40.0)

        assembler = EditorialDossierAssembler()
        dossier1 = assembler.assemble(
            candidates=[c1, c2],
            title="Repeatability Test",
            dossier_id="dos_fixed_id",
        )
        dossier2 = assembler.assemble(
            candidates=[c2, c1],  # Reverse input order
            title="Repeatability Test",
            dossier_id="dos_fixed_id",
        )

        assert dossier1.content_hash == dossier2.content_hash
        assert dossier1.canonical_content_dict() == dossier2.canonical_content_dict()

    def test_summary_aggregates_counts_correctly(self) -> None:
        c1 = make_candidate("inc_001", "Event 1", evidence_count=3, has_dispute=True)
        c2 = make_candidate("inc_002", "Event 2", evidence_count=2, has_dispute=False)
        c3 = make_candidate("inc_003", "Event 3", evidence_count=4, has_dispute=True)

        assembler = EditorialDossierAssembler()
        dossier = assembler.assemble(
            candidates=[c1, c2, c3],
            title="Aggregate Test",
        )

        assert dossier.summary.total_incidents == 3
        assert dossier.summary.total_evidence_links == 9
        assert dossier.summary.disputed_incident_count == 2
        assert any("conflicting accounts" in theme for theme in dossier.summary.learning_and_prevention_themes)

    def test_zero_eligible_candidates_raises_value_error(self) -> None:
        ineligible = make_candidate("inc_bad", "No Evidence", is_eligible=False)

        assembler = EditorialDossierAssembler()
        with pytest.raises(ValueError) as exc:
            assembler.assemble(
                candidates=[ineligible],
                title="Invalid Dossier",
            )
        assert "zero eligible candidate incidents" in str(exc.value)

    def test_default_and_custom_methodology_notes(self) -> None:
        c1 = make_candidate("inc_001", "Event 1")
        assembler = EditorialDossierAssembler()

        dossier_default = assembler.assemble(candidates=[c1], title="Default Notes")
        assert dossier_default.methodology_notes == DEFAULT_METHODOLOGY_NOTES

        custom_notes = "Custom methodology approved for forensic evaluation."
        dossier_custom = assembler.assemble(
            candidates=[c1], title="Custom Notes", methodology_notes=custom_notes
        )
        assert dossier_custom.methodology_notes == custom_notes
