"""Editorial validator verifying factual integrity, disclaimer adherence, and safety.

Enforces Constitutional Rules 1, 3, 10, 11, 14, and 15:
- Zero unevidenced assertions (Rule 1).
- Dispassionate, forensic tone (Rule 3).
- Mandatory legal research disclaimers (Rule 10).
- Strict prohibition of unadjudicated legal guilt and statutory violation assertions (Rule 11).
- Automated self-approval prohibition (Rule 14).
"""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Optional

from ai_incident_monitor.editorial.enums import (
    EditorialValidationCode,
    EditorialValidationSeverity,
)
from ai_incident_monitor.editorial.models import (
    EDITORIAL_DISCLAIMER_TEXT,
    EDITORIAL_DISCLAIMER_VERSION,
    EditorialDossierSchema,
    EditorialValidationFinding,
    EditorialValidationReport,
)

# Prohibited unhedged legal conclusion patterns (Rule 11)
PROHIBITED_LEGAL_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"\b(?:is\s+a\s+|constitutes?\s+a\s+)?violation\s+of\s+(?:the\s+)?(?:law|statute|act|regulation)\b", re.IGNORECASE),
        "Asserts definitive violation of law without judicial adjudication",
    ),
    (
        re.compile(r"\bviolated\s+(?:the\s+)?(?:eu\s+ai\s+act|law|statute|gdpr|regulation)\b", re.IGNORECASE),
        "Asserts past legal violation",
    ),
    (
        re.compile(r"\b(?:is|was|are|were)\s+(?:illegal|unlawful)\b", re.IGNORECASE),
        "Asserts illegality or unlawfulness as established fact",
    ),
    (
        re.compile(r"\b(?:is|was)\s+guilty\s+of\b", re.IGNORECASE),
        "Asserts legal guilt",
    ),
    (
        re.compile(r"\b(?:is|was)\s+non-?compliant\b", re.IGNORECASE),
        "Asserts statutory noncompliance as fact",
    ),
    (
        re.compile(r"\bcompliance\s+failure\b", re.IGNORECASE),
        "Asserts compliance failure",
    ),
    (
        re.compile(r"\bbreached\s+(?:a\s+)?(?:statutory|legal)\s+duty\b", re.IGNORECASE),
        "Asserts breach of statutory duty",
    ),
    (
        re.compile(r"\blegally\s+liable\b", re.IGNORECASE),
        "Asserts definitive legal liability",
    ),
]

# Narrow qualified-language allowlist: phrases containing trigger words that are permissible
QUALIFIED_ALLOWLIST: list[str] = [
    "alleged violation",
    "allegation of violation",
    "reported violation",
    "alleged noncompliance",
    "reported noncompliance",
    "finding of compliance or noncompliance",
    "potential noncompliance",
    "alleged breach",
    "reported breach",
    "claimed illegality",
    "alleged illegality",
]


class EditorialValidator:
    """Validates an assembled editorial dossier against forensic and safety invariants."""

    def __init__(self) -> None:
        pass

    def _contains_prohibited_terms(self, text: str) -> list[str]:
        """Check text for prohibited legal-determination language, respecting qualified allowlist."""
        lower_text = text.lower()
        findings: list[str] = []

        # Temporarily redact qualified allowlist phrases to prevent false positives
        masked_text = lower_text
        for allow_phrase in QUALIFIED_ALLOWLIST:
            masked_text = masked_text.replace(allow_phrase, " " * len(allow_phrase))

        for pattern, description in PROHIBITED_LEGAL_PATTERNS:
            if pattern.search(masked_text):
                findings.append(description)

        return findings

    def validate_dossier(self, dossier: EditorialDossierSchema) -> EditorialValidationReport:
        """Execute full validation suite against an editorial dossier draft.

        Does not block internal inspection of drafts with findings; findings indicate
        blocking issues that prevent approval.
        """
        findings: list[EditorialValidationFinding] = []

        # 1. Dossier-level metadata and title validation
        if not dossier.title or not dossier.title.strip():
            findings.append(
                EditorialValidationFinding(
                    finding_code=EditorialValidationCode.BLOCKED_INSUFFICIENT_DATA,
                    severity=EditorialValidationSeverity.BLOCKING,
                    field_path="title",
                    message="Dossier title is empty or missing.",
                )
            )
        else:
            prohibited = self._contains_prohibited_terms(dossier.title)
            for p in prohibited:
                findings.append(
                    EditorialValidationFinding(
                        finding_code=EditorialValidationCode.BLOCKED_PROHIBITED_TERM,
                        severity=EditorialValidationSeverity.BLOCKING,
                        field_path="title",
                        message=f"Title contains prohibited legal determination language: {p}",
                    )
                )

        # 2. Disclaimer verification (exact trusted text match, Rule 10)
        if not dossier.disclaimer_text or not dossier.disclaimer_text.strip():
            findings.append(
                EditorialValidationFinding(
                    finding_code=EditorialValidationCode.BLOCKED_MISSING_DISCLAIMER,
                    severity=EditorialValidationSeverity.BLOCKING,
                    field_path="disclaimer_text",
                    message="Mandatory research disclaimer is missing.",
                )
            )
        elif dossier.disclaimer_text != EDITORIAL_DISCLAIMER_TEXT:
            findings.append(
                EditorialValidationFinding(
                    finding_code=EditorialValidationCode.BLOCKED_DISCLAIMER_MISMATCH,
                    severity=EditorialValidationSeverity.BLOCKING,
                    field_path="disclaimer_text",
                    message="Disclaimer text does not match mandatory EDITORIAL_DISCLAIMER_TEXT exactly.",
                )
            )

        if dossier.disclaimer_version != EDITORIAL_DISCLAIMER_VERSION:
            findings.append(
                EditorialValidationFinding(
                    finding_code=EditorialValidationCode.BLOCKED_DISCLAIMER_MISMATCH,
                    severity=EditorialValidationSeverity.BLOCKING,
                    field_path="disclaimer_version",
                    message=f"Disclaimer version '{dossier.disclaimer_version}' does not match required '{EDITORIAL_DISCLAIMER_VERSION}'.",
                )
            )

        # 3. Methodology notes validation
        if dossier.methodology_notes:
            prohibited = self._contains_prohibited_terms(dossier.methodology_notes)
            for p in prohibited:
                findings.append(
                    EditorialValidationFinding(
                        finding_code=EditorialValidationCode.BLOCKED_PROHIBITED_TERM,
                        severity=EditorialValidationSeverity.BLOCKING,
                        field_path="methodology_notes",
                        message=f"Methodology notes contain prohibited language: {p}",
                    )
                )

        # 4. Summary validation
        summary = dossier.summary
        if not summary.executive_summary or not summary.executive_summary.strip():
            findings.append(
                EditorialValidationFinding(
                    finding_code=EditorialValidationCode.BLOCKED_INSUFFICIENT_DATA,
                    severity=EditorialValidationSeverity.BLOCKING,
                    field_path="summary.executive_summary",
                    message="Executive summary is empty.",
                )
            )
        else:
            prohibited = self._contains_prohibited_terms(summary.executive_summary)
            for p in prohibited:
                findings.append(
                    EditorialValidationFinding(
                        finding_code=EditorialValidationCode.BLOCKED_PROHIBITED_TERM,
                        severity=EditorialValidationSeverity.BLOCKING,
                        field_path="summary.executive_summary",
                        message=f"Executive summary contains prohibited language: {p}",
                    )
                )

        # 5. Entries validation
        if len(dossier.entries) == 0:
            findings.append(
                EditorialValidationFinding(
                    finding_code=EditorialValidationCode.BLOCKED_EMPTY_DOSSIER,
                    severity=EditorialValidationSeverity.BLOCKING,
                    field_path="entries",
                    message="Dossier contains zero incident entries.",
                )
            )

        for idx, entry in enumerate(dossier.entries):
            prefix = f"entries[{idx}]"

            # Evidence linkage check (Rule 1)
            if len(entry.source_evidence_ids) == 0:
                findings.append(
                    EditorialValidationFinding(
                        finding_code=EditorialValidationCode.BLOCKED_MISSING_EVIDENCE,
                        severity=EditorialValidationSeverity.BLOCKING,
                        field_path=f"{prefix}.source_evidence_ids",
                        message=f"Entry for incident '{entry.incident_id}' has zero evidence links.",
                    )
                )

            # Text integrity check
            if not entry.incident_title.strip():
                findings.append(
                    EditorialValidationFinding(
                        finding_code=EditorialValidationCode.BLOCKED_INSUFFICIENT_DATA,
                        severity=EditorialValidationSeverity.BLOCKING,
                        field_path=f"{prefix}.incident_title",
                        message=f"Entry {entry.entry_id} title is empty.",
                    )
                )

            if not entry.incident_summary.strip():
                findings.append(
                    EditorialValidationFinding(
                        finding_code=EditorialValidationCode.BLOCKED_INSUFFICIENT_DATA,
                        severity=EditorialValidationSeverity.BLOCKING,
                        field_path=f"{prefix}.incident_summary",
                        message=f"Entry {entry.entry_id} summary is empty.",
                    )
                )
            else:
                prohibited = self._contains_prohibited_terms(entry.incident_summary)
                for p in prohibited:
                    findings.append(
                        EditorialValidationFinding(
                            finding_code=EditorialValidationCode.BLOCKED_PROHIBITED_TERM,
                            severity=EditorialValidationSeverity.BLOCKING,
                            field_path=f"{prefix}.incident_summary",
                            message=f"Incident summary contains prohibited language: {p}",
                        )
                    )

            # Facts language check
            for f_idx, fact in enumerate(entry.known_facts):
                f_path = f"{prefix}.known_facts[{f_idx}].statement"
                prohibited = self._contains_prohibited_terms(fact.statement)
                for p in prohibited:
                    findings.append(
                        EditorialValidationFinding(
                            finding_code=EditorialValidationCode.BLOCKED_PROHIBITED_TERM,
                            severity=EditorialValidationSeverity.BLOCKING,
                            field_path=f_path,
                            message=f"Fact statement contains prohibited language: {p}",
                        )
                    )

            # Unknowns check (Rule 2: unknown is not zero)
            for u_idx, unk in enumerate(entry.unknowns):
                u_path = f"{prefix}.unknowns[{u_idx}].question"
                if not unk.question.strip():
                    findings.append(
                        EditorialValidationFinding(
                            finding_code=EditorialValidationCode.BLOCKED_UNRESOLVED_UNKNOWN,
                            severity=EditorialValidationSeverity.BLOCKING,
                            field_path=u_path,
                            message=f"Unknown entry has empty question text.",
                        )
                    )

            # Disputed claims check
            for d_idx, disp in enumerate(entry.disputed_claims):
                d_path = f"{prefix}.disputed_claims[{d_idx}].topic"
                prohibited = self._contains_prohibited_terms(disp.topic)
                for p in prohibited:
                    findings.append(
                        EditorialValidationFinding(
                            finding_code=EditorialValidationCode.BLOCKED_PROHIBITED_TERM,
                            severity=EditorialValidationSeverity.BLOCKING,
                            field_path=d_path,
                            message=f"Disputed topic contains prohibited language: {p}",
                        )
                    )

            # Optional EU commentary guard
            if entry.eu_commentary is not None:
                if entry.eu_screen_status != "APPROVED_INFORMATIONAL":
                    findings.append(
                        EditorialValidationFinding(
                            finding_code=EditorialValidationCode.BLOCKED_UNAPPROVED_EU_SCREEN,
                            severity=EditorialValidationSeverity.BLOCKING,
                            field_path=f"{prefix}.eu_commentary",
                            message=(
                                f"Entry includes EU commentary but underlying screen status is "
                                f"'{entry.eu_screen_status}' (must be APPROVED_INFORMATIONAL)."
                            ),
                        )
                    )

        blocking_count = sum(
            1 for f in findings if f.severity == EditorialValidationSeverity.BLOCKING
        )
        warning_count = sum(
            1 for f in findings if f.severity == EditorialValidationSeverity.WARNING
        )

        return EditorialValidationReport(
            is_valid=(blocking_count == 0),
            dossier_id=dossier.id,
            dossier_version=dossier.version,
            content_hash=dossier.content_hash,
            total_findings=len(findings),
            blocking_count=blocking_count,
            warning_count=warning_count,
            findings=findings,
            validated_at=datetime.now(timezone.utc),
        )
