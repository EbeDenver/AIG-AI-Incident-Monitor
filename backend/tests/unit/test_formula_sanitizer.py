"""Unit tests for formula injection defense (CWE-1236) and control character stripping."""

from __future__ import annotations

import pytest

from ai_incident_monitor.importers.sanitizers import (
    FORMULA_TRIGGERS,
    sanitize_cell_value,
    sanitize_formula_injection,
    sanitize_row_dict,
)


@pytest.mark.parametrize(
    "attack_payload,expected_sanitized",
    [
        ("=cmd|' /C calc'!A0", "'=cmd|' /C calc'!A0"),
        ("+12345-alert()", "'+12345-alert()"),
        ("-2+3+cmd|' /C notepad'!A0", "'-2+3+cmd|' /C notepad'!A0"),
        ("@SUM(1+1)*cmd|' /C calc'!A0", "'@SUM(1+1)*cmd|' /C calc'!A0"),
        ("\t=1+1", "'\t=1+1"),
        ("\r=cmd", "'\r=cmd"),
        (" =SUM(A1:A10)", "' =SUM(A1:A10)"),
        ("   @HYPERLINK('http://malicious.com')", "'   @HYPERLINK('http://malicious.com')"),
    ],
)
def test_formula_injection_neutralized(attack_payload: str, expected_sanitized: str) -> None:
    """Verify that dangerous formula triggers are neutralized by prepending a single quote."""
    sanitized = sanitize_formula_injection(attack_payload)
    assert sanitized == expected_sanitized
    assert sanitized.startswith("'")


@pytest.mark.parametrize(
    "benign_text",
    [
        "Autonomous vehicle sensor calibration failure",
        "Algorithmic pricing discrepancy on 2025-03-01",
        "Clinical AI voice assistant error report",
        "100.50",
        "Normal text without triggers",
    ],
)
def test_benign_text_unaltered(benign_text: str) -> None:
    """Verify that benign text without formula triggers remains unaltered."""
    assert sanitize_formula_injection(benign_text) == benign_text


def test_null_bytes_and_unprintable_control_characters_stripped() -> None:
    """Verify that null bytes and dangerous control characters are stripped."""
    raw = "Header\x00Name\x08With\x1fControls"
    sanitized = sanitize_formula_injection(raw)
    assert "\x00" not in sanitized
    assert "\x08" not in sanitized
    assert "\x1f" not in sanitized
    assert sanitized == "HeaderNameWithControls"


def test_sanitize_cell_value_types() -> None:
    """Verify sanitize_cell_value preserves non-string primitives."""
    assert sanitize_cell_value(None) is None
    assert sanitize_cell_value(42) == 42
    assert sanitize_cell_value(3.14) == 3.14
    assert sanitize_cell_value(True) is True
    assert sanitize_cell_value("=cmd") == "'=cmd"


def test_sanitize_row_dict_recursively() -> None:
    """Verify sanitize_row_dict cleans keys, values, and nested structures."""
    raw_row = {
        "=key1": "+dangerous_value",
        "benign_key": "safe_value",
        "nested": {"@nested_key": "=nested_formula"},
        "list_val": ["=elem1", "elem2"],
    }
    sanitized = sanitize_row_dict(raw_row)
    assert sanitized["'=key1"] == "'+dangerous_value"
    assert sanitized["benign_key"] == "safe_value"
    assert sanitized["nested"]["'@nested_key"] == "'=nested_formula"
    assert sanitized["list_val"] == ["'=elem1", "elem2"]
