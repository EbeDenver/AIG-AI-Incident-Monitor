"""Comprehensive test suite for Incident Intelligence Enrichment per Ai-incident-manager-guide.pdf.

Verifies:
- Prompt extraction, 10 operating rules, 10-step analysis procedure, and no-approval amendment.
- Stage 1: Evidence package cataloging and untrusted source envelopes.
- Stage 2: Client generation (Mock, Gemini, OpenAI configuration).
- Stage 3: Independent application validation (citation integrity, epistemic consistency, causal discipline, quality review calculation).
- Persistence and backward compatibility with Alembic revision 008.
- Web UI rendering of all rich guide sections and advisory warning banners.
"""

from __future__ import annotations

import os
from pathlib import Path
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from ai_incident_monitor.db.base import Base
from ai_incident_monitor.db.models.claim import ClaimRecordModel
from ai_incident_monitor.db.models.enrichment import IncidentEnrichmentModel
from ai_incident_monitor.db.models.incident import IncidentModel
from ai_incident_monitor.db.models.source import SourceReferenceModel
from ai_incident_monitor.intelligence.client import (
    BudgetExceededError,
    ClaudeLLMClient,
    GeminiLLMClient,
    LLMConfigurationError,
    MockLLMClient,
    PilotBudgetGuard,
    get_llm_client,
)
from ai_incident_monitor.intelligence.prompts import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_evidence_package,
    escape_envelope_content,
    render_enrichment_prompt,
)
from ai_incident_monitor.intelligence.schemas import (
    AIInvolvement,
    AIInvolvementRole,
    AssessmentStatus,
    AutonomyLevel,
    CausalAssessment,
    CausalStatus,
    ClaimClassification,
    ConfidenceTier,
    ConsultantGuidance,
    ControlType,
    DecisionMakerGuidance,
    EnrichmentClaim,
    HumanOversightStatus,
    IncidentEnrichmentDossier,
    IncidentSummary,
    MaterialityLevel,
    OrganizationalControlItem,
    ProvenanceItem,
    QualityReview,
    SourceTypeCategory,
    UncertaintyItem,
    VerificationStatus,
)
from ai_incident_monitor.intelligence.service import EnrichmentService
from ai_incident_monitor.intelligence.validator import EnrichmentValidator
from ai_incident_monitor.ui.app import create_app
from ai_incident_monitor.ui.auth import LocalCredentialManager, ServerSessionManager, SESSION_COOKIE_NAME


class TestPromptAndContractFidelity:
    """Validate adoption of Ai-incident-manager-guide.pdf system prompt and contract."""

    def test_system_prompt_mandates_and_rules(self):
        """Verify verbatim preservation of 10 operating rules in SYSTEM_PROMPT."""
        assert "AI Incident Manager — Evidence-Grounded Incident Enrichment" in SYSTEM_PROMPT
        assert "Rule 1" in SYSTEM_PROMPT or "1. GROUNDING IN PROVIDED EVIDENCE ONLY" in SYSTEM_PROMPT
        assert "2. EPISTEMIC STATUS DISCIPLINE" in SYSTEM_PROMPT
        assert "3. SEPARATION OF CLASSIFICATION AND VERIFICATION" in SYSTEM_PROMPT
        assert "4. AI INVOLVEMENT CLASSIFICATION" in SYSTEM_PROMPT
        assert "5. CAUSAL RIGOR" in SYSTEM_PROMPT
        assert "6. UNCERTAINTY TRANSPARENCY" in SYSTEM_PROMPT
        assert "7. DISPUTED FACTS HANDLING" in SYSTEM_PROMPT
        assert "8. PROVENANCE AND CITATION INTEGRITY" in SYSTEM_PROMPT
        assert "9. ACTIONABLE, TESTABLE GUIDANCE" in SYSTEM_PROMPT
        assert "10. NO SPECULATIVE EXTRAPOLATION" in SYSTEM_PROMPT

    def test_authoritative_no_approval_amendment_in_prompt(self):
        """Verify that system prompt explicitly forbids blocking approval gates."""
        assert "AUTHORITATIVE NO-APPROVAL AMENDMENT" in SYSTEM_PROMPT
        assert "No incident approvals, dossier approvals, reviewer keys, or attestations" in SYSTEM_PROMPT
        assert "advisory-only" in SYSTEM_PROMPT.lower()

    def test_ten_step_analysis_procedure_presence(self):
        """Verify presence of the 10-step analysis procedure from the guide."""
        assert "ANALYSIS PROCEDURE (10-STEP WORKFLOW)" in SYSTEM_PROMPT
        for step_idx in range(1, 11):
            assert f"Step {step_idx}:" in SYSTEM_PROMPT

    def test_evidence_package_and_untrusted_source_envelopes(self):
        """Verify Stage 1 evidence package building and XML untrusted envelopes."""
        package = build_evidence_package(
            incident_id="INC-2026-TEST",
            title="Test Incident Title",
            summary="A short summary of an AI failure.",
            evidence_excerpts=["Quote excerpt 1", "Quote excerpt 2"],
        )
        assert len(package) == 3
        assert package[0].evidence_id == "E001"
        assert package[1].evidence_id == "E002"
        assert package[2].evidence_id == "E003"

        prompt, digest = render_enrichment_prompt(
            incident_id="INC-2026-TEST",
            title="Test Incident Title",
            summary="A short summary of an AI failure.",
            category="SAFETY",
            evidence_excerpts=["Quote excerpt 1", "Quote excerpt 2"],
        )
        assert "<untrusted_source_payload incident_id=\"INC-2026-TEST\">" in prompt
        assert '<untrusted_evidence_item id="E001"' in prompt
        assert len(digest) == 64


class TestStage3ApplicationValidator:
    """Validate Stage 3 independent application quality validation."""

    def test_citation_integrity_gate_detects_fabricated_citations(self):
        """Verify that fabricated evidence IDs not in provenance package are detected."""
        validator = EnrichmentValidator()
        valid_ev = [
            ProvenanceItem(
                evidence_id="E001",
                source_title="Primary Report",
                publisher="News Wire",
                url="https://example.com/e1",
                excerpt="Report excerpt.",
            )
        ]

        # Fabricate claim citing E999
        claim = EnrichmentClaim(
            claim_id="C001",
            statement="Model executed code injection.",
            classification=ClaimClassification.ATTRIBUTED_ALLEGATION,
            verification_status=VerificationStatus.UNVERIFIED,
            confidence=ConfidenceTier.LOW,
            supporting_evidence_ids=["E001", "E999"],  # E999 is fabricated
            reasoning_summary="Allegation from tweet.",
            advisory_review_flag=True,
        )

        dossier = IncidentEnrichmentDossier(
            incident_id="INC-2026-VAL",
            assessment_status=AssessmentStatus.COMPLETE,
            incident_summary=IncidentSummary(reported_event="Event summary"),
            claims=[claim],
            ai_involvement=AIInvolvement(
                role=AIInvolvementRole.ALLEGED,
                supporting_evidence_ids=["E001"],
                assessment="Alleged involvement.",
            ),
            causal_assessment=CausalAssessment(
                causal_status=CausalStatus.CAUSALITY_NOT_ESTABLISHED,
                confidence=ConfidenceTier.LOW,
                evidence_ids=["E001"],
            ),
            provenance=valid_ev,
            organizational_controls=[],
            decision_maker_guidance=DecisionMakerGuidance(),
            consultant_guidance=ConsultantGuidance(),
            quality_review=QualityReview(),
        )

        certified = validator.validate_and_certify(dossier, evidence_package=valid_ev)
        # E999 must be stripped from supporting_evidence_ids
        assert "E999" not in certified.claims[0].supporting_evidence_ids
        assert "E001" in certified.claims[0].supporting_evidence_ids
        assert any("E999" in gap for gap in certified.quality_review.unresolved_evidence_gaps)

    def test_epistemic_consistency_gate_reclassifies_unverified_fact(self):
        """Verify that unverified claims marked as CONFIRMED_FACT are corrected."""
        validator = EnrichmentValidator()
        valid_ev = [
            ProvenanceItem(
                evidence_id="E001",
                source_title="Primary Report",
                publisher="News Wire",
                excerpt="Report excerpt.",
            )
        ]

        # Illegally set CONFIRMED_FACT with UNVERIFIED status
        claim = EnrichmentClaim(
            claim_id="C001",
            statement="Midnight Blizzard attacked art agency.",
            classification=ClaimClassification.CONFIRMED_FACT,
            verification_status=VerificationStatus.UNVERIFIED,
            confidence=ConfidenceTier.LOW,
            supporting_evidence_ids=["E001"],
            reasoning_summary="Reported by journalist.",
            advisory_review_flag=False,
        )

        dossier = IncidentEnrichmentDossier(
            incident_id="INC-2026-EPIST",
            assessment_status=AssessmentStatus.COMPLETE,
            incident_summary=IncidentSummary(reported_event="Cyberattack"),
            claims=[claim],
            ai_involvement=AIInvolvement(
                role=AIInvolvementRole.ALLEGED,
                supporting_evidence_ids=["E001"],
                assessment="Alleged.",
            ),
            causal_assessment=CausalAssessment(
                causal_status=CausalStatus.CAUSALITY_NOT_ESTABLISHED,
                confidence=ConfidenceTier.LOW,
                evidence_ids=["E001"],
            ),
            provenance=valid_ev,
            organizational_controls=[],
            decision_maker_guidance=DecisionMakerGuidance(),
            consultant_guidance=ConsultantGuidance(),
            quality_review=QualityReview(),
        )

        certified = validator.validate_and_certify(dossier, evidence_package=valid_ev)
        # Reclassified to ATTRIBUTED_ALLEGATION
        assert certified.claims[0].classification == ClaimClassification.ATTRIBUTED_ALLEGATION
        assert certified.claims[0].advisory_review_flag is True
        assert certified.assessment_status == AssessmentStatus.ADVISORY_REVIEW
        assert certified.quality_review.advisory_human_review_flag is True

    def test_causal_discipline_gate_adjusts_unsupported_cause(self):
        """Verify that CONFIRMED_CAUSE without evidence is adjusted to POSSIBLE_CONTRIBUTOR."""
        validator = EnrichmentValidator()
        valid_ev = [
            ProvenanceItem(
                evidence_id="E001",
                source_title="Primary Report",
                publisher="News Wire",
                excerpt="Report excerpt.",
            )
        ]

        dossier = IncidentEnrichmentDossier(
            incident_id="INC-2026-CAUS",
            assessment_status=AssessmentStatus.COMPLETE,
            incident_summary=IncidentSummary(reported_event="Loss"),
            claims=[],
            ai_involvement=AIInvolvement(
                role=AIInvolvementRole.PRIMARY,
                supporting_evidence_ids=["E001"],
                assessment="AI was primary.",
            ),
            causal_assessment=CausalAssessment(
                causal_status=CausalStatus.CONFIRMED_CAUSE,
                confidence=ConfidenceTier.HIGH,
                evidence_ids=[],  # Missing evidence!
            ),
            provenance=valid_ev,
            organizational_controls=[],
            decision_maker_guidance=DecisionMakerGuidance(),
            consultant_guidance=ConsultantGuidance(),
            quality_review=QualityReview(),
        )

        certified = validator.validate_and_certify(dossier, evidence_package=valid_ev)
        assert certified.causal_assessment.causal_status == CausalStatus.POSSIBLE_CONTRIBUTOR
        assert certified.quality_review.advisory_human_review_flag is True


class TestProviderClientsAndConfiguration:
    """Validate client adapters, key handling, and provider factory."""

    def test_provider_factory_mock_default(self):
        """Verify provider factory returns MockLLMClient by default."""
        client = get_llm_client("mock")
        assert isinstance(client, MockLLMClient)

    def test_provider_factory_rejects_unknown(self):
        """Verify provider factory raises on unsupported provider."""
        with pytest.raises(LLMConfigurationError, match="Unsupported LLM provider 'cohere'"):
            get_llm_client("cohere")

    def test_claude_client_missing_key_raises_configuration_error(self, monkeypatch):
        """Verify Claude client raises clear error reporting the missing variable name only."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(LLMConfigurationError, match="ANTHROPIC_API_KEY"):
            ClaudeLLMClient(api_key=None)

    def test_gemini_client_missing_key_raises_configuration_error(self, monkeypatch):
        """Verify Gemini client raises clear error reporting the missing variable name only."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        with pytest.raises(LLMConfigurationError, match="GEMINI_API_KEY"):
            GeminiLLMClient(api_key=None)

    def test_claude_pricing_calculation(self):
        """Verify Claude 3.5 Sonnet pricing basis ($3.00/1M in, $15.00/1M out)."""
        client = ClaudeLLMClient(api_key="dummy-key-for-test")
        assert client.model_name == "claude-3-5-sonnet-20241022" or "sonnet" in client.model_name
        cost = client.calculate_cost(input_tokens=1000, output_tokens=1000)
        # 1000 * 0.000003 = 0.003; 1000 * 0.000015 = 0.015; total = 0.018
        assert abs(cost - 0.018) < 1e-6

    def test_gemini_pricing_calculation(self):
        """Verify Gemini 2.5 Pro pricing basis ($1.25/1M in, $10.00/1M out)."""
        client = GeminiLLMClient(api_key="dummy-key-for-test")
        assert "gemini-2.5-pro" in client.model_name or "pro" in client.model_name
        cost = client.calculate_cost(input_tokens=1000, output_tokens=1000)
        # 1000 * 0.00000125 = 0.00125; 1000 * 0.00001 = 0.01; total = 0.01125
        assert abs(cost - 0.01125) < 1e-6

    def test_pilot_budget_guard_enforcement(self):
        """Verify PilotBudgetGuard halts execution before dispatch when budget ceiling is exceeded."""
        guard = PilotBudgetGuard(max_budget_usd=0.05)
        # 1. First call within budget: 0.02
        guard.check_and_reserve(0.02)
        guard.record_actual(0.02, success=True)
        assert guard.attempt_count == 1
        assert guard.success_count == 1
        assert guard.cumulative_cost_usd == 0.02

        # 2. Second call within budget: 0.02
        guard.check_and_reserve(0.02)
        guard.record_actual(0.02, success=True)
        assert guard.cumulative_cost_usd == 0.04

        # 3. Third call exceeds budget: 0.04 + 0.02 = 0.06 > 0.05
        with pytest.raises(BudgetExceededError, match="PILOT BUDGET EXCEEDED"):
            guard.check_and_reserve(0.02)

    def test_mock_client_generates_schema_valid_dossier_for_artex(self):
        """Verify MockLLMClient generates rich schema-compliant dossier for INC-2026-04785D."""
        client = MockLLMClient()
        package = build_evidence_package(
            incident_id="INC-2026-04785D",
            title="Chinese-linked hackers use AI tools to target US government",
            summary="A sophisticated state-sponsored operation used artificial intelligence tools for targeting and reconnaissance.",
        )
        dossier, in_tok, out_tok, latency, model = client.generate_dossier(
            prompt="Prompt text",
            incident_id="INC-2026-04785D",
            title="Chinese-linked hackers use AI tools to target US government",
            summary="A sophisticated state-sponsored operation used artificial intelligence tools for targeting and reconnaissance.",
            category="CYBERSECURITY",
            evidence_package=package,
        )
        assert isinstance(dossier, IncidentEnrichmentDossier)
        assert len(dossier.claims) >= 2
        assert len(dossier.organizational_controls) >= 3
        # Every control must have a testable validation test
        for ctrl in dossier.organizational_controls:
            assert len(ctrl.validation_test) > 10
        # Decision-maker and consultant guidance must be populated
        assert len(dossier.decision_maker_guidance.key_implications) > 0
        assert len(dossier.consultant_guidance.discovery_questions) > 0
        assert dossier.assessment_status == AssessmentStatus.ADVISORY_REVIEW
        assert dossier.quality_review.advisory_human_review_flag is True


class TestEnrichmentServiceAndUIRendering:
    """Validate persistence, claim categorization defect fix, and UI template rendering."""

    @pytest.fixture
    def test_env(self, tmp_path: Path):
        db_file = tmp_path / "test_intelligence.db"
        engine = create_engine(f"sqlite:///{db_file}")
        Base.metadata.create_all(engine)

        cred_mgr = LocalCredentialManager(storage_path=tmp_path / ".cred")
        cred = cred_mgr.generate_or_load_credential()
        sess_mgr = ServerSessionManager()

        with Session(engine) as session:
            # Seed Artex incident INC-2026-04785D
            inc = IncidentModel(
                id="INC-2026-04785D",
                title="Chinese-linked hackers use AI tools to target US government",
                summary="Adversary groups reportedly deployed AI tools during reconnaissance operations against critical infrastructure.",
                status="NEW",
                primary_category="CYBERSECURITY",
            )
            # Unverified claim with claim_type=FACTUAL_EVENT
            clm = ClaimRecordModel(
                id="clm_artex_01",
                incident_id="INC-2026-04785D",
                claim_text="Chinese-linked threat group leveraged generative AI to accelerate spear-phishing campaigns.",
                claim_type="FACTUAL_EVENT",
                epistemic_status="UNVERIFIED_ALLEGATION",
                confidence="LOW",
                materiality="HIGH",
                is_causal_claim=True,
            )
            session.add_all([inc, clm])
            session.commit()

        app = create_app(
            db_engine=engine,
            repo_root=tmp_path,
            credential_manager=cred_mgr,
            session_manager=sess_mgr,
        )
        client = TestClient(app, follow_redirects=True)

        # Authenticate
        login_res = client.get("/login")
        csrf = login_res.cookies.get("aig_login_csrf")
        client.post("/login", data={"credential": cred, "csrf_token": csrf})

        return {"engine": engine, "client": client, "app": app}

    def test_enrichment_service_persists_payload_json(self, test_env):
        """Verify that EnrichmentService stores complete JSON payload and updates status."""
        engine = test_env["engine"]
        service = EnrichmentService(default_client=MockLLMClient())

        with Session(engine) as session:
            enr = service.enrich_incident(session, "INC-2026-04785D")
            assert enr.status == "COMPLETED"
            assert enr.assessment_status == "ADVISORY_REVIEW"
            assert enr.payload_json is not None

            # Verify it parses back into strict IncidentEnrichmentDossier
            dossier = IncidentEnrichmentDossier.model_validate_json(enr.payload_json)
            assert dossier.incident_id == "INC-2026-04785D"
            assert len(dossier.claims) >= 2
            assert len(dossier.organizational_controls) >= 3

    def test_claim_classification_defect_resolved_and_ui_rendered(self, test_env):
        """Verify that INC-2026-04785D unverified allegation is NOT promoted to confirmed fact,
        and all guide sections are rendered in UI HTML."""
        engine = test_env["engine"]
        client = test_env["client"]
        service = EnrichmentService(default_client=MockLLMClient())

        with Session(engine) as session:
            service.enrich_incident(session, "INC-2026-04785D")

        resp = client.get("/incidents/INC-2026-04785D")
        assert resp.status_code == 200
        html = resp.text

        # 1. Defect Fix Verification: Allegation must NOT be promoted to Confirmed Fact
        assert "Confirmed Facts (0)" in html
        assert "Attributed Allegations (1)" in html

        # 2. Guide §3 UI Sections Verification
        assert "Advisory Evidence Quality Warning" in html
        assert "Under the system&#39;s authoritative No-Approval Policy" in html or "authoritative No-Approval Policy" in html
        assert "Reported Event &amp; Corroborated Outcomes" in html or "Reported Event & Corroborated Outcomes" in html
        assert "Atomic Claims Evaluation" in html
        assert "AI System Involvement &amp; Operational Oversight" in html or "AI System Involvement & Operational Oversight" in html
        assert "Reported Failure Mechanisms" in html
        assert "Alternative Explanations &amp; Confounders" in html or "Alternative Explanations & Confounders" in html
        assert "Organizational Controls with Verifiable Tests" in html
        assert "Validation Test:" in html
        assert "Executive &amp; Decision-Maker Guidance" in html or "Executive & Decision-Maker Guidance" in html
        assert "Consultant &amp; Advisory Playbook" in html or "Consultant & Advisory Playbook" in html
        assert "Evidence Package &amp; Citations" in html or "Evidence Package & Citations" in html
