"""Hardened XML containment, resource bounds, and safe parsing enforcement.

Governing Charter: Project Constitution (Rules 11, 14, 15),
ADR-008, ADR-011, SRC-001, SEC-001, SEC-002.
"""

from __future__ import annotations

from dataclasses import dataclass
import io
import re
from typing import Any, Optional
import xml.etree.ElementTree as standard_ET

import defusedxml.ElementTree as defused_ET
from defusedxml.common import DefusedXmlException, DTDForbidden, EntitiesForbidden

# Default resource bounds for XML payloads
DEFAULT_MAX_XML_BYTES = 5 * 1024 * 1024  # 5 MB
DEFAULT_MAX_XML_NESTING_DEPTH = 20
DEFAULT_MAX_XML_ELEMENT_COUNT = 5_000
DEFAULT_MAX_XML_ATTRIBUTES_PER_ELEMENT = 50
DEFAULT_MAX_TEXT_FIELD_CHARS = 50_000
DEFAULT_MAX_URL_CHARS = 2_048
DEFAULT_MAX_TOTAL_NORMALIZED_CHARS = 100_000


class XMLResourceLimitExceededError(Exception):
    """Raised when an XML payload violates structural resource limits."""


class XMLSecurityViolationError(Exception):
    """Raised when an XML payload attempts unsafe entity expansion or DTD loading."""


@dataclass(frozen=True)
class XMLParseProfile:
    """Configurable security bounds for parsing XML documents."""

    max_bytes: int = DEFAULT_MAX_XML_BYTES
    max_nesting_depth: int = DEFAULT_MAX_XML_NESTING_DEPTH
    max_element_count: int = DEFAULT_MAX_XML_ELEMENT_COUNT
    max_attributes_per_element: int = DEFAULT_MAX_XML_ATTRIBUTES_PER_ELEMENT
    max_text_field_chars: int = DEFAULT_MAX_TEXT_FIELD_CHARS
    max_url_chars: int = DEFAULT_MAX_URL_CHARS
    max_total_normalized_chars: int = DEFAULT_MAX_TOTAL_NORMALIZED_CHARS


@dataclass
class XMLValidationResult:
    """Outcome of XML containment pre-screening."""

    is_valid: bool
    element_count: int
    max_depth_observed: int
    warning_codes: list[str]
    error_message: Optional[str] = None


def inspect_xml_structure_and_bounds(
    xml_bytes: bytes,
    profile: XMLParseProfile = XMLParseProfile(),
) -> XMLValidationResult:
    """Inspect XML bytes for structural resource bounds and forbidden entities.

    Validates:
    - Byte length <= max_bytes
    - Defused XML parsing without DTDs or external entities
    - Element count <= max_element_count
    - Nesting depth <= max_nesting_depth
    - Attributes per element <= max_attributes_per_element
    - Field text length within bounds
    """
    warning_codes: list[str] = []

    # 1. Byte limit check
    if len(xml_bytes) > profile.max_bytes:
        return XMLValidationResult(
            is_valid=False,
            element_count=0,
            max_depth_observed=0,
            warning_codes=["PAYLOAD_TOO_LARGE"],
            error_message=f"Payload size ({len(xml_bytes)} bytes) exceeds limit ({profile.max_bytes} bytes)",
        )

    # 2. Defused XML Parse (prohibits DTD, Entities, XInclude)
    try:
        # Use defusedxml to safely parse without external network or entity expansion
        tree = defused_ET.fromstring(xml_bytes)
    except (DTDForbidden, EntitiesForbidden, DefusedXmlException) as e:
        return XMLValidationResult(
            is_valid=False,
            element_count=0,
            max_depth_observed=0,
            warning_codes=["FORBIDDEN_ENTITY_OR_DTD"],
            error_message=f"XML security violation: {e}",
        )
    except Exception as e:
        return XMLValidationResult(
            is_valid=False,
            element_count=0,
            max_depth_observed=0,
            warning_codes=["MALFORMED_XML"],
            error_message=f"Malformed XML syntax: {e}",
        )

    # 3. Structural bounds traversal (element count, depth, attributes)
    element_count = 0
    max_depth = 0

    def traverse(elem: standard_ET.Element, current_depth: int) -> None:
        nonlocal element_count, max_depth
        element_count += 1
        if current_depth > max_depth:
            max_depth = current_depth

        if element_count > profile.max_element_count:
            raise XMLResourceLimitExceededError(
                f"Element count ({element_count}) exceeded limit ({profile.max_element_count})"
            )

        if current_depth > profile.max_nesting_depth:
            raise XMLResourceLimitExceededError(
                f"Nesting depth ({current_depth}) exceeded limit ({profile.max_nesting_depth})"
            )

        if len(elem.attrib) > profile.max_attributes_per_element:
            raise XMLResourceLimitExceededError(
                f"Attribute count ({len(elem.attrib)}) exceeded limit ({profile.max_attributes_per_element})"
            )

        # Check element text length
        if elem.text and len(elem.text) > profile.max_text_field_chars:
            warning_codes.append("TEXT_FIELD_TRUNCATED")

        for child in elem:
            traverse(child, current_depth + 1)

    try:
        traverse(tree, current_depth=1)
    except XMLResourceLimitExceededError as e:
        return XMLValidationResult(
            is_valid=False,
            element_count=element_count,
            max_depth_observed=max_depth,
            warning_codes=["RESOURCE_LIMIT_EXCEEDED"],
            error_message=str(e),
        )

    return XMLValidationResult(
        is_valid=True,
        element_count=element_count,
        max_depth_observed=max_depth,
        warning_codes=warning_codes,
        error_message=None,
    )
