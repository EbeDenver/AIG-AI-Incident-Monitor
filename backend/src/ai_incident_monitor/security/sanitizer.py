"""Content normalization, HTML stripping, Unicode sanitization, and display safety.

Governing Charter: Project Constitution (Rules 1, 9, 11, 15),
ADR-003, ADR-007, ADR-011, SEC-001, SEC-002.
"""

from __future__ import annotations

import html
import re
from typing import Any, Optional
import unicodedata

# Dangerous HTML elements strictly stripped along with contents
DANGEROUS_HTML_ELEMENTS_REGEX = re.compile(
    r"<(script|style|iframe|object|embed|applet|form|svg|canvas|meta|link)[\s\S]*?</\1>",
    re.IGNORECASE,
)

# Self-closing or void dangerous tags
DANGEROUS_VOID_TAGS_REGEX = re.compile(
    r"<(script|style|iframe|object|embed|applet|form|svg|canvas|meta|link|input|button)[\s\S]*?/?>",
    re.IGNORECASE,
)

# HTML comments
HTML_COMMENT_REGEX = re.compile(r"<!--[\s\S]*?-->")

# All HTML tags (for full stripping to safe plain text)
HTML_TAG_REGEX = re.compile(r"<[^>]+>")

# Event handlers: onclick=, onload=, onerror=, etc.
EVENT_HANDLER_REGEX = re.compile(r"\s+on\w+\s*=\s*(['\"][^'\"]*['\"]|[^\s>]+)", re.IGNORECASE)

# Dangerous URL schemes: javascript:, data:, vbscript:
DANGEROUS_URL_SCHEMES_REGEX = re.compile(
    r"(javascript|data|vbscript|file):[^\s\"']+",
    re.IGNORECASE,
)

# Tracking pixel patterns: 1x1 images, transparent gifs
TRACKING_PIXEL_REGEX = re.compile(
    r'<img[^>]+(?:width=["\']?[01]["\']?|height=["\']?[01]["\']?)[^>]*>',
    re.IGNORECASE,
)

# Bidirectional overrides: U+202A..U+202E, U+2066..U+2069
BIDI_OVERRIDE_CHARS: frozenset[str] = frozenset({
    "\u202A", "\u202B", "\u202C", "\u202D", "\u202E",
    "\u2066", "\u2067", "\u2068", "\u2069",
})

# Zero-width characters: U+200B (ZWSP), U+200C (ZWNJ), U+200D (ZWJ), U+FEFF (BOM)
ZERO_WIDTH_CHARS: frozenset[str] = frozenset({
    "\u200B", "\u200C", "\u200D", "\uFEFF",
})

# Formula injection trigger characters per CWE-1236
FORMULA_TRIGGERS: tuple[str, ...] = ("=", "+", "-", "@", "\t", "\r")


class SanitizationResult:
    """Outcome of content sanitization and normalization."""

    def __init__(
        self,
        cleaned_text: str,
        actions_taken: list[str],
        removed_bidi_count: int = 0,
        removed_zero_width_count: int = 0,
        had_dangerous_html: bool = False,
        had_formula_trigger: bool = False,
    ) -> None:
        self.cleaned_text = cleaned_text
        self.actions_taken = actions_taken
        self.removed_bidi_count = removed_bidi_count
        self.removed_zero_width_count = removed_zero_width_count
        self.had_dangerous_html = had_dangerous_html
        self.had_formula_trigger = had_formula_trigger


def strip_html_safely(raw_html: str) -> tuple[str, list[str]]:
    """Strip HTML markup completely, converting to safe plain text.

    Strictly removes scripts, styles, iframes, SVGs, event handlers,
    tracking pixels, and dangerous URI schemes.
    """
    actions: list[str] = []
    text = raw_html

    # 1. Strip tracking pixels
    if TRACKING_PIXEL_REGEX.search(text):
        text = TRACKING_PIXEL_REGEX.sub(" ", text)
        actions.append("STRIPPED_TRACKING_PIXELS")

    # 2. Strip dangerous elements with contents (scripts, styles, iframes)
    if DANGEROUS_HTML_ELEMENTS_REGEX.search(text):
        text = DANGEROUS_HTML_ELEMENTS_REGEX.sub(" ", text)
        actions.append("STRIPPED_DANGEROUS_ELEMENTS")

    # 3. Strip dangerous void tags
    if DANGEROUS_VOID_TAGS_REGEX.search(text):
        text = DANGEROUS_VOID_TAGS_REGEX.sub(" ", text)
        actions.append("STRIPPED_DANGEROUS_TAGS")

    # 4. Strip HTML comments
    if HTML_COMMENT_REGEX.search(text):
        text = HTML_COMMENT_REGEX.sub(" ", text)
        actions.append("STRIPPED_HTML_COMMENTS")

    # 5. Strip dangerous URL schemes
    if DANGEROUS_URL_SCHEMES_REGEX.search(text):
        text = DANGEROUS_URL_SCHEMES_REGEX.sub("[STRIPPED_URI]", text)
        actions.append("STRIPPED_DANGEROUS_SCHEMES")

    # 6. Strip all remaining HTML tags
    if HTML_TAG_REGEX.search(text):
        text = HTML_TAG_REGEX.sub(" ", text)
        actions.append("STRIPPED_ALL_HTML_TAGS")

    # 7. Unescape HTML entities
    unescaped = html.unescape(text)
    if unescaped != text:
        actions.append("UNESCAPED_HTML_ENTITIES")
        text = unescaped

    return text, actions


def normalize_unicode_and_control_chars(raw_text: str) -> tuple[str, list[str], int, int]:
    """Normalize Unicode to NFKC and strip invisible/control characters.

    Removes:
    - ASCII control characters (0-31 except \n, \r, \t)
    - Bidirectional override characters
    - Zero-width spaces and joiners
    """
    actions: list[str] = []
    # 1. NFKC Normalization
    text = unicodedata.normalize("NFKC", raw_text)
    if text != raw_text:
        actions.append("UNICODE_NFKC_NORMALIZED")

    # 2. Strip BiDi overrides and zero-width characters
    bidi_count = 0
    zero_width_count = 0
    cleaned_chars: list[str] = []

    for char in text:
        if char in BIDI_OVERRIDE_CHARS:
            bidi_count += 1
            continue
        if char in ZERO_WIDTH_CHARS:
            zero_width_count += 1
            continue
        # Strip non-printable ASCII control characters except \n, \r, \t
        code = ord(char)
        if code < 32 and char not in ("\n", "\r", "\t"):
            continue
        if code == 127:  # DEL
            continue
        cleaned_chars.append(char)

    if bidi_count > 0:
        actions.append(f"STRIPPED_BIDI_OVERRIDES_{bidi_count}")
    if zero_width_count > 0:
        actions.append(f"STRIPPED_ZERO_WIDTH_CHARS_{zero_width_count}")

    # Normalize multiple whitespace characters
    cleaned_text = "".join(cleaned_chars)
    # Collapse multiple spaces but preserve single newlines
    cleaned_text = re.sub(r"[ \t]+", " ", cleaned_text)
    cleaned_text = re.sub(r"\n\s*\n", "\n\n", cleaned_text).strip()

    return cleaned_text, actions, bidi_count, zero_width_count


def neutralize_formula_injection(text: str) -> tuple[str, bool]:
    """Neutralize spreadsheet formula injection per CWE-1236.

    If the text begins with dangerous triggers (=, +, -, @, \\t, \\r),
    prepends a single quote (').
    """
    if not text:
        return text, False
    stripped_l = text.lstrip(" ")
    if text.startswith(FORMULA_TRIGGERS) or (stripped_l and stripped_l.startswith(FORMULA_TRIGGERS)):
        return f"'{text}", True
    return text, False


def sanitize_feed_text(raw_text: str) -> SanitizationResult:
    """Comprehensive multi-stage sanitization for external feed text."""
    if not raw_text:
        return SanitizationResult(cleaned_text="", actions_taken=[])

    all_actions: list[str] = []

    # Stage 1: HTML stripping
    stage1_text, html_actions = strip_html_safely(raw_text)
    all_actions.extend(html_actions)
    had_dangerous_html = "STRIPPED_DANGEROUS_ELEMENTS" in html_actions or "STRIPPED_DANGEROUS_TAGS" in html_actions

    # Stage 2: Unicode & Control character normalization
    stage2_text, unicode_actions, bidi_count, zw_count = normalize_unicode_and_control_chars(stage1_text)
    all_actions.extend(unicode_actions)

    # Stage 3: Formula injection neutralization
    stage3_text, had_formula = neutralize_formula_injection(stage2_text)
    if had_formula:
        all_actions.append("FORMULA_INJECTION_NEUTRALIZED")

    return SanitizationResult(
        cleaned_text=stage3_text,
        actions_taken=all_actions,
        removed_bidi_count=bidi_count,
        removed_zero_width_count=zw_count,
        had_dangerous_html=had_dangerous_html,
        had_formula_trigger=had_formula,
    )


def safe_log_snippet(text: str, max_length: int = 80) -> str:
    """Format a safe, bounded log snippet without leaking full payloads or secrets."""
    if not text:
        return ""
    # Strip newlines and non-printable chars
    clean = " ".join(text.split())
    if len(clean) > max_length:
        clean = clean[:max_length] + "..."
    # Sanitize any potential log formatting or control sequences
    return clean.replace("\r", "").replace("\n", "")
