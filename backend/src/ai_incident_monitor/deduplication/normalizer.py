"""URL and title normalization utilities for deterministic deduplication."""

from __future__ import annotations

import difflib
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

TRACKING_PARAMS: set[str] = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
    "ref",
    "source",
    "feature",
    "mc_cid",
    "mc_eid",
}

PUNCTUATION_REGEX = re.compile(r"[^\w\s]")
WHITESPACE_REGEX = re.compile(r"\s+")


def normalize_url(url: str) -> str:
    """Normalize a URL by stripping tracking parameters, lowercase host, and removing fragments."""
    if not url:
        return ""

    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    # Strip default ports
    if ":" in netloc:
        host, port = netloc.split(":", 1)
        if (scheme == "http" and port == "80") or (scheme == "https" and port == "443"):
            netloc = host

    # Normalize path (remove trailing slash unless it's root)
    path = parsed.path
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    # Filter out tracking query parameters
    query_tuples = parse_qsl(parsed.query, keep_blank_values=True)
    filtered_query = [
        (k, v) for k, v in query_tuples if k.lower() not in TRACKING_PARAMS
    ]
    query_str = urlencode(filtered_query)

    # Reconstruct URL without fragment
    return urlunparse((scheme, netloc, path, "", query_str, ""))


def normalize_title(title: str) -> str:
    """Normalize title string for fuzzy comparison."""
    if not title:
        return ""

    # Convert to lowercase
    lowered = title.strip().lower()
    # Remove punctuation
    no_punct = PUNCTUATION_REGEX.sub(" ", lowered)
    # Collapse multiple whitespaces
    collapsed = WHITESPACE_REGEX.sub(" ", no_punct).strip()
    return collapsed


def calculate_title_similarity(title_a: str, title_b: str) -> float:
    """Calculate SequenceMatcher similarity ratio between two titles."""
    norm_a = normalize_title(title_a)
    norm_b = normalize_title(title_b)
    if not norm_a or not norm_b:
        return 0.0
    if norm_a == norm_b:
        return 1.0

    matcher = difflib.SequenceMatcher(None, norm_a, norm_b)
    return float(matcher.ratio())
