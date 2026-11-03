"""LLM client interfaces, deterministic mock implementations, and provider adapters.

Governing Charter: Project Constitution (Rules 1, 2, 3, 4, 11, 14, 16),
ADR-011, SEC-006, OPS-004, Ai-incident-manager-guide.pdf (§1–§3),
amended by Section B (No-Approval Amendment: advisory quality warnings only).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import json
import logging
import os
import re
import time
from typing import Optional, Sequence
import urllib.error
import urllib.request

from ai_incident_monitor.config import (
    get_claude_model,
    get_gemini_model,
    get_llm_provider,
    get_pilot_budget_cap_usd,
    load_env_file,
)
from ai_incident_monitor.domain.taxonomy import IncidentCategory
from ai_incident_monitor.intelligence.prompts import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_evidence_package,
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
    DisputedFactItem,
    EnrichmentClaim,
    EvidenceSufficiency,
    HumanOversightStatus,
    IncidentEnrichmentDossier,
    IncidentEnrichmentPayload,
    IncidentExplanation,
    IncidentSummary,
    MaterialityLevel,
    OrganizationalControlItem,
    PreparednessGuidance,
    ProvenanceItem,
    QualityReview,
    SourceTypeCategory,
    UncertaintyItem,
    VerificationStatus,
)
from ai_incident_monitor.intelligence.validator import EnrichmentValidator

logger = logging.getLogger(__name__)


class LLMClientError(Exception):
    """Base exception for LLM inference failures."""


class LLMConfigurationError(LLMClientError):
    """Raised when provider configuration or credentials are missing."""


class BudgetExceededError(LLMClientError):
    """Raised when request execution would breach the approved pilot budget cap."""


class PilotBudgetGuard:
    """Enforces strict, verifiable spending limits and attempt tracking for live pilots."""

    def __init__(self, max_budget_usd: Optional[float] = None) -> None:
        self.max_budget_usd = max_budget_usd if max_budget_usd is not None else get_pilot_budget_cap_usd()
        self.cumulative_cost_usd: float = 0.0
        self.attempt_count: int = 0
        self.success_count: int = 0
        self.failure_count: int = 0

    def check_and_reserve(self, estimated_call_cost: float) -> None:
        """Reserve cost before dispatch; stop before starting if ceiling is breached."""
        if (self.cumulative_cost_usd + estimated_call_cost) > (self.max_budget_usd + 1e-9):
            msg = (
                f"PILOT BUDGET EXCEEDED: Execution halted. Cumulative spend (${self.cumulative_cost_usd:.4f}) "
                f"+ estimated request cost (${estimated_call_cost:.4f}) exceeds spending ceiling of "
                f"${self.max_budget_usd:.2f} USD."
            )
            logger.error(msg)
            raise BudgetExceededError(msg)
        self.attempt_count += 1

    def record_actual(self, actual_cost_usd: float, success: bool = True) -> None:
        """Record actual usage cost and update outcome counts."""
        self.cumulative_cost_usd = round(self.cumulative_cost_usd + actual_cost_usd, 6)
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1


class BaseLLMClient(ABC):
    """Abstract interface for LLM incident intelligence generation."""

    model_name: str = "base-llm"
    provider_id: str = "base"

    @abstractmethod
    def generate_dossier(
        self,
        prompt: str,
        *,
        incident_id: str,
        title: str,
        summary: str,
        category: str,
        evidence_package: Sequence[ProvenanceItem],
    ) -> tuple[IncidentEnrichmentDossier, int, int, float, str]:
        """Generate structured IncidentEnrichmentDossier.

        Returns:
            Tuple of (dossier, input_tokens, output_tokens, latency_seconds, model_name)
        """
        ...

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate estimated cost in USD based on model pricing."""
        return 0.0

    def generate_enrichment(
        self,
        prompt: str,
        *,
        incident_id: str,
        title: str,
        summary: str,
        category: str,
    ) -> tuple[IncidentEnrichmentPayload, int, int, float, str]:
        """Backward-compatible generation method producing legacy IncidentEnrichmentPayload."""
        package = build_evidence_package(
            incident_id=incident_id,
            title=title,
            summary=summary,
        )
        dossier, in_tok, out_tok, latency, model_id = self.generate_dossier(
            prompt,
            incident_id=incident_id,
            title=title,
            summary=summary,
            category=category,
            evidence_package=package,
        )

        words = summary.split()
        is_brief = len(words) < 10 or summary.strip() == title.strip()
        if is_brief:
            sufficiency = EvidenceSufficiency.LIMITED_EVIDENCE
        elif len(words) < 50:
            sufficiency = EvidenceSufficiency.PARTIAL
        else:
            sufficiency = EvidenceSufficiency.COMPLETE

        explanation = IncidentExplanation(
            executive_summary=dossier.incident_summary.reported_event,
            event_chronology=[
                f"Reported event: {dossier.incident_summary.reported_event}",
                f"Verified outcome: {dossier.incident_summary.verified_outcome or 'Pending independent verification'}",
            ],
            ai_system_role=dossier.ai_involvement.assessment,
            affected_stakeholders=dossier.incident_summary.affected_entities or ["Impacted parties"],
            documented_consequences=dossier.causal_assessment.observed_outcomes or ["Public incident report"],
            unknowns_and_disputes=[u.question for u in dossier.uncertainties],
            evidence_limitations=(
                dossier.provenance[0].limitations if dossier.provenance else "Syndicated feed reporting"
            ),
            sufficiency=sufficiency,
        )

        preparedness = PreparednessGuidance(
            applicable_profiles=[dossier.category if hasattr(dossier, "category") else category],
            early_warning_indicators=dossier.causal_assessment.reported_mechanisms or ["Anomalous AI output"],
            prioritized_preventive_controls=[c.control for c in dossier.organizational_controls if c.control_type == ControlType.PREVENTIVE],
            detection_mechanisms=[c.control for c in dossier.organizational_controls if c.control_type == ControlType.DETECTIVE],
            incident_response_actions=[c.control for c in dossier.organizational_controls if c.control_type == ControlType.CORRECTIVE],
            responsible_functions=["AI Risk Engineering", "Enterprise Governance"],
            validation_methods=[c.validation_test for c in dossier.organizational_controls],
        )

        legacy_payload = IncidentEnrichmentPayload(
            prompt_version=PROMPT_VERSION,
            explanation=explanation,
            preparedness=preparedness,
        )

        return legacy_payload, in_tok, out_tok, latency, model_id


class MockLLMClient(BaseLLMClient):
    """Deterministic, grounded mock LLM client for testing and offline development.

    Strictly satisfies:
    - Zero external network dependencies.
    - Explicit LIMITED_EVIDENCE handling for brief/unsubstantiated records.
    - Full synthesis for rich incidents (e.g. INC-2026-04785D Artex incident).
    """

    provider_id: str = "mock"

    def __init__(self, model_name: str = "mock-intelligence-v2") -> None:
        self.model_name = model_name
        self.validator = EnrichmentValidator()

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        return 0.0

    def generate_dossier(
        self,
        prompt: str,
        *,
        incident_id: str,
        title: str,
        summary: str,
        category: str,
        evidence_package: Sequence[ProvenanceItem],
    ) -> tuple[IncidentEnrichmentDossier, int, int, float, str]:
        start_time = time.time()
        words = summary.split()
        is_brief = len(words) < 10 or summary.strip() == title.strip()
        cat_upper = category.upper()

        primary_eid = evidence_package[0].evidence_id if evidence_package else "E001"

        if is_brief:
            # Explicit limited evidence invariant
            dossier = IncidentEnrichmentDossier(
                incident_id=incident_id,
                assessment_status=AssessmentStatus.PARTIAL,
                incident_summary=IncidentSummary(
                    reported_event=f"Reported incident: {title}. Primary feed provides brief syndicated headline without engineering postmortem.",
                    verified_outcome=None,
                    affected_entities=["Impacted organizations cited in headline"],
                    event_date=None,
                    reporting_date=None,
                ),
                claims=[
                    EnrichmentClaim(
                        claim_id="C001",
                        statement=f"Incident event '{title}' reported in public surveillance stream.",
                        classification=ClaimClassification.ATTRIBUTED_ALLEGATION,
                        verification_status=VerificationStatus.UNVERIFIED,
                        confidence=ConfidenceTier.LOW,
                        supporting_evidence_ids=[primary_eid],
                        reasoning_summary="Primary ingested record is a brief headline lacking technical corroboration.",
                        advisory_review_flag=True,
                    )
                ],
                ai_involvement=AIInvolvement(
                    role=AIInvolvementRole.ALLEGED,
                    system_name=None,
                    documented_capabilities=["Capability details undisclosed in brief wire summary"],
                    autonomy_level=AutonomyLevel.UNKNOWN,
                    human_oversight=HumanOversightStatus.UNKNOWN,
                    supporting_evidence_ids=[primary_eid],
                    assessment="LIMITED_EVIDENCE: Source text does not disclose specific model architecture, inference telemetry, or execution logs.",
                ),
                causal_assessment=CausalAssessment(
                    observed_outcomes=["Public incident notice published in syndication feed."],
                    reported_mechanisms=["LIMITED_EVIDENCE: Mechanism withheld or unstated in source text."],
                    supported_causal_links=[],
                    hypotheses=["System anomaly, automated workflow failure, or unverified external exploitation."],
                    alternative_explanations=["Non-AI software misconfiguration, network outage, or human administrative error."],
                    causal_status=CausalStatus.CAUSALITY_NOT_ESTABLISHED,
                    confidence=ConfidenceTier.LOW,
                    evidence_ids=[primary_eid],
                ),
                uncertainties=[
                    UncertaintyItem(
                        question="Did an AI component actively participate in causing the reported incident?",
                        materiality=MaterialityLevel.HIGH,
                        evidence_needed="Detailed vendor postmortem, technical telemetry, or formal regulatory investigation findings.",
                    )
                ],
                disputed_facts=[],
                provenance=list(evidence_package),
                organizational_controls=[
                    OrganizationalControlItem(
                        risk="Unverified AI telemetry and operational opacity during production incidents.",
                        control="Implement centralized immutable audit logging and telemetry ingestion for all deployed AI services.",
                        control_type=ControlType.PREVENTIVE,
                        incident_specific=False,
                        validation_test="Execute automated synthetic transaction and verify cryptographic trace capture across all pipeline hops.",
                        evidence_ids=[primary_eid],
                    ),
                    OrganizationalControlItem(
                        risk="Silent failure or anomalous automated model behavior.",
                        control="Deploy automated health probes with real-time alerting on distribution drift.",
                        control_type=ControlType.DETECTIVE,
                        incident_specific=False,
                        validation_test="Inject anomalous inputs during staging drills and confirm alert triggering within 30 seconds.",
                        evidence_ids=[primary_eid],
                    ),
                ],
                decision_maker_guidance=DecisionMakerGuidance(
                    key_implications=[
                        "Preliminary public reporting without verifiable postmortem data carries high uncertainty.",
                        "Premature architectural overhauls based on unverified reporting risk misallocating engineering capacity.",
                    ],
                    decisions_to_consider=[
                        "Await verified vendor disclosure or regulatory findings before implementing incident-specific mitigations.",
                        "Re-evaluate baseline defense-in-depth posture for systems operating with similar external interfaces.",
                    ],
                    evidence_required=[
                        "Independent technical analysis or vendor security disclosure.",
                        "Confirmation of root-cause software components.",
                    ],
                    effectiveness_measures=[
                        "Mean time to verify public incident reports impacting company technology stack.",
                    ],
                ),
                consultant_guidance=ConsultantGuidance(
                    discovery_questions=[
                        "Does your enterprise deploy automated decision systems without independent telemetry channels?",
                        "What is your protocol for evaluating external threat intelligence regarding newly reported vulnerabilities?",
                    ],
                    assessment_activities=[
                        "Conduct architecture review of model invocation boundaries.",
                        "Audit completeness of incident logging pipelines.",
                    ],
                    architecture_considerations=[
                        "Ensure fail-safe fallback heuristics exist for all automated model decisions.",
                    ],
                    implementation_controls=[
                        "Enforce strict input sanitization and token rate limiting on external interfaces.",
                    ],
                    acceptance_criteria=[
                        "All production model calls produce structured, queryable audit traces.",
                    ],
                ),
                quality_review=QualityReview(
                    unsupported_claim_count=0,
                    unresolved_evidence_gaps=[],
                    advisory_human_review_flag=True,
                    review_reasons=["Sparse source evidence: analysis limited to syndicated headline."],
                ),
            )
        else:
            # Rich incident synthesis (e.g., INC-2026-04785D or detailed records)
            is_cyber = "CYBER" in cat_upper or "ATTACK" in title.upper() or "ARTEX" in title.upper()

            if is_cyber:
                claims = [
                    EnrichmentClaim(
                        claim_id="C001",
                        statement=f"Adversaries reportedly targeted enterprise assets: {title}.",
                        classification=ClaimClassification.ATTRIBUTED_ALLEGATION,
                        verification_status=VerificationStatus.UNVERIFIED,
                        confidence=ConfidenceTier.LOW,
                        supporting_evidence_ids=[primary_eid],
                        reasoning_summary="Allegation reported by intelligence feeds; independent technical forensics not published in primary excerpt.",
                        advisory_review_flag=True,
                    ),
                    EnrichmentClaim(
                        claim_id="C002",
                        statement="Incident reported in public surveillance and regulatory monitoring streams.",
                        classification=ClaimClassification.CONFIRMED_FACT,
                        verification_status=VerificationStatus.VERIFIED,
                        confidence=ConfidenceTier.HIGH,
                        supporting_evidence_ids=[primary_eid],
                        reasoning_summary="Syndication and public cataloging of the report is empirically verified.",
                        advisory_review_flag=False,
                    ),
                ]
                ai_role = AIInvolvementRole.ALLEGED
                ai_capabilities = ["AI-assisted lure generation", "Automated code vulnerability scanning"]
                autonomy = AutonomyLevel.HUMAN_DIRECTED
                oversight = HumanOversightStatus.DEFICIENT
                ai_assessment = (
                    "AI involvement is an ATTRIBUTED_ALLEGATION cited in external threat summaries. "
                    "Technical telemetry confirming autonomous agentic execution versus human-directed scripting is unverified."
                )
                mechanisms = ["AI-assisted spear-phishing synthesis", "Automated credential spray tooling"]
                hypotheses = ["Adversaries used generative models to craft context-specific lure communications."]
                alternatives = ["Compromised third-party credentials", "Unpatched external VPN vulnerability", "Social engineering without AI assistance"]
                causal_status = CausalStatus.CAUSALITY_NOT_ESTABLISHED
                controls = [
                    OrganizationalControlItem(
                        risk="Credential misuse and API token leakage from agentic tooling.",
                        control="Enforce strict least-privilege scoping and ephemeral credential issuance on all autonomous agent and developer API keys.",
                        control_type=ControlType.PREVENTIVE,
                        incident_specific=True,
                        validation_test="Simulate token privilege escalation; confirm API gateway denies access to out-of-scope resources.",
                        evidence_ids=[primary_eid],
                    ),
                    OrganizationalControlItem(
                        risk="AI-generated phishing and personalized credential harvesting lures.",
                        control="Mandate FIDO2/WebAuthn hardware-bound passkeys for all administrative and user authentication.",
                        control_type=ControlType.PREVENTIVE,
                        incident_specific=True,
                        validation_test="Perform simulated adversary-in-the-middle phishing test; verify hardware tokens prevent token interception.",
                        evidence_ids=[primary_eid],
                    ),
                    OrganizationalControlItem(
                        risk="Automated lateral movement and API key exfiltration.",
                        control="Enforce microsegmentation and strict zero-trust egress network controls on worker nodes.",
                        control_type=ControlType.PREVENTIVE,
                        incident_specific=True,
                        validation_test="Initiate simulated outbound socket connection to unauthorized public IP; confirm kernel drop within 10ms.",
                        evidence_ids=[primary_eid],
                    ),
                    OrganizationalControlItem(
                        risk="Undetected adversary reconnaissance leveraging AI tooling.",
                        control="Deploy continuous behavioral anomaly detection on developer token usage and outbound network sockets.",
                        control_type=ControlType.DETECTIVE,
                        incident_specific=False,
                        validation_test="Simulate abnormal rapid sequence API calls; verify automated session suspension and SOC alert.",
                        evidence_ids=[primary_eid],
                    ),
                ]
                decisions = [
                    "Accelerate phased migration to phishing-resistant authentication across all enterprise identity providers.",
                    "Review external network exposure of internal developer tooling and agent orchestration sandboxes.",
                ]
                disc_questions = [
                    "Does your organization rely on legacy MFA (SMS or mobile push) that is vulnerable to AI-crafted lure campaigns?",
                    "Are autonomous coding assistants permitted access to production credentials or unrestricted outbound network sockets?",
                ]
            else:
                claims = [
                    EnrichmentClaim(
                        claim_id="C001",
                        statement=f"Reported incident event: {title}.",
                        classification=ClaimClassification.ATTRIBUTED_ALLEGATION,
                        verification_status=VerificationStatus.PARTIALLY_VERIFIED,
                        confidence=ConfidenceTier.MEDIUM,
                        supporting_evidence_ids=[primary_eid],
                        reasoning_summary="Documented in primary monitoring feed with factual corroboration from multiple reporting streams.",
                        advisory_review_flag=False,
                    ),
                ]
                ai_role = AIInvolvementRole.CONTRIBUTING
                ai_capabilities = ["Automated inference execution", "Real-time decision scoring"]
                autonomy = AutonomyLevel.ASSISTIVE
                oversight = HumanOversightStatus.EFFECTIVE
                ai_assessment = (
                    f"AI system operated as a contributing factor in the {category} failure mode. "
                    "System telemetry indicates model scoring deviations contributed to the downstream event."
                )
                mechanisms = ["Automated scoring threshold deviation", "Model output distribution drift"]
                hypotheses = ["Model edge case triggered unexpected downstream state change."]
                alternatives = ["Upstream data pipeline corruption", "Human operator override failure"]
                causal_status = CausalStatus.POSSIBLE_CONTRIBUTOR
                controls = [
                    OrganizationalControlItem(
                        risk=f"Unchecked model drift or algorithmic failure in {category} domain.",
                        control="Implement automated circuit breakers with deterministic fallback upon model output anomaly.",
                        control_type=ControlType.PREVENTIVE,
                        incident_specific=True,
                        validation_test="Inject out-of-distribution feature vectors; confirm automated fallback engages without pipeline crash.",
                        evidence_ids=[primary_eid],
                    ),
                    OrganizationalControlItem(
                        risk="Latency in detecting model scoring errors.",
                        control="Continuous statistical monitoring comparing production inference to baseline distributions.",
                        control_type=ControlType.DETECTIVE,
                        incident_specific=False,
                        validation_test="Verify Kolmogorov-Smirnov test trigger fires when distribution shift exceeds 10%.",
                        evidence_ids=[primary_eid],
                    ),
                ]
                decisions = [
                    f"Establish mandatory review thresholds for high-stakes decisions in {category} workflows.",
                    "Audit model calibration and validation test datasets against recent real-world operational distributions.",
                ]
                disc_questions = [
                    "What deterministic guardrails exist between model outputs and operational execution?",
                    "How are edge-case failures surfaced to human operators before systemic harm occurs?",
                ]

            dossier = IncidentEnrichmentDossier(
                incident_id=incident_id,
                assessment_status=AssessmentStatus.COMPLETE,
                incident_summary=IncidentSummary(
                    reported_event=summary[:350] + ("..." if len(summary) > 350 else ""),
                    verified_outcome=f"Documented reporting and operational response within the {category} operational context.",
                    affected_entities=["Impacted organizations", "Affected users and enterprise stakeholders"],
                    event_date=None,
                    reporting_date=None,
                ),
                claims=claims,
                ai_involvement=AIInvolvement(
                    role=ai_role,
                    system_name=None,
                    documented_capabilities=ai_capabilities,
                    autonomy_level=autonomy,
                    human_oversight=oversight,
                    supporting_evidence_ids=[primary_eid],
                    assessment=ai_assessment,
                ),
                causal_assessment=CausalAssessment(
                    observed_outcomes=[summary[:150] + "..."],
                    reported_mechanisms=mechanisms,
                    supported_causal_links=[],
                    hypotheses=hypotheses,
                    alternative_explanations=alternatives,
                    causal_status=causal_status,
                    confidence=ConfidenceTier.MEDIUM,
                    evidence_ids=[primary_eid],
                ),
                uncertainties=[
                    UncertaintyItem(
                        question="What specific model architecture or training data vulnerabilities contributed to the failure?",
                        materiality=MaterialityLevel.HIGH,
                        evidence_needed="Internal engineering postmortem, model card, or architecture audit report.",
                    )
                ],
                disputed_facts=[],
                provenance=list(evidence_package),
                organizational_controls=controls,
                decision_maker_guidance=DecisionMakerGuidance(
                    key_implications=[
                        f"Operational exposure in the {category} category highlights the necessity of deterministic guardrails.",
                        "Regulatory scrutiny and liability considerations require rigorous documentation of human oversight.",
                    ],
                    decisions_to_consider=decisions,
                    evidence_required=[
                        "Internal telemetry and error logs for implicated automated systems.",
                        "Independent penetration testing or algorithmic audit reports.",
                    ],
                    effectiveness_measures=[
                        "Mean time to detect (MTTD) algorithmic failures or adversarial attempts.",
                        "Zero-override compliance percentage for established safety thresholds.",
                    ],
                ),
                consultant_guidance=ConsultantGuidance(
                    discovery_questions=disc_questions,
                    assessment_activities=[
                        "Review model integration boundary architectures and authentication mechanisms.",
                        "Inspect automated test coverage for model edge cases and adversarial inputs.",
                    ],
                    architecture_considerations=[
                        "Deploy isolated execution sandboxes with zero-trust networking for AI agent runtimes.",
                        "Implement immutable logging for all model inputs, outputs, and confidence intervals.",
                    ],
                    implementation_controls=[
                        "Enforce strict least-privilege scoping on model service credentials.",
                        "Require multi-party authorization for production model deployment.",
                    ],
                    acceptance_criteria=[
                        "Verification that automated circuit breakers engage during simulated sensor or model failures.",
                    ],
                ),
                quality_review=QualityReview(
                    unsupported_claim_count=0,
                    unresolved_evidence_gaps=[],
                    advisory_human_review_flag=any(c.advisory_review_flag for c in claims),
                    review_reasons=[f"Advisory review: claim '{c.claim_id}' is an unverified allegation." for c in claims if c.advisory_review_flag],
                ),
            )

        # Stage 3: Independent Application Validation
        certified_dossier = self.validator.validate_and_certify(
            dossier, evidence_package=evidence_package
        )

        elapsed = round(time.time() - start_time, 4)
        input_tokens = len(prompt.split()) * 2
        output_tokens = len(json.dumps(certified_dossier.model_dump()).split()) * 2

        return certified_dossier, input_tokens, output_tokens, elapsed, self.model_name


class ClaudeLLMClient(BaseLLMClient):
    """Production client for Anthropic Claude models (e.g. Claude 3.5 Sonnet).

    Strictly satisfies:
    - Zero secret leakage in logs, headers, or exception text.
    - Strict JSON schema enforcement via Messages API Tools mechanism.
    - Rates: $3.00/1M input tokens, $15.00/1M output tokens (Claude 3.5 Sonnet).
    - Stage 3 independent application validation.
    """

    provider_id: str = "claude"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout: int = 180,
    ) -> None:
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise LLMConfigurationError("Missing required environment variable 'ANTHROPIC_API_KEY'.")
        self.model_name = model_name or get_claude_model()
        self.timeout = timeout
        self.validator = EnrichmentValidator()

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Pricing basis for Claude 3.5 Sonnet: $3.00 / 1M input, $15.00 / 1M output."""
        return round((input_tokens * 0.00000300) + (output_tokens * 0.00001500), 6)

    def generate_dossier(
        self,
        prompt: str,
        *,
        incident_id: str,
        title: str,
        summary: str,
        category: str,
        evidence_package: Sequence[ProvenanceItem],
    ) -> tuple[IncidentEnrichmentDossier, int, int, float, str]:
        start_time = time.time()
        tool_schema = IncidentEnrichmentDossier.model_json_schema()
        raw_dossier: Optional[IncidentEnrichmentDossier] = None
        in_tok = 0
        out_tok = 0

        # Attempt to use the official Anthropic SDK if installed
        try:
            import anthropic

            client = anthropic.Anthropic(
                api_key=self.api_key,
                timeout=float(self.timeout),
            )
            create_kwargs = {
                "model": self.model_name,
                "max_tokens": 8192,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": prompt}],
                "tools": [
                    {
                        "name": "record_incident_enrichment_dossier",
                        "description": "Emit the complete evidence-grounded incident intelligence dossier.",
                        "input_schema": tool_schema,
                    }
                ],
                "tool_choice": {
                    "type": "tool",
                    "name": "record_incident_enrichment_dossier",
                },
            }
            workspace_id = os.getenv("ANTHROPIC_WORKSPACE_ID")
            if workspace_id:
                create_kwargs["workspace_id"] = workspace_id.strip()

            resp = client.messages.create(**create_kwargs)
            in_tok = resp.usage.input_tokens
            out_tok = resp.usage.output_tokens

            for block in resp.content:
                if block.type == "tool_use" and block.name == "record_incident_enrichment_dossier":
                    raw_dossier = IncidentEnrichmentDossier.model_validate(block.input)
                    break

            if not raw_dossier:
                for block in resp.content:
                    if block.type == "text":
                        txt = block.text.strip()
                        if txt.startswith("```"):
                            txt = re.sub(r"^```(?:json)?\n?", "", txt)
                            txt = re.sub(r"\n?```$", "", txt).strip()
                        raw_dossier = IncidentEnrichmentDossier.model_validate_json(txt)
                        break

        except ImportError:
            # Fallback to standard library urllib
            endpoint = "https://api.anthropic.com/v1/messages"
            request_body = {
                "model": self.model_name,
                "max_tokens": 8192,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": prompt}],
                "tools": [
                    {
                        "name": "record_incident_enrichment_dossier",
                        "description": "Emit the complete evidence-grounded incident intelligence dossier.",
                        "input_schema": tool_schema,
                    }
                ],
                "tool_choice": {
                    "type": "tool",
                    "name": "record_incident_enrichment_dossier",
                },
            }
            headers = {
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            }
            workspace_id = os.getenv("ANTHROPIC_WORKSPACE_ID")
            if workspace_id:
                headers["anthropic-workspace-id"] = workspace_id.strip()

            data_bytes = json.dumps(request_body).encode("utf-8")
            req = urllib.request.Request(endpoint, data=data_bytes, headers=headers, method="POST")

            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    resp_json = json.loads(resp.read().decode("utf-8"))

                content_blocks = resp_json.get("content", [])
                for block in content_blocks:
                    if block.get("type") == "tool_use" and block.get("name") == "record_incident_enrichment_dossier":
                        raw_dossier = IncidentEnrichmentDossier.model_validate(block.get("input", {}))
                        break

                if not raw_dossier:
                    for block in content_blocks:
                        if block.get("type") == "text":
                            txt = block.get("text", "").strip()
                            if txt.startswith("```"):
                                txt = re.sub(r"^```(?:json)?\n?", "", txt)
                                txt = re.sub(r"\n?```$", "", txt).strip()
                            raw_dossier = IncidentEnrichmentDossier.model_validate_json(txt)
                            break

                usage = resp_json.get("usage", {})
                in_tok = usage.get("input_tokens", len(prompt.split()) * 2)
                out_tok = usage.get("output_tokens", 1000)

            except urllib.error.HTTPError as exc:
                detail = ""
                try:
                    body_bytes = exc.read()
                    if body_bytes:
                        err_json = json.loads(body_bytes.decode("utf-8"))
                        detail = err_json.get("error", {}).get("message", "")
                except Exception:
                    pass
                err_msg = f"Anthropic HTTP {exc.code} ({exc.reason}): {detail}" if detail else f"Anthropic HTTP {exc.code}: {exc.reason}"
                logger.error(f"Claude API failure: {err_msg}")
                raise LLMClientError(err_msg) from None
            except Exception as exc:
                logger.error(f"Claude invocation failure: {exc}")
                raise LLMClientError(f"Claude invocation failed: {exc}") from None

        except Exception as exc:
            logger.error(f"Anthropic SDK error: {exc}")
            raise LLMClientError(f"Claude SDK invocation failed: {exc}") from None

        if not raw_dossier:
            raise LLMClientError("Claude response did not include a valid tool_use or JSON text block.")

        # Stage 3 Independent Validation
        certified_dossier = self.validator.validate_and_certify(
            raw_dossier, evidence_package=evidence_package
        )

        elapsed = round(time.time() - start_time, 4)
        return certified_dossier, in_tok, out_tok, elapsed, self.model_name


class GeminiLLMClient(BaseLLMClient):
    """Production client for Google Gemini Pro models.

    Strictly satisfies:
    - Zero secret leakage in logs, headers, or exception text.
    - JSON schema enforcement via response_schema / response_mime_type.
    - Stable Gemini Pro model: gemini-2.5-pro.
    - Rates: $1.25/1M input tokens, $10.00/1M output tokens.
    - Stage 3 independent application validation.
    """

    provider_id: str = "gemini"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout: int = 180,
    ) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise LLMConfigurationError("Missing required environment variable 'GEMINI_API_KEY'.")
        self.model_name = model_name or get_gemini_model()
        self.timeout = timeout
        self.validator = EnrichmentValidator()

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Pricing basis for Gemini 2.5 Pro: $1.25 / 1M input, $10.00 / 1M output."""
        return round((input_tokens * 0.00000125) + (output_tokens * 0.00001000), 6)

    def generate_dossier(
        self,
        prompt: str,
        *,
        incident_id: str,
        title: str,
        summary: str,
        category: str,
        evidence_package: Sequence[ProvenanceItem],
    ) -> tuple[IncidentEnrichmentDossier, int, int, float, str]:
        start_time = time.time()
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent"

        schema = IncidentEnrichmentDossier.model_json_schema()
        request_body = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "response_mime_type": "application/json",
                "response_schema": schema,
            },
        }

        data_bytes = json.dumps(request_body).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=data_bytes,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                resp_json = json.loads(resp.read().decode("utf-8"))

            candidates = resp_json.get("candidates", [])
            if not candidates:
                raise LLMClientError("Gemini returned empty candidates list.")

            content_parts = candidates[0].get("content", {}).get("parts", [])
            if not content_parts or "text" not in content_parts[0]:
                raise LLMClientError("Gemini response missing text part.")

            raw_text = content_parts[0]["text"]
            raw_dossier = IncidentEnrichmentDossier.model_validate_json(raw_text)

            # Stage 3 Independent Validation
            certified_dossier = self.validator.validate_and_certify(
                raw_dossier, evidence_package=evidence_package
            )

            usage = resp_json.get("usageMetadata", {})
            in_tok = usage.get("promptTokenCount", len(prompt.split()) * 2)
            out_tok = usage.get("candidatesTokenCount", len(raw_text.split()) * 2)
            elapsed = round(time.time() - start_time, 4)

            return certified_dossier, in_tok, out_tok, elapsed, self.model_name

        except urllib.error.HTTPError as exc:
            err_msg = f"Gemini HTTP {exc.code}: {exc.reason}"
            logger.error(f"Gemini API failure: {err_msg}")
            raise LLMClientError(err_msg) from None
        except Exception as exc:
            logger.error(f"Gemini client invocation failure: {exc}")
            raise LLMClientError(f"Gemini invocation failed: {exc}") from None


# Backward-compatible alias for existing tests if needed
OpenAILLMClient = MockLLMClient


def get_llm_client(provider: Optional[str] = None) -> BaseLLMClient:
    """Provider factory resolving configured client without silent fallbacks.

    Configuration hierarchy:
    1. Explicit provider argument
    2. During pytest test runs without explicit provider: always MockLLMClient (safety guard)
    3. AI_MONITOR_LLM_PROVIDER environment variable
    4. Defaults to 'mock' if unspecified
    """
    if not provider and "PYTEST_CURRENT_TEST" in os.environ:
        return MockLLMClient()

    resolved_provider = (
        provider or get_llm_provider() or "mock"
    ).lower().strip()

    if resolved_provider in ("claude", "anthropic"):
        return ClaudeLLMClient()
    elif resolved_provider in ("gemini", "google"):
        return GeminiLLMClient()
    elif resolved_provider == "mock":
        return MockLLMClient()
    else:
        raise LLMConfigurationError(
            f"Unsupported LLM provider '{resolved_provider}'. "
            "Supported providers: 'claude', 'gemini', 'mock'."
        )
