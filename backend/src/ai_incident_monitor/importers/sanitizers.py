"""Sanitization utilities defending against formula injection (CWE-1236) and control characters."""

from __future__ import annotations

import re
from typing import Any

# Dangerous characters that spreadsheet software (Excel, LibreOffice, Google Sheets)
# may interpret as formula prefixes when opening CSV, TSV, or XLSX files.
FORMULA_TRIGGERS: tuple[str, ...] = ("=", "+", "-", "@", "\t", "\r")

# Strip null bytes and non-printable control characters (except standard newline/tab)
CONTROL_CHARS_REGEX = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_formula_injection(text: str) -> str:
    """Neutralize formula injection by prepending a single quote per CWE-1236.

    If a text field begins with '=', '+', '-', '@', tab, or carriage return,
    prepending a single quote (') instructs spreadsheet viewers to render the
    cell strictly as inert text rather than executing macro or DDE expressions.
    """
    if not isinstance(text, str):
        return text

    # Strip null bytes and dangerous unprintable controls
    cleaned = text.replace("\x00", "")
    cleaned = CONTROL_CHARS_REGEX.sub("", cleaned)

    stripped_l = cleaned.lstrip()
    if stripped_l and stripped_l.startswith(FORMULA_TRIGGERS):
        # Prepend single quote to neutralize execution in spreadsheet applications
        return "'" + cleaned

    return cleaned


def sanitize_cell_value(value: Any) -> Any:
    """Sanitize arbitrary cell values, neutralizing formula injection for strings."""
    if value is None:
        return None
    if isinstance(value, str):
        return sanitize_formula_injection(value)
    return value


def sanitize_row_dict(row: dict[str, Any]) -> dict[str, Any]:
    """Recursively sanitize all keys and string values in an imported row dictionary."""
    sanitized: dict[str, Any] = {}
    for k, v in row.items():
        clean_key = sanitize_formula_injection(str(k)).strip()
        if isinstance(v, dict):
            sanitized[clean_key] = sanitize_row_dict(v)
        elif isinstance(v, list):
            sanitized[clean_key] = [sanitize_cell_value(item) for item in v]
        else:
            sanitized[clean_key] = sanitize_cell_value(v)
    return sanitized
