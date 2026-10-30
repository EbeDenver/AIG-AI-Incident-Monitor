"""Sanitization, log injection defense (CWE-117), and data minimization for operational logs.

Governing Charter: Project Constitution (Rules 1, 10, 16), PRD §5.
"""

from __future__ import annotations

import re
from typing import Any

SENSITIVE_KEY_PATTERN = re.compile(
    r"(token|secret|password|passwd|auth|api_key|apikey|private_key|credential|bearer)",
    re.IGNORECASE,
)

REDACTED_PLACEHOLDER = "[REDACTED]"
MAX_LOG_STRING_LENGTH = 1000


def sanitize_log_string(raw: str, max_length: int = MAX_LOG_STRING_LENGTH) -> str:
    """Sanitize strings for log safety: strip control characters and newlines (CWE-117)."""
    if not isinstance(raw, str):
        raw = str(raw)

    # Replace CR, LF, and null bytes to prevent log injection / splitting
    cleaned = raw.replace("\r", " ").replace("\n", " ").replace("\0", " ")

    # Strip non-printable ASCII control characters (0x01-0x1F, 0x7F)
    cleaned = "".join(ch if (ch >= " " and ch != "\x7f") else " " for ch in cleaned)

    # Collapse repeated whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if len(cleaned) > max_length:
        return cleaned[:max_length] + " [TRUNCATED]"
    return cleaned


def mask_sensitive_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively mask sensitive keys in nested dictionaries or lists."""
    masked: dict[str, Any] = {}
    for key, value in data.items():
        if SENSITIVE_KEY_PATTERN.search(str(key)):
            masked[str(key)] = REDACTED_PLACEHOLDER
        elif isinstance(value, dict):
            masked[str(key)] = mask_sensitive_dict(value)
        elif isinstance(value, list):
            masked[str(key)] = [
                mask_sensitive_dict(item) if isinstance(item, dict)
                else sanitize_log_string(str(item)) if isinstance(item, str)
                else item
                for item in value
            ]
        elif isinstance(value, str):
            # Check if value itself looks like an inline token / secret
            if SENSITIVE_KEY_PATTERN.search(value) and any(kw in value.lower() for kw in ("bearer ", "ghp_", "gho_")):
                masked[str(key)] = REDACTED_PLACEHOLDER
            else:
                masked[str(key)] = sanitize_log_string(value)
        else:
            masked[str(key)] = value
    return masked


def safe_exception_summary(exc: BaseException) -> tuple[str, str]:
    """Extract safe exception type and sanitized message without leaking frames or locals."""
    exc_type = type(exc).__name__
    raw_msg = str(exc)
    safe_msg = sanitize_log_string(raw_msg, max_length=500)
    return exc_type, safe_msg
