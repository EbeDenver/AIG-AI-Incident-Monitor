"""Pydantic v2 schemas for validated, structured incident enrichment.

Governing Charter: Project Constitution (Rules 1, 2, 3, 4, 11, 14, 16),
ADR-011 (Untrusted Source Envelopes), AUD-005, OPS-004.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field


class EvidenceSufficiency(str, Enum):
    """Categorical evaluation of raw evidentiary completeness."""

    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    LIMITED_EVIDENCE = "LIMITED_EVIDENCE"


class IncidentExplanation(BaseModel):
    """Structured, evidence-grounded explanation of the incident events."""

    executive_summary: str = Field(
        ...,
        description="2-3 sentence factual executive summary of the verified event.",
    )
    event_chronology: list[str] = Field(
        default_factory=list,
        description="Chronological sequence of verified reported events.",
    )
    ai_system_role: str = Field(
        ...,
        description="Specific technical role played by the AI component, or explicit limited-evidence note.",
    )
    affected_stakeholders: list[str] = Field(
        default_factory=list,
        description="Directly impacted parties, organizations, or user groups.",
    )
    documented_consequences: list[str] = Field(
        default_factory=list,
        description="Observed and reported technical, physical, economic, or legal outcomes.",
    )
    unknowns_and_disputes: list[str] = Field(
        default_factory=list,
        description="Unresolved factual disputes, withheld information, or missing postmortem details.",
    )
    evidence_limitations: str = Field(
        default="",
        description="Explicit caveats regarding data source directness, hearsay, or brevity.",
    )
    sufficiency: EvidenceSufficiency = Field(
        default=EvidenceSufficiency.LIMITED_EVIDENCE,
        description="Qualitative assessment of raw evidence sufficiency.",
    )


class PreparednessGuidance(BaseModel):
    """Practical, actionable organizational guidance for enterprise defense and resilience."""

    applicable_profiles: list[str] = Field(
        default_factory=list,
        description="Enterprise or system profiles vulnerable to similar failure modes.",
    )
    early_warning_indicators: list[str] = Field(
        default_factory=list,
        description="Operational warning signs, telemetry anomalies, or threshold deviations.",
    )
    prioritized_preventive_controls: list[str] = Field(
        default_factory=list,
        description="High-priority technical safeguards, architecture patterns, and defense-in-depth measures.",
    )
    detection_mechanisms: list[str] = Field(
        default_factory=list,
        description="Continuous monitoring, logging, and automated alert mechanisms.",
    )
    incident_response_actions: list[str] = Field(
        default_factory=list,
        description="Immediate containment, quarantine, human escalation, and recovery protocols.",
    )
    responsible_functions: list[str] = Field(
        default_factory=list,
        description="Organizational roles and business units accountable for implementing safeguards.",
    )
    validation_methods: list[str] = Field(
        default_factory=list,
        description="Practical verification methods, chaos testing, penetration testing, or red-teaming steps.",
    )


class IncidentEnrichmentPayload(BaseModel):
    """Master structured output container for incident intelligence enrichment."""

    prompt_version: str = Field(default="1.0.0")
    explanation: IncidentExplanation
    preparedness: PreparednessGuidance
