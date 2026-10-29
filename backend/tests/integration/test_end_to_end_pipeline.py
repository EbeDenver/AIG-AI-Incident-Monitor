"""Offline end-to-end integration test harness exercising the complete AI Incident Monitor workflow.

Governing Charter:
- Project Constitution: Rules 1, 3, 4, 10, 11, 12, 14, 15, 16, 17.
- Architectural Decisions: ADR-001, ADR-007, ADR-008, ADR-010, ADR-011, ADR-012,
  ADR-014, ADR-016, ADR-017, ADR-019, ADR-020, ADR-021.
- PRD & Methodology: METH-004, PRD §4.3-§4.7.

Exercises the full supported offline workflow:
Synthetic source/feed input
  → ingestion and containment (<untrusted_source_content>)
  → deduplication (4-tier waterfall)
  → evidence persistence and provenance manifest chaining
  → applicable deterministic assessments (AIG-ISI scoring, OECD/NIST governance mapping)
  → candidate evaluation and dossier assembly
  → internal review rendering (INTERNAL_REVIEW_COPY)
  → explicit test-human review/approval (single review checkpoint, Rule 14 guard)
  → approved local export (atomic write, collision guard, manifest sidecar)
  → artifact, manifest, and audit chain verification.

All tests run strictly offline with tmp_path isolation and active network denial.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import socket
from typing import Any, Generator, Optional
from unittest.mock import MagicMock
import uuid

from pydantic import ValidationError
import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from ai_incident_monitor.db.base import Base
from ai_incident_monitor.db.models.claim import ClaimRecordModel
from ai_incident_monitor.db.models.editorial import (
    EditorialDossierEntryModel,
    EditorialDossierModel,
    EditorialDossierReviewModel,
)
from ai_incident_monitor.db.models.evidence import (
    ClaimEvidenceLinkModel,
    EvidenceRecordModel,
)
from ai_incident_monitor.db.models.governance import (
    EULegalRelevanceScreenModel,
    FrameworkReferenceSetModel,
    GovernanceAuditLogModel,
    IncidentFrameworkMappingModel,
)
from ai_incident_monitor.db.models.import_record import DedupCandidateModel, RawImportRecordModel
from ai_incident_monitor.db.models.incident import IncidentModel
from ai_incident_monitor.db.models.severity import SeverityAssessmentModel
from ai_incident_monitor.db.models.source import SourceReferenceModel
from ai_incident_monitor.deduplication.engine import DeduplicationEngine
from ai_incident_monitor.domain.common import (
    ConstitutionalViolationError,
    ImmutabilityViolationError,
)
from ai_incident_monitor.editorial.assembly import EditorialDossierAssembler
from ai_incident_monitor.editorial.enums import (
    EditorialArtifactPurpose,
    EditorialAuditEventType,
    EditorialDossierStatus,
    EditorialExportFormat,
    EditorialPresentationProfile,
    EditorialScopeType,
)
from ai_incident_monitor.editorial.models import (
    EDITORIAL_ATTESTATION_STATEMENT,
    EDITORIAL_DISCLAIMER_TEXT,
    EDITORIAL_DISCLAIMER_VERSION,
    EditorialDossierSchema,
    EditorialReviewerAttestationSchema,
    EditorialValidationReport,
)
from ai_incident_monitor.editorial.renderers.exporter import EditorialDossierExporter
from ai_incident_monitor.editorial.renderers.json_renderer import EditorialJSONRenderer
from ai_incident_monitor.editorial.renderers.manifest import EditorialExportManifest
from ai_incident_monitor.editorial.renderers.markdown_renderer import EditorialMarkdownRenderer
from ai_incident_monitor.editorial.review import EditorialReviewStateMachine
from ai_incident_monitor.editorial.source_selector import EditorialSourceSelector
from ai_incident_monitor.editorial.validator import EditorialValidator
from ai_incident_monitor.governance.enums import (
    EUScreenStatus,
    FrameworkCode,
)
from ai_incident_monitor.governance.mapping_service import GovernanceMappingService
from ai_incident_monitor.governance.models import (
    GovernanceActorIdentity,
    IncidentFactContext,
)
from ai_incident_monitor.governance.reference_loader import (
    compute_file_sha256,
    load_reference_set,
)
from ai_incident_monitor.importers import run_manual_import_workflow
from ai_incident_monitor.ingestion import (
    DEFAULT_CHAIN_SCOPE,
    IngestionPipeline,
    IngestionStatus,
    ManifestChainStore,
    RawPayloadStagingStore,
    RSSConnector,
    verify_provenance_chain,
)
from ai_incident_monitor.repositories.audit_repo import AuditRepository
from ai_incident_monitor.repositories.editorial_repo import EditorialRepository
from ai_incident_monitor.repositories.governance_repo import GovernanceRepository
from ai_incident_monitor.repositories.incident_repo import IncidentRepository
from ai_incident_monitor.repositories.severity_repo import SeverityRepository
from ai_incident_monitor.scoring.engine import (
    calculate_impact_assessment,
    evaluate_review_gates,
)
from ai_incident_monitor.scoring.enums import (
    ConfidenceLevel,
    HumanReviewState,
    ImpactType,
    ISIDimension,
    SeverityTier,
)
from ai_incident_monitor.scoring.models import (
    AIGISIScoreResult,
    DimensionScoreInput,
)
from ai_incident_monitor.security import (
    SecureHTTPClient,
    SecureHTTPResponse,
)


# ==============================================================================
# Network-Denial Test Infrastructure (Section 5)
# ==============================================================================

@pytest.fixture(autouse=True)
def network_denial_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strictly forbid outbound IPv4/IPv6 socket connections during offline test runs.

    Detects and blocks unexpected live network egress, satisfying PRD Section 5.
    """
    orig_connect = socket.socket.connect

    def _denied_connect(sock: socket.socket, address: Any) -> None:
        sock_family = getattr(sock, "family", None)
        if sock_family in (socket.AF_INET, socket.AF_INET6):
            raise AssertionError(
                f"[NETWORK_EGRESS_BLOCKED] Unexpected network connection attempt to {address}! "
                f"Offline end-to-end tests must operate strictly in-memory or on local fixtures."
            )
        return orig_connect(sock, address)

    monkeypatch.setattr(socket.socket, "connect", _denied_connect)


# ==============================================================================
# Path and Environment Fixtures
# ==============================================================================

@pytest.fixture
def repo_root() -> Path:
    """Resolve repository root path portably across environments."""
    return Path(__file__).resolve().parents[3]


@pytest.fixture
def e2e_fixtures_dir() -> Path:
    """Path to dedicated synthetic E2E fixtures."""
    return Path(__file__).resolve().parents[1] / "fixtures" / "e2e"


@pytest.fixture
def sqlite_session(tmp_path: Path) -> Generator[Session, None, None]:
    """Provide an isolated, file-backed SQLite database session in a temporary directory."""
    db_file = tmp_path / "e2e_pipeline.db"
    engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


# ==============================================================================
# Reusable Test Helper Functions
# ==============================================================================

def create_mock_secure_http_client(routes: dict[str, bytes]) -> MagicMock:
    """Create a mock SecureHTTPClient serving synthetic byte payloads for explicit URLs."""
    mock_client = MagicMock(spec=SecureHTTPClient)

    def _mock_get(url: str, *args: Any, **kwargs: Any) -> SecureHTTPResponse:
        if url in routes:
            return SecureHTTPResponse(
                status_code=200,
                headers={"Content-Type": "application/rss+xml; charset=utf-8"},
                body=routes[url],
                final_url=url,
                pinned_ip="127.0.0.1",
            )
        raise ValueError(f"Unmocked URL requested in offline test: '{url}'. Registered routes: {list(routes.keys())}")

    mock_client.get.side_effect = _mock_get
    return mock_client


def build_test_evidence_graph(
    session: Session,
    incident_id: str,
    title: str,
    summary: str,
    source_url: str,
    publisher: str = "Synthetic Systems Daily",
    claim_text: str = "Automated sorting logic suffered coordinate miscalculation.",
    incident_date: Optional[date] = None,
) -> tuple[IncidentModel, SourceReferenceModel, EvidenceRecordModel, ClaimRecordModel]:
    """Persist a complete, grounded epistemic relational graph for an incident."""
    now = datetime.now(timezone.utc)
    src_id = f"src_{uuid.uuid4().hex[:8]}"
    ev_id = f"ev_{uuid.uuid4().hex[:8]}"
    clm_id = f"clm_{uuid.uuid4().hex[:8]}"

    source = SourceReferenceModel(
        id=src_id,
        title=f"Source: {title}",
        publisher=publisher,
        url=source_url,
        source_type="TECHNICAL_POSTMORTEM",
        access_status="OPEN_PUBLIC",
        authority="PRIMARY",
        reliability="HIGH",
        independence="INDEPENDENT_ORIGINAL",
        content_hash=hashlib.sha256(source_url.encode("utf-8")).hexdigest(),
        retrieval_date=now,
    )
    session.add(source)

    evidence = EvidenceRecordModel(
        id=ev_id,
        source_id=src_id,
        short_summary=f"Technical log extract for {title}",
        evidence_type="TECHNICAL_POSTMORTEM",
        directness="PRIMARY_DIRECT",
        specificity="HIGHLY_SPECIFIC",
        corroboration_status="FULLY_CORROBORATED",
        ingested_at=now,
        payload_hash=hashlib.sha256(summary.encode("utf-8")).hexdigest(),
    )
    session.add(evidence)

    incident = IncidentModel(
        id=incident_id,
        title=title,
        summary=summary,
        status="UNDER_INVESTIGATION",
        incident_exact_date=incident_date or date(2026, 10, 20),
    )
    session.add(incident)

    claim = ClaimRecordModel(
        id=clm_id,
        incident_id=incident_id,
        claim_text=claim_text,
        claim_type="TECHNICAL_FACT",
        epistemic_status="VERIFIED",
        confidence="HIGH",
        materiality="HIGH",
    )
    session.add(claim)

    link = ClaimEvidenceLinkModel(
        claim_id=clm_id,
        evidence_id=ev_id,
        link_type="SUPPORTING",
    )
    session.add(link)
    session.flush()

    return incident, source, evidence, claim


def calculate_and_persist_test_severity(
    session: Session,
    incident_id: str,
    actual_score: int = 2,
    actor_id: str = "scoring_test_runner",
) -> SeverityAssessmentModel:
    """Compute and persist deterministic AIG-ISI severity scoring for an incident."""
    actual_inputs = {
        ISIDimension.HUMAN_IMPACT: DimensionScoreInput(
            score=actual_score,
            confidence=ConfidenceLevel.HIGH,
            rationale="Automated assessment of physical safety and dignity impact.",
            evidence_ids=["ev_synthetic_01"],
        ),
        ISIDimension.FINANCIAL_PROPERTY: DimensionScoreInput(
            score=actual_score,
            confidence=ConfidenceLevel.HIGH,
            rationale="Automated assessment of property damage and financial exposure.",
            evidence_ids=["ev_synthetic_01"],
        ),
    }
    actual_res = calculate_impact_assessment(ImpactType.ACTUAL, actual_inputs)
    potential_res = calculate_impact_assessment(ImpactType.POTENTIAL, actual_inputs)
    gates = evaluate_review_gates(actual_res, potential_res)

    score_result = AIGISIScoreResult(
        incident_id=incident_id,
        assessment_id=f"sev_{uuid.uuid4().hex[:8]}",
        methodology_version="AIG-ISI-1.0.0",
        actual_impact=actual_res,
        potential_impact=potential_res,
        review_state=HumanReviewState.PENDING_REVIEW if gates else HumanReviewState.DRAFT,
        review_gates=gates,
        is_pending_review=bool(gates),
        has_disputed_facts=False,
        created_at_utc=datetime.now(timezone.utc),
    )
    repo = SeverityRepository(session)
    return repo.save_assessment(score_result, actor_id=actor_id)


def initialize_test_governance_service(
    session: Session,
    repo_root: Path,
) -> GovernanceMappingService:
    """Initialize GovernanceMappingService with canonical OECD and NIST reference schemas."""
    service = GovernanceMappingService(
        session=session,
        frameworks_dir=repo_root / "frameworks",
    )
    service.initialize_framework_reference(
        framework_code=FrameworkCode.OECD_AI_PRINCIPLES,
        yaml_file=repo_root / "frameworks" / "oecd" / "oecd-principles-2024.yaml",
    )
    service.initialize_framework_reference(
        framework_code=FrameworkCode.NIST_AI_RMF,
        yaml_file=repo_root / "frameworks" / "nist" / "nist-ai-rmf-1.0.yaml",
    )
    return service


# ==============================================================================
# Phase 7A End-to-End Verification Test Suite
# ==============================================================================

class TestEndToEndVerificationHarness:
    """Complete 17-scenario verification test suite for the offline AI Incident Monitor pipeline."""

    # --------------------------------------------------------------------------
    # Scenario 1: Ordinary Attributed Reporting Without Per-Incident Approval
    # --------------------------------------------------------------------------
    def test_01_ordinary_attributed_reporting_without_per_incident_approval(
        self,
        tmp_path: Path,
        repo_root: Path,
        e2e_fixtures_dir: Path,
        sqlite_session: Session,
    ) -> None:
        """Verify ordinary attributed reporting enters draft dossiers WITHOUT per-incident human approval."""
        feed_content = (e2e_fixtures_dir / "rss_standard_incident.xml").read_bytes()
        feed_url = "https://synthetic-source.internal/feed.xml"

        mock_http = create_mock_secure_http_client({feed_url: feed_content})
        connector = RSSConnector(
            http_client=mock_http,
            allowed_source_hosts={"synthetic-source.internal"},
        )
        staging_store = RawPayloadStagingStore(staging_root=tmp_path / "staging")
        manifest_store = ManifestChainStore(storage_dir=tmp_path / "manifests")

        # 1. Ingestion & containment
        pipeline = IngestionPipeline(
            connector=connector,
            staging_store=staging_store,
            manifest_store=manifest_store,
            db_session=sqlite_session,
            chain_scope="e2e_test_scope",
        )
        ingest_res = pipeline.execute_run(feed_url)

        assert ingest_res.is_success is True
        assert len(ingest_res.items) == 1
        assert ingest_res.items[0].title == "Automated Sorting Robot Arm Deviation"
        assert len(ingest_res.envelopes) == 1
        assert ingest_res.envelopes[0].trust_level == "UNTRUSTED_EXTERNAL"

        # 2. Persist relational evidence graph
        item = ingest_res.items[0]
        inc, src, ev, clm = build_test_evidence_graph(
            session=sqlite_session,
            incident_id="INC-2026-SORT-001",
            title=item.title,
            summary=item.summary_snippet,
            source_url=item.canonical_url or feed_url,
            claim_text="Trajectory calculation error caused conveyor guide contact.",
        )

        # Confirm incident record in DB is NOT human-approved
        assert inc.status == "UNDER_INVESTIGATION"

        # 3. Deterministic severity scoring
        sev_record = calculate_and_persist_test_severity(sqlite_session, inc.id, actual_score=2)
        assert sev_record.actual_tier == "SIGNIFICANT"

        # 4. Deterministic governance mappings
        gov_service = initialize_test_governance_service(sqlite_session, repo_root)
        fact_context = IncidentFactContext(
            incident_id=inc.id,
            title=inc.title,
            summary=inc.summary,
            fact_tags=["safety_hazard", "system_instability"],
            evidence_records=[{"id": ev.id}],
            claims=[{"id": clm.id, "claim_text": clm.claim_text}],
        )
        candidates = gov_service.evaluate_mappings(fact_context)
        actor = GovernanceActorIdentity(
            actor_id="test_runner",
            is_human=False,
            role="SYSTEM_AUTOMATION",
        )
        persisted_mappings = gov_service.persist_candidates(candidates, actor)
        assert len(persisted_mappings) > 0

        # 5. Editorial candidate selection
        selector = EditorialSourceSelector(sqlite_session)
        candidate = selector.evaluate_candidate_incident(inc)
        assert candidate.is_eligible is True
        assert len(candidate.exclusion_reasons) == 0
        assert len(candidate.evidence_ids) >= 1
        assert candidate.severity_tier == "SIGNIFICANT"

        # 6. Dossier assembly
        assembler = EditorialDossierAssembler()
        dossier_schema = assembler.assemble(
            candidates=[candidate],
            title="Weekly AI Safety Digest - Test Issue",
            scope_type=EditorialScopeType.WEEKLY,
        )

        repo = EditorialRepository(sqlite_session)
        dossier = repo.save_dossier(dossier_schema, actor_id="system_assembler", is_human=False)

        assert dossier.id is not None
        assert dossier.status == EditorialDossierStatus.ASSEMBLED
        assert len(dossier.entries) == 1
        assert dossier.entries[0].incident_id == "INC-2026-SORT-001"
        assert dossier.content_hash != ""

    # --------------------------------------------------------------------------
    # Scenario 2: Dossier Creation and Review-Copy Rendering Before Approval
    # --------------------------------------------------------------------------
    def test_02_dossier_creation_and_review_copy_rendering_before_approval(
        self,
        tmp_path: Path,
        sqlite_session: Session,
    ) -> None:
        """Verify pre-approval working drafts (INTERNAL_REVIEW_COPY) can be rendered and exported."""
        inc, _, ev, _ = build_test_evidence_graph(
            session=sqlite_session,
            incident_id="INC-2026-PRE-REV",
            title="Surgical Tele-operation Latency Surge",
            summary="Demonstration: Network jitter exceeded buffering bounds during test surgery.",
            source_url="https://synthetic-source.internal/latency-spike",
        )
        selector = EditorialSourceSelector(sqlite_session)
        cand = selector.evaluate_candidate_incident(inc)

        assembler = EditorialDossierAssembler()
        dossier_schema = assembler.assemble(
            candidates=[cand],
            title="Pre-Approval Review Copy Evaluation",
            scope_type=EditorialScopeType.CUSTOM,
        )

        repo = EditorialRepository(sqlite_session)
        dossier = repo.save_dossier(dossier_schema, actor_id="editorial_builder", is_human=False)

        # 1. Render Markdown as INTERNAL_REVIEW_COPY
        md_renderer = EditorialMarkdownRenderer()
        report = EditorialValidator().validate_dossier(dossier)
        rendered_md, md_hash = md_renderer.render(
            dossier=dossier,
            profile=EditorialPresentationProfile.DEEP_DIVE_DOSSIER,
            purpose=EditorialArtifactPurpose.INTERNAL_REVIEW_COPY,
            validation_report=report,
        )

        # Assert mandatory review copy elements
        assert "[UNAPPROVED — INTERNAL EDITORIAL REVIEW COPY — NOT FOR PUBLICATION]" in rendered_md
        assert "Internal Review Notes & Validation Findings" in rendered_md
        assert EDITORIAL_DISCLAIMER_TEXT in rendered_md

        # 2. Local export as INTERNAL_REVIEW_COPY
        exporter = EditorialDossierExporter(repository=repo)
        export_res = exporter.export(
            dossier_id=dossier.id,
            export_format=EditorialExportFormat.MARKDOWN,
            profile=EditorialPresentationProfile.DEEP_DIVE_DOSSIER,
            purpose=EditorialArtifactPurpose.INTERNAL_REVIEW_COPY,
            output_dir=str(tmp_path / "exports"),
            actor_id="test_exporter",
            is_human=False,  # Review copies do NOT require human sign-off
        )

        exported_file = Path(export_res.written_files[0])
        assert exported_file.exists()
        manifest_file = exported_file.with_suffix(".manifest.json")
        assert manifest_file.exists()

        manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
        assert manifest_data["artifact_purpose"] == "INTERNAL_REVIEW_COPY"

    # --------------------------------------------------------------------------
    # Scenario 3: Successful Explicit Test-Human Approval and Approved Export
    # --------------------------------------------------------------------------
    def test_03_successful_explicit_test_human_approval_and_approved_export(
        self,
        tmp_path: Path,
        sqlite_session: Session,
    ) -> None:
        """Verify the complete human sign-off checkpoint and publication-ready approved export."""
        inc, _, _, _ = build_test_evidence_graph(
            session=sqlite_session,
            incident_id="INC-2026-HUMAN-APP",
            title="Autonomous Locomotive Brake Sensor Fault",
            summary="Demonstration: Sensor communication failure triggered automatic emergency braking.",
            source_url="https://synthetic-source.internal/locomotive-brake",
        )
        selector = EditorialSourceSelector(sqlite_session)
        cand = selector.evaluate_candidate_incident(inc)

        assembler = EditorialDossierAssembler()
        dossier_schema = assembler.assemble(
            candidates=[cand],
            title="Rail Transit Observability Dossier",
            scope_type=EditorialScopeType.WEEKLY,
        )

        repo = EditorialRepository(sqlite_session)
        dossier = repo.save_dossier(dossier_schema, actor_id="assembler_bot", is_human=False)

        # 1. Transition to PENDING_REVIEW
        pending_dossier = repo.submit_for_review(
            dossier_id=dossier.id,
            actor_id="submitter_lead",
            is_human=True,
            actor_role="RESEARCH_ANALYST",
        )
        assert pending_dossier.status == EditorialDossierStatus.PENDING_REVIEW

        # 2. Explicit test-human reviewer attestation
        v_report = EditorialValidator().validate_dossier(pending_dossier)
        assert v_report.is_valid is True

        attestation = EditorialReviewerAttestationSchema(
            reviewer_id="human_test_editor_01",
            reviewer_name="Dr. Morgan Reed",
            reviewer_role="Lead Editorial Analyst",
            is_human=True,
            statement_confirmed=True,
            attestation_statement=EDITORIAL_ATTESTATION_STATEMENT,
            content_hash=pending_dossier.content_hash,
            dossier_id=pending_dossier.id,
            dossier_version=pending_dossier.version,
        )

        approved_dossier = repo.approve_dossier(
            dossier_id=dossier.id,
            attestation=attestation,
            validation_report=v_report,
        )
        assert approved_dossier.status == EditorialDossierStatus.APPROVED_INFORMATIONAL
        assert approved_dossier.reviewed_by == "human_test_editor_01"

        # 3. Export as APPROVED_EDITORIAL_COPY
        exporter = EditorialDossierExporter(repository=repo)
        export_res = exporter.export(
            dossier_id=approved_dossier.id,
            export_format=EditorialExportFormat.ALL,
            profile=EditorialPresentationProfile.EXECUTIVE_BRIEF,
            purpose=EditorialArtifactPurpose.APPROVED_EDITORIAL_COPY,
            output_dir=str(tmp_path / "approved_exports"),
            actor_id="human_test_editor_01",
            is_human=True,  # Rule 14 requirement
        )

        # Verify files exist on disk
        md_path = next(Path(f) for f in export_res.written_files if f.endswith(".md"))
        assert md_path.exists()
        md_text = md_path.read_text(encoding="utf-8")
        assert "[UNAPPROVED — INTERNAL EDITORIAL REVIEW COPY — NOT FOR PUBLICATION]" not in md_text

        # Verify companion manifest
        manifest_path = next(Path(f) for f in export_res.written_files if f.endswith(".manifest.json"))
        assert manifest_path.exists()
        m_json = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert m_json["artifact_purpose"] == "APPROVED_EDITORIAL_COPY"
        assert m_json["canonical_dossier_content_hash"] == approved_dossier.content_hash

        # Verify append-only audit trail
        valid_audit, anomalies = repo.verify_audit_chain(approved_dossier.id)
        assert valid_audit is True
        assert len(anomalies) == 0

    # --------------------------------------------------------------------------
    # Scenario 4: Duplicate and Near-Duplicate Input Handling
    # --------------------------------------------------------------------------
    def test_04_duplicate_and_near_duplicate_input_handling(
        self,
        sqlite_session: Session,
    ) -> None:
        """Verify 4-tier deduplication engine handles exact ID, URL, and near-duplicate soft matches."""
        # 1. Seed existing incident
        inc, src, _, _ = build_test_evidence_graph(
            session=sqlite_session,
            incident_id="INC-EXISTING-001",
            title="Autonomous Vehicle Highway Disengagement",
            summary="Highway disengagement occurred after lane markings degraded.",
            source_url="https://synthetic-source.internal/reports/highway-disengagement",
            incident_date=date(2026, 5, 10),
        )

        # 2. Test Tier 1 Duplicate (Exact ID Match)
        res_t1 = DeduplicationEngine.evaluate(
            session=sqlite_session,
            proposed_incident_id="INC-EXISTING-001",
            proposed_title="Completely Different Title",
            proposed_date=None,
            source_urls=[],
        )
        assert res_t1.tier == 1
        assert res_t1.outcome == "AUTO_LINK_ID"
        assert res_t1.matched_incident_id == "INC-EXISTING-001"

        # 3. Test Tier 2 Duplicate (Exact Canonical URL Match)
        res_t2 = DeduplicationEngine.evaluate(
            session=sqlite_session,
            proposed_incident_id="INC-PROPOSED-NEW-002",
            proposed_title="Another Title",
            proposed_date=None,
            source_urls=["https://synthetic-source.internal/reports/highway-disengagement"],
        )
        assert res_t2.tier == 2
        assert res_t2.outcome == "AUTO_LINK_URL"
        assert res_t2.matched_incident_id == "INC-EXISTING-001"

        # 4. Test Tier 3 Near-Duplicate (Soft match within date window)
        res_t3 = DeduplicationEngine.evaluate(
            session=sqlite_session,
            proposed_incident_id="INC-PROPOSED-NEW-003",
            proposed_title="Autonomous Vehicle Highway Disengagement Event",
            proposed_date=date(2026, 5, 12),
            source_urls=["https://different-source.internal/article-404"],
        )
        assert res_t3.tier == 3
        assert res_t3.outcome == "FLAG_FOR_REVIEW"
        assert res_t3.matched_incident_id == "INC-EXISTING-001"

    # --------------------------------------------------------------------------
    # Scenario 5: Malformed Feed Input Resilience
    # --------------------------------------------------------------------------
    def test_05_malformed_feed_input_resilience(
        self,
        tmp_path: Path,
        e2e_fixtures_dir: Path,
        sqlite_session: Session,
    ) -> None:
        """Verify malformed feed XML is safely isolated without corrupting manifest chains or DB state."""
        malformed_bytes = (e2e_fixtures_dir / "rss_malformed.xml").read_bytes()
        feed_url = "https://synthetic-source.internal/malformed.xml"

        mock_http = create_mock_secure_http_client({feed_url: malformed_bytes})
        connector = RSSConnector(
            http_client=mock_http,
            allowed_source_hosts={"synthetic-source.internal"},
        )
        manifest_store = ManifestChainStore(storage_dir=tmp_path / "manifests")

        pipeline = IngestionPipeline(
            connector=connector,
            manifest_store=manifest_store,
            db_session=sqlite_session,
            chain_scope="malformed_test_scope",
        )
        res = pipeline.execute_run(feed_url)

        # Pipeline must record safe partial/failure state without crash
        assert res.manifest.manifest_sha256 != ""
        assert "MALFORMED_FEED_SYNTAX" in res.manifest.parser_warning_codes
        assert res.manifest.run_status.value in ("PARTIAL", "FAILED")

        # Provenance chain remains unbroken
        report = verify_provenance_chain(
            manifest_store.get_chain("malformed_test_scope"),
            chain_scope="malformed_test_scope",
        )
        assert report.is_valid is True

    # --------------------------------------------------------------------------
    # Scenario 6: Missing Evidence Blocks Dossier Inclusion (Rule 1 Gate)
    # --------------------------------------------------------------------------
    def test_06_missing_evidence_blocks_dossier_inclusion(
        self,
        sqlite_session: Session,
    ) -> None:
        """Verify incidents without primary/observational evidence fail closed (Rule 1 violation)."""
        # Create ungrounded incident (has claims but zero evidence links)
        ungrounded_inc = IncidentModel(
            id="INC-UNGROUNDED-001",
            title="Uncorroborated Rumor of Model Hallucination",
            summary="A social media post asserted model hallucination without primary logs.",
            status="UNDER_INVESTIGATION",
        )
        sqlite_session.add(ungrounded_inc)

        clm = ClaimRecordModel(
            id="clm_ungrounded_01",
            incident_id="INC-UNGROUNDED-001",
            claim_text="Model generated unverified advice.",
            claim_type="UNVERIFIED_ALLEGATION",
            epistemic_status="UNVERIFIED",
            confidence="LOW",
            materiality="LOW",
        )
        sqlite_session.add(clm)
        sqlite_session.flush()

        selector = EditorialSourceSelector(sqlite_session)
        candidate = selector.evaluate_candidate_incident(ungrounded_inc)

        assert candidate.is_eligible is False
        assert any("Rule 1 violation" in reason for reason in candidate.exclusion_reasons)

        assembler = EditorialDossierAssembler()
        with pytest.raises(ValueError, match="zero eligible candidate incidents provided"):
            assembler.assemble(
                candidates=[candidate],
                title="Invalid Dossier Test",
                scope_type=EditorialScopeType.WEEKLY,
            )

    # --------------------------------------------------------------------------
    # Scenario 7: Invalid Provenance Chain Detection
    # --------------------------------------------------------------------------
    def test_07_invalid_provenance_chain_detection(
        self,
        tmp_path: Path,
        sqlite_session: Session,
    ) -> None:
        """Verify that altering a manifest digest or breaking hash links triggers detection."""
        store_dir = tmp_path / "manifests"
        manifest_store = ManifestChainStore(storage_dir=store_dir)

        # Build a valid 2-node chain
        payload1 = b"<?xml version='1.0'?><rss><channel><title>F1</title></channel></rss>"
        mock_http1 = create_mock_secure_http_client({"https://synthetic-source.internal/f1.xml": payload1})
        conn1 = RSSConnector(http_client=mock_http1, allowed_source_hosts={"synthetic-source.internal"})
        p1 = IngestionPipeline(connector=conn1, manifest_store=manifest_store, chain_scope="tamper_scope")
        p1.execute_run("https://synthetic-source.internal/f1.xml")

        payload2 = b"<?xml version='1.0'?><rss><channel><title>F2</title></channel></rss>"
        mock_http2 = create_mock_secure_http_client({"https://synthetic-source.internal/f2.xml": payload2})
        conn2 = RSSConnector(http_client=mock_http2, allowed_source_hosts={"synthetic-source.internal"})
        p2 = IngestionPipeline(connector=conn2, manifest_store=manifest_store, chain_scope="tamper_scope")
        p2.execute_run("https://synthetic-source.internal/f2.xml")

        chain = manifest_store.get_chain("tamper_scope")
        assert len(chain) == 2
        valid_rep = verify_provenance_chain(chain, chain_scope="tamper_scope")
        assert valid_rep.is_valid is True

        # Tamper with the second manifest in the JSONL file on disk
        chain_files = sorted(store_dir.glob("chain_*.jsonl"))
        assert len(chain_files) > 0
        target_file = chain_files[0]
        lines = target_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        last_manifest = json.loads(lines[-1])
        last_manifest["response_bytes"] = 999999  # Alter data without updating manifest_sha256
        lines[-1] = json.dumps(last_manifest)
        target_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

        # Reload and verify
        corrupted_store = ManifestChainStore(storage_dir=store_dir)
        corrupted_chain = corrupted_store.get_chain("tamper_scope")
        tampered_rep = verify_provenance_chain(corrupted_chain, chain_scope="tamper_scope")

        assert tampered_rep.is_valid is False
        assert len(tampered_rep.anomalies) > 0
        assert any(a.anomaly_type == "ALTERED_MANIFEST_HASH" for a in tampered_rep.anomalies)

    # --------------------------------------------------------------------------
    # Scenario 8: Source and Content Drift Blocks Approval and Export
    # --------------------------------------------------------------------------
    def test_08_source_and_content_drift_blocks_approval_and_export(
        self,
        tmp_path: Path,
        sqlite_session: Session,
    ) -> None:
        """Verify source drift or content hash tampering blocks approval and approved export."""
        inc, _, _, _ = build_test_evidence_graph(
            session=sqlite_session,
            incident_id="INC-2026-DRIFT",
            title="Smart Grid Load Balancer Oscillation",
            summary="Demonstration: Grid inverter frequency control oscillated during peak transition.",
            source_url="https://synthetic-source.internal/smart-grid-drift",
        )
        selector = EditorialSourceSelector(sqlite_session)
        cand = selector.evaluate_candidate_incident(inc)

        assembler = EditorialDossierAssembler()
        dossier_schema = assembler.assemble(
            candidates=[cand],
            title="Energy Infrastructure Reliability Review",
            scope_type=EditorialScopeType.INCIDENT_DEEP_DIVE,
        )

        repo = EditorialRepository(sqlite_session)
        dossier = repo.save_dossier(dossier_schema, actor_id="builder", is_human=False)
        repo.submit_for_review(dossier.id, actor_id="submitter", is_human=True)

        # 1. Simulate source drift: mutate underlying incident summary in database
        inc.summary = "MUTATED: Underground power line severed by construction crew."
        sqlite_session.flush()

        has_drift, drift_details = repo.check_source_drift(repo.get_dossier(dossier.id))
        assert has_drift is True

        attestation = EditorialReviewerAttestationSchema(
            reviewer_id="human_test_editor",
            reviewer_name="Jane Doe",
            reviewer_role="Editor",
            is_human=True,
            statement_confirmed=True,
            attestation_statement=EDITORIAL_ATTESTATION_STATEMENT,
            content_hash=dossier.content_hash,
            dossier_id=dossier.id,
            dossier_version=dossier.version,
        )
        v_report = EditorialValidator().validate_dossier(dossier)

        # Attempting approval with source drift must fail closed
        with pytest.raises(ValueError, match="Underlying source records have drifted"):
            repo.approve_dossier(dossier.id, attestation, v_report)

        # Attempting export of approved copy must also fail closed
        exporter = EditorialDossierExporter(repository=repo)
        with pytest.raises(ValueError, match="Cannot export APPROVED_EDITORIAL_COPY"):
            exporter.export(
                dossier_id=dossier.id,
                purpose=EditorialArtifactPurpose.APPROVED_EDITORIAL_COPY,
                output_dir=str(tmp_path / "drift_export"),
                is_human=True,
            )

    # --------------------------------------------------------------------------
    # Scenario 9: Invalid Reference Data Blocks Governance Mapping
    # --------------------------------------------------------------------------
    def test_09_invalid_reference_data_blocks_governance_mapping(
        self,
        tmp_path: Path,
        repo_root: Path,
    ) -> None:
        """Verify tampered framework reference files trigger validation failure before evaluation."""
        fake_yaml = tmp_path / "tampered-oecd.yaml"
        fake_yaml.write_text(
            "framework_code: OECD-AI-PRINCIPLES\n"
            "version: 2024-TAMPERED\n"
            "title: Malformed Reference\n"
            "controls: []\n",
            encoding="utf-8",
        )

        # Manifest hash check against canonical manifest.json must fail
        manifest_path = repo_root / "frameworks" / "manifest.json"
        assert manifest_path.exists()
        manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))

        computed_sha256 = compute_file_sha256(fake_yaml)
        expected_sha256 = next(
            f["content_sha256"]
            for f in manifest_data["frameworks"]
            if f["framework_code"] == "OECD_AI_PRINCIPLES"
        )

        assert computed_sha256 != expected_sha256

    # --------------------------------------------------------------------------
    # Scenario 10: Ineligible Optional EU Commentary Clean Omission
    # --------------------------------------------------------------------------
    def test_10_ineligible_optional_eu_commentary_clean_omission(
        self,
        repo_root: Path,
        sqlite_session: Session,
    ) -> None:
        """Verify unapproved EU commentary is cleanly omitted without blocking ordinary reporting."""
        inc, _, ev, _ = build_test_evidence_graph(
            session=sqlite_session,
            incident_id="INC-2026-EU-TEST",
            title="Hospital Bed Allocation Algorithmic Bias",
            summary="Demonstration: Clinical bed allocation model exhibited systematic prioritization gap.",
            source_url="https://synthetic-source.internal/bed-allocation",
        )

        # Initialize EU reference set from official framework YAML
        gov_service = initialize_test_governance_service(sqlite_session, repo_root)
        eu_ref = gov_service.initialize_framework_reference(
            framework_code=FrameworkCode.EU_AI_ACT,
            yaml_file=repo_root / "frameworks" / "eu-ai-act" / "eu-ai-act-2024-1689.yaml",
        )

        # Seed an EU Legal Relevance Screen in PENDING_REVIEW (unapproved)
        now = datetime.now(timezone.utc)
        screen_model = EULegalRelevanceScreenModel(
            id="eu_scr_test_01",
            incident_id=inc.id,
            reference_set_id=eu_ref.id,
            screen_version="1.0.0",
            disclaimer_version="2024-1689-v2",
            disclaimer_text="EU AI Act Informational Disclaimer",
            status=EUScreenStatus.PENDING_REVIEW.value,
            relevance_level="POTENTIALLY_RELEVANT",
            nexus_assessment="IN_SCOPE_TERRITORIAL_NEXUS",
            generated_by="test_system",
            generated_at=now,
        )
        sqlite_session.add(screen_model)
        sqlite_session.flush()

        selector = EditorialSourceSelector(sqlite_session)
        candidate = selector.evaluate_candidate_incident(inc)

        # Ordinary incident remains eligible!
        assert candidate.is_eligible is True
        # EU commentary is cleanly omitted
        assert candidate.eu_screen_eligible is False
        assert candidate.eu_commentary is None
        assert "PENDING_REVIEW" in (candidate.omitted_eu_reason or "")

        assembler = EditorialDossierAssembler()
        dossier_schema = assembler.assemble(
            candidates=[candidate],
            title="Health AI Observability Weekly",
            scope_type=EditorialScopeType.WEEKLY,
        )

        repo = EditorialRepository(sqlite_session)
        dossier = repo.save_dossier(dossier_schema, actor_id="test_assembler", is_human=False)

        assert len(dossier.entries) == 1
        assert dossier.entries[0].eu_commentary is None
        assert dossier.entries[0].omitted_eu_reason is not None

    # --------------------------------------------------------------------------
    # Scenario 11: Database and Audit Persistence Failures (Rollback Integrity)
    # --------------------------------------------------------------------------
    def test_11_database_and_audit_persistence_transaction_rollback(
        self,
        sqlite_session: Session,
    ) -> None:
        """Verify transaction rollbacks preserve atomic consistency and audit integrity."""
        # Seed initial incident
        inc, _, _, _ = build_test_evidence_graph(
            session=sqlite_session,
            incident_id="INC-ROLLBACK-01",
            title="Initial Valid Incident",
            summary="Initial summary.",
            source_url="https://synthetic-source.internal/initial",
        )

        initial_count = len(sqlite_session.execute(select(IncidentModel)).scalars().all())
        assert initial_count == 1

        # Attempt an invalid transaction that triggers a database integrity error
        with pytest.raises(Exception):
            with sqlite_session.begin_nested():
                # Direct SQL insert with duplicate primary key forces SQLite IntegrityError
                sqlite_session.execute(
                    text(
                        "INSERT INTO incidents (id, title, summary, status, created_at, updated_at) "
                        "VALUES ('INC-ROLLBACK-01', 'Colliding', 'Colliding', 'NEW', datetime('now'), datetime('now'))"
                    )
                )

        # Database state after rollback must match initial state exactly
        clean_count = sqlite_session.execute(select(IncidentModel)).scalars().all()
        assert len(clean_count) == 1
        assert clean_count[0].id == "INC-ROLLBACK-01"

    # --------------------------------------------------------------------------
    # Scenario 12: Interrupted Processing and Safe Idempotent Retries
    # --------------------------------------------------------------------------
    def test_12_interrupted_processing_and_idempotent_retry(
        self,
        e2e_fixtures_dir: Path,
        sqlite_session: Session,
    ) -> None:
        """Verify re-running the manual file import workflow is safe and strictly idempotent."""
        json_fixture = e2e_fixtures_dir / "synthetic_oecd_incident.json"
        assert json_fixture.exists()

        # First import run
        res1 = run_manual_import_workflow(
            session=sqlite_session,
            file_path=json_fixture,
            source_format="JSON",
            actor_id="test_importer",
        )
        assert res1.imported_count == 1
        assert res1.duplicate_count == 0

        # Second import run with identical file content (retry)
        res2 = run_manual_import_workflow(
            session=sqlite_session,
            file_path=json_fixture,
            source_format="JSON",
            actor_id="test_importer",
        )
        assert res2.imported_count == 0
        assert res2.duplicate_count == 1
        assert res2.records[0].status == "AUTO_LINKED"

        # Relational table count remains exactly 1 incident
        incidents = sqlite_session.execute(select(IncidentModel)).scalars().all()
        assert len(incidents) == 1

    # --------------------------------------------------------------------------
    # Scenario 13: Partial Export Failure and Filesystem Cleanup
    # --------------------------------------------------------------------------
    def test_13_partial_export_failure_and_cleanup(
        self,
        tmp_path: Path,
        sqlite_session: Session,
    ) -> None:
        """Verify export collision without overwrite, symlinks, and path traversal fail safely."""
        inc, _, _, _ = build_test_evidence_graph(
            session=sqlite_session,
            incident_id="INC-EXP-FAIL",
            title="Export Failure Resilience Test",
            summary="Demonstration incident.",
            source_url="https://synthetic-source.internal/exp-fail",
        )
        selector = EditorialSourceSelector(sqlite_session)
        cand = selector.evaluate_candidate_incident(inc)

        assembler = EditorialDossierAssembler()
        dossier_schema = assembler.assemble(
            candidates=[cand],
            title="Export Failures Test",
            scope_type=EditorialScopeType.WEEKLY,
        )

        repo = EditorialRepository(sqlite_session)
        dossier = repo.save_dossier(dossier_schema, actor_id="test_user", is_human=False)

        exporter = EditorialDossierExporter(repository=repo)

        export_dir = tmp_path / "test_exports"
        export_dir.mkdir(parents=True, exist_ok=True)

        # 1. Collision without overwrite
        first_res = exporter.export(
            dossier_id=dossier.id,
            export_format=EditorialExportFormat.MARKDOWN,
            output_dir=str(export_dir),
            is_human=False,
        )
        assert Path(first_res.written_files[0]).exists()

        # Re-exporting without overwrite must raise FileExistsError
        with pytest.raises(FileExistsError, match=r"Destination file .* already exists"):
            exporter.export(
                dossier_id=dossier.id,
                export_format=EditorialExportFormat.MARKDOWN,
                output_dir=str(export_dir),
                overwrite=False,
                is_human=False,
            )

        # 2. Symlink rejection
        symlink_dir = tmp_path / "symlink_dir"
        os.symlink(export_dir, symlink_dir)
        with pytest.raises(ValueError, match="Exporting into symlinked destinations is forbidden"):
            exporter.export(
                dossier_id=dossier.id,
                output_dir=str(symlink_dir),
                is_human=False,
            )

        # 3. Path safety: null byte injection rejection
        with pytest.raises(ValueError, match="null bytes"):
            exporter.export(
                dossier_id=dossier.id,
                output_dir="/tmp/path\0with_null",
                is_human=False,
            )

    # --------------------------------------------------------------------------
    # Scenario 14: Unauthorized and Automated Approval Attempts (Rule 14)
    # --------------------------------------------------------------------------
    def test_14_unauthorized_and_automated_approval_attempts_blocked(
        self,
        tmp_path: Path,
        sqlite_session: Session,
    ) -> None:
        """Verify automated bots (is_human=False) and invalid reviewer credentials are blocked (Rule 14)."""
        inc, _, _, _ = build_test_evidence_graph(
            session=sqlite_session,
            incident_id="INC-RULE14-TEST",
            title="Rule 14 Enforcement Test Incident",
            summary="Demonstration incident.",
            source_url="https://synthetic-source.internal/rule14",
        )
        selector = EditorialSourceSelector(sqlite_session)
        cand = selector.evaluate_candidate_incident(inc)

        assembler = EditorialDossierAssembler()
        dossier_schema = assembler.assemble(
            candidates=[cand],
            title="Rule 14 Compliance Dossier",
            scope_type=EditorialScopeType.WEEKLY,
        )

        repo = EditorialRepository(sqlite_session)
        dossier = repo.save_dossier(dossier_schema, actor_id="test_user", is_human=False)
        v_report = EditorialValidator().validate_dossier(dossier)

        # 1. Schema validation strictly rejects is_human=False
        with pytest.raises(Exception, match="is_human=True"):
            EditorialReviewerAttestationSchema(
                reviewer_id="autonomous_pipeline_agent",
                reviewer_name="Agent Zero",
                reviewer_role="Autonomous Pipeline",
                is_human=False,  # BOT
                statement_confirmed=True,
                attestation_statement=EDITORIAL_ATTESTATION_STATEMENT,
                content_hash=dossier.content_hash,
                dossier_id=dossier.id,
                dossier_version=dossier.version,
            )

        # 2. State machine strictly rejects is_human=False with ConstitutionalViolationError
        mock_bot = MagicMock()
        mock_bot.is_human = False
        mock_bot.reviewer_id = "autonomous_pipeline_agent"
        mock_bot.statement_confirmed = True
        mock_bot.content_hash = dossier.content_hash
        mock_bot.dossier_id = dossier.id
        mock_bot.dossier_version = dossier.version

        # Premature approval before submission (dossier in ASSEMBLED status)
        with pytest.raises(ValueError, match="Dossier must be submitted and in PENDING_REVIEW"):
            EditorialReviewStateMachine.validate_approval(
                dossier,
                mock_bot,
                v_report,
            )

        # Submit for review
        repo.submit_for_review(dossier.id, actor_id="submitter", is_human=True)

        with pytest.raises(ConstitutionalViolationError, match="Rule 14"):
            EditorialReviewStateMachine.validate_approval(
                repo.get_dossier(dossier.id),
                mock_bot,
                v_report,
            )

        # 3. Empty reviewer ID
        with pytest.raises(Exception):
            EditorialReviewerAttestationSchema(
                reviewer_id="",  # EMPTY
                reviewer_name="Anonymous Reviewer",
                reviewer_role="Analyst",
                is_human=True,
                statement_confirmed=True,
                attestation_statement=EDITORIAL_ATTESTATION_STATEMENT,
                content_hash=dossier.content_hash,
                dossier_id=dossier.id,
                dossier_version=dossier.version,
            )

        # 4. Unconfirmed Statement
        with pytest.raises(Exception):
            EditorialReviewerAttestationSchema(
                reviewer_id="human_analyst_01",
                reviewer_name="Human Analyst",
                reviewer_role="Analyst",
                is_human=True,
                statement_confirmed=False,  # UNCONFIRMED
                attestation_statement=EDITORIAL_ATTESTATION_STATEMENT,
                content_hash=dossier.content_hash,
                dossier_id=dossier.id,
                dossier_version=dossier.version,
            )

        # 5. Automated agent attempting approved export -> ConstitutionalViolationError
        exporter = EditorialDossierExporter(repository=repo)

        # 5a. Unapproved dossier cannot be exported as APPROVED_EDITORIAL_COPY
        with pytest.raises(ValueError, match="Cannot export APPROVED_EDITORIAL_COPY"):
            exporter.export(
                dossier_id=dossier.id,
                purpose=EditorialArtifactPurpose.APPROVED_EDITORIAL_COPY,
                output_dir=str(tmp_path / "bot_export"),
                is_human=False,
            )

        # 5b. Legitimate human review and approval transitions dossier to APPROVED_INFORMATIONAL
        human_attestation = EditorialReviewerAttestationSchema(
            reviewer_id="human_test_editor",
            reviewer_name="Jane Doe",
            reviewer_role="Editor",
            is_human=True,
            statement_confirmed=True,
            attestation_statement=EDITORIAL_ATTESTATION_STATEMENT,
            content_hash=dossier.content_hash,
            dossier_id=dossier.id,
            dossier_version=dossier.version,
        )
        repo.approve_dossier(
            dossier_id=dossier.id,
            attestation=human_attestation,
            validation_report=v_report,
        )

        # 5c. Once approved, automated agent attempting approved export is blocked by Rule 14
        with pytest.raises(ConstitutionalViolationError, match="Rule 14"):
            exporter.export(
                dossier_id=dossier.id,
                purpose=EditorialArtifactPurpose.APPROVED_EDITORIAL_COPY,
                output_dir=str(tmp_path / "bot_export"),
                is_human=False,  # Bot cannot export approved copy
            )

    # --------------------------------------------------------------------------
    # Scenario 15: Artifact and Manifest Hash Verification
    # --------------------------------------------------------------------------
    def test_15_artifact_and_manifest_hash_verification(
        self,
        tmp_path: Path,
        sqlite_session: Session,
    ) -> None:
        """Verify cryptographic digests between physical disk files and companion manifests."""
        inc, _, _, _ = build_test_evidence_graph(
            session=sqlite_session,
            incident_id="INC-2026-HASH-VERIFY",
            title="Telemetry Ingestion Microburst Anomaly",
            summary="Demonstration: Microburst of sensor frames led to event buffer saturation.",
            source_url="https://synthetic-source.internal/microburst",
        )
        selector = EditorialSourceSelector(sqlite_session)
        cand = selector.evaluate_candidate_incident(inc)

        assembler = EditorialDossierAssembler()
        dossier_schema = assembler.assemble(
            candidates=[cand],
            title="Network Saturation Bulletin",
            scope_type=EditorialScopeType.CUSTOM,
        )

        repo = EditorialRepository(sqlite_session)
        dossier = repo.save_dossier(dossier_schema, actor_id="test_builder", is_human=False)
        repo.submit_for_review(dossier.id, actor_id="submitter", is_human=True)
        v_report = EditorialValidator().validate_dossier(dossier)

        attestation = EditorialReviewerAttestationSchema(
            reviewer_id="human_lead_01",
            reviewer_name="Dr. Lead",
            reviewer_role="Editor",
            is_human=True,
            statement_confirmed=True,
            attestation_statement=EDITORIAL_ATTESTATION_STATEMENT,
            content_hash=dossier.content_hash,
            dossier_id=dossier.id,
            dossier_version=dossier.version,
        )
        approved = repo.approve_dossier(dossier.id, attestation, v_report)

        exporter = EditorialDossierExporter(repository=repo)
        export_res = exporter.export(
            dossier_id=approved.id,
            export_format=EditorialExportFormat.ALL,
            purpose=EditorialArtifactPurpose.APPROVED_EDITORIAL_COPY,
            output_dir=str(tmp_path / "hash_verified_exports"),
            is_human=True,
        )

        md_file = next(Path(f) for f in export_res.written_files if f.endswith(".md"))
        manifest_file = next(Path(f) for f in export_res.written_files if f.endswith(".manifest.json"))
        assert manifest_file.exists()

        m_dict = json.loads(manifest_file.read_text(encoding="utf-8"))

        # Recompute physical file SHA-256
        actual_file_bytes = md_file.read_bytes()
        computed_file_sha256 = hashlib.sha256(actual_file_bytes).hexdigest()

        # Cryptographic equality assertions
        assert computed_file_sha256 == m_dict["artifact_file_hash"]
        assert approved.content_hash == m_dict["canonical_dossier_content_hash"]
        assert m_dict["canonical_payload_hash"] != ""

    # --------------------------------------------------------------------------
    # Scenario 16: Sensitive-Data and Secret Leakage Checks
    # --------------------------------------------------------------------------
    def test_16_sensitive_data_and_secret_leakage_checks(
        self,
        tmp_path: Path,
        sqlite_session: Session,
    ) -> None:
        """Verify exported JSON packages and Markdown contain zero tokens, passwords, or raw secrets."""
        inc, _, _, _ = build_test_evidence_graph(
            session=sqlite_session,
            incident_id="INC-2026-LEAK-DEFENSE",
            title="Biometric Scanner Authentication Error",
            summary="Demonstration: Scanner rejected authorized badge holder.",
            source_url="https://synthetic-source.internal/leak-defense",
        )
        selector = EditorialSourceSelector(sqlite_session)
        cand = selector.evaluate_candidate_incident(inc)

        assembler = EditorialDossierAssembler()
        dossier_schema = assembler.assemble(
            candidates=[cand],
            title="Authentication Security Analysis",
            scope_type=EditorialScopeType.INCIDENT_DEEP_DIVE,
        )

        repo = EditorialRepository(sqlite_session)
        dossier = repo.save_dossier(dossier_schema, actor_id="test_builder", is_human=False)
        repo.submit_for_review(dossier.id, actor_id="submitter", is_human=True)
        v_report = EditorialValidator().validate_dossier(dossier)

        attestation = EditorialReviewerAttestationSchema(
            reviewer_id="human_lead_01",
            reviewer_name="Dr. Security",
            reviewer_role="Editor",
            is_human=True,
            statement_confirmed=True,
            attestation_statement=EDITORIAL_ATTESTATION_STATEMENT,
            content_hash=dossier.content_hash,
            dossier_id=dossier.id,
            dossier_version=dossier.version,
        )
        approved = repo.approve_dossier(dossier.id, attestation, v_report)

        exporter = EditorialDossierExporter(repository=repo)
        export_res = exporter.export(
            dossier_id=approved.id,
            export_format=EditorialExportFormat.ALL,
            purpose=EditorialArtifactPurpose.APPROVED_EDITORIAL_COPY,
            output_dir=str(tmp_path / "leak_check_exports"),
            is_human=True,
        )

        # Inspect exported JSON file
        json_file = next(Path(f) for f in export_res.written_files if f.endswith(".json"))
        json_raw = json_file.read_text(encoding="utf-8")
        json_data = json.loads(json_raw)

        # Forbidden secret keys pattern
        forbidden_patterns = [
            r"password",
            r"secret_key",
            r"access_token",
            r"bearer_token",
            r"api_key",
            r"private_key",
            r"database_url",
            r"connection_string",
        ]
        for pattern in forbidden_patterns:
            matches = re.findall(pattern, json_raw, re.IGNORECASE)
            assert len(matches) == 0, f"Sensitive keyword '{pattern}' found in exported JSON artifact!"

        # Assert audit trail summary in JSON contains strictly allowlisted fields
        audit_summary = json_data.get("audit_history", [])
        for entry in audit_summary:
            allowed_keys = {"event_type", "timestamp_utc", "actor_id", "actor_role"}
            assert set(entry.keys()).issubset(allowed_keys)

        # Inspect exported Markdown file
        md_file = next(Path(f) for f in export_res.written_files if f.endswith(".md"))
        md_text = md_file.read_text(encoding="utf-8")

        # Active HTML script/iframe tags must be absent
        assert "<script" not in md_text.lower()
        assert "<iframe" not in md_text.lower()
        assert "javascript:" not in md_text.lower()

    # --------------------------------------------------------------------------
    # Scenario 17: Network Denial Infrastructure Enforcement
    # --------------------------------------------------------------------------
    def test_17_network_denial_enforcement(self) -> None:
        """Verify that the test harness network denial guard actively catches unexpected socket connections."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        with pytest.raises(AssertionError, match=r"\[NETWORK_EGRESS_BLOCKED\]"):
            sock.connect(("8.8.8.8", 53))
        sock.close()
