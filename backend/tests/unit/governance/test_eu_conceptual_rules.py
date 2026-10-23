"""Unit tests for EU AI Act deterministic conceptual relevance rules and screening engine.

Phase 5 Increment 2C-3A:
Tests:
- Reference Integrity & Canonical Validation (Safety Rule 2)
- Rejection of Fabricated / Invented Reference Identifiers
- Rule Family D1: Article 5 Prohibited Practice Concepts (Art. 5(1)(a)–(h))
- Rule Family D2: Annex III Regulated Operational Domain Concepts (Points 1–8)
- Rule Family D3: Article 50 Transparency Concepts (Art. 50(1), 50(2), 50(4))
- Rule Family D4: General-Purpose AI Concepts (Articles 51 and 53)
- Rule Family D5: Operational Control Concepts (Articles 10, 12, 14, 15, 72, 73)
- Rule Family D6: Serious Incident Conceptual Relevance (Article 3(49))
- Strict Safety Controls:
  - Evidence First (zero evidence = zero affirmative findings)
  - Epistemic Modesty (absent facts preserved as explicit unknowns)
  - Disputed Evidence Visibility and Review Routing
  - Non-Legal Terminology Invariants (Safety Rule 7)
  - Mandatory PENDING_REVIEW Routing
  - Orthogonal Governance Confidence
  - Deterministic Repeatability
- Screening Engine Integration (EURelevanceScreeningEngine) & Relational Persistence
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ai_incident_monitor.db.base import Base
from ai_incident_monitor.db.models.governance import (
    EULegalRelevanceScreenModel,
    EUScreenRuleTraceModel,
    FrameworkReferenceSetModel,
)
from ai_incident_monitor.domain.common import ConstitutionalViolationError
from ai_incident_monitor.governance.enums import (
    ControlLevel,
    EUAISystemRelevance,
    EUActorRole,
    EUActorRoleConfidence,
    EUConceptType,
    EUConceptualRelevanceLevel,
    EUEvidenceStrength,
    EUNexusAssessment,
    EURelevanceLevel,
    EUScreenStatus,
    EUSeriousIncidentRelevance,
    EUTimingAssessment,
    FrameworkCode,
    FrameworkStatus,
    GovernanceConfidence,
    SensitiveDomain,
)
from ai_incident_monitor.governance.eu_screen import EURelevanceScreeningEngine
from ai_incident_monitor.governance.models import (
    EU_AI_ACT_DISCLAIMER_V2,
    EU_AI_ACT_DISCLAIMER_VERSION,
    EUConceptualFinding,
    EULegalRelevanceScreenSchema,
    FrameworkControlSchema,
    FrameworkReferenceSetSchema,
    GovernanceActorIdentity,
    IncidentFactContext,
    MappingRuleMetadata,
    validate_no_legal_language,
)
from ai_incident_monitor.governance.reference_loader import (
    compute_file_sha256,
    load_framework_manifest,
    load_reference_set,
)
from ai_incident_monitor.governance.rules.eu_conceptual_relevance_rules import (
    ALL_EU_CONCEPTUAL_RULES,
    BaseEUConceptualRule,
    EUAnnex3BiometricsRule,
    EUAnnex3CriticalInfrastructureRule,
    EUAnnex3EducationRule,
    EUAnnex3EmploymentRule,
    EUAnnex3EssentialServicesRule,
    EUAnnex3JusticeDemocracyRule,
    EUAnnex3LawEnforcementRule,
    EUAnnex3MigrationBorderRule,
    EUArticle5BiometricCategorizationRule,
    EUArticle5EmotionRecognitionRule,
    EUArticle5FacialScrapingRule,
    EUArticle5PredictivePolicingRule,
    EUArticle5RealTimeBiometricRule,
    EUArticle5SocialScoringRule,
    EUArticle5SubliminalManipulativeRule,
    EUArticle5VulnerabilityExploitationRule,
    EUArticle10DataGovernanceRule,
    EUArticle12LoggingRule,
    EUArticle14HumanOversightRule,
    EUArticle15RobustnessCybersecurityRule,
    EUArticle50InteractionNotificationRule,
    EUArticle50SyntheticMediaRule,
    EUArticle50TextDisclosureRule,
    EUArticle72PostMarketMonitoringRule,
    EUArticle73SeriousIncidentReportingRule,
    EUArticle349SeriousIncidentRule,
    EUGPAIProviderObligationsRule,
    EUGPAISystemicRiskRule,
    evaluate_eu_conceptual_context,
)
from ai_incident_monitor.repositories.governance_repo import GovernanceRepository


@pytest.fixture
def repo_root() -> Path:
    """Return repository root path."""
    return Path(__file__).resolve().parents[4]


@pytest.fixture
def sqlite_session() -> Session:
    """Provide an in-memory SQLite database session initialized with the full schema."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def active_eu_reference_set(sqlite_session: Session, repo_root: Path) -> FrameworkReferenceSetModel:
    """Load and persist the official EU AI Act reference set."""
    yaml_path = repo_root / "frameworks" / "eu-ai-act" / "eu-ai-act-2024-1689.yaml"
    ref_schema = load_reference_set(yaml_path)
    content_hash = compute_file_sha256(yaml_path)
    repo = GovernanceRepository(sqlite_session)
    return repo.create_reference_set(ref_schema, content_hash=content_hash)


@pytest.fixture
def loaded_eu_ref_schema(repo_root: Path) -> FrameworkReferenceSetSchema:
    """Load the official EU AI Act reference schema directly from YAML."""
    yaml_path = repo_root / "frameworks" / "eu-ai-act" / "eu-ai-act-2024-1689.yaml"
    return load_reference_set(yaml_path)


@pytest.fixture
def base_context() -> IncidentFactContext:
    """Provide a verified base incident context with primary evidence."""
    return IncidentFactContext(
        incident_id="INC-2026-EU-CONCEPT-001",
        title="Automated evaluation anomaly",
        summary="A machine learning system exhibited unexpected outputs in operational testing.",
        claims=[
            {
                "claim_id": "CLM-001",
                "statement": "The AI system processed inputs without explicit operator oversight.",
            }
        ],
        evidence_records=[
            {
                "id": "EV-001",
                "directness": "PRIMARY_DIRECT",
                "corroboration_status": "FULLY_CORROBORATED",
                "content": "Audit log confirming algorithmic output execution.",
            }
        ],
        fact_tags=["eu_established", "machine_learning"],
    )


# ==============================================================================
# 1. Reference Library Validation & Invented Reference Rejection Tests
# ==============================================================================


class TestReferenceValidationAndRejection:
    """Verify that conceptual rules strictly target validated references only."""

    def test_all_conceptual_rules_target_validated_controls(
        self, loaded_eu_ref_schema: FrameworkReferenceSetSchema
    ) -> None:
        """Every registered conceptual rule must target a valid, active control in the canonical reference set."""
        valid_identifiers = {c.external_identifier for c in loaded_eu_ref_schema.controls}
        assert len(valid_identifiers) == 33

        for rule in ALL_EU_CONCEPTUAL_RULES:
            assert rule.target_identifier in valid_identifiers, (
                f"Rule {rule.metadata.rule_id} targets unvalidated identifier '{rule.target_identifier}'"
            )
            assert rule.source_locator.startswith("Regulation (EU) 2024/1689"), (
                f"Rule {rule.metadata.rule_id} missing authoritative citation"
            )

    def test_screening_engine_rejects_invented_reference(
        self, loaded_eu_ref_schema: FrameworkReferenceSetSchema
    ) -> None:
        """Engine must raise ConstitutionalViolationError if a rule references a non-existent control."""
        class InventedRule(BaseEUConceptualRule):
            @property
            def metadata(self) -> MappingRuleMetadata:
                return MappingRuleMetadata(
                    rule_id="RULE-EU-CONC-FABRICATED",
                    rule_version="1.0.0",
                    framework_code=FrameworkCode.EU_AI_ACT,
                    target_identifier="EU-ART-999-NONEXISTENT",
                    target_level=ControlLevel.ARTICLE,
                    title="Fabricated Rule",
                    description="Tests safety rejection of invented reference.",
                    prerequisite_fact_keys=["fabricated"],
                    applicability="NOT_APPLICABLE",
                )

            @property
            def concept_type(self) -> EUConceptType:
                return EUConceptType.ARTICLE_5_CONCEPT

            @property
            def target_identifier(self) -> str:
                return "EU-ART-999-NONEXISTENT"

            @property
            def source_locator(self) -> str:
                return "Regulation (EU) 2024/1689, Article 999"

            def evaluate(self, context: IncidentFactContext) -> Optional[EUConceptualFinding]:
                return None

        with pytest.raises(ConstitutionalViolationError) as exc_info:
            EURelevanceScreeningEngine(
                reference_set=loaded_eu_ref_schema,
                conceptual_rules=(InventedRule(),),
            )
        assert "Safety Rule 2" in str(exc_info.value)
        assert "EU-ART-999-NONEXISTENT" in str(exc_info.value)


# ==============================================================================
# 2. Rule Family D1: Article 5 Prohibited AI Practice Concepts Tests
# ==============================================================================


class TestArticle5ConceptualRules:
    """Verify deterministic evaluation of Article 5 prohibited practice concepts."""

    def test_article_5_1_a_subliminal_manipulation(self, base_context: IncidentFactContext) -> None:
        rule = EUArticle5SubliminalManipulativeRule()
        ctx = base_context.model_copy(update={"fact_tags": ["subliminal_technique", "behavioral_manipulation"]})
        finding = rule.evaluate(ctx)

        assert finding is not None
        assert finding.reference_id == "EU-ART-5.1.a"
        assert finding.concept_type == EUConceptType.ARTICLE_5_CONCEPT
        assert finding.relevance_level == EUConceptualRelevanceLevel.POTENTIALLY_RELEVANT_FOR_QUALIFIED_REVIEW
        assert finding.review_routing == EUScreenStatus.PENDING_REVIEW
        assert "COND-CONC-PROHIB-SUBLIMINAL" in finding.matched_condition_ids
        validate_no_legal_language(finding.rationale)

    def test_article_5_1_b_vulnerability_exploitation(self, base_context: IncidentFactContext) -> None:
        rule = EUArticle5VulnerabilityExploitationRule()
        ctx = base_context.model_copy(update={"fact_tags": ["child_exploitation", "vulnerability_exploitation"]})
        finding = rule.evaluate(ctx)

        assert finding is not None
        assert finding.reference_id == "EU-ART-5.1.b"
        assert finding.concept_type == EUConceptType.ARTICLE_5_CONCEPT
        assert finding.review_routing == EUScreenStatus.PENDING_REVIEW
        validate_no_legal_language(finding.rationale)

    def test_article_5_1_c_social_scoring(self, base_context: IncidentFactContext) -> None:
        rule = EUArticle5SocialScoringRule()
        ctx = base_context.model_copy(update={"fact_tags": ["social_scoring", "citizen_scoring"]})
        finding = rule.evaluate(ctx)

        assert finding is not None
        assert finding.reference_id == "EU-ART-5.1.c"
        assert finding.concept_type == EUConceptType.ARTICLE_5_CONCEPT
        validate_no_legal_language(finding.rationale)

    def test_article_5_1_d_predictive_policing(self, base_context: IncidentFactContext) -> None:
        rule = EUArticle5PredictivePolicingRule()
        ctx = base_context.model_copy(update={"fact_tags": ["predictive_policing", "criminal_risk_assessment_profiling"]})
        finding = rule.evaluate(ctx)

        assert finding is not None
        assert finding.reference_id == "EU-ART-5.1.d"
        assert finding.concept_type == EUConceptType.ARTICLE_5_CONCEPT
        validate_no_legal_language(finding.rationale)

    def test_article_5_1_e_facial_scraping(self, base_context: IncidentFactContext) -> None:
        rule = EUArticle5FacialScrapingRule()
        ctx = base_context.model_copy(update={"fact_tags": ["untargeted_facial_scraping", "bulk_face_scraping"]})
        finding = rule.evaluate(ctx)

        assert finding is not None
        assert finding.reference_id == "EU-ART-5.1.e"
        assert finding.concept_type == EUConceptType.ARTICLE_5_CONCEPT
        validate_no_legal_language(finding.rationale)

    def test_article_5_1_f_emotion_recognition(self, base_context: IncidentFactContext) -> None:
        rule = EUArticle5EmotionRecognitionRule()
        ctx = base_context.model_copy(update={"fact_tags": ["workplace_emotion_recognition", "affect_sensing_employee"]})
        finding = rule.evaluate(ctx)

        assert finding is not None
        assert finding.reference_id == "EU-ART-5.1.f"
        assert finding.concept_type == EUConceptType.ARTICLE_5_CONCEPT
        validate_no_legal_language(finding.rationale)

    def test_article_5_1_g_biometric_categorization(self, base_context: IncidentFactContext) -> None:
        rule = EUArticle5BiometricCategorizationRule()
        ctx = base_context.model_copy(update={"fact_tags": ["sensitive_biometric_categorization", "race_inference_biometric"]})
        finding = rule.evaluate(ctx)

        assert finding is not None
        assert finding.reference_id == "EU-ART-5.1.g"
        assert finding.concept_type == EUConceptType.ARTICLE_5_CONCEPT
        validate_no_legal_language(finding.rationale)

    def test_article_5_1_h_real_time_public_biometrics(self, base_context: IncidentFactContext) -> None:
        rule = EUArticle5RealTimeBiometricRule()
        ctx = base_context.model_copy(update={"fact_tags": ["real_time_biometric_id", "public_space_facial_recognition"]})
        finding = rule.evaluate(ctx)

        assert finding is not None
        assert finding.reference_id == "EU-ART-5.1.h"
        assert finding.concept_type == EUConceptType.ARTICLE_5_CONCEPT
        validate_no_legal_language(finding.rationale)


# ==============================================================================
# 3. Rule Family D2: Annex III Regulated Operational Domain Tests
# ==============================================================================


class TestAnnexIIIConceptualRules:
    """Verify deterministic evaluation of Annex III critical domain concepts."""

    def test_annex_3_point_1_biometrics(self, base_context: IncidentFactContext) -> None:
        rule = EUAnnex3BiometricsRule()
        ctx = base_context.model_copy(update={"fact_tags": ["remote_biometric_identification", "biometric_categorization"]})
        finding = rule.evaluate(ctx)

        assert finding is not None
        assert finding.reference_id == "EU-ANNEX-III.1"
        assert finding.concept_type == EUConceptType.ANNEX_III_CONCEPT
        assert finding.relevance_level == EUConceptualRelevanceLevel.CONCEPTUALLY_RELEVANT
        validate_no_legal_language(finding.rationale)

    def test_annex_3_point_2_critical_infrastructure(self, base_context: IncidentFactContext) -> None:
        rule = EUAnnex3CriticalInfrastructureRule()
        ctx = base_context.model_copy(update={"fact_tags": ["critical_infrastructure_safety", "power_grid_management"]})
        finding = rule.evaluate(ctx)

        assert finding is not None
        assert finding.reference_id == "EU-ANNEX-III.2"
        assert finding.concept_type == EUConceptType.ANNEX_III_CONCEPT
        validate_no_legal_language(finding.rationale)

    def test_annex_3_point_3_education(self, base_context: IncidentFactContext) -> None:
        rule = EUAnnex3EducationRule()
        ctx = base_context.model_copy(update={"fact_tags": ["educational_admissions", "student_evaluation_system"]})
        finding = rule.evaluate(ctx)

        assert finding is not None
        assert finding.reference_id == "EU-ANNEX-III.3"
        assert finding.concept_type == EUConceptType.ANNEX_III_CONCEPT
        validate_no_legal_language(finding.rationale)

    def test_annex_3_point_4_employment(self, base_context: IncidentFactContext) -> None:
        rule = EUAnnex3EmploymentRule()
        ctx = base_context.model_copy(update={"fact_tags": ["recruitment_screening", "worker_performance_monitoring"]})
        finding = rule.evaluate(ctx)

        assert finding is not None
        assert finding.reference_id == "EU-ANNEX-III.4"
        assert finding.concept_type == EUConceptType.ANNEX_III_CONCEPT
        validate_no_legal_language(finding.rationale)

    def test_annex_3_point_5_essential_services(self, base_context: IncidentFactContext) -> None:
        rule = EUAnnex3EssentialServicesRule()
        ctx = base_context.model_copy(update={"fact_tags": ["creditworthiness_evaluation", "public_benefit_eligibility"]})
        finding = rule.evaluate(ctx)

        assert finding is not None
        assert finding.reference_id == "EU-ANNEX-III.5"
        assert finding.concept_type == EUConceptType.ANNEX_III_CONCEPT
        validate_no_legal_language(finding.rationale)

    def test_annex_3_point_6_law_enforcement(self, base_context: IncidentFactContext) -> None:
        rule = EUAnnex3LawEnforcementRule()
        ctx = base_context.model_copy(update={"fact_tags": ["law_enforcement_ai", "police_risk_assessment"]})
        finding = rule.evaluate(ctx)

        assert finding is not None
        assert finding.reference_id == "EU-ANNEX-III.6"
        assert finding.concept_type == EUConceptType.ANNEX_III_CONCEPT
        validate_no_legal_language(finding.rationale)

    def test_annex_3_point_7_migration_border(self, base_context: IncidentFactContext) -> None:
        rule = EUAnnex3MigrationBorderRule()
        ctx = base_context.model_copy(update={"fact_tags": ["border_control_ai", "asylum_application_screening"]})
        finding = rule.evaluate(ctx)

        assert finding is not None
        assert finding.reference_id == "EU-ANNEX-III.7"
        assert finding.concept_type == EUConceptType.ANNEX_III_CONCEPT
        validate_no_legal_language(finding.rationale)

    def test_annex_3_point_8_justice_democracy(self, base_context: IncidentFactContext) -> None:
        rule = EUAnnex3JusticeDemocracyRule()
        ctx = base_context.model_copy(update={"fact_tags": ["judicial_assistance_ai", "legal_interpretation_ai"]})
        finding = rule.evaluate(ctx)

        assert finding is not None
        assert finding.reference_id == "EU-ANNEX-III.8"
        assert finding.concept_type == EUConceptType.ANNEX_III_CONCEPT
        validate_no_legal_language(finding.rationale)

    def test_annex_3_no_match_without_sector_evidence(self, base_context: IncidentFactContext) -> None:
        """Rules must not infer Annex III without domain-specific evidence (epistemic modesty)."""
        rule = EUAnnex3CriticalInfrastructureRule()
        # Generic context with no infrastructure tags
        finding = rule.evaluate(base_context)
        assert finding is None


# ==============================================================================
# 4. Rule Family D3: Article 50 Transparency Concepts Tests
# ==============================================================================


class TestArticle50ConceptualRules:
    """Verify deterministic evaluation of Article 50 transparency concepts."""

    def test_article_50_1_interaction_disclosure(self, base_context: IncidentFactContext) -> None:
        rule = EUArticle50InteractionNotificationRule()
        ctx = base_context.model_copy(update={"fact_tags": ["conversational_agent", "human_interaction_ai"]})
        finding = rule.evaluate(ctx)

        assert finding is not None
        assert finding.reference_id == "EU-ART-50.1"
        assert finding.concept_type == EUConceptType.ARTICLE_50_CONCEPT
        validate_no_legal_language(finding.rationale)

    def test_article_50_2_synthetic_media(self, base_context: IncidentFactContext) -> None:
        rule = EUArticle50SyntheticMediaRule()
        ctx = base_context.model_copy(update={"fact_tags": ["deepfake_content", "synthetic_media_labeling"]})
        finding = rule.evaluate(ctx)

        assert finding is not None
        assert finding.reference_id == "EU-ART-50.2"
        assert finding.concept_type == EUConceptType.ARTICLE_50_CONCEPT
        validate_no_legal_language(finding.rationale)

    def test_article_50_4_text_disclosure(self, base_context: IncidentFactContext) -> None:
        rule = EUArticle50TextDisclosureRule()
        ctx = base_context.model_copy(update={"fact_tags": ["ai_generated_public_text", "automated_news_generation"]})
        finding = rule.evaluate(ctx)

        assert finding is not None
        assert finding.reference_id == "EU-ART-50.4"
        assert finding.concept_type == EUConceptType.ARTICLE_50_CONCEPT
        validate_no_legal_language(finding.rationale)


# ==============================================================================
# 5. Rule Family D4: General-Purpose AI Concepts Tests
# ==============================================================================


class TestGPAIConceptualRules:
    """Verify deterministic evaluation of General-Purpose AI model concepts (Articles 51 and 53)."""

    def test_article_51_systemic_risk(self, base_context: IncidentFactContext) -> None:
        rule = EUGPAISystemicRiskRule()
        ctx = base_context.model_copy(update={"fact_tags": ["gpai_systemic_risk", "high_compute_foundation_model"]})
        finding = rule.evaluate(ctx)

        assert finding is not None
        assert finding.reference_id == "EU-ART-51"
        assert finding.concept_type == EUConceptType.GPAI_CONCEPT
        validate_no_legal_language(finding.rationale)

    def test_article_53_provider_obligations(self, base_context: IncidentFactContext) -> None:
        rule = EUGPAIProviderObligationsRule()
        ctx = base_context.model_copy(update={"fact_tags": ["gpai_provider_documentation", "model_training_summary"]})
        finding = rule.evaluate(ctx)

        assert finding is not None
        assert finding.reference_id == "EU-ART-53"
        assert finding.concept_type == EUConceptType.GPAI_CONCEPT
        validate_no_legal_language(finding.rationale)


# ==============================================================================
# 6. Rule Family D5: Operational Control Concepts Tests
# ==============================================================================


class TestOperationalControlConceptualRules:
    """Verify deterministic evaluation of operational control concepts (Arts 10, 12, 14, 15, 72, 73)."""

    def test_article_10_data_governance(self, base_context: IncidentFactContext) -> None:
        rule = EUArticle10DataGovernanceRule()
        ctx = base_context.model_copy(update={"fact_tags": ["training_data_governance", "dataset_bias"]})
        finding = rule.evaluate(ctx)

        assert finding is not None
        assert finding.reference_id == "EU-ART-10"
        assert finding.concept_type == EUConceptType.OPERATIONAL_CONTROL_CONCEPT
        validate_no_legal_language(finding.rationale)

    def test_article_12_logging(self, base_context: IncidentFactContext) -> None:
        rule = EUArticle12LoggingRule()
        ctx = base_context.model_copy(update={"fact_tags": ["audit_logging_deficiency", "event_recording_gap"]})
        finding = rule.evaluate(ctx)

        assert finding is not None
        assert finding.reference_id == "EU-ART-12"
        assert finding.concept_type == EUConceptType.OPERATIONAL_CONTROL_CONCEPT
        validate_no_legal_language(finding.rationale)

    def test_article_14_human_oversight(self, base_context: IncidentFactContext) -> None:
        rule = EUArticle14HumanOversightRule()
        ctx = base_context.model_copy(update={"fact_tags": ["human_oversight_failure", "automation_bias"]})
        finding = rule.evaluate(ctx)

        assert finding is not None
        assert finding.reference_id == "EU-ART-14"
        assert finding.concept_type == EUConceptType.OPERATIONAL_CONTROL_CONCEPT
        validate_no_legal_language(finding.rationale)

    def test_article_15_robustness_cybersecurity(self, base_context: IncidentFactContext) -> None:
        rule = EUArticle15RobustnessCybersecurityRule()
        ctx = base_context.model_copy(update={"fact_tags": ["adversarial_vulnerability", "prompt_injection_susceptibility"]})
        finding = rule.evaluate(ctx)

        assert finding is not None
        assert finding.reference_id == "EU-ART-15"
        assert finding.concept_type == EUConceptType.OPERATIONAL_CONTROL_CONCEPT
        validate_no_legal_language(finding.rationale)

    def test_article_72_post_market_monitoring(self, base_context: IncidentFactContext) -> None:
        rule = EUArticle72PostMarketMonitoringRule()
        ctx = base_context.model_copy(update={"fact_tags": ["post_market_monitoring_deficiency", "field_telemetry_gap"]})
        finding = rule.evaluate(ctx)

        assert finding is not None
        assert finding.reference_id == "EU-ART-72"
        assert finding.concept_type == EUConceptType.OPERATIONAL_CONTROL_CONCEPT
        validate_no_legal_language(finding.rationale)

    def test_article_73_serious_incident_reporting(self, base_context: IncidentFactContext) -> None:
        rule = EUArticle73SeriousIncidentReportingRule()
        ctx = base_context.model_copy(update={"fact_tags": ["incident_reporting_protocol", "authority_notification_delay"]})
        finding = rule.evaluate(ctx)

        assert finding is not None
        assert finding.reference_id == "EU-ART-73"
        assert finding.concept_type == EUConceptType.OPERATIONAL_CONTROL_CONCEPT
        validate_no_legal_language(finding.rationale)


# ==============================================================================
# 7. Rule Family D6: Serious Incident Conceptual Relevance Tests
# ==============================================================================


class TestSeriousIncidentConceptualRule:
    """Verify deterministic evaluation of Article 3(49) serious incident harm thresholds."""

    def test_article_3_49_serious_incident_matched(self, base_context: IncidentFactContext) -> None:
        rule = EUArticle349SeriousIncidentRule()
        ctx = base_context.model_copy(update={"fact_tags": ["death_or_serious_health_injury", "critical_infrastructure_disruption"]})
        finding = rule.evaluate(ctx)

        assert finding is not None
        assert finding.reference_id == "EU-ART-3.49"
        assert finding.concept_type == EUConceptType.SERIOUS_INCIDENT_CONCEPT
        assert finding.relevance_level == EUConceptualRelevanceLevel.POTENTIALLY_RELEVANT_FOR_QUALIFIED_REVIEW
        validate_no_legal_language(finding.rationale)

    def test_article_3_49_serious_incident_unmatched(self, base_context: IncidentFactContext) -> None:
        rule = EUArticle349SeriousIncidentRule()
        finding = rule.evaluate(base_context)
        assert finding is None


# ==============================================================================
# 8. Mandatory Safety Controls & Epistemic Modesty Tests
# ==============================================================================


class TestSafetyInvariantsAndModesty:
    """Verify that mandatory safety controls are strictly and unconditionally enforced."""

    def test_zero_evidence_records_yields_zero_affirmative_findings(self) -> None:
        """Safety Rule 1: No evidence = No affirmative findings."""
        ctx = IncidentFactContext(
            incident_id="INC-EMPTY-001",
            title="Uncorroborated report",
            summary="No verified evidence available.",
            claims=[],
            evidence_records=[],
            fact_tags=["subliminal_technique", "social_scoring"],
        )
        res = evaluate_eu_conceptual_context(ctx)
        assert len(res.findings) == 0
        assert len(res.rule_traces) == 0
        assert res.serious_incident_relevance == EUSeriousIncidentRelevance.INSUFFICIENT_INFORMATION
        assert res.status == EUScreenStatus.PENDING_REVIEW

    def test_conflicting_evidence_preserves_disputes_and_routes_to_pending_review(
        self, base_context: IncidentFactContext
    ) -> None:
        """Disputed facts must remain visible, reduce confidence, and enforce PENDING_REVIEW."""
        ctx = base_context.model_copy(
            update={
                "fact_tags": ["subliminal_technique", "disputed"],
                "disputed_facts": ["Contested whether user choice was genuinely constrained."],
            }
        )
        rule = EUArticle5SubliminalManipulativeRule()
        finding = rule.evaluate(ctx)

        assert finding is not None
        assert finding.evidence_strength == EUEvidenceStrength.DISPUTED
        assert finding.confidence == GovernanceConfidence.LOW
        assert "Contested whether user choice was genuinely constrained." in finding.disputed_facts
        assert finding.review_routing == EUScreenStatus.PENDING_REVIEW

    def test_all_affirmative_findings_unconditionally_route_to_pending_review(
        self, base_context: IncidentFactContext
    ) -> None:
        """Safety Rule 7: Zero automated approvals. All findings must enter PENDING_REVIEW."""
        ctx = base_context.model_copy(
            update={
                "fact_tags": [
                    "subliminal_technique",
                    "deepfake_content",
                    "gpai_systemic_risk",
                    "training_data_governance",
                ]
            }
        )
        res = evaluate_eu_conceptual_context(ctx)
        assert len(res.findings) >= 3
        for finding in res.findings:
            assert finding.review_routing == EUScreenStatus.PENDING_REVIEW
        assert res.status == EUScreenStatus.PENDING_REVIEW

    def test_no_legal_determination_language_in_any_rule_output(
        self, base_context: IncidentFactContext
    ) -> None:
        """Safety Rule 7: Prohibit legal conclusion terminology across all rule outputs."""
        # Fire all rules
        all_tags = [
            "subliminal_technique",
            "vulnerability_exploitation",
            "social_scoring",
            "predictive_policing",
            "untargeted_facial_scraping",
            "workplace_emotion_recognition",
            "sensitive_biometric_categorization",
            "real_time_biometric_id",
            "remote_biometric_identification",
            "critical_infrastructure_safety",
            "educational_admissions",
            "recruitment_screening",
            "creditworthiness_evaluation",
            "law_enforcement_ai",
            "border_control_ai",
            "judicial_assistance_ai",
            "conversational_agent",
            "deepfake_content",
            "ai_generated_public_text",
            "gpai_systemic_risk",
            "gpai_provider_documentation",
            "training_data_governance",
            "audit_logging_deficiency",
            "human_oversight_failure",
            "adversarial_vulnerability",
            "post_market_monitoring_deficiency",
            "incident_reporting_protocol",
            "death_or_serious_health_injury",
        ]
        ctx = base_context.model_copy(update={"fact_tags": all_tags})
        res = evaluate_eu_conceptual_context(ctx)

        assert len(res.findings) == 28, f"Expected 28 findings, got {len(res.findings)}"

        for finding in res.findings:
            validate_no_legal_language(finding.rationale)
            for kf in finding.known_facts:
                validate_no_legal_language(kf)
            for unk in finding.unknowns:
                validate_no_legal_language(unk)
            for df in finding.disputed_facts:
                validate_no_legal_language(df)

        validate_no_legal_language(res.rationale)

    def test_deterministic_repeatability(self, base_context: IncidentFactContext) -> None:
        """Identical inputs must produce bit-for-bit identical findings and traces."""
        ctx = base_context.model_copy(update={"fact_tags": ["deepfake_content", "gpai_systemic_risk"]})
        res1 = evaluate_eu_conceptual_context(ctx)
        res2 = evaluate_eu_conceptual_context(ctx)

        d1 = res1.model_dump()
        d2 = res2.model_dump()
        for t in d1["rule_traces"]:
            t.pop("created_at", None)
        for t in d2["rule_traces"]:
            t.pop("created_at", None)
        assert d1 == d2


# ==============================================================================
# 9. EURelevanceScreeningEngine End-to-End & Persistence Tests
# ==============================================================================


class TestEURelevanceScreeningEngine:
    """Verify complete orchestration and relational database persistence of EU AI Act screens."""

    def test_screen_incident_end_to_end(
        self, loaded_eu_ref_schema: FrameworkReferenceSetSchema, base_context: IncidentFactContext
    ) -> None:
        engine = EURelevanceScreeningEngine(reference_set=loaded_eu_ref_schema)
        ctx = base_context.model_copy(
            update={
                "fact_tags": [
                    "eu_established",
                    "machine_learning",
                    "autonomous_inference",
                    "developer",
                    "deepfake_content",
                    "synthetic_media_labeling",
                ],
                "incident_date": date(2026, 10, 1),
            }
        )

        screen: EULegalRelevanceScreenSchema = engine.screen_incident(ctx)

        # Core assertions
        assert screen.incident_id == "INC-2026-EU-CONCEPT-001"
        assert screen.status == EUScreenStatus.PENDING_REVIEW
        assert screen.relevance_level == EURelevanceLevel.CONCEPTUAL_RELEVANCE
        assert screen.nexus_assessment == EUNexusAssessment.POSSIBLE_EU_NEXUS
        assert screen.ai_system_context == "MEETS_DEFINITION"
        assert "PROVIDER" in screen.actor_roles
        assert screen.disclaimer_version == EU_AI_ACT_DISCLAIMER_VERSION
        assert screen.disclaimer_text == EU_AI_ACT_DISCLAIMER_V2

        # References and parents
        assert "EU-ART-50.2" in screen.potentially_relevant_reference_ids
        assert "EU-ART-50" in screen.potentially_relevant_reference_ids  # Parent control
        assert "EU-ART-2" in screen.potentially_relevant_reference_ids
        assert "EU-ART-3.1" in screen.potentially_relevant_reference_ids

        # Traces
        assert len(screen.rule_traces) >= 5
        rule_ids = {t.rule_id for t in screen.rule_traces}
        assert "RULE-EU-NEXUS-01" in rule_ids
        assert "RULE-EU-AISYS-01" in rule_ids
        assert "RULE-EU-ROLE-01" in rule_ids
        assert "RULE-EU-CONC-TRANSP-02" in rule_ids

        # Metadata JSON structured findings
        assert "conceptual_findings" in screen.metadata_json
        assert len(screen.metadata_json["conceptual_findings"]) >= 1

    def test_screen_incident_zero_evidence_modesty(
        self, loaded_eu_ref_schema: FrameworkReferenceSetSchema
    ) -> None:
        engine = EURelevanceScreeningEngine(reference_set=loaded_eu_ref_schema)
        ctx = IncidentFactContext(
            incident_id="INC-EMPTY-002",
            title="Empty incident",
            summary="Zero evidence.",
            claims=[],
            evidence_records=[],
            fact_tags=["subliminal_technique"],
        )
        screen = engine.screen_incident(ctx)

        assert screen.status == EUScreenStatus.PENDING_REVIEW
        assert screen.relevance_level == EURelevanceLevel.INSUFFICIENT_INFORMATION
        assert screen.confidence == GovernanceConfidence.INSUFFICIENT
        assert len(screen.potentially_relevant_reference_ids) == 0
        assert len(screen.rule_traces) == 0

    def test_relational_persistence_of_screen_and_traces(
        self,
        sqlite_session: Session,
        active_eu_reference_set: FrameworkReferenceSetModel,
        loaded_eu_ref_schema: FrameworkReferenceSetSchema,
        base_context: IncidentFactContext,
    ) -> None:
        engine = EURelevanceScreeningEngine(reference_set=loaded_eu_ref_schema)
        ctx = base_context.model_copy(
            update={
                "fact_tags": [
                    "eu_established",
                    "machine_learning",
                    "autonomous_inference",
                    "developer",
                    "subliminal_technique",
                    "behavioral_manipulation",
                ],
                "incident_date": date(2026, 10, 1),
            }
        )

        screen = engine.screen_incident(ctx)
        repo = GovernanceRepository(sqlite_session)
        actor = GovernanceActorIdentity(actor_id="ACTOR-ANALYST-1", is_human=True, role="compliance_screener")

        persisted = repo.create_eu_screen(screen.model_dump(), actor=actor)
        sqlite_session.commit()

        # Verify screen model
        assert persisted.id.startswith("euscreen_")
        assert persisted.status == EUScreenStatus.PENDING_REVIEW.value
        assert persisted.relevance_level == EURelevanceLevel.CONCEPTUAL_RELEVANCE.value
        assert "EU-ART-5.1.a" in persisted.potentially_relevant_reference_ids
        assert "EU-ART-5" in persisted.potentially_relevant_reference_ids
        assert persisted.disclaimer_version == EU_AI_ACT_DISCLAIMER_VERSION

        # Verify persisted traces in relational table
        traces = repo.get_eu_screen_rule_traces(persisted.id)
        assert len(traces) >= 5
        trace_rule_ids = {t.rule_id for t in traces}
        assert "RULE-EU-CONC-PROHIB-01" in trace_rule_ids
        assert "RULE-EU-NEXUS-01" in trace_rule_ids

        # Verify audit trail and chain integrity
        is_valid, audit_errors = repo.verify_governance_audit_chain("eu_legal_relevance_screens", persisted.id)
        assert is_valid is True
        assert len(audit_errors) == 0
