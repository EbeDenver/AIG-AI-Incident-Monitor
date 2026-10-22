"""Unit tests for EU AI Act core deterministic fact evaluators.

Phase 5 Increment 2C-2:
Tests:
- Rule Family A: Territorial and Market Nexus (Art. 2)
- Rule Family B: AI-System Context (Art. 3(1))
- Rule Family C: Actor-Role Context (Art. 3(2)–(8))
- Temporal Alignment Evaluator (Statutory Effective Dates)
- Rule Family E: Missing Facts & Follow-Up Questions (Epistemic Voids)
- Evaluation Orchestrator (evaluate_eu_fact_context)
- Relational Persistence of Traces
- Strict Enforcement of Safety Rule 7 (Zero Legal Terminology)
"""

from datetime import date, datetime, timezone
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
    EUNexusAssessment,
    EURelevanceLevel,
    EUScreenStatus,
    EUTimingAssessment,
    FrameworkCode,
    FrameworkStatus,
    GovernanceConfidence,
)
from ai_incident_monitor.governance.models import (
    EU_AI_ACT_DISCLAIMER_V2,
    EU_AI_ACT_DISCLAIMER_VERSION,
    EULegalRelevanceScreenSchema,
    GovernanceActorIdentity,
    IncidentFactContext,
    validate_no_legal_language,
)
from ai_incident_monitor.governance.rules.eu_fact_rules import (
    ALL_EU_AISYS_RULES,
    ALL_EU_NEXUS_RULES,
    ALL_EU_ROLE_RULES,
    EU_ART_2_IDENTIFIER,
    EU_ART_3_1_IDENTIFIER,
    EUAISystemBorderlineRule,
    EUAISystemMeetsDefinitionRule,
    EUAISystemOutsideDefinitionRule,
    EUActorRoleDeployerRule,
    EUActorRoleGPAIProviderRule,
    EUActorRoleImporterDistributorRule,
    EUActorRoleProviderRule,
    EUEstablishmentNexusRule,
    EUMarketPlacementNexusRule,
    EUMissingFactsQuestionsRule,
    EUNexusAbsenceInsufficiencyRule,
    EUOutputUsedNexusRule,
    EUTemporalAlignmentRule,
    EUFactEvaluationResult,
    evaluate_eu_fact_context,
)
from ai_incident_monitor.repositories.governance_repo import GovernanceRepository


@pytest.fixture
def sqlite_session() -> Session:
    """Provide an in-memory SQLite database session initialized with full schema."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def base_incident_context() -> IncidentFactContext:
    """Fixture providing a base minimal incident context."""
    return IncidentFactContext(
        incident_id="INC-2026-EU-001",
        title="Automated customer scoring anomaly",
        summary="A commercial scoring tool produced unintended classification outputs.",
        claims=[
            {
                "claim_id": "CLM-001",
                "statement": "The model produced disparate scores for certain user segments.",
            }
        ],
        evidence_records=[
            {
                "id": "EV-001",
                "directness": "PRIMARY_DIRECT",
                "corroboration_status": "FULLY_CORROBORATED",
                "specificity": "HIGHLY_SPECIFIC",
                "content": "Technical audit of the model deployment.",
            }
        ],
        known_facts=["System was used in production workflows."],
        unknowns=[],
        disputed_facts=[],
        sensitive_domains=[],
        fact_tags=[],
        system_context={},
        incident_date=date(2026, 9, 15),
    )


# ==============================================================================
# 1. Rule Family A: Territorial and Market Nexus (Art. 2)
# ==============================================================================


class TestRuleFamilyANexus:
    """Verifies deterministic territorial and market nexus evaluation under Article 2."""

    def test_establishment_nexus_rule_matches(self, base_incident_context: IncidentFactContext) -> None:
        rule = EUEstablishmentNexusRule()
        ctx = base_incident_context.model_copy(update={"fact_tags": ["eu_headquarters"]})
        res = rule.evaluate(ctx)

        assert res["matched"] is True
        assert "COND-NEXUS-ESTABLISHMENT" in res["matched_condition_ids"]
        assert res["updates"]["nexus_assessment"] == EUNexusAssessment.POSSIBLE_EU_NEXUS
        assert any("establishment" in obs.lower() for obs in res["factual_observations"])

    def test_establishment_nexus_rule_matches_system_context(
        self, base_incident_context: IncidentFactContext
    ) -> None:
        rule = EUEstablishmentNexusRule()
        ctx = base_incident_context.model_copy(update={"system_context": {"eu_established": True}})
        res = rule.evaluate(ctx)

        assert res["matched"] is True
        assert res["updates"]["nexus_assessment"] == EUNexusAssessment.POSSIBLE_EU_NEXUS

    def test_market_placement_nexus_rule_matches(self, base_incident_context: IncidentFactContext) -> None:
        rule = EUMarketPlacementNexusRule()
        ctx = base_incident_context.model_copy(update={"fact_tags": ["placed_on_market_eu"]})
        res = rule.evaluate(ctx)

        assert res["matched"] is True
        assert "COND-NEXUS-MARKET-PLACEMENT" in res["matched_condition_ids"]
        assert res["updates"]["nexus_assessment"] == EUNexusAssessment.POSSIBLE_EU_NEXUS

    def test_output_used_nexus_rule_matches(self, base_incident_context: IncidentFactContext) -> None:
        rule = EUOutputUsedNexusRule()
        ctx = base_incident_context.model_copy(update={"fact_tags": ["eu_affected_persons"]})
        res = rule.evaluate(ctx)

        assert res["matched"] is True
        assert "COND-NEXUS-OUTPUT-USED-IN-EU" in res["matched_condition_ids"]
        assert res["updates"]["nexus_assessment"] == EUNexusAssessment.POSSIBLE_EU_NEXUS

    def test_nexus_absence_outside_territorial_scope(self, base_incident_context: IncidentFactContext) -> None:
        rule = EUNexusAbsenceInsufficiencyRule()
        ctx = base_incident_context.model_copy(update={"fact_tags": ["exclusively_non_eu"]})
        res = rule.evaluate(ctx)

        assert res["matched"] is True
        assert "COND-NEXUS-OUTSIDE-TERRITORIAL-SCOPE" in res["matched_condition_ids"]
        assert res["updates"]["nexus_assessment"] == EUNexusAssessment.OUTSIDE_APPARENT_TERRITORIAL_SCOPE

    def test_nexus_absence_no_eu_nexus_evidence(self, base_incident_context: IncidentFactContext) -> None:
        rule = EUNexusAbsenceInsufficiencyRule()
        # Evidence records exist, but no nexus indicators
        res = rule.evaluate(base_incident_context)

        assert res["matched"] is True
        assert "COND-NEXUS-NO-EVIDENCE" in res["matched_condition_ids"]
        assert res["updates"]["nexus_assessment"] == EUNexusAssessment.NO_EU_NEXUS_EVIDENCE

    def test_nexus_absence_insufficient_information(self, base_incident_context: IncidentFactContext) -> None:
        rule = EUNexusAbsenceInsufficiencyRule()
        # Zero evidence records
        ctx = base_incident_context.model_copy(update={"evidence_records": []})
        res = rule.evaluate(ctx)

        assert res["matched"] is True
        assert "COND-NEXUS-INSUFFICIENT-INFO" in res["matched_condition_ids"]
        assert res["updates"]["nexus_assessment"] == EUNexusAssessment.INSUFFICIENT_NEXUS_INFORMATION


# ==============================================================================
# 2. Rule Family B: AI-System Context (Art. 3(1))
# ==============================================================================


class TestRuleFamilyBAISystem:
    """Verifies deterministic AI system definitional evaluation under Article 3(1)."""

    def test_ai_system_meets_definition_rule(self, base_incident_context: IncidentFactContext) -> None:
        rule = EUAISystemMeetsDefinitionRule()
        ctx = base_incident_context.model_copy(update={"fact_tags": ["machine_learning", "autonomous_inference"]})
        res = rule.evaluate(ctx)

        assert res["matched"] is True
        assert "COND-AISYS-AUTONOMOUS-INFERENCE" in res["matched_condition_ids"]
        assert res["updates"]["ai_system_context"] == EUAISystemRelevance.MEETS_DEFINITION

    def test_ai_system_meets_definition_system_context(
        self, base_incident_context: IncidentFactContext
    ) -> None:
        rule = EUAISystemMeetsDefinitionRule()
        ctx = base_incident_context.model_copy(
            update={"system_context": {"system_architecture": "Deep learning transformer model"}}
        )
        res = rule.evaluate(ctx)

        assert res["matched"] is True
        assert res["updates"]["ai_system_context"] == EUAISystemRelevance.MEETS_DEFINITION

    def test_ai_system_borderline_rule(self, base_incident_context: IncidentFactContext) -> None:
        rule = EUAISystemBorderlineRule()
        ctx = base_incident_context.model_copy(update={"fact_tags": ["heuristic_algorithm", "borderline_autonomy"]})
        res = rule.evaluate(ctx)

        assert res["matched"] is True
        assert "COND-AISYS-BORDERLINE-AUTONOMY" in res["matched_condition_ids"]
        assert res["updates"]["ai_system_context"] == EUAISystemRelevance.BORDERLINE_OR_UNCLEAR

    def test_ai_system_outside_definition_rule(self, base_incident_context: IncidentFactContext) -> None:
        rule = EUAISystemOutsideDefinitionRule()
        ctx = base_incident_context.model_copy(update={"fact_tags": ["deterministic_script", "static_database"]})
        res = rule.evaluate(ctx)

        assert res["matched"] is True
        assert "COND-AISYS-CLASSICAL-SOFTWARE" in res["matched_condition_ids"]
        assert res["updates"]["ai_system_context"] == EUAISystemRelevance.OUTSIDE_DEFINITION

    def test_ai_system_unmatched_returns_false(self, base_incident_context: IncidentFactContext) -> None:
        rule = EUAISystemMeetsDefinitionRule()
        res = rule.evaluate(base_incident_context)
        assert res["matched"] is False


# ==============================================================================
# 3. Rule Family C: Actor Role Context (Art. 3(2)–(8))
# ==============================================================================


class TestRuleFamilyCActorRoles:
    """Verifies deterministic operator attribution and role confidence under Article 3."""

    def test_actor_role_provider_rule(self, base_incident_context: IncidentFactContext) -> None:
        rule = EUActorRoleProviderRule()
        ctx = base_incident_context.model_copy(update={"fact_tags": ["developer", "market_placer"]})
        res = rule.evaluate(ctx)

        assert res["matched"] is True
        assert "COND-ROLE-PROVIDER" in res["matched_condition_ids"]
        assert res["updates"]["role"] == EUActorRole.PROVIDER

    def test_actor_role_deployer_rule(self, base_incident_context: IncidentFactContext) -> None:
        rule = EUActorRoleDeployerRule()
        ctx = base_incident_context.model_copy(update={"fact_tags": ["enterprise_user", "system_operator"]})
        res = rule.evaluate(ctx)

        assert res["matched"] is True
        assert "COND-ROLE-DEPLOYER" in res["matched_condition_ids"]
        assert res["updates"]["role"] == EUActorRole.DEPLOYER

    def test_actor_role_importer_distributor_rule(self, base_incident_context: IncidentFactContext) -> None:
        rule = EUActorRoleImporterDistributorRule()
        ctx = base_incident_context.model_copy(update={"fact_tags": ["importer", "distributor"]})
        res = rule.evaluate(ctx)

        assert res["matched"] is True
        assert "COND-ROLE-IMPORTER-DISTRIBUTOR" in res["matched_condition_ids"]
        roles = res["updates"]["roles"]
        assert EUActorRole.IMPORTER in roles
        assert EUActorRole.DISTRIBUTOR in roles

    def test_actor_role_gpai_provider_rule(self, base_incident_context: IncidentFactContext) -> None:
        rule = EUActorRoleGPAIProviderRule()
        ctx = base_incident_context.model_copy(update={"fact_tags": ["foundation_model_vendor", "gpai_provider"]})
        res = rule.evaluate(ctx)

        assert res["matched"] is True
        assert "COND-ROLE-GPAI-PROVIDER" in res["matched_condition_ids"]
        assert res["updates"]["role"] == EUActorRole.GPAI_MODEL_PROVIDER

    def test_actor_role_confidence_corroborated(self, base_incident_context: IncidentFactContext) -> None:
        ctx = base_incident_context.model_copy(update={"fact_tags": ["developer"]})
        result = evaluate_eu_fact_context(ctx)

        assert EUActorRole.PROVIDER in result.actor_roles
        assert result.actor_role_confidence == EUActorRoleConfidence.IDENTIFIED_FROM_EVIDENCE

    def test_actor_role_confidence_disputed(self, base_incident_context: IncidentFactContext) -> None:
        ctx = base_incident_context.model_copy(
            update={
                "fact_tags": ["developer", "disputed_role"],
                "disputed_facts": ["Contested whether entity acted as provider or deployer."],
            }
        )
        result = evaluate_eu_fact_context(ctx)

        assert result.actor_role_confidence == EUActorRoleConfidence.DISPUTED

    def test_actor_role_confidence_unknown(self, base_incident_context: IncidentFactContext) -> None:
        # No role tags
        result = evaluate_eu_fact_context(base_incident_context)

        assert result.actor_roles == [EUActorRole.UNKNOWN]
        assert result.actor_role_confidence == EUActorRoleConfidence.UNKNOWN


# ==============================================================================
# 4. Temporal Alignment Evaluator
# ==============================================================================


class TestTemporalAlignmentEvaluator:
    """Verifies chronological comparison against statutory reference effective dates."""

    def test_temporal_incident_date_unknown(self, base_incident_context: IncidentFactContext) -> None:
        rule = EUTemporalAlignmentRule()
        ctx = base_incident_context.model_copy(update={"incident_date": None, "system_context": {}})
        res = rule.evaluate(ctx)

        assert res["updates"]["timing_assessment"] == EUTimingAssessment.INCIDENT_DATE_UNKNOWN
        assert "COND-TIMING-INCIDENT-DATE-UNKNOWN" in res["matched_condition_ids"]

    def test_temporal_incident_precedes_statutory_effective_date(
        self, base_incident_context: IncidentFactContext
    ) -> None:
        rule = EUTemporalAlignmentRule()
        # Incident occurred in 2024; general effective date is 2026-08-02
        ctx = base_incident_context.model_copy(update={"incident_date": date(2024, 11, 15)})
        res = rule.evaluate_temporal(ctx, target_effective_date=date(2026, 8, 2))

        assert res["updates"]["timing_assessment"] == EUTimingAssessment.TEMPORAL_CONTEXT_REQUIRES_REVIEW
        assert "COND-TIMING-REQUIRES-REVIEW" in res["matched_condition_ids"]

    def test_temporal_incident_aligns_with_effective_date(
        self, base_incident_context: IncidentFactContext
    ) -> None:
        rule = EUTemporalAlignmentRule()
        # Incident occurred in late 2026; general effective date is 2026-08-02
        ctx = base_incident_context.model_copy(update={"incident_date": date(2026, 9, 1)})
        res = rule.evaluate_temporal(ctx, target_effective_date=date(2026, 8, 2))

        assert res["updates"]["timing_assessment"] == EUTimingAssessment.REFERENCE_METADATA_ALIGNS
        assert "COND-TIMING-ALIGNS" in res["matched_condition_ids"]

    def test_temporal_parse_iso_string_from_system_context(
        self, base_incident_context: IncidentFactContext
    ) -> None:
        rule = EUTemporalAlignmentRule()
        ctx = base_incident_context.model_copy(
            update={
                "incident_date": None,
                "system_context": {"incident_date": "2027-01-10T14:30:00Z"},
            }
        )
        res = rule.evaluate_temporal(ctx, target_effective_date=date(2026, 8, 2))

        assert res["updates"]["timing_assessment"] == EUTimingAssessment.REFERENCE_METADATA_ALIGNS
        assert res["updates"]["resolved_incident_date"] == date(2027, 1, 10)


# ==============================================================================
# 5. Rule Family E: Missing Facts & Follow-Up Questions
# ==============================================================================


class TestRuleFamilyEMissingFactsQuestions:
    """Verifies targeted identification of factual voids and non-leading question generation."""

    def test_missing_facts_and_questions_all_gaps(self, base_incident_context: IncidentFactContext) -> None:
        rule = EUMissingFactsQuestionsRule()
        res = rule.evaluate_gaps(
            context=base_incident_context,
            nexus_assessment=EUNexusAssessment.INSUFFICIENT_NEXUS_INFORMATION,
            ai_system_context=EUAISystemRelevance.INSUFFICIENT_INFORMATION,
            actor_roles=[EUActorRole.UNKNOWN],
            actor_role_confidence=EUActorRoleConfidence.UNKNOWN,
            timing_assessment=EUTimingAssessment.INCIDENT_DATE_UNKNOWN,
        )

        assert res["matched"] is True
        assert "COND-QUESTIONS-NEXUS" in res["matched_condition_ids"]
        assert "COND-QUESTIONS-AUTONOMY" in res["matched_condition_ids"]
        assert "COND-QUESTIONS-ROLE" in res["matched_condition_ids"]
        assert "COND-QUESTIONS-TIMING" in res["matched_condition_ids"]

        missing_facts = res["updates"]["missing_facts"]
        questions = res["updates"]["follow_up_questions"]

        assert any("geographic" in mf.lower() or "territorial" in mf.lower() for mf in missing_facts)
        assert any("architecture" in mf.lower() for mf in missing_facts)
        assert any("role" in mf.lower() for mf in missing_facts)
        assert any("date" in mf.lower() for mf in missing_facts)

        assert any("placed on the market" in q.lower() for q in questions)
        assert any("autonomous machine inference" in q.lower() for q in questions)
        assert any("intended purpose" in q.lower() for q in questions)
        assert any("date or date range" in q.lower() for q in questions)

    def test_missing_facts_minimal_when_established(self, base_incident_context: IncidentFactContext) -> None:
        rule = EUMissingFactsQuestionsRule()
        res = rule.evaluate_gaps(
            context=base_incident_context,
            nexus_assessment=EUNexusAssessment.POSSIBLE_EU_NEXUS,
            ai_system_context=EUAISystemRelevance.MEETS_DEFINITION,
            actor_roles=[EUActorRole.PROVIDER],
            actor_role_confidence=EUActorRoleConfidence.IDENTIFIED_FROM_EVIDENCE,
            timing_assessment=EUTimingAssessment.REFERENCE_METADATA_ALIGNS,
        )

        assert "COND-QUESTIONS-NEXUS" not in res["matched_condition_ids"]
        assert "COND-QUESTIONS-AUTONOMY" not in res["matched_condition_ids"]
        assert "COND-QUESTIONS-ROLE" not in res["matched_condition_ids"]
        assert "COND-QUESTIONS-TIMING" not in res["matched_condition_ids"]
        assert len(res["updates"]["follow_up_questions"]) == 0


# ==============================================================================
# 6. Screening Context Orchestrator: evaluate_eu_fact_context
# ==============================================================================


class TestEvaluateEUFactContextOrchestrator:
    """Verifies end-to-end evaluation orchestration and rule trace generation."""

    def test_full_evaluation_pipeline(self, base_incident_context: IncidentFactContext) -> None:
        ctx = base_incident_context.model_copy(
            update={
                "fact_tags": [
                    "eu_established",
                    "machine_learning",
                    "autonomous_inference",
                    "developer",
                ],
                "incident_date": date(2026, 10, 1),
            }
        )
        result: EUFactEvaluationResult = evaluate_eu_fact_context(ctx)

        assert result.incident_id == "INC-2026-EU-001"
        assert result.nexus_assessment == EUNexusAssessment.POSSIBLE_EU_NEXUS
        assert result.ai_system_context == EUAISystemRelevance.MEETS_DEFINITION
        assert EUActorRole.PROVIDER in result.actor_roles
        assert result.actor_role_confidence == EUActorRoleConfidence.IDENTIFIED_FROM_EVIDENCE
        assert result.timing_assessment == EUTimingAssessment.REFERENCE_METADATA_ALIGNS

        # Check rule traces coverage
        rule_ids = {t.rule_id for t in result.rule_traces}
        assert "RULE-EU-NEXUS-01" in rule_ids
        assert "RULE-EU-AISYS-01" in rule_ids
        assert "RULE-EU-ROLE-01" in rule_ids
        assert "RULE-EU-TEMPORAL-01" in rule_ids

    def test_to_screen_dict_matches_create_eu_screen_expectations(
        self, base_incident_context: IncidentFactContext
    ) -> None:
        result = evaluate_eu_fact_context(base_incident_context)
        screen_dict = result.to_screen_dict()

        assert screen_dict["incident_id"] == "INC-2026-EU-001"
        assert screen_dict["reference_set_id"] == "eu-ai-act-2024-1689"
        assert screen_dict["disclaimer_version"] == EU_AI_ACT_DISCLAIMER_VERSION
        assert screen_dict["disclaimer_text"] == EU_AI_ACT_DISCLAIMER_V2
        assert isinstance(screen_dict["rule_traces"], list)
        assert len(screen_dict["rule_traces"]) >= 4

    def test_to_screen_schema_validates_successfully(
        self, base_incident_context: IncidentFactContext
    ) -> None:
        result = evaluate_eu_fact_context(base_incident_context)
        schema = result.to_screen_schema(evidence_ids=["EV-001"])

        assert isinstance(schema, EULegalRelevanceScreenSchema)
        assert schema.incident_id == "INC-2026-EU-001"
        assert schema.evidence_ids == ["EV-001"]
        assert schema.disclaimer_version == "2024-1689-v2"
        assert schema.disclaimer_text == EU_AI_ACT_DISCLAIMER_V2


# ==============================================================================
# 7. Database Persistence & Trace Storage
# ==============================================================================


class TestDatabasePersistenceOfEvaluatorTraces:
    """Verifies that evaluator output and rule traces persist cleanly in PostgreSQL/SQLite."""

    def test_persist_screen_with_evaluator_traces(
        self,
        sqlite_session: Session,
        base_incident_context: IncidentFactContext,
    ) -> None:
        repo = GovernanceRepository(sqlite_session)
        actor = GovernanceActorIdentity(
            actor_id="usr_governance_analyst_01",
            is_human=True,
            role="Lead EU Governance Analyst",
        )

        # 1. Ensure EU reference set exists
        ref_set = sqlite_session.get(FrameworkReferenceSetModel, "eu-ai-act-2024-1689")
        if not ref_set:
            ref_set = FrameworkReferenceSetModel(
                id="eu-ai-act-2024-1689",
                framework_code="EU_AI_ACT",
                framework_name="Regulation (EU) 2024/1689 (Artificial Intelligence Act)",
                version="2024/1689",
                source_url="http://data.europa.eu/eli/reg/2024/1689/oj",
                publisher="Publications Office of the European Union",
                retrieved_at=datetime.now(timezone.utc),
                verified_at=datetime.now(timezone.utc),
                verified_by="Analyst",
                content_hash="a" * 64,
                status="ACTIVE",
            )
            sqlite_session.add(ref_set)
            sqlite_session.flush()

        # 2. Evaluate context
        ctx = base_incident_context.model_copy(
            update={"fact_tags": ["placed_on_market_eu", "machine_learning", "deployer"]}
        )
        result = evaluate_eu_fact_context(ctx, reference_set_id="eu-ai-act-2024-1689")

        # 3. Create screen in repository
        screen_model = repo.create_eu_screen(result.to_screen_dict(), actor=actor)
        sqlite_session.commit()

        # 4. Verify persisted record and traces
        retrieved_screen = sqlite_session.get(EULegalRelevanceScreenModel, screen_model.id)
        assert retrieved_screen is not None
        assert retrieved_screen.nexus_assessment == EUNexusAssessment.POSSIBLE_EU_NEXUS.value
        assert retrieved_screen.ai_system_context == EUAISystemRelevance.MEETS_DEFINITION.value
        assert EUActorRole.DEPLOYER.value in retrieved_screen.actor_roles

        traces = (
            sqlite_session.query(EUScreenRuleTraceModel)
            .filter_by(eu_legal_relevance_screen_id=retrieved_screen.id)
            .all()
        )
        assert len(traces) >= 4
        trace_rule_ids = {t.rule_id for t in traces}
        assert "RULE-EU-NEXUS-02" in trace_rule_ids
        assert "RULE-EU-AISYS-01" in trace_rule_ids
        assert "RULE-EU-ROLE-02" in trace_rule_ids
        assert "RULE-EU-TEMPORAL-01" in trace_rule_ids


# ==============================================================================
# 8. Strict Enforcement of Safety Rule 7 (Zero Legal Terminology)
# ==============================================================================


class TestSafetyRule7LegalTerminologyExclusion:
    """Verifies that all generated observations, rationales, and questions are free of legal conclusions."""

    def test_all_standard_evaluator_texts_pass_legal_language_filter(
        self, base_incident_context: IncidentFactContext
    ) -> None:
        # Run across all permutations of tags
        tag_combinations = [
            [],
            ["eu_established", "machine_learning", "provider"],
            ["placed_on_market_eu", "heuristic_algorithm", "deployer"],
            ["eu_output_used", "deterministic_script", "importer", "distributor"],
            ["exclusively_non_eu", "gpai_provider", "disputed_role"],
        ]

        for tags in tag_combinations:
            ctx = base_incident_context.model_copy(update={"fact_tags": tags})
            result = evaluate_eu_fact_context(ctx)

            validate_no_legal_language(result.rationale)
            for kf in result.known_facts:
                validate_no_legal_language(kf)
            for unk in result.unknowns:
                validate_no_legal_language(unk)
            for df in result.disputed_facts:
                validate_no_legal_language(df)
            for mf in result.missing_facts:
                validate_no_legal_language(mf)
            for q in result.follow_up_questions:
                validate_no_legal_language(q)

    def test_evaluator_rejects_injected_prohibited_legal_terms(
        self, base_incident_context: IncidentFactContext
    ) -> None:
        prohibited_samples = [
            "This constitutes an unlawful practice under the EU AI Act.",
            "The provider is in breach of Article 10.",
            "Evidence confirms noncompliant deployment.",
            "Entity failed its statutory duty.",
        ]

        for sample in prohibited_samples:
            with pytest.raises(ValueError, match="Prohibited legal determination language detected"):
                validate_no_legal_language(sample)


# ==============================================================================
# 9. Rule Metadata and Canonical Reference Integrity
# ==============================================================================


class TestEUFactRuleMetadataIntegrity:
    """Verifies rule metadata consistency and canonical reference identifiers."""

    def test_all_rules_have_valid_metadata_and_canonical_targets(self) -> None:
        all_rules = (
            ALL_EU_NEXUS_RULES
            + ALL_EU_AISYS_RULES
            + ALL_EU_ROLE_RULES
            + (EUTemporalAlignmentRule(), EUMissingFactsQuestionsRule())
        )

        for rule in all_rules:
            meta = rule.metadata
            assert meta.rule_id.startswith("RULE-EU-")
            assert meta.rule_version == "1.0.0"
            assert meta.framework_code == FrameworkCode.EU_AI_ACT
            assert meta.target_identifier in {EU_ART_2_IDENTIFIER, EU_ART_3_1_IDENTIFIER}
            assert meta.target_level == ControlLevel.ARTICLE
            assert len(meta.title) > 0
            assert len(meta.description) > 0
