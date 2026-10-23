"""EU AI Act informational output linter for fail-closed governance safety.

Enforces Constitutional Rules 10, 11, 14 & 15 and LGL-001/LGL-002:
- Never asserts unadjudicated legal violations, statutory breaches, or liability.
- Detects and blocks prohibited legal-conclusion language across all structured fields.
- Validates immutable disclaimer integrity and versioning.
- Provides structured, deterministic finding reports suitable for output eligibility gates.
- Detects without silent rewriting or auto-correction (Safety Rule 3 & 7).
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import re
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from ai_incident_monitor.governance.enums import (
    EUScreenStatus,
    FrameworkCode,
    FrameworkStatus,
)
from ai_incident_monitor.governance.models import (
    EU_AI_ACT_DISCLAIMER_V2,
    EU_AI_ACT_DISCLAIMER_VERSION,
)


class EULinterResult(str, Enum):
    """Controlled vocabulary for EU output linter results."""

    PASS = "PASS"
    BLOCKED_PROHIBITED_TERM = "BLOCKED_PROHIBITED_TERM"
    BLOCKED_MISSING_DISCLAIMER = "BLOCKED_MISSING_DISCLAIMER"
    BLOCKED_UNAPPROVED_STATUS = "BLOCKED_UNAPPROVED_STATUS"
    BLOCKED_MISSING_EVIDENCE = "BLOCKED_MISSING_EVIDENCE"
    BLOCKED_INVALID_REFERENCE = "BLOCKED_INVALID_REFERENCE"
    BLOCKED_STALE_REFERENCE_SET = "BLOCKED_STALE_REFERENCE_SET"
    BLOCKED_OUTPUT_SCHEMA_ERROR = "BLOCKED_OUTPUT_SCHEMA_ERROR"


class EULinterFinding(BaseModel):
    """Structured finding emitted by the EU output linter for a specific field or check."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    overall_result: str = Field(description="Result code e.g. PASS or BLOCKED_*")
    field_name: str = Field(description="Name or path of inspected field")
    finding_code: str = Field(description="Specific finding code matching EULinterResult")
    message: str = Field(description="Human-readable explanation of why this finding was raised")
    matched_text: Optional[str] = Field(
        default=None, description="Exact substring triggering the finding if applicable"
    )
    matched_pattern: Optional[str] = Field(
        default=None, description="Pattern identifier or regex triggering the finding"
    )
    blocked_boolean: bool = Field(
        default=True, description="True if this finding blocks external output eligibility"
    )


class EULinterReport(BaseModel):
    """Consolidated report produced by EUOutputLinter."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    overall_result: str = Field(
        description="Overall outcome: PASS if zero blocking findings, else first blocking code"
    )
    is_clean: bool = Field(description="True if zero blocking findings")
    findings: list[EULinterFinding] = Field(default_factory=list)
    inspected_fields_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def has_violations(self) -> bool:
        return not self.is_clean

    def block_reasons(self) -> list[str]:
        return [f.message for f in self.findings if f.blocked_boolean]


# Prohibited pattern definitions: (pattern_id, human_label, compiled_regex)
PROHIBITED_PATTERNS: list[tuple[str, str, re.Pattern[str]]] = [
    (
        "PROHIB_VIOLATION",
        "violation/violates/infringes",
        re.compile(
            r"\b(violat(e|es|ed|ing|ion|ions)|infring(e|es|ed|ing|ement|ements))\b",
            re.IGNORECASE,
        ),
    ),
    (
        "PROHIB_BREACH",
        "breach/breached",
        re.compile(r"\bbreach(es|ed|ing)?\b", re.IGNORECASE),
    ),
    (
        "PROHIB_ILLEGAL",
        "illegal/unlawful",
        re.compile(r"\b(illegal(ity|ly)?|unlawful(ly|ness)?)\b", re.IGNORECASE),
    ),
    (
        "PROHIB_NONCOMPLIANT",
        "noncompliant/non-compliance",
        re.compile(
            r"\b(non[-\s_]+complian(t|ce)|noncompliant|compliance\s+failure)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "PROHIB_AFFIRMATIVE_COMPLIANT",
        "affirmative compliance claim",
        re.compile(
            r"\b((is|in|full|fully)\s+compliance|complies\s+with)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "PROHIB_LEGAL_STATUTORY_DUTY",
        "statutory/legal duty applies",
        re.compile(
            r"\b((statutory|legal)\s+duty(\s+applies)?|duty\s+applies)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "PROHIB_MANDATORY_REPORT",
        "required to report/must report",
        re.compile(
            r"\b((must|mandatory)\s+(to\s+)?report|required\s+to\s+report|incident\s+is\s+reportable)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "PROHIB_LEGALLY_HIGH_RISK",
        "legally high-risk / high-risk under EU AI Act",
        re.compile(
            r"\b(legally\s+high[-\s_]+risk|high[-\s_]+risk\s+under(\s+the)?\s+eu\s+ai\s+act|high[-\s_]+risk\s+(ai\s+)?system)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "PROHIB_PROHIBITED_PRACTICE",
        "prohibited practice / prohibited AI system",
        re.compile(
            r"\bprohibited\s+(practice|ai\s+system)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "PROHIB_STATUTORY_APPLICABILITY",
        "EU AI Act applies / statutory obligation applies",
        re.compile(
            r"\b(eu\s+ai\s+act\s+applies|eu\s+ai\s+act\s+is\s+applicable|(statutory\s+)?obligation\s+applies)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "PROHIB_LEGAL_LIABILITY",
        "legal liability / liable for",
        re.compile(
            r"\b((legal|statutory)\s+liability|liable\s+for)\b",
            re.IGNORECASE,
        ),
    ),
]

# Narrow qualified language allowlist (preserves disclaimers, external citations, and neutral conceptual phrases)
QUALIFIED_ALLOWLIST: list[re.Pattern[str]] = [
    re.compile(r"finding of compliance or noncompliance", re.IGNORECASE),
    re.compile(r"compliance or noncompliance", re.IGNORECASE),
    re.compile(r"alleged\s+(violation|breach|infringement)", re.IGNORECASE),
    re.compile(r"reported\s+(violation|breach|infringement)", re.IGNORECASE),
    re.compile(r"potential\s+high[-\s_]+risk\s+area(s)?", re.IGNORECASE),
    re.compile(r"potential\s+high[-\s_]+risk\s+conceptual\s+area(s)?", re.IGNORECASE),
    re.compile(r"potential\s+conceptual\s+relevance\s+to\s+high[-\s_]+risk\s+areas", re.IGNORECASE),
    re.compile(r"conceptual\s+relevance\s+to\s+article\s+5", re.IGNORECASE),
    re.compile(r"serious\s+incident\s+reporting\s+relevance", re.IGNORECASE),
    re.compile(r"serious\s+incident\s+reporting", re.IGNORECASE),
]


class EUOutputLinter:
    """Deterministic, offline output safety linter for EU AI Act informational screens.

    Inspects all narrative and structured fields to prevent unadjudicated legal assertions,
    verifies exact immutable disclaimers, checks reference currency, and validates
    prerequisites for external output eligibility.
    """

    def __init__(
        self,
        prohibited_patterns: Optional[list[tuple[str, str, re.Pattern[str]]]] = None,
        qualified_allowlist: Optional[list[re.Pattern[str]]] = None,
    ) -> None:
        self.prohibited_patterns = prohibited_patterns or PROHIBITED_PATTERNS
        self.qualified_allowlist = qualified_allowlist or QUALIFIED_ALLOWLIST

    def lint_text(self, text: Optional[str], field_name: str) -> list[EULinterFinding]:
        """Lint a single text string against prohibited legal-conclusion patterns.

        Applies narrow qualified-language masking first so authorized phrases are not
        flagged as false positives, then applies case-insensitive word-boundary regex checks.
        """
        if text is None:
            return []

        raw_text = str(text).strip()
        if not raw_text:
            return []

        # Mask allowlisted qualified phrases
        masked_text = raw_text
        for allow_pat in self.qualified_allowlist:
            masked_text = allow_pat.sub("[MASKED_QUALIFIED_ALLOWLIST]", masked_text)

        findings: list[EULinterFinding] = []
        for pattern_id, label, regex in self.prohibited_patterns:
            match = regex.search(masked_text)
            if match:
                matched_str = match.group(0)
                findings.append(
                    EULinterFinding(
                        overall_result=EULinterResult.BLOCKED_PROHIBITED_TERM.value,
                        field_name=field_name,
                        finding_code=EULinterResult.BLOCKED_PROHIBITED_TERM.value,
                        message=(
                            f"Prohibited legal-conclusion language detected in field '{field_name}': "
                            f"matched prohibited pattern '{label}' ('{matched_str}')."
                        ),
                        matched_text=matched_str,
                        matched_pattern=pattern_id,
                        blocked_boolean=True,
                    )
                )

        return findings

    def lint_screen(
        self,
        screen: Any,
        reference_set: Optional[Any] = None,
        evidence_links: Optional[list[Any]] = None,
        check_eligibility_prerequisites: bool = True,
    ) -> EULinterReport:
        """Comprehensively lint an EU informational screen model, schema, or dictionary.

        Traverses all top-level and nested text fields, verifies status and disclaimer
        integrity, validates evidence links and reference currency.
        """
        findings: list[EULinterFinding] = []
        inspected_count = 0

        try:
            # 1. Status Check (if evaluating external output eligibility)
            if check_eligibility_prerequisites:
                raw_status = getattr(screen, "status", None)
                if raw_status is None and isinstance(screen, dict):
                    raw_status = screen.get("status")
                status_str = raw_status.value if hasattr(raw_status, "value") else str(raw_status)
                if status_str != EUScreenStatus.APPROVED_INFORMATIONAL.value:
                    findings.append(
                        EULinterFinding(
                            overall_result=EULinterResult.BLOCKED_UNAPPROVED_STATUS.value,
                            field_name="status",
                            finding_code=EULinterResult.BLOCKED_UNAPPROVED_STATUS.value,
                            message=(
                                f"Screen status is '{status_str}'; must be "
                                f"'{EUScreenStatus.APPROVED_INFORMATIONAL.value}' for output eligibility."
                            ),
                            blocked_boolean=True,
                        )
                    )

            # 2. Immutable Disclaimer Checks
            disclaimer_ver = getattr(screen, "disclaimer_version", None)
            if disclaimer_ver is None and isinstance(screen, dict):
                disclaimer_ver = screen.get("disclaimer_version")

            if disclaimer_ver != EU_AI_ACT_DISCLAIMER_VERSION:
                findings.append(
                    EULinterFinding(
                        overall_result=EULinterResult.BLOCKED_MISSING_DISCLAIMER.value,
                        field_name="disclaimer_version",
                        finding_code=EULinterResult.BLOCKED_MISSING_DISCLAIMER.value,
                        message=(
                            f"Invalid or missing disclaimer version '{disclaimer_ver}'; "
                            f"expected '{EU_AI_ACT_DISCLAIMER_VERSION}'."
                        ),
                        blocked_boolean=True,
                    )
                )

            disclaimer_txt = getattr(screen, "disclaimer_text", None)
            if disclaimer_txt is None and isinstance(screen, dict):
                disclaimer_txt = screen.get("disclaimer_text")

            if disclaimer_txt != EU_AI_ACT_DISCLAIMER_V2:
                findings.append(
                    EULinterFinding(
                        overall_result=EULinterResult.BLOCKED_MISSING_DISCLAIMER.value,
                        field_name="disclaimer_text",
                        finding_code=EULinterResult.BLOCKED_MISSING_DISCLAIMER.value,
                        message=(
                            "Disclaimer text has been modified, truncated, reordered, or "
                            "does not match mandatory EU_AI_ACT_DISCLAIMER_V2 exactly."
                        ),
                        blocked_boolean=True,
                    )
                )

            # 3. Evidence Link Count Check
            if check_eligibility_prerequisites:
                link_count = 0
                if evidence_links is not None:
                    link_count = len(evidence_links)
                elif hasattr(screen, "evidence_links") and screen.evidence_links:
                    link_count = len(screen.evidence_links)
                elif hasattr(screen, "evidence_ids") and screen.evidence_ids:
                    link_count = len(screen.evidence_ids)
                elif isinstance(screen, dict):
                    link_count = len(screen.get("evidence_links") or screen.get("evidence_ids") or [])

                if link_count < 1:
                    findings.append(
                        EULinterFinding(
                            overall_result=EULinterResult.BLOCKED_MISSING_EVIDENCE.value,
                            field_name="evidence_links",
                            finding_code=EULinterResult.BLOCKED_MISSING_EVIDENCE.value,
                            message="Screen lacks required primary evidence links (minimum 1 required).",
                            blocked_boolean=True,
                        )
                    )

            # 4. Reference Set Checks (if provided)
            if reference_set is not None:
                ref_status = getattr(reference_set, "status", None)
                if ref_status is None and isinstance(reference_set, dict):
                    ref_status = reference_set.get("status")
                ref_status_str = ref_status.value if hasattr(ref_status, "value") else str(ref_status)

                if ref_status_str in [FrameworkStatus.SUPERSEDED.value, FrameworkStatus.DEPRECATED.value]:
                    findings.append(
                        EULinterFinding(
                            overall_result=EULinterResult.BLOCKED_STALE_REFERENCE_SET.value,
                            field_name="reference_set_id",
                            finding_code=EULinterResult.BLOCKED_STALE_REFERENCE_SET.value,
                            message=(
                                f"Screen references stale or superseded framework reference set "
                                f"'{getattr(reference_set, 'id', 'unknown')}'."
                            ),
                            blocked_boolean=True,
                        )
                    )

                ref_code = getattr(reference_set, "framework_code", None)
                if ref_code is None and isinstance(reference_set, dict):
                    ref_code = reference_set.get("framework_code")
                ref_code_str = ref_code.value if hasattr(ref_code, "value") else str(ref_code)

                ref_id = str(getattr(reference_set, "id", "") or "")
                if ref_code_str != FrameworkCode.EU_AI_ACT.value and "eu-ai-act" not in ref_id:
                    findings.append(
                        EULinterFinding(
                            overall_result=EULinterResult.BLOCKED_INVALID_REFERENCE.value,
                            field_name="reference_set_id",
                            finding_code=EULinterResult.BLOCKED_INVALID_REFERENCE.value,
                            message=f"Screen references non-EU AI Act framework reference set '{ref_id}'.",
                            blocked_boolean=True,
                        )
                    )

            # 5. Extract and Lint Narrative Text Fields
            text_fields = self._extract_screen_text_fields(screen)
            inspected_count = len(text_fields)

            for field_path, field_text in text_fields:
                field_findings = self.lint_text(field_text, field_path)
                findings.extend(field_findings)

        except Exception as exc:
            findings.append(
                EULinterFinding(
                    overall_result=EULinterResult.BLOCKED_OUTPUT_SCHEMA_ERROR.value,
                    field_name="screen",
                    finding_code=EULinterResult.BLOCKED_OUTPUT_SCHEMA_ERROR.value,
                    message=f"Output linter encountered unexpected error evaluating screen: {exc}",
                    blocked_boolean=True,
                )
            )

        is_clean = len(findings) == 0
        overall_result = EULinterResult.PASS.value if is_clean else findings[0].finding_code

        return EULinterReport(
            overall_result=overall_result,
            is_clean=is_clean,
            findings=findings,
            inspected_fields_count=inspected_count,
        )

    def _extract_screen_text_fields(self, screen: Any) -> list[tuple[str, str]]:
        """Extract all candidate narrative and text strings from a screen model or dict."""
        results: list[tuple[str, str]] = []

        def get_val(key: str, default: Any = None) -> Any:
            if isinstance(screen, dict):
                return screen.get(key, default)
            return getattr(screen, key, default)

        # Top-level narrative string fields
        for field in ["rationale", "applicability_date_assessment"]:
            val = get_val(field)
            if val and isinstance(val, str):
                results.append((field, val))

        # Top-level list-of-string fields
        list_fields = [
            "known_facts",
            "unknowns",
            "disputed_facts",
            "missing_facts",
            "follow_up_questions",
            "recommended_next_steps",
        ]
        for field in list_fields:
            items = get_val(field, [])
            if items and isinstance(items, (list, tuple)):
                for idx, item in enumerate(items):
                    if item and isinstance(item, str):
                        results.append((f"{field}[{idx}]", item))

        # Metadata JSON nested structures
        meta = get_val("metadata_json", {}) or {}
        if isinstance(meta, dict):
            # Reviewer notes/rationale
            for rk in ["reviewer_notes", "reviewer_rationale"]:
                rval = meta.get(rk)
                if rval and isinstance(rval, str):
                    results.append((f"metadata_json.{rk}", rval))

            # Conceptual findings
            findings_list = meta.get("conceptual_findings", [])
            if isinstance(findings_list, list):
                for idx, finding in enumerate(findings_list):
                    if isinstance(finding, dict):
                        for subfield in [
                            "finding_rationale",
                            "context_notes",
                            "qualifying_remarks",
                        ]:
                            fval = finding.get(subfield)
                            if fval and isinstance(fval, str):
                                results.append(
                                    (f"metadata_json.conceptual_findings[{idx}].{subfield}", fval)
                                )
                        # Matched facts inside finding
                        mf_list = finding.get("matched_facts", [])
                        if isinstance(mf_list, list):
                            for mf_idx, mf in enumerate(mf_list):
                                if mf and isinstance(mf, str):
                                    results.append(
                                        (
                                            f"metadata_json.conceptual_findings[{idx}].matched_facts[{mf_idx}]",
                                            mf,
                                        )
                                    )

        return results
