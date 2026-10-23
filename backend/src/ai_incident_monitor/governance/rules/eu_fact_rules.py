"""Core deterministic fact evaluators for EU AI Act informational relevance screening.

Phase 5 Increment 2C-2 Implementation:
Provides offline, inspectable, evidence-linked rule evaluators assessing:
- Rule Family A (Territorial and Market Nexus - Article 2)
- Rule Family B (AI-System Context - Article 3(1))
- Rule Family C (Actor-Role Context - Article 3(2)-(8))
- Temporal Alignment Evaluator (Statutory Effective Dates)
- Rule Family E (Missing Facts & Neutral Follow-Up Questions)

Strict Non-Negotiable Boundaries:
- Zero generative LLMs, embeddings, or heuristic guesswork.
- Zero legal determinations, compliance conclusions, or violation language.
- Pure determinism and explicit epistemic uncertainty preservation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

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
    GovernanceConfidence,
)
from ai_incident_monitor.governance.models import (
    EU_AI_ACT_DISCLAIMER_V2,
    EU_AI_ACT_DISCLAIMER_VERSION,
    EULegalRelevanceScreenSchema,
    EUScreenRuleTraceSchema,
    IncidentFactContext,
    MappingRuleMetadata,
    validate_no_legal_language,
)

# Canonical reference identifier constants from frameworks/eu-ai-act/eu-ai-act-2024-1689.yaml
EU_ART_2_IDENTIFIER = "EU-ART-2"
EU_ART_3_1_IDENTIFIER = "EU-ART-3.1"
DEFAULT_EU_REFERENCE_SET_ID = "eu-ai-act-2024-1689"

# Statutory timeline milestones under Regulation (EU) 2024/1689
STATUTORY_ENTRY_INTO_FORCE = date(2024, 8, 1)
STATUTORY_CHAPTER_I_II_EFFECTIVE = date(2025, 2, 2)  # Chapter I (Definitions) & Chapter II (Prohibited)
STATUTORY_GPAI_EFFECTIVE = date(2025, 8, 2)  # Chapter V (GPAI models)
STATUTORY_GENERAL_EFFECTIVE = date(2026, 8, 2)  # General application & Annex III High-Risk


class BaseEUFactRule(ABC):
    """Abstract base class for EU AI Act deterministic fact evaluation rules."""

    @property
    @abstractmethod
    def metadata(self) -> MappingRuleMetadata:
        """Rule metadata and specification."""
        ...

    @abstractmethod
    def evaluate(self, context: IncidentFactContext) -> dict[str, Any]:
        """Evaluate rule deterministically against incident context.

        Returns a dictionary containing:
            matched (bool): whether rule conditions were met
            matched_condition_ids (list[str]): identifiers of matched conditions
            factual_observations (list[str]): neutral factual statements
            rationale (str): explanatory rationale passing non-legal validation
            updates (dict[str, Any]): domain-specific result values
        """
        ...


# ==============================================================================
# Rule Family A: Territorial and Market Nexus (Article 2)
# ==============================================================================


class EUEstablishmentNexusRule(BaseEUFactRule):
    """Evaluates provider or deployer establishment within an EU Member State (Art. 2(1)(a)-(b))."""

    RULE_ID = "RULE-EU-NEXUS-01"
    RULE_VERSION = "1.0.0"

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.EU_AI_ACT,
            target_identifier=EU_ART_2_IDENTIFIER,
            target_level=ControlLevel.ARTICLE,
            title="EU Article 2 — Establishment or Physical Presence in Member State",
            description=(
                "Evaluates documented factual evidence indicating that the AI provider, developer, "
                "or deployer is established, incorporated, or located within an EU Member State."
            ),
            prerequisite_fact_keys=[
                "eu_established",
                "eu_headquarters",
                "eu_registered",
                "eu_member_state_location",
                "establishment_in_union",
            ],
            applicability=EUNexusAssessment.POSSIBLE_EU_NEXUS.value,
        )

    def evaluate(self, context: IncidentFactContext) -> dict[str, Any]:
        establishment_tags = {
            "eu_established",
            "eu_headquarters",
            "eu_registered",
            "eu_member_state_location",
            "establishment_in_union",
            "eu_office",
        }
        matched_tags = establishment_tags.intersection(context.fact_tags)
        system_ctx_flag = bool(
            context.system_context.get("eu_established")
            or context.system_context.get("establishment_in_union")
        )

        if not matched_tags and not system_ctx_flag:
            return {"matched": False, "matched_condition_ids": [], "factual_observations": [], "rationale": "", "updates": {}}

        matched_conditions = ["COND-NEXUS-ESTABLISHMENT"]
        obs = "Observed evidence indicates provider or deployer establishment or physical presence within an EU Member State."
        validate_no_legal_language(obs, field_name="factual_observations")

        rationale = (
            "Documented incident facts record entity establishment, incorporation, or physical "
            "presence in an EU Member State, satisfying initial territorial nexus indicators under Article 2."
        )
        validate_no_legal_language(rationale, field_name="rationale")

        return {
            "matched": True,
            "matched_condition_ids": matched_conditions,
            "factual_observations": [obs],
            "rationale": rationale,
            "updates": {"nexus_assessment": EUNexusAssessment.POSSIBLE_EU_NEXUS},
        }


class EUMarketPlacementNexusRule(BaseEUFactRule):
    """Evaluates placing on the market or putting into service in the EU (Art. 2(1)(a))."""

    RULE_ID = "RULE-EU-NEXUS-02"
    RULE_VERSION = "1.0.0"

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.EU_AI_ACT,
            target_identifier=EU_ART_2_IDENTIFIER,
            target_level=ControlLevel.ARTICLE,
            title="EU Article 2 — Placing on the Market or Putting into Service in the Union",
            description=(
                "Evaluates evidence of commercial distribution, marketing, or operational deployment "
                "of an AI system within European Union territory."
            ),
            prerequisite_fact_keys=[
                "placed_on_market_eu",
                "put_into_service_eu",
                "eu_market_distribution",
                "commercial_availability_eu",
            ],
            applicability=EUNexusAssessment.POSSIBLE_EU_NEXUS.value,
        )

    def evaluate(self, context: IncidentFactContext) -> dict[str, Any]:
        market_tags = {
            "placed_on_market_eu",
            "put_into_service_eu",
            "eu_market_distribution",
            "commercial_availability_eu",
            "marketed_in_union",
            "eu_deployment",
        }
        matched_tags = market_tags.intersection(context.fact_tags)
        system_ctx_flag = bool(
            context.system_context.get("placed_on_market_eu")
            or context.system_context.get("put_into_service_eu")
        )

        if not matched_tags and not system_ctx_flag:
            return {"matched": False, "matched_condition_ids": [], "factual_observations": [], "rationale": "", "updates": {}}

        matched_conditions = ["COND-NEXUS-MARKET-PLACEMENT"]
        obs = "Observed evidence indicates commercial distribution, placing on the market, or putting into service within EU territory."
        validate_no_legal_language(obs, field_name="factual_observations")

        rationale = (
            "Incident evidence records commercial availability, distribution, or operational deployment "
            "within European Union territory, corresponding to Article 2(1)(a) market placement criteria."
        )
        validate_no_legal_language(rationale, field_name="rationale")

        return {
            "matched": True,
            "matched_condition_ids": matched_conditions,
            "factual_observations": [obs],
            "rationale": rationale,
            "updates": {"nexus_assessment": EUNexusAssessment.POSSIBLE_EU_NEXUS},
        }


class EUOutputUsedNexusRule(BaseEUFactRule):
    """Evaluates third-country AI system outputs used in the Union (Art. 2(1)(c))."""

    RULE_ID = "RULE-EU-NEXUS-03"
    RULE_VERSION = "1.0.0"

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.EU_AI_ACT,
            target_identifier=EU_ART_2_IDENTIFIER,
            target_level=ControlLevel.ARTICLE,
            title="EU Article 2 — Third-Country Output Used in the Union",
            description=(
                "Evaluates documented evidence where an AI system located outside the Union produces "
                "outputs (predictions, recommendations, decisions, content) utilized within the Union "
                "or affecting persons located in the EU."
            ),
            prerequisite_fact_keys=[
                "eu_output_used",
                "eu_affected_persons",
                "third_country_output_in_eu",
                "eu_downstream_impact",
            ],
            applicability=EUNexusAssessment.POSSIBLE_EU_NEXUS.value,
        )

    def evaluate(self, context: IncidentFactContext) -> dict[str, Any]:
        output_tags = {
            "eu_output_used",
            "eu_affected_persons",
            "third_country_output_in_eu",
            "eu_downstream_impact",
            "eu_users_affected",
        }
        matched_tags = output_tags.intersection(context.fact_tags)
        system_ctx_flag = bool(
            context.system_context.get("eu_output_used")
            or context.system_context.get("eu_affected_persons")
        )

        if not matched_tags and not system_ctx_flag:
            return {"matched": False, "matched_condition_ids": [], "factual_observations": [], "rationale": "", "updates": {}}

        matched_conditions = ["COND-NEXUS-OUTPUT-USED-IN-EU"]
        obs = "Observed evidence indicates AI system outputs are utilized within the Union or affect natural persons located in the EU."
        validate_no_legal_language(obs, field_name="factual_observations")

        rationale = (
            "Recorded facts indicate that although the primary operator may be located in a third country, "
            "outputs generated by the AI system are utilized within EU territory or impact persons residing in the EU."
        )
        validate_no_legal_language(rationale, field_name="rationale")

        return {
            "matched": True,
            "matched_condition_ids": matched_conditions,
            "factual_observations": [obs],
            "rationale": rationale,
            "updates": {"nexus_assessment": EUNexusAssessment.POSSIBLE_EU_NEXUS},
        }


class EUNexusAbsenceInsufficiencyRule(BaseEUFactRule):
    """Evaluates absence, insufficiency, or exclusively foreign territorial scope under Article 2."""

    RULE_ID = "RULE-EU-NEXUS-04"
    RULE_VERSION = "1.0.0"

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.EU_AI_ACT,
            target_identifier=EU_ART_2_IDENTIFIER,
            target_level=ControlLevel.ARTICLE,
            title="EU Article 2 — Territorial Nexus Absence, Insufficiency, or Foreign Scope",
            description=(
                "Evaluates factual contexts lacking positive EU nexus indicators, including exclusively "
                "foreign deployment or inadequate geographic evidence."
            ),
            prerequisite_fact_keys=[],
            applicability=EUNexusAssessment.INSUFFICIENT_NEXUS_INFORMATION.value,
        )

    def evaluate(self, context: IncidentFactContext) -> dict[str, Any]:
        # Subcase 1: Positive evidence of exclusively non-EU deployment
        foreign_tags = {
            "exclusively_non_eu",
            "outside_eu_territory",
            "no_eu_involvement",
            "foreign_domestic_only",
            "us_only_deployment",
            "asia_only_deployment",
        }
        if foreign_tags.intersection(context.fact_tags) or context.system_context.get("exclusively_non_eu") is True:
            obs = "Documented facts indicate deployment exclusively outside Union territory with no observed Union nexus."
            validate_no_legal_language(obs, field_name="factual_observations")
            rationale = (
                "Verified evidence describes an operational context located and functioning exclusively "
                "outside European Union territory, with no documented distribution or output use in the Union."
            )
            validate_no_legal_language(rationale, field_name="rationale")
            return {
                "matched": True,
                "matched_condition_ids": ["COND-NEXUS-OUTSIDE-TERRITORIAL-SCOPE"],
                "factual_observations": [obs],
                "rationale": rationale,
                "updates": {"nexus_assessment": EUNexusAssessment.OUTSIDE_APPARENT_TERRITORIAL_SCOPE},
            }

        # Subcase 2: Evidence records exist, but contain zero geographic/EU nexus indicators
        if context.evidence_records:
            obs = "Currently recorded evidence contains no observable indicators of European Union territorial or market nexus."
            validate_no_legal_language(obs, field_name="factual_observations")
            rationale = (
                "Available evidence records substantiate incident occurrences but contain no factual indicators "
                "demonstrating establishment, market placement, or output use within the European Union."
            )
            validate_no_legal_language(rationale, field_name="rationale")
            return {
                "matched": True,
                "matched_condition_ids": ["COND-NEXUS-NO-EVIDENCE"],
                "factual_observations": [obs],
                "rationale": rationale,
                "updates": {"nexus_assessment": EUNexusAssessment.NO_EU_NEXUS_EVIDENCE},
            }

        # Subcase 3: Zero or vague evidence
        obs = "Geographic deployment location and European Union nexus facts are not established in available evidence."
        validate_no_legal_language(obs, field_name="factual_observations")
        rationale = "Insufficient geographic and operational evidence to substantiate territorial nexus under Article 2."
        validate_no_legal_language(rationale, field_name="rationale")
        return {
            "matched": True,
            "matched_condition_ids": ["COND-NEXUS-INSUFFICIENT-INFO"],
            "factual_observations": [obs],
            "rationale": rationale,
            "updates": {"nexus_assessment": EUNexusAssessment.INSUFFICIENT_NEXUS_INFORMATION},
        }


ALL_EU_NEXUS_RULES: tuple[BaseEUFactRule, ...] = (
    EUEstablishmentNexusRule(),
    EUMarketPlacementNexusRule(),
    EUOutputUsedNexusRule(),
    EUNexusAbsenceInsufficiencyRule(),
)


# ==============================================================================
# Rule Family B: AI System Context (Article 3(1))
# ==============================================================================


class EUAISystemMeetsDefinitionRule(BaseEUFactRule):
    """Evaluates correspondence to machine-based autonomy and inference definition (Art. 3(1))."""

    RULE_ID = "RULE-EU-AISYS-01"
    RULE_VERSION = "1.0.0"

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.EU_AI_ACT,
            target_identifier=EU_ART_3_1_IDENTIFIER,
            target_level=ControlLevel.ARTICLE,
            title="EU Article 3(1) — Meets AI System Definition",
            description=(
                "Evaluates evidence of machine-based inferencing, varying levels of autonomy, "
                "adaptiveness, and output generation influencing physical or virtual environments."
            ),
            prerequisite_fact_keys=[
                "machine_learning",
                "autonomous_inference",
                "adaptive_system",
                "deep_learning",
                "llm",
            ],
            applicability=EUAISystemRelevance.MEETS_DEFINITION.value,
        )

    def evaluate(self, context: IncidentFactContext) -> dict[str, Any]:
        ai_tags = {
            "machine_learning",
            "autonomous_inference",
            "adaptive_system",
            "deep_learning",
            "llm",
            "neural_network",
            "generative_ai",
            "computer_vision",
            "reinforcement_learning",
            "nlp_model",
            "foundation_model",
            "gpai_model",
            "speech_recognition",
            "predictive_model",
        }
        matched_tags = ai_tags.intersection(context.fact_tags)
        tech_type = str(context.system_context.get("technology_type", "")).lower()
        sys_arch = str(context.system_context.get("system_architecture", "")).lower()

        tech_match = any(
            kw in tech_type or kw in sys_arch
            for kw in ["machine learning", "neural", "llm", "deep learning", "generative ai", "model inference"]
        )

        if not matched_tags and not tech_match:
            return {"matched": False, "matched_condition_ids": [], "factual_observations": [], "rationale": "", "updates": {}}

        matched_conditions = ["COND-AISYS-AUTONOMOUS-INFERENCE"]
        obs = "System operates through machine-based inference and varying levels of autonomy corresponding to the Article 3(1) definition."
        validate_no_legal_language(obs, field_name="factual_observations")

        rationale = (
            "Documented technical characteristics establish machine-based inferencing from inputs to generate "
            "outputs influencing physical or virtual environments, satisfying Article 3(1) criteria."
        )
        validate_no_legal_language(rationale, field_name="rationale")

        return {
            "matched": True,
            "matched_condition_ids": matched_conditions,
            "factual_observations": [obs],
            "rationale": rationale,
            "updates": {"ai_system_context": EUAISystemRelevance.MEETS_DEFINITION},
        }


class EUAISystemBorderlineRule(BaseEUFactRule):
    """Evaluates complex statistical models, heuristic expert systems, or ambiguous autonomy."""

    RULE_ID = "RULE-EU-AISYS-02"
    RULE_VERSION = "1.0.0"

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.EU_AI_ACT,
            target_identifier=EU_ART_3_1_IDENTIFIER,
            target_level=ControlLevel.ARTICLE,
            title="EU Article 3(1) — Borderline or Unclear Autonomy Architecture",
            description=(
                "Evaluates complex statistical scoring, heuristic algorithms, or hybrid systems "
                "where machine inference versus deterministic logic is ambiguous or contested."
            ),
            prerequisite_fact_keys=[
                "borderline_autonomy",
                "heuristic_algorithm",
                "statistical_scoring_system",
                "expert_system",
            ],
            applicability=EUAISystemRelevance.BORDERLINE_OR_UNCLEAR.value,
        )

    def evaluate(self, context: IncidentFactContext) -> dict[str, Any]:
        borderline_tags = {
            "borderline_autonomy",
            "heuristic_algorithm",
            "statistical_scoring_system",
            "expert_system",
            "complex_rules_with_heuristics",
            "unclear_autonomy",
            "hybrid_rule_ml",
        }
        matched_tags = borderline_tags.intersection(context.fact_tags)
        system_ctx_flag = bool(context.system_context.get("borderline_autonomy"))

        if not matched_tags and not system_ctx_flag:
            return {"matched": False, "matched_condition_ids": [], "factual_observations": [], "rationale": "", "updates": {}}

        matched_conditions = ["COND-AISYS-BORDERLINE-AUTONOMY"]
        obs = "System architecture reflects heuristic or statistical automation with unclear autonomous inferencing capability."
        validate_no_legal_language(obs, field_name="factual_observations")

        rationale = (
            "Recorded evidence describes complex algorithmic or statistical scoring but leaves the degree of "
            "autonomous inferencing uncertain, requiring specialized technical review under Article 3(1)."
        )
        validate_no_legal_language(rationale, field_name="rationale")

        return {
            "matched": True,
            "matched_condition_ids": matched_conditions,
            "factual_observations": [obs],
            "rationale": rationale,
            "updates": {"ai_system_context": EUAISystemRelevance.BORDERLINE_OR_UNCLEAR},
        }


class EUAISystemOutsideDefinitionRule(BaseEUFactRule):
    """Evaluates classical deterministic scripts, static databases, or traditional software."""

    RULE_ID = "RULE-EU-AISYS-03"
    RULE_VERSION = "1.0.0"

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.EU_AI_ACT,
            target_identifier=EU_ART_3_1_IDENTIFIER,
            target_level=ControlLevel.ARTICLE,
            title="EU Article 3(1) — Outside AI System Definition (Classical Software)",
            description=(
                "Evaluates deterministic rule engines, traditional procedural code, or static data structures "
                "lacking autonomous machine inferencing."
            ),
            prerequisite_fact_keys=[
                "deterministic_script",
                "rule_based_system",
                "classical_software",
                "static_database",
            ],
            applicability=EUAISystemRelevance.OUTSIDE_DEFINITION.value,
        )

    def evaluate(self, context: IncidentFactContext) -> dict[str, Any]:
        classical_tags = {
            "deterministic_script",
            "rule_based_system",
            "classical_software",
            "static_database",
            "traditional_automation",
            "non_ai_software",
            "relational_database",
            "spreadsheet_macro",
        }
        matched_tags = classical_tags.intersection(context.fact_tags)
        system_ctx_flag = bool(context.system_context.get("classical_software"))

        if not matched_tags and not system_ctx_flag:
            return {"matched": False, "matched_condition_ids": [], "factual_observations": [], "rationale": "", "updates": {}}

        matched_conditions = ["COND-AISYS-CLASSICAL-SOFTWARE"]
        obs = "Factual evidence describes deterministic software or fixed logic lacking autonomous machine inference."
        validate_no_legal_language(obs, field_name="factual_observations")

        rationale = (
            "Recorded facts indicate the system operates via fixed, deterministic rules or procedural scripts, "
            "falling outside the autonomous inferencing criteria established in Article 3(1)."
        )
        validate_no_legal_language(rationale, field_name="rationale")

        return {
            "matched": True,
            "matched_condition_ids": matched_conditions,
            "factual_observations": [obs],
            "rationale": rationale,
            "updates": {"ai_system_context": EUAISystemRelevance.OUTSIDE_DEFINITION},
        }


ALL_EU_AISYS_RULES: tuple[BaseEUFactRule, ...] = (
    EUAISystemMeetsDefinitionRule(),
    EUAISystemBorderlineRule(),
    EUAISystemOutsideDefinitionRule(),
)


# ==============================================================================
# Rule Family C: Actor Role Context (Article 3(2)–(8))
# ==============================================================================


class EUActorRoleProviderRule(BaseEUFactRule):
    """Evaluates provider context (developed, trained, branded, or placed on market under own name)."""

    RULE_ID = "RULE-EU-ROLE-01"
    RULE_VERSION = "1.0.0"

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.EU_AI_ACT,
            target_identifier=EU_ART_3_1_IDENTIFIER,
            target_level=ControlLevel.ARTICLE,
            title="EU Article 3(3) — Provider Context",
            description=(
                "Evaluates evidence indicating an entity developed, trained, branded, or placed an AI system "
                "on the market under its own name or trademark."
            ),
            prerequisite_fact_keys=["provider", "developer", "model_creator", "market_placer"],
            applicability=EUActorRole.PROVIDER.value,
        )

    def evaluate(self, context: IncidentFactContext) -> dict[str, Any]:
        provider_tags = {
            "provider",
            "developer",
            "model_creator",
            "market_placer",
            "branded_system",
            "system_manufacturer",
        }
        matched_tags = provider_tags.intersection(context.fact_tags)
        system_ctx_flag = bool(context.system_context.get("is_provider") or context.system_context.get("provider_entity"))

        if not matched_tags and not system_ctx_flag:
            return {"matched": False, "matched_condition_ids": [], "factual_observations": [], "rationale": "", "updates": {}}

        matched_conditions = ["COND-ROLE-PROVIDER"]
        obs = "Observed evidence indicates entity developed or marketed the AI system under its own name or trademark (Provider context)."
        validate_no_legal_language(obs, field_name="factual_observations")

        rationale = (
            "Recorded facts indicate organizational responsibility for system creation, model training, "
            "or commercial release under its own trademark, corresponding to Article 3(3) provider characteristics."
        )
        validate_no_legal_language(rationale, field_name="rationale")

        return {
            "matched": True,
            "matched_condition_ids": matched_conditions,
            "factual_observations": [obs],
            "rationale": rationale,
            "updates": {"role": EUActorRole.PROVIDER},
        }


class EUActorRoleDeployerRule(BaseEUFactRule):
    """Evaluates deployer context (utilizing AI system under own authority in professional context)."""

    RULE_ID = "RULE-EU-ROLE-02"
    RULE_VERSION = "1.0.0"

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.EU_AI_ACT,
            target_identifier=EU_ART_3_1_IDENTIFIER,
            target_level=ControlLevel.ARTICLE,
            title="EU Article 3(4) — Deployer Context",
            description=(
                "Evaluates evidence indicating an entity utilized an AI system under its authority "
                "in a professional, commercial, or public operational activity."
            ),
            prerequisite_fact_keys=["deployer", "system_operator", "enterprise_user", "downstream_user"],
            applicability=EUActorRole.DEPLOYER.value,
        )

    def evaluate(self, context: IncidentFactContext) -> dict[str, Any]:
        deployer_tags = {
            "deployer",
            "system_operator",
            "enterprise_user",
            "downstream_user",
            "operational_deployer",
            "employer_deployer",
        }
        matched_tags = deployer_tags.intersection(context.fact_tags)
        system_ctx_flag = bool(context.system_context.get("is_deployer") or context.system_context.get("deployer_entity"))

        if not matched_tags and not system_ctx_flag:
            return {"matched": False, "matched_condition_ids": [], "factual_observations": [], "rationale": "", "updates": {}}

        matched_conditions = ["COND-ROLE-DEPLOYER"]
        obs = "Observed evidence indicates entity utilized the AI system under its authority in an operational context (Deployer context)."
        validate_no_legal_language(obs, field_name="factual_observations")

        rationale = (
            "Recorded facts indicate an organization deployed and operated the system within its operational "
            "or professional workflow, corresponding to Article 3(4) deployer characteristics."
        )
        validate_no_legal_language(rationale, field_name="rationale")

        return {
            "matched": True,
            "matched_condition_ids": matched_conditions,
            "factual_observations": [obs],
            "rationale": rationale,
            "updates": {"role": EUActorRole.DEPLOYER},
        }


class EUActorRoleImporterDistributorRule(BaseEUFactRule):
    """Evaluates importer or distributor supply chain intermediary context (Art. 3(6), 3(7))."""

    RULE_ID = "RULE-EU-ROLE-03"
    RULE_VERSION = "1.0.0"

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.EU_AI_ACT,
            target_identifier=EU_ART_3_1_IDENTIFIER,
            target_level=ControlLevel.ARTICLE,
            title="EU Article 3(6)-(7) — Importer or Distributor Context",
            description=(
                "Evaluates evidence indicating supply chain distribution or importation of third-country "
                "AI systems into the European Union market."
            ),
            prerequisite_fact_keys=["importer", "distributor", "channel_partner", "reseller"],
            applicability=EUActorRole.DISTRIBUTOR.value,
        )

    def evaluate(self, context: IncidentFactContext) -> dict[str, Any]:
        importer_tags = {"importer"}
        distributor_tags = {"distributor", "channel_partner", "reseller", "supply_chain_intermediary"}

        matched_imp = importer_tags.intersection(context.fact_tags)
        matched_dist = distributor_tags.intersection(context.fact_tags)

        if not matched_imp and not matched_dist and not context.system_context.get("is_importer") and not context.system_context.get("is_distributor"):
            return {"matched": False, "matched_condition_ids": [], "factual_observations": [], "rationale": "", "updates": {}}

        roles: list[EUActorRole] = []
        if matched_imp or context.system_context.get("is_importer"):
            roles.append(EUActorRole.IMPORTER)
        if matched_dist or context.system_context.get("is_distributor"):
            roles.append(EUActorRole.DISTRIBUTOR)

        matched_conditions = ["COND-ROLE-IMPORTER-DISTRIBUTOR"]
        obs = "Observed evidence indicates supply chain intermediary role (Importer or Distributor context)."
        validate_no_legal_language(obs, field_name="factual_observations")

        rationale = (
            "Recorded facts describe commercial distribution or importation of an AI system without alteration "
            "of core properties, corresponding to intermediary supply chain roles under Article 3(6)-(7)."
        )
        validate_no_legal_language(rationale, field_name="rationale")

        return {
            "matched": True,
            "matched_condition_ids": matched_conditions,
            "factual_observations": [obs],
            "rationale": rationale,
            "updates": {"roles": roles},
        }


class EUActorRoleGPAIProviderRule(BaseEUFactRule):
    """Evaluates upstream general-purpose AI model provider context (Art. 3(63), Art. 51-53)."""

    RULE_ID = "RULE-EU-ROLE-04"
    RULE_VERSION = "1.0.0"

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.EU_AI_ACT,
            target_identifier=EU_ART_3_1_IDENTIFIER,
            target_level=ControlLevel.ARTICLE,
            title="EU Article 3(63) — GPAI Model Provider Context",
            description=(
                "Evaluates evidence indicating upstream development or provision of a general-purpose "
                "AI model integrated into downstream commercial systems."
            ),
            prerequisite_fact_keys=["gpai_provider", "foundation_model_vendor", "upstream_provider"],
            applicability=EUActorRole.GPAI_MODEL_PROVIDER.value,
        )

    def evaluate(self, context: IncidentFactContext) -> dict[str, Any]:
        gpai_tags = {
            "gpai_provider",
            "foundation_model_vendor",
            "upstream_provider",
            "foundation_model_developer",
            "llm_provider",
        }
        matched_tags = gpai_tags.intersection(context.fact_tags)
        system_ctx_flag = bool(context.system_context.get("is_gpai_provider") or context.system_context.get("gpai_model_provider"))

        if not matched_tags and not system_ctx_flag:
            return {"matched": False, "matched_condition_ids": [], "factual_observations": [], "rationale": "", "updates": {}}

        matched_conditions = ["COND-ROLE-GPAI-PROVIDER"]
        obs = "Observed evidence indicates upstream general-purpose AI model provider context."
        validate_no_legal_language(obs, field_name="factual_observations")

        rationale = (
            "Recorded facts indicate the entity developed or supplied a foundation model intended for "
            "general-purpose downstream integration, corresponding to Article 3(63) criteria."
        )
        validate_no_legal_language(rationale, field_name="rationale")

        return {
            "matched": True,
            "matched_condition_ids": matched_conditions,
            "factual_observations": [obs],
            "rationale": rationale,
            "updates": {"role": EUActorRole.GPAI_MODEL_PROVIDER},
        }


ALL_EU_ROLE_RULES: tuple[BaseEUFactRule, ...] = (
    EUActorRoleProviderRule(),
    EUActorRoleDeployerRule(),
    EUActorRoleImporterDistributorRule(),
    EUActorRoleGPAIProviderRule(),
)


# ==============================================================================
# Temporal Alignment Evaluator
# ==============================================================================


class EUTemporalAlignmentRule(BaseEUFactRule):
    """Compares incident dates against reference library statutory effective dates."""

    RULE_ID = "RULE-EU-TEMPORAL-01"
    RULE_VERSION = "1.0.0"

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.EU_AI_ACT,
            target_identifier=EU_ART_2_IDENTIFIER,
            target_level=ControlLevel.ARTICLE,
            title="EU Temporal Alignment Evaluator",
            description=(
                "Evaluates whether the verified incident occurrence date aligns with, precedes, "
                "or follows relevant statutory effective dates recorded in reference metadata."
            ),
            prerequisite_fact_keys=[],
            applicability=EUTimingAssessment.REFERENCE_METADATA_ALIGNS.value,
        )

    def evaluate_temporal(
        self,
        context: IncidentFactContext,
        target_effective_date: Optional[date] = None,
    ) -> dict[str, Any]:
        """Evaluate temporal correspondence deterministically."""
        # 1. Resolve incident occurrence date
        incident_date: Optional[date] = context.incident_date

        if incident_date is None:
            raw_date = context.system_context.get("incident_date") or context.system_context.get("incident_exact_date")
            if isinstance(raw_date, date):
                incident_date = raw_date
            elif isinstance(raw_date, str):
                try:
                    incident_date = date.fromisoformat(raw_date.strip()[:10])
                except ValueError:
                    incident_date = None

        # If date is not established in context
        if incident_date is None:
            obs = "Incident occurrence date is not established in currently verified evidence records."
            validate_no_legal_language(obs, field_name="factual_observations")
            rationale = (
                "The chronological occurrence date of the incident is unverified, precluding "
                "definitive alignment against statutory effective dates."
            )
            validate_no_legal_language(rationale, field_name="rationale")
            return {
                "matched": True,
                "matched_condition_ids": ["COND-TIMING-INCIDENT-DATE-UNKNOWN"],
                "factual_observations": [obs],
                "rationale": rationale,
                "updates": {
                    "timing_assessment": EUTimingAssessment.INCIDENT_DATE_UNKNOWN,
                    "resolved_incident_date": None,
                },
            }

        # 2. Resolve target effective date (default to general statutory effective date 2026-08-02)
        effective_date = target_effective_date or STATUTORY_GENERAL_EFFECTIVE

        if effective_date is None:
            obs = "Statutory effective date for the reference provision is uncertain or not documented."
            validate_no_legal_language(obs, field_name="factual_observations")
            rationale = "Reference metadata lacks a validated statutory effective date for comparison."
            validate_no_legal_language(rationale, field_name="rationale")
            return {
                "matched": True,
                "matched_condition_ids": ["COND-TIMING-EFFECTIVE-DATE-UNCERTAIN"],
                "factual_observations": [obs],
                "rationale": rationale,
                "updates": {
                    "timing_assessment": EUTimingAssessment.EFFECTIVE_DATE_UNCERTAIN,
                    "resolved_incident_date": incident_date,
                },
            }

        # 3. Compare incident date against effective date
        if incident_date < effective_date:
            obs = (
                f"Incident date ({incident_date.isoformat()}) precedes the statutory effective date "
                f"({effective_date.isoformat()}) of the reference provision; informational screening requires temporal review."
            )
            validate_no_legal_language(obs, field_name="factual_observations")
            rationale = (
                f"The documented incident occurred on {incident_date.isoformat()}, which precedes the statutory "
                f"effective date of {effective_date.isoformat()} in European Union law. Informational relevance "
                "is noted for governance analysis but requires temporal review."
            )
            validate_no_legal_language(rationale, field_name="rationale")
            return {
                "matched": True,
                "matched_condition_ids": ["COND-TIMING-REQUIRES-REVIEW"],
                "factual_observations": [obs],
                "rationale": rationale,
                "updates": {
                    "timing_assessment": EUTimingAssessment.TEMPORAL_CONTEXT_REQUIRES_REVIEW,
                    "resolved_incident_date": incident_date,
                },
            }

        # Incident date >= effective date
        obs = (
            f"Incident date ({incident_date.isoformat()}) aligns with or follows the statutory effective date "
            f"({effective_date.isoformat()}) in reference library metadata."
        )
        validate_no_legal_language(obs, field_name="factual_observations")
        rationale = (
            f"Incident occurrence on {incident_date.isoformat()} coincides with or postdates the applicable "
            f"effective date of {effective_date.isoformat()} documented in statutory reference metadata."
        )
        validate_no_legal_language(rationale, field_name="rationale")
        return {
            "matched": True,
            "matched_condition_ids": ["COND-TIMING-ALIGNS"],
            "factual_observations": [obs],
            "rationale": rationale,
            "updates": {
                "timing_assessment": EUTimingAssessment.REFERENCE_METADATA_ALIGNS,
                "resolved_incident_date": incident_date,
            },
        }

    def evaluate(self, context: IncidentFactContext) -> dict[str, Any]:
        return self.evaluate_temporal(context, target_effective_date=None)


# ==============================================================================
# Rule Family E: Missing Facts & Follow-Up Questions
# ==============================================================================


class EUMissingFactsQuestionsRule(BaseEUFactRule):
    """Identifies epistemic voids and generates neutral fact-gathering follow-up questions."""

    RULE_ID = "RULE-EU-QUESTIONS-01"
    RULE_VERSION = "1.0.0"

    @property
    def metadata(self) -> MappingRuleMetadata:
        return MappingRuleMetadata(
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
            framework_code=FrameworkCode.EU_AI_ACT,
            target_identifier=EU_ART_2_IDENTIFIER,
            target_level=ControlLevel.ARTICLE,
            title="EU Missing Facts and Non-Leading Follow-Up Questions",
            description=(
                "Systematically identifies factual voids across nexus, technical autonomy, actor roles, "
                "and timeline, generating targeted neutral inquiries for human governance investigators."
            ),
            prerequisite_fact_keys=[],
            applicability=EURelevanceLevel.INSUFFICIENT_INFORMATION.value,
        )

    def evaluate_gaps(
        self,
        context: IncidentFactContext,
        nexus_assessment: EUNexusAssessment,
        ai_system_context: EUAISystemRelevance,
        actor_roles: list[EUActorRole],
        actor_role_confidence: EUActorRoleConfidence,
        timing_assessment: EUTimingAssessment,
    ) -> dict[str, Any]:
        """Synthesize missing facts and generate neutral follow-up questions based on evaluation state."""
        missing_facts: list[str] = []
        follow_up_questions: list[str] = []
        matched_conditions: list[str] = []

        # 1. Territorial Nexus Gap
        if nexus_assessment in {
            EUNexusAssessment.INSUFFICIENT_NEXUS_INFORMATION,
            EUNexusAssessment.NO_EU_NEXUS_EVIDENCE,
        }:
            matched_conditions.append("COND-QUESTIONS-NEXUS")
            mf = "Geographic deployment location and commercial distribution within the European Union."
            validate_no_legal_language(mf, field_name="missing_facts")
            missing_facts.append(mf)

            q1 = "Where was the AI system placed on the market, put into service, or commercially deployed?"
            q2 = "Are natural persons affected by the system outputs located within an EU Member State?"
            validate_no_legal_language(q1, field_name="follow_up_questions")
            validate_no_legal_language(q2, field_name="follow_up_questions")
            follow_up_questions.extend([q1, q2])

        # 2. AI System Context Gap
        if ai_system_context in {
            EUAISystemRelevance.INSUFFICIENT_INFORMATION,
            EUAISystemRelevance.BORDERLINE_OR_UNCLEAR,
        }:
            matched_conditions.append("COND-QUESTIONS-AUTONOMY")
            mf = "System technical architecture and degree of autonomous machine inferencing."
            validate_no_legal_language(mf, field_name="missing_facts")
            missing_facts.append(mf)

            q = "Does the system generate outputs through autonomous machine inference or through deterministic rule sets?"
            validate_no_legal_language(q, field_name="follow_up_questions")
            follow_up_questions.append(q)

        # 3. Actor Role Context Gap
        if (
            actor_role_confidence in {EUActorRoleConfidence.UNKNOWN, EUActorRoleConfidence.DISPUTED}
            or not actor_roles
            or EUActorRole.UNKNOWN in actor_roles
        ):
            matched_conditions.append("COND-QUESTIONS-ROLE")
            mf = "Entity operational role and supply-chain relationship (provider versus deployer)."
            validate_no_legal_language(mf, field_name="missing_facts")
            missing_facts.append(mf)

            q1 = "What entity determined the system intended purpose and marketed it under its name?"
            q2 = "Did the operational user deploy the system under its own authority without modifying core parameters?"
            validate_no_legal_language(q1, field_name="follow_up_questions")
            validate_no_legal_language(q2, field_name="follow_up_questions")
            follow_up_questions.extend([q1, q2])

        # 4. Temporal Context Gap
        if timing_assessment == EUTimingAssessment.INCIDENT_DATE_UNKNOWN:
            matched_conditions.append("COND-QUESTIONS-TIMING")
            mf = "Verified date or timeframe of incident occurrence."
            validate_no_legal_language(mf, field_name="missing_facts")
            missing_facts.append(mf)

            q = "On what specific date or date range did the incident or deployment take place?"
            validate_no_legal_language(q, field_name="follow_up_questions")
            follow_up_questions.append(q)

        # Incorporate existing unknowns from incident context as potential missing facts
        for unk in context.unknowns[:2]:
            if unk not in missing_facts:
                validate_no_legal_language(unk, field_name="unknowns_as_missing_facts")
                missing_facts.append(unk)

        rationale = (
            f"Generated {len(follow_up_questions)} targeted follow-up inquiries to address "
            f"{len(missing_facts)} documented factual voids across territorial nexus, technical autonomy, "
            "actor supply-chain roles, and occurrence timing."
        )
        validate_no_legal_language(rationale, field_name="rationale")

        return {
            "matched": bool(missing_facts or follow_up_questions),
            "matched_condition_ids": matched_conditions,
            "factual_observations": [],
            "rationale": rationale,
            "updates": {
                "missing_facts": missing_facts,
                "follow_up_questions": follow_up_questions,
            },
        }

    def evaluate(self, context: IncidentFactContext) -> dict[str, Any]:
        # Fallback evaluation assuming uninitialized state
        return self.evaluate_gaps(
            context=context,
            nexus_assessment=EUNexusAssessment.INSUFFICIENT_NEXUS_INFORMATION,
            ai_system_context=EUAISystemRelevance.INSUFFICIENT_INFORMATION,
            actor_roles=[EUActorRole.UNKNOWN],
            actor_role_confidence=EUActorRoleConfidence.UNKNOWN,
            timing_assessment=EUTimingAssessment.INCIDENT_DATE_UNKNOWN,
        )


# ==============================================================================
# Screening Context Evaluator & Result Schema
# ==============================================================================


class EUFactEvaluationResult(BaseModel):
    """Consolidated outcome of core deterministic fact evaluations for EU AI Act screening."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    incident_id: str = Field(min_length=1, max_length=64)
    reference_set_id: str = Field(default=DEFAULT_EU_REFERENCE_SET_ID, max_length=64)
    nexus_assessment: EUNexusAssessment
    ai_system_context: EUAISystemRelevance
    actor_roles: list[EUActorRole]
    actor_role_confidence: EUActorRoleConfidence
    timing_assessment: EUTimingAssessment
    known_facts: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    disputed_facts: list[str] = Field(default_factory=list)
    missing_facts: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    rule_traces: list[EUScreenRuleTraceSchema] = Field(default_factory=list)
    rationale: str = Field(min_length=1)

    def to_screen_dict(self) -> dict[str, Any]:
        """Convert evaluation result into dictionary compatible with GovernanceRepository.create_eu_screen."""
        return {
            "incident_id": self.incident_id,
            "reference_set_id": self.reference_set_id,
            "screen_version": "1.0.0",
            "status": EUScreenStatus.DRAFT.value,
            "relevance_level": EURelevanceLevel.INSUFFICIENT_INFORMATION.value,
            "nexus_assessment": self.nexus_assessment.value,
            "ai_system_context": self.ai_system_context.value,
            "actor_roles": [r.value for r in self.actor_roles],
            "actor_role_confidence": self.actor_role_confidence.value,
            "timing_assessment": self.timing_assessment.value,
            "known_facts": list(self.known_facts),
            "unknowns": list(self.unknowns),
            "disputed_facts": list(self.disputed_facts),
            "missing_facts": list(self.missing_facts),
            "follow_up_questions": list(self.follow_up_questions),
            "rationale": self.rationale,
            "disclaimer_version": EU_AI_ACT_DISCLAIMER_VERSION,
            "disclaimer_text": EU_AI_ACT_DISCLAIMER_V2,
            "rule_traces": self.rule_traces,
        }

    def to_screen_schema(
        self,
        evidence_ids: Optional[list[str]] = None,
        status: EUScreenStatus = EUScreenStatus.DRAFT,
    ) -> EULegalRelevanceScreenSchema:
        """Construct a validated EULegalRelevanceScreenSchema."""
        return EULegalRelevanceScreenSchema(
            incident_id=self.incident_id,
            reference_set_id=self.reference_set_id,
            screen_version="1.0.0",
            status=status,
            relevance_level=EURelevanceLevel.INSUFFICIENT_INFORMATION,
            nexus_assessment=self.nexus_assessment,
            ai_system_context=self.ai_system_context.value,
            actor_roles=[r.value for r in self.actor_roles],
            actor_role_confidence=self.actor_role_confidence,
            timing_assessment=self.timing_assessment,
            known_facts=self.known_facts,
            unknowns=self.unknowns,
            disputed_facts=self.disputed_facts,
            missing_facts=self.missing_facts,
            follow_up_questions=self.follow_up_questions,
            rationale=self.rationale,
            evidence_ids=evidence_ids or [],
            rule_traces=self.rule_traces,
            disclaimer_version=EU_AI_ACT_DISCLAIMER_VERSION,
            disclaimer_text=EU_AI_ACT_DISCLAIMER_V2,
        )


def evaluate_eu_fact_context(
    context: IncidentFactContext,
    reference_set_id: str = DEFAULT_EU_REFERENCE_SET_ID,
    target_effective_date: Optional[date] = None,
) -> EUFactEvaluationResult:
    """Coordinate core deterministic fact evaluators for EU AI Act informational screening.

    Executes:
    1. Rule Family A (Territorial and Market Nexus - Art. 2)
    2. Rule Family B (AI-System Context - Art. 3(1))
    3. Rule Family C (Actor-Role Context - Art. 3(2)-(8))
    4. Temporal Alignment Evaluator (Statutory Effective Dates)
    5. Rule Family E (Missing Facts & Neutral Follow-Up Questions)

    Args:
        context: Validated IncidentFactContext with evidence records, fact tags, and system context.
        reference_set_id: Identifier of the authoritative EU reference set (default 'eu-ai-act-2024-1689').
        target_effective_date: Optional specific effective date for temporal evaluation.

    Returns:
        Structured, immutable EUFactEvaluationResult with complete rule provenance traces.
    """
    rule_traces: list[EUScreenRuleTraceSchema] = []
    known_facts: list[str] = list(context.known_facts)
    unknowns: list[str] = list(context.unknowns)
    disputed_facts: list[str] = list(context.disputed_facts)
    rationales: list[str] = []

    # --------------------------------------------------------------------------
    # 1. Evaluate Rule Family A (Nexus)
    # --------------------------------------------------------------------------
    nexus_assessment: EUNexusAssessment = EUNexusAssessment.INSUFFICIENT_NEXUS_INFORMATION
    nexus_evaluated = False

    # Check positive nexus rules in order of directness
    for rule in (EUEstablishmentNexusRule(), EUMarketPlacementNexusRule(), EUOutputUsedNexusRule()):
        res = rule.evaluate(context)
        if res.get("matched"):
            nexus_assessment = res["updates"]["nexus_assessment"]
            known_facts.extend(res.get("factual_observations", []))
            rationales.append(res.get("rationale", ""))
            rule_traces.append(
                EUScreenRuleTraceSchema(
                    rule_id=rule.RULE_ID,
                    rule_version=rule.RULE_VERSION,
                    reference_set_id=reference_set_id,
                    matched_condition_ids=res.get("matched_condition_ids", []),
                )
            )
            nexus_evaluated = True
            break

    # If no positive nexus condition matched, evaluate absence/insufficiency rule
    if not nexus_evaluated:
        absence_rule = EUNexusAbsenceInsufficiencyRule()
        res = absence_rule.evaluate(context)
        nexus_assessment = res["updates"]["nexus_assessment"]
        known_facts.extend(res.get("factual_observations", []))
        rationales.append(res.get("rationale", ""))
        rule_traces.append(
            EUScreenRuleTraceSchema(
                rule_id=absence_rule.RULE_ID,
                rule_version=absence_rule.RULE_VERSION,
                reference_set_id=reference_set_id,
                matched_condition_ids=res.get("matched_condition_ids", []),
            )
        )

    # --------------------------------------------------------------------------
    # 2. Evaluate Rule Family B (AI System Context)
    # --------------------------------------------------------------------------
    ai_system_context: EUAISystemRelevance = EUAISystemRelevance.INSUFFICIENT_INFORMATION
    aisys_evaluated = False

    for rule in (EUAISystemMeetsDefinitionRule(), EUAISystemBorderlineRule(), EUAISystemOutsideDefinitionRule()):
        res = rule.evaluate(context)
        if res.get("matched"):
            ai_system_context = res["updates"]["ai_system_context"]
            known_facts.extend(res.get("factual_observations", []))
            rationales.append(res.get("rationale", ""))
            rule_traces.append(
                EUScreenRuleTraceSchema(
                    rule_id=rule.RULE_ID,
                    rule_version=rule.RULE_VERSION,
                    reference_set_id=reference_set_id,
                    matched_condition_ids=res.get("matched_condition_ids", []),
                )
            )
            aisys_evaluated = True
            break

    if not aisys_evaluated:
        obs = "Technical architecture and inferencing characteristics of the system are not documented in available evidence."
        validate_no_legal_language(obs, field_name="unknowns")
        unknowns.append(obs)
        rule_traces.append(
            EUScreenRuleTraceSchema(
                rule_id="RULE-EU-AISYS-01",
                rule_version="1.0.0",
                reference_set_id=reference_set_id,
                matched_condition_ids=["COND-AISYS-INSUFFICIENT-INFO"],
            )
        )

    # --------------------------------------------------------------------------
    # 3. Evaluate Rule Family C (Actor Roles Context)
    # --------------------------------------------------------------------------
    detected_roles: list[EUActorRole] = []
    role_traces_matched: list[str] = []

    for rule in (
        EUActorRoleProviderRule(),
        EUActorRoleDeployerRule(),
        EUActorRoleImporterDistributorRule(),
        EUActorRoleGPAIProviderRule(),
    ):
        res = rule.evaluate(context)
        if res.get("matched"):
            updates = res.get("updates", {})
            if "role" in updates:
                detected_roles.append(updates["role"])
            if "roles" in updates:
                detected_roles.extend(updates["roles"])
            known_facts.extend(res.get("factual_observations", []))
            rationales.append(res.get("rationale", ""))
            rule_traces.append(
                EUScreenRuleTraceSchema(
                    rule_id=rule.RULE_ID,
                    rule_version=rule.RULE_VERSION,
                    reference_set_id=reference_set_id,
                    matched_condition_ids=res.get("matched_condition_ids", []),
                )
            )
            role_traces_matched.extend(res.get("matched_condition_ids", []))

    # Deduplicate roles preserving order
    unique_roles: list[EUActorRole] = []
    for r in detected_roles:
        if r not in unique_roles:
            unique_roles.append(r)

    # Resolve actor role confidence
    is_disputed = (
        "disputed_role" in context.fact_tags
        or "disputed_actor_role" in context.fact_tags
        or any(
            any(term in df.lower() for term in ["provider", "deployer", "developer", "operator", "role"])
            for df in context.disputed_facts
        )
    )

    if is_disputed:
        actor_role_confidence = EUActorRoleConfidence.DISPUTED
        if not unique_roles:
            unique_roles = [EUActorRole.UNKNOWN]
    elif unique_roles:
        # Check corroboration in evidence records
        has_corroboration = any(
            ev.get("corroboration_status") == "FULLY_CORROBORATED"
            for ev in context.evidence_records
        ) or len(context.evidence_records) >= 2
        actor_role_confidence = (
            EUActorRoleConfidence.IDENTIFIED_FROM_EVIDENCE
            if has_corroboration
            else EUActorRoleConfidence.POSSIBLE_FROM_EVIDENCE
        )
    else:
        actor_role_confidence = EUActorRoleConfidence.UNKNOWN
        unique_roles = [EUActorRole.UNKNOWN]

    # --------------------------------------------------------------------------
    # 4. Temporal Alignment Evaluation
    # --------------------------------------------------------------------------
    temporal_rule = EUTemporalAlignmentRule()
    temporal_res = temporal_rule.evaluate_temporal(context, target_effective_date=target_effective_date)
    timing_assessment = temporal_res["updates"]["timing_assessment"]
    known_facts.extend(temporal_res.get("factual_observations", []))
    rationales.append(temporal_res.get("rationale", ""))
    rule_traces.append(
        EUScreenRuleTraceSchema(
            rule_id=temporal_rule.RULE_ID,
            rule_version=temporal_rule.RULE_VERSION,
            reference_set_id=reference_set_id,
            matched_condition_ids=temporal_res.get("matched_condition_ids", []),
        )
    )

    # --------------------------------------------------------------------------
    # 5. Rule Family E: Missing Facts & Follow-Up Questions
    # --------------------------------------------------------------------------
    questions_rule = EUMissingFactsQuestionsRule()
    questions_res = questions_rule.evaluate_gaps(
        context=context,
        nexus_assessment=nexus_assessment,
        ai_system_context=ai_system_context,
        actor_roles=unique_roles,
        actor_role_confidence=actor_role_confidence,
        timing_assessment=timing_assessment,
    )
    missing_facts = questions_res["updates"].get("missing_facts", [])
    follow_up_questions = questions_res["updates"].get("follow_up_questions", [])
    if questions_res.get("matched"):
        rationales.append(questions_res.get("rationale", ""))
        rule_traces.append(
            EUScreenRuleTraceSchema(
                rule_id=questions_rule.RULE_ID,
                rule_version=questions_rule.RULE_VERSION,
                reference_set_id=reference_set_id,
                matched_condition_ids=questions_res.get("matched_condition_ids", []),
            )
        )

    # --------------------------------------------------------------------------
    # 6. Synthesis & Deduplication
    # --------------------------------------------------------------------------
    # Deduplicate facts preserving order
    dedup_known: list[str] = []
    for kf in known_facts:
        if kf and kf not in dedup_known:
            dedup_known.append(kf)

    dedup_unknown: list[str] = []
    for unk in unknowns:
        if unk and unk not in dedup_unknown:
            dedup_unknown.append(unk)

    dedup_disputed: list[str] = []
    for df in disputed_facts:
        if df and df not in dedup_disputed:
            dedup_disputed.append(df)

    dedup_missing: list[str] = []
    for mf in missing_facts:
        if mf and mf not in dedup_missing:
            dedup_missing.append(mf)

    dedup_questions: list[str] = []
    for q in follow_up_questions:
        if q and q not in dedup_questions:
            dedup_questions.append(q)

    # Synthesize comprehensive non-legal rationale
    composite_rationale = (
        f"Informational fact screening for incident '{context.incident_id}': "
        f"Territorial nexus assessed as {nexus_assessment.value}. "
        f"AI system technical context evaluated as {ai_system_context.value}. "
        f"Operator attribution reflects roles [{', '.join(r.value for r in unique_roles)}] "
        f"with confidence {actor_role_confidence.value}. "
        f"Temporal alignment evaluated as {timing_assessment.value}."
    )
    validate_no_legal_language(composite_rationale, field_name="composite_rationale")

    # Extra sanity check on all collections
    for item in dedup_known:
        validate_no_legal_language(item, field_name="known_facts")
    for item in dedup_unknown:
        validate_no_legal_language(item, field_name="unknowns")
    for item in dedup_disputed:
        validate_no_legal_language(item, field_name="disputed_facts")
    for item in dedup_missing:
        validate_no_legal_language(item, field_name="missing_facts")
    for item in dedup_questions:
        validate_no_legal_language(item, field_name="follow_up_questions")

    return EUFactEvaluationResult(
        incident_id=context.incident_id,
        reference_set_id=reference_set_id,
        nexus_assessment=nexus_assessment,
        ai_system_context=ai_system_context,
        actor_roles=unique_roles,
        actor_role_confidence=actor_role_confidence,
        timing_assessment=timing_assessment,
        known_facts=dedup_known,
        unknowns=dedup_unknown,
        disputed_facts=dedup_disputed,
        missing_facts=dedup_missing,
        follow_up_questions=dedup_questions,
        rule_traces=rule_traces,
        rationale=composite_rationale,
    )
