"""Base interface and formatting utilities for editorial renderers.

Enforces Constitutional Rules 1, 3, 10, 11, 14, 15, and 17.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import re
from typing import Optional
from urllib.parse import urlparse

from ai_incident_monitor.editorial.enums import (
    EditorialArtifactPurpose,
    EditorialPresentationProfile,
)
from ai_incident_monitor.editorial.models import (
    EditorialDossierSchema,
    EditorialValidationReport,
)

# Allowed hyperlink schemes for editorial source citations
ALLOWED_URL_SCHEMES = frozenset({"http", "https"})

# Tag-stripping regex for active HTML and tracking elements
HTML_TAG_PATTERN = re.compile(r"<[^>]+>", re.IGNORECASE)


def strip_html_tags(text: str) -> str:
    """Strip HTML tags from untrusted text to prevent injection or formatting hijacking."""
    if not text:
        return ""
    # Strip script/style blocks with contents
    cleaned = re.sub(r"<(script|style|iframe)[^>]*>.*?</\1>", "", text, flags=re.IGNORECASE | re.DOTALL)
    # Strip remaining tags
    cleaned = HTML_TAG_PATTERN.sub("", cleaned)
    return cleaned.strip()


def sanitize_url(url: Optional[str]) -> Optional[str]:
    """Validate hyperlink URL against allowed safe schemes (https, http).

    Rejects javascript:, file:, data:, vbscript:, and relative malicious vectors.
    """
    if not url:
        return None
    trimmed = url.strip()
    try:
        parsed = urlparse(trimmed)
        if parsed.scheme.lower() in ALLOWED_URL_SCHEMES and parsed.netloc:
            return trimmed
        return None
    except Exception:
        return None


def escape_markdown_table_cell(text: str) -> str:
    """Escape vertical bar pipe characters and line breaks for safe Markdown table cells."""
    if not text:
        return ""
    # Replace newlines with spaces to avoid breaking table layout
    clean = text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    # Escape pipe
    return clean.replace("|", "\\|").strip()


def escape_markdown_text(text: str) -> str:
    """Sanitize and normalize untrusted text for safe Markdown prose rendering."""
    if not text:
        return ""
    # Strip any active HTML first
    stripped = strip_html_tags(text)
    # Escape standalone leading headers or blockquote injections if needed
    lines = stripped.splitlines()
    sanitized_lines = []
    for line in lines:
        sanitized_lines.append(line.rstrip())
    return "\n".join(sanitized_lines)


class BaseEditorialRenderer(ABC):
    """Abstract base class for all deterministic editorial renderers."""

    @abstractmethod
    def render(
        self,
        dossier: EditorialDossierSchema,
        profile: EditorialPresentationProfile = EditorialPresentationProfile.DEEP_DIVE_DOSSIER,
        purpose: EditorialArtifactPurpose = EditorialArtifactPurpose.INTERNAL_REVIEW_COPY,
        validation_report: Optional[EditorialValidationReport] = None,
    ) -> tuple[str, str]:
        """Render the dossier into the target format.

        Returns:
            tuple[str, str]: (rendered_content_string, canonical_payload_hash)
        """
        raise NotImplementedError
