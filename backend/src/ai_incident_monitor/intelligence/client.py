"""LLM client interfaces, deterministic mock implementations, and provider adapters.

Governing Charter: Project Constitution (Rules 1, 2, 3, 4, 11, 14, 16),
ADR-011, SEC-006, OPS-004.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import json
import logging
import time
from typing import Optional

from ai_incident_monitor.domain.taxonomy import IncidentCategory
from ai_incident_monitor.intelligence.prompts import PROMPT_VERSION
from ai_incident_monitor.intelligence.schemas import (
    EvidenceSufficiency,
    IncidentEnrichmentPayload,
    IncidentExplanation,
    PreparednessGuidance,
)

logger = logging.getLogger(__name__)


class LLMClientError(Exception):
    """Base exception for LLM inference failures."""


class LLMConfigurationError(LLMClientError):
    """Raised when provider configuration or credentials are missing."""


class BaseLLMClient(ABC):
    """Abstract interface for LLM enrichment generation."""

    @abstractmethod
    def generate_enrichment(
        self,
        prompt: str,
        *,
        incident_id: str,
        title: str,
        summary: str,
        category: str,
    ) -> tuple[IncidentEnrichmentPayload, int, int, float, str]:
        """Generate structured incident enrichment.

        Returns:
            Tuple of (payload, input_tokens, output_tokens, latency_seconds, model_name)
        """
        ...


class MockLLMClient(BaseLLMClient):
    """Deterministic, grounded mock LLM client for testing and offline development.

    Strictly satisfies:
    - Zero external network dependencies.
    - Explicit LIMITED_EVIDENCE handling for brief/unsubstantiated records.
    - Deep, realistic risk & defense patterns tailored to the incident category.
    """

    def __init__(self, model_name: str = "mock-intelligence-v1") -> None:
        self.model_name = model_name

    def generate_enrichment(
        self,
        prompt: str,
        *,
        incident_id: str,
        title: str,
        summary: str,
        category: str,
    ) -> tuple[IncidentEnrichmentPayload, int, int, float, str]:
        start_time = time.time()
        words = summary.split()
        is_brief = len(words) < 15 or summary == title

        cat_upper = category.upper()

        if is_brief:
            # Explicit limited evidence invariant
            sufficiency = EvidenceSufficiency.LIMITED_EVIDENCE
            explanation = IncidentExplanation(
                executive_summary=f"Reported incident: {title}. Insufficient technical postmortem details in primary source feed.",
                event_chronology=[
                    f"Event published or reported in monitoring feed: {title}",
                    "Detailed technical postmortem timeline unavailable in ingested excerpt.",
                ],
                ai_system_role="LIMITED_EVIDENCE: Source text does not disclose specific model architecture, inference pipeline, or telemetry details.",
                affected_stakeholders=["Reported organizations and impacted public users."],
                documented_consequences=[
                    "Public reporting of incident or potential hazard.",
                    "LIMITED_EVIDENCE: Detailed economic or physical consequences not quantified in source text.",
                ],
                unknowns_and_disputes=[
                    "Root-cause architecture failure mechanism unverified.",
                    "Internal incident response and remediation actions undisclosed.",
                ],
                evidence_limitations="Primary record contains only syndicated headline/summary without engineering postmortem.",
                sufficiency=sufficiency,
            )
            preparedness = PreparednessGuidance(
                applicable_profiles=[
                    "Enterprises deploying automated AI decision-making or content generation pipelines."
                ],
                early_warning_indicators=[
                    "Anomalous distribution shifts in model telemetry outputs.",
                    "Spike in unhandled model edge cases or user dispute flags.",
                ],
                prioritized_preventive_controls=[
                    "Implement fail-closed circuit breakers for automated model decisions.",
                    "Mandate human-in-the-loop review for high-impact model outputs.",
                ],
                detection_mechanisms=[
                    "Real-time logging of model inputs, outputs, and system confidence scores.",
                ],
                incident_response_actions=[
                    "Initiate fallback to deterministic heuristics upon model error rate increase.",
                    "Preserve raw telemetry payloads for post-incident root-cause investigation.",
                ],
                responsible_functions=[
                    "AI Safety Engineering",
                    "Enterprise Risk Management",
                ],
                validation_methods=[
                    "Offline adversarial evaluation against regression test sets.",
                ],
            )
        else:
            # Full structured synthesis tailored to category
            sufficiency = EvidenceSufficiency.PARTIAL if len(words) < 50 else EvidenceSufficiency.COMPLETE

            if "CYBER" in cat_upper:
                ai_role = "Adversarial or autonomous exploitation of AI capabilities, API tools, or software vulnerabilities."
                profiles = [
                    "Organizations providing autonomous coding assistants, public APIs, or developer tooling.",
                    "Financial institutions and media organizations vulnerable to automated targeted attacks.",
                ]
                warnings = [
                    "High-volume, automated API queries exhibiting programmatic evasion patterns.",
                    "Unusual credential access or session token exfiltration from developer environments.",
                ]
                controls = [
                    "Enforce strict least-privilege scoping on autonomous agent API credentials.",
                    "Mandate isolated sandboxing with zero network egress for untrusted code execution.",
                    "Deploy prompt injection defenses and strict schema validation at API ingestion boundaries.",
                ]
                detection = [
                    "Continuous anomaly detection on developer token usage and outbound network sockets.",
                    "Automated alerting on anomalous API key activity or rapid credential rotation.",
                ]
                response = [
                    "Revoke compromised API keys and invalidate all active bearer tokens immediately.",
                    "Quarantine implicated agent sandboxes and capture disk/memory forensic snapshots.",
                ]
                roles = ["Chief Information Security Officer (CISO)", "Security Operations Center (SOC) Lead"]
                validation = [
                    "Automated adversarial prompt-injection penetration testing against API endpoints.",
                    "Red-team simulations of agentic privilege escalation.",
                ]
            elif "FINANCIAL" in cat_upper:
                ai_role = "Algorithmic decision execution, market prediction model failure, or automated financial transaction routing."
                profiles = [
                    "Financial institutions, algorithmic trading venues, digital asset exchanges, and fintech platforms.",
                ]
                warnings = [
                    "Cascading liquidity withdrawals or anomalous spikes in automated order cancellation rates.",
                    "Unusual concentration of automated transactions approaching risk exposure limits.",
                ]
                controls = [
                    "Deploy deterministic, hard-coded circuit breakers independent of model state.",
                    "Implement multi-signature authorization for transactions exceeding defined monetary thresholds.",
                ]
                detection = [
                    "Real-time slippage and order-book liquidity monitoring with sub-second alert triggers.",
                ]
                response = [
                    "Trigger automated trading halts upon breach of volatility or drawdown thresholds.",
                    "Revert to manual order routing and notify regulatory oversight bodies.",
                ]
                roles = ["Head of Quantitative Risk", "Chief Compliance Officer (CCO)"]
                validation = [
                    "Historical backtesting against historic market flash-crash scenarios.",
                    "Chaos stress-testing of model execution latencies under synthetic market shocks.",
                ]
            elif "RIGHTS" in cat_upper:
                ai_role = "Automated classification, biometric recognition, or content filtering system generating discriminatory or rights-infringing outcomes."
                profiles = [
                    "Public sector agencies, law enforcement, healthcare providers, and HR/employment platforms.",
                ]
                warnings = [
                    "Statistically significant demographic disparity in false-positive or rejection rates.",
                    "Clustering of appeals or user complaints regarding automated denial of access.",
                ]
                controls = [
                    "Implement mandatory demographic parity and fairness constraints in model optimization objectives.",
                    "Provide accessible human appeal mechanisms with deterministic explanations.",
                ]
                detection = [
                    "Continuous fairness monitoring across protected demographic cohorts.",
                ]
                response = [
                    "Halt automated enforcement and route flagged cases to human adjudicators.",
                    "Publish transparency disclosures detailing identified disparities and corrective actions.",
                ]
                roles = ["Chief Privacy Officer", "Algorithmic Ethics & Compliance Officer"]
                validation = [
                    "Third-party algorithmic bias audits against standardized demographic evaluation datasets.",
                ]
            else:  # SAFETY / REPUTATIONAL / SYSTEMIC
                ai_role = "Autonomous perception, physical actuation control, or generative content synthesis system."
                profiles = [
                    "Autonomous vehicle fleets, industrial robotics operators, and public information platforms.",
                ]
                warnings = [
                    "Sensor confidence degradation under unmodeled environmental conditions.",
                    "Latency spikes in real-time control loop telemetry.",
                ]
                controls = [
                    "Implement fail-safe physical interlocks that disengage autonomous drive upon sensor doubt.",
                    "Enforce dual-redundant sensor architectures with independent validation channels.",
                ]
                detection = [
                    "Hardware watchdog timers verifying control-loop responsiveness every 50ms.",
                ]
                response = [
                    "Execute safe emergency stop maneuvers into designated containment states.",
                    "Notify public safety authorities and freeze fleet firmware updates pending investigation.",
                ]
                roles = ["VP of Safety Engineering", "Fleet Operations Director"]
                validation = [
                    "Hardware-in-the-loop (HIL) fault injection testing across physical operating extremes.",
                ]

            explanation = IncidentExplanation(
                executive_summary=summary[:300] + ("..." if len(summary) > 300 else ""),
                event_chronology=[
                    f"Reported incident: {title}",
                    f"Observed impact described in primary reporting: {summary[:150]}...",
                    "Independent technical corroboration and regulatory inquiries initiated.",
                ],
                ai_system_role=ai_role,
                affected_stakeholders=[
                    "Primary operational entities and customers.",
                    "Impacted end users and broader industry ecosystem.",
                ],
                documented_consequences=[
                    "Operational disruption and public disclosure.",
                    "Regulatory attention and technical vulnerability remediation.",
                ],
                unknowns_and_disputes=[
                    "Complete internal telemetry and detailed engineering postmortem not fully public.",
                ],
                evidence_limitations="Synthesized from syndicated incident feed reporting; primary telemetry withheld by operators.",
                sufficiency=sufficiency,
            )
            preparedness = PreparednessGuidance(
                applicable_profiles=profiles,
                early_warning_indicators=warnings,
                prioritized_preventive_controls=controls,
                detection_mechanisms=detection,
                incident_response_actions=response,
                responsible_functions=roles,
                validation_methods=validation,
            )

        payload = IncidentEnrichmentPayload(
            prompt_version=PROMPT_VERSION,
            explanation=explanation,
            preparedness=preparedness,
        )

        elapsed = round(time.time() - start_time, 4)
        input_tokens = len(prompt.split()) * 2
        output_tokens = len(json.dumps(payload.model_dump()).split()) * 2

        return payload, input_tokens, output_tokens, elapsed, self.model_name
