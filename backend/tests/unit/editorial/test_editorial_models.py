"""Unit tests for editorial domain models, schemas, canonical hashing, and attestation."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import pytest
from pydantic import ValidationError

from ai_incident_monitor.editorial.enums import (
    EditorialDossierStatus,
    EditorialEntryType,
    EditorialScopeType,
    EditorialValidationCode,
    EditorialValidationSeverity,
)
from ai_incident_monitor.editorial.models import (
    EDITORIAL_ATTESTATION_STATEMENT,
    EDITORIAL_DISCLAIMER_TEXT,
    EDITORIAL_DISCLAIMER_VERSION,
    EditorialCandidate,
    EditorialDossierEntrySchema,
    EditorialDossierSchema,
    EditorialDossierSummary,
    EditorialEntryDispute,
    EditorialEntryFact,
    EditorialEntryUnknown,
    EditorialReviewerAttestationSchema,
    EditorialValidationFinding,
    EditorialValidationReport,
    canonical_sha256,
)


def compute_sample_source_hash(
    incident_id: str = "inc_test_100",
    title: str = "Autonomous Agent Database Purge",
    summary: str = "Autonomous code agent deleted customer production records.",
    evidence_ids: list[str] | None = None,
    claim_count: int = 1,
) -> str:
    payload = {
        "incident_id": incident_id,
        "title": title,
        "summary": summary,
        "evidence_ids": evidence_ids or ["ev_101", "ev_102"],
        "claim_count": claim_count,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def create_sample_entry(
    entry_id: str = "entry_001",
    order: int = 1,
    source_version_hash: str | None = None,
) -> EditorialDossierEntrySchema:
    resolved_hash = source_version_hash or compute_sample_source_hash()
    return EditorialDossierEntrySchema(
        entry_id=entry_id,
        incident_id="inc_test_100",
        entry_order=order,
        entry_type=EditorialEntryType.PRIMARY,
        incident_title="Autonomous Agent Database Purge",
        incident_summary="Autonomous code agent deleted customer production records.",
        incident_date_str="2026-03-01",
        source_evidence_ids=["ev_101", "ev_102"],
        source_version_hash=resolved_hash,
        primary_source_url="https://example.com/reports/incident-100",
        primary_source_publisher="Tech Incident Log",
        primary_source_published_date="2026-03-02",
        known_facts=[
            EditorialEntryFact(
                statement="Agent deleted table 'users' at 04:15 UTC.",
                source_id="ev_101",
                evidence_id="ev_101",
                is_allegation=False,
                attribution="Official Engineering Postmortem",
            )
        ],
        unknowns=[
            EditorialEntryUnknown(
                question="Why did human supervisor bypass the confirmation gate?",
                domain="Human Oversight",
                impact="Root cause determination",
            )
        ],
        disputed_claims=[
            EditorialEntryDispute(
                topic="Advance test execution",
                position_a="Vendor claims testing occurred in staging",
                source_a="Vendor Blog",
                position_b="Customer claims tests ran directly against prod",
                source_b="Customer Incident Report",
            )
        ],
        severity_tier="TIER_3_HIGH",
        severity_score=68.5,
    )


def create_sample_dossier() -> EditorialDossierSchema:
    entry = create_sample_entry()
    summary = EditorialDossierSummary(
        executive_summary="Weekly AI safety monitoring overview covering 1 incident.",
        key_themes=["Autonomous Systems", "Database Operations"],
        total_incidents=1,
        total_evidence_links=2,
        disputed_incident_count=1,
        learning_and_prevention_themes=["Mandatory human dual-authorization for DROP TABLE commands"],
    )
    dossier = EditorialDossierSchema(
        id="dos_2026_w10",
        version=1,
        title="Weekly AI Safety Incident Dossier - Week 10 2026",
        scope_type=EditorialScopeType.WEEKLY,
        coverage_period_start=datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc),
        coverage_period_end=datetime(2026, 3, 7, 23, 59, tzinfo=timezone.utc),
        status=EditorialDossierStatus.ASSEMBLED,
        disclaimer_version=EDITORIAL_DISCLAIMER_VERSION,
        disclaimer_text=EDITORIAL_DISCLAIMER_TEXT,
        methodology_notes="Compiled via AI Incident Monitor deterministic pipeline.",
        summary=summary,
        entries=[entry],
    )
    return dossier.model_copy(update={"content_hash": dossier.compute_content_hash()})


class TestEditorialModels:
    def test_canonical_content_dict_deterministic(self) -> None:
        dossier1 = create_sample_dossier()
        dossier2 = create_sample_dossier()

        dict1 = dossier1.canonical_content_dict()
        dict2 = dossier2.canonical_content_dict()

        assert dict1 == dict2
        assert dossier1.compute_content_hash() == dossier2.compute_content_hash()

    def test_content_hash_sensitive_to_title_change(self) -> None:
        dossier1 = create_sample_dossier()
        hash1 = dossier1.compute_content_hash()

        dossier2 = dossier1.model_copy(update={"title": "Altered Dossier Title"})
        hash2 = dossier2.compute_content_hash()

        assert hash1 != hash2

    def test_content_hash_sensitive_to_entry_order(self) -> None:
        entry1 = create_sample_entry("entry_1", order=1)
        entry2 = create_sample_entry("entry_2", order=2)
        entry2 = entry2.model_copy(update={"incident_id": "inc_test_200", "incident_title": "Second Incident"})

        dossier_a = create_sample_dossier().model_copy(update={"entries": [entry1, entry2]})
        dossier_b = create_sample_dossier().model_copy(update={"entries": [entry2, entry1]})

        assert dossier_a.compute_content_hash() != dossier_b.compute_content_hash()

    def test_content_hash_insensitive_to_mutable_status_or_reviewer(self) -> None:
        dossier1 = create_sample_dossier()
        hash1 = dossier1.compute_content_hash()

        dossier2 = dossier1.model_copy(
            update={
                "status": EditorialDossierStatus.APPROVED_INFORMATIONAL,
                "reviewed_by": "editor_jane_doe",
                "reviewed_at": datetime.now(timezone.utc),
            }
        )
        hash2 = dossier2.compute_content_hash()

        assert hash1 == hash2, "Content hash must represent invariant editorial content, not review metadata"

    def test_reviewer_attestation_requires_is_human_true(self) -> None:
        valid_hash = "b" * 64
        with pytest.raises(ValidationError) as exc:
            EditorialReviewerAttestationSchema(
                reviewer_id="bot_reviewer",
                reviewer_role="Automated Bot",
                is_human=False,
                statement_confirmed=True,
                attestation_statement=EDITORIAL_ATTESTATION_STATEMENT,
                content_hash=valid_hash,
                dossier_id="dos_123",
                dossier_version=1,
            )
        assert "is_human=True" in str(exc.value)

    def test_reviewer_attestation_requires_statement_confirmed(self) -> None:
        valid_hash = "c" * 64
        with pytest.raises(ValidationError) as exc:
            EditorialReviewerAttestationSchema(
                reviewer_id="human_editor",
                reviewer_role="Senior Editor",
                is_human=True,
                statement_confirmed=False,
                attestation_statement=EDITORIAL_ATTESTATION_STATEMENT,
                content_hash=valid_hash,
                dossier_id="dos_123",
                dossier_version=1,
            )
        assert "statement must be explicitly confirmed" in str(exc.value)

    def test_valid_reviewer_attestation(self) -> None:
        valid_hash = "d" * 64
        att = EditorialReviewerAttestationSchema(
            reviewer_id="editor_john",
            reviewer_name="John Doe",
            reviewer_role="Lead Analyst",
            is_human=True,
            statement_confirmed=True,
            content_hash=valid_hash,
            dossier_id="dos_123",
            dossier_version=1,
        )
        assert att.reviewer_id == "editor_john"
        assert att.is_human is True
        assert att.statement_confirmed is True
        assert att.content_hash == valid_hash

    def test_editorial_entry_fact_allegation_attribution(self) -> None:
        fact = EditorialEntryFact(
            statement="Whistleblower alleges bypass occurred.",
            source_id="ev_001",
            evidence_id="ev_001",
            is_allegation=True,
            attribution="Whistleblower Complaint",
        )
        assert fact.is_allegation is True
        assert fact.attribution == "Whistleblower Complaint"

    def test_validation_report_construction(self) -> None:
        finding = EditorialValidationFinding(
            finding_code=EditorialValidationCode.BLOCKED_MISSING_EVIDENCE,
            severity=EditorialValidationSeverity.BLOCKING,
            field_path="entries[0].source_evidence_ids",
            message="Evidence is missing",
        )
        report = EditorialValidationReport(
            is_valid=False,
            dossier_id="dos_test",
            dossier_version=1,
            total_findings=1,
            blocking_count=1,
            warning_count=0,
            findings=[finding],
        )
        assert report.is_valid is False
        assert report.blocking_count == 1
        assert report.findings[0].finding_code == EditorialValidationCode.BLOCKED_MISSING_EVIDENCE
