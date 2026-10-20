"""Deterministic prompt-injection signal detection and triage.

Governing Charter: Project Constitution (Rules 1, 11, 12),
ADR-008, ADR-011, SEC-001, SEC-002.
"""

from __future__ import annotations

import re
from typing import NamedTuple

# Injection signal codes
CODE_OVERRIDE_INSTRUCTION = "INJ-OVERRIDE-INSTRUCTION"
CODE_REVEAL_SECRET = "INJ-REVEAL-SECRET"
CODE_EXEC_TOOL = "INJ-EXEC-TOOL"
CODE_OBFUSCATION = "INJ-OBFUSCATION"
CODE_CONTROL_CHARS = "INJ-CONTROL-CHARS"
CODE_HTML_HIDING = "INJ-HTML-HIDING"
CODE_ROLE_CONFUSION = "INJ-ROLE-CONFUSION"

# High-risk signal codes that trigger quarantine
HIGH_RISK_SIGNAL_CODES: frozenset[str] = frozenset({
    CODE_OVERRIDE_INSTRUCTION,
    CODE_REVEAL_SECRET,
    CODE_EXEC_TOOL,
    CODE_ROLE_CONFUSION,
})

# Patterns for override instructions directed at the model
# Using imperative patterns that distinguish directives from objective descriptions
OVERRIDE_PATTERNS = [
    re.compile(r"\bignore\s+(all\s+)?(previous|prior|above|former)\s+(instructions|prompts|directives|guidelines|rules)\b", re.IGNORECASE),
    re.compile(r"\bdisregard\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|rules|context)\b", re.IGNORECASE),
    re.compile(r"\bnew\s+instructions\s*:\s*(you\s+must|do\s+not|from\s+now\s+on)\b", re.IGNORECASE),
    re.compile(r"\bsystem\s+override\s*:\s*", re.IGNORECASE),
    re.compile(r"\byou\s+are\s+now\s+(in\s+developer\s+mode|unconstrained|DAN|an\s+unrestricted\s+AI)\b", re.IGNORECASE),
    re.compile(r"\bfrom\s+now\s+on,\s+ignore\b", re.IGNORECASE),
]

# Patterns for revealing system secrets or prompts
REVEAL_SECRET_PATTERNS = [
    re.compile(r"\b(show|print|reveal|output|display|echo)\s+(the\s+|your\s+)?(system\s+prompt|initial\s+prompt|hidden\s+instructions|secret\s+key|api\s*key)\b", re.IGNORECASE),
    re.compile(r"\brepeat\s+the\s+(words|text)\s+above\s+(starting\s+with|verbatim)\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+are\s+your\s+(instructions|system\s+rules|hidden\s+prompts)\b", re.IGNORECASE),
]

# Patterns for executing tools or shell commands
EXEC_TOOL_PATTERNS = [
    re.compile(r"\b(execute|run|invoke|call)\s+(the\s+|a\s+)?(bash|shell|terminal|python|eval|exec|tool|function)\s*[:(]", re.IGNORECASE),
    re.compile(r"\bcurl\s+https?://[^\s]+", re.IGNORECASE),
    re.compile(r"\b(rm\s+-rf|wget\s+|chmod\s+\+x)\b", re.IGNORECASE),
]

# Patterns for role confusion or delimiter spoofing
ROLE_CONFUSION_PATTERNS = [
    re.compile(r"<\|im_start\|>", re.IGNORECASE),
    re.compile(r"<\|im_end\|>", re.IGNORECASE),
    re.compile(r"^\s*\[SYSTEM\]", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\s*\[INSTRUCTION\]", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\s*(Human|Assistant|System)\s*:\s*", re.MULTILINE),
]

# Patterns for HTML/CSS hiding
HTML_HIDING_PATTERNS = [
    re.compile(r"style\s*=\s*['\"][^'\"]*display\s*:\s*none", re.IGNORECASE),
    re.compile(r"style\s*=\s*['\"][^'\"]*visibility\s*:\s*hidden", re.IGNORECASE),
    re.compile(r"style\s*=\s*['\"][^'\"]*opacity\s*:\s*0", re.IGNORECASE),
    re.compile(r"<[a-z0-9]+\s+hidden\b", re.IGNORECASE),
    re.compile(r"font-size\s*:\s*0px", re.IGNORECASE),
]

# Patterns for base64 / obfuscated instruction blocks
OBFUSCATION_PATTERNS = [
    re.compile(r"\b(base64\s+decode|eval\s*\(\s*base64|atob\s*\()\b", re.IGNORECASE),
    re.compile(r"[A-Za-z0-9+/]{80,}={0,2}"),  # Long dense base64 string
]


class InjectionDetectionResult(NamedTuple):
    """Result of prompt injection triage evaluation."""

    signal_codes: list[str]
    is_quarantined: bool
    highest_severity: str  # "NONE", "LOW", "MEDIUM", "HIGH"
    rationale: list[str]


def detect_prompt_injection_signals(
    raw_text: str,
    had_bidi: bool = False,
    had_zero_width: bool = False,
) -> InjectionDetectionResult:
    """Analyze text for prompt injection and instruction override signals.

    Important Epistemic Nuance:
    This classifier does NOT treat the mere discussion of AI security, prompt
    injection, or jailbreaks as an attack. It inspects whether the text
    contains active, imperative directives attempting to commandeer the system.
    """
    if not raw_text:
        return InjectionDetectionResult([], False, "NONE", [])

    signals: list[str] = []
    rationales: list[str] = []

    # 1. Override Instructions Check
    for pat in OVERRIDE_PATTERNS:
        match = pat.search(raw_text)
        if match:
            signals.append(CODE_OVERRIDE_INSTRUCTION)
            rationales.append(f"Detected override directive matching pattern: '{match.group(0)[:50]}'")
            break

    # 2. Reveal Secret Check
    for pat in REVEAL_SECRET_PATTERNS:
        match = pat.search(raw_text)
        if match:
            signals.append(CODE_REVEAL_SECRET)
            rationales.append(f"Detected secret-extraction directive matching pattern: '{match.group(0)[:50]}'")
            break

    # 3. Tool Execution Check
    for pat in EXEC_TOOL_PATTERNS:
        match = pat.search(raw_text)
        if match:
            signals.append(CODE_EXEC_TOOL)
            rationales.append(f"Detected unauthorized tool/command execution request: '{match.group(0)[:50]}'")
            break

    # 4. Role Confusion / Delimiter Spoofing Check
    for pat in ROLE_CONFUSION_PATTERNS:
        match = pat.search(raw_text)
        if match:
            signals.append(CODE_ROLE_CONFUSION)
            rationales.append(f"Detected system role or delimiter spoofing: '{match.group(0)[:50]}'")
            break

    # 5. HTML Hiding Check
    for pat in HTML_HIDING_PATTERNS:
        match = pat.search(raw_text)
        if match:
            signals.append(CODE_HTML_HIDING)
            rationales.append("Detected hidden HTML or zero-font styling")
            break

    # 6. Obfuscation Check
    for pat in OBFUSCATION_PATTERNS:
        match = pat.search(raw_text)
        if match:
            signals.append(CODE_OBFUSCATION)
            rationales.append("Detected obfuscated or base64-encoded instruction payload")
            break

    # 7. Control Characters Check (BiDi overrides / zero-width bursts)
    if had_bidi or had_zero_width:
        signals.append(CODE_CONTROL_CHARS)
        rationales.append("Text contained bidirectional overrides or zero-width character bursts")

    # Evaluate quarantine condition
    is_quarantined = any(code in HIGH_RISK_SIGNAL_CODES for code in signals)
    severity = "NONE"
    if is_quarantined:
        severity = "HIGH"
    elif signals:
        severity = "MEDIUM"

    return InjectionDetectionResult(
        signal_codes=signals,
        is_quarantined=is_quarantined,
        highest_severity=severity,
        rationale=rationales,
    )
