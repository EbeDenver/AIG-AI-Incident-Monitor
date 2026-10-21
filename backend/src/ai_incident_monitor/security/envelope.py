"""Typed untrusted-content envelope and prompt serialization container.

Governing Charter: Project Constitution (Rules 1, 3, 11, 12, 14, 15, 16),
ADR-008, ADR-011, SRC-003, SEC-001, SEC-002.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
from typing import Any, Optional
import xml.sax.saxutils as saxutils


DEFAULT_MAX_ENVELOPE_CHARS = 25_000
ENVELOPE_SCHEMA_VERSION = "1.0.0"
TRUST_LEVEL_EXTERNAL = "UNTRUSTED_EXTERNAL"


@dataclass(frozen=True)
class UntrustedSourceContentEnvelope:
    """Canonical envelope packaging untrusted external content.

    Important Security Rule:
    The XML block `<untrusted_source_content>` is for provenance tracking and
    prompt serialization ONLY. It is NOT an authorization boundary and cannot
    by itself prevent prompt injection. External text must remain untrusted
    and cannot invoke tools, alter prompts, or change system state.
    """

    schema_version: str
    source_system: str
    source_record_id: str
    provenance_manifest_id: str
    content_sha256: str
    content_type: str
    character_encoding: str
    retrieved_at: str
    trust_level: str
    normalized_text: str
    original_text_available: bool
    sanitization_actions: list[str]
    injection_signal_codes: list[str]
    truncation_applied: bool
    maximum_character_limit: int
    quarantined: bool = False

    def to_xml_prompt_block(self) -> str:
        """Serialize envelope into a strict, escaped XML prompt enclosure.

        Ensures that any occurrences of `</untrusted_source_content>` or other
        markup inside the normalized text are fully escaped as entities so
        external content cannot break out of the enclosure.
        """
        # Escape XML entities: &, <, >, ", '
        escaped_text = saxutils.escape(
            self.normalized_text,
            entities={
                '"': "&quot;",
                "'": "&apos;",
            },
        )

        # Attribute values must also be safely escaped
        safe_source = saxutils.quoteattr(self.source_system)
        safe_record_id = saxutils.quoteattr(self.source_record_id)
        safe_manifest_id = saxutils.quoteattr(self.provenance_manifest_id)
        safe_trust = saxutils.quoteattr(self.trust_level.lower())
        safe_quarantine = saxutils.quoteattr("true" if self.quarantined else "false")

        return (
            f"<untrusted_source_content\n"
            f"  source={safe_source}\n"
            f"  record_id={safe_record_id}\n"
            f"  manifest_id={safe_manifest_id}\n"
            f"  trust={safe_trust}\n"
            f"  quarantined={safe_quarantine}>\n"
            f"{escaped_text}\n"
            f"</untrusted_source_content>"
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert envelope to serializable dictionary."""
        return {
            "schema_version": self.schema_version,
            "source_system": self.source_system,
            "source_record_id": self.source_record_id,
            "provenance_manifest_id": self.provenance_manifest_id,
            "content_sha256": self.content_sha256,
            "content_type": self.content_type,
            "character_encoding": self.character_encoding,
            "retrieved_at": self.retrieved_at,
            "trust_level": self.trust_level,
            "normalized_text": self.normalized_text,
            "original_text_available": self.original_text_available,
            "sanitization_actions": list(self.sanitization_actions),
            "injection_signal_codes": list(self.injection_signal_codes),
            "truncation_applied": self.truncation_applied,
            "maximum_character_limit": self.maximum_character_limit,
            "quarantined": self.quarantined,
        }


def create_untrusted_envelope(
    *,
    text: str,
    source_system: str,
    source_record_id: str,
    provenance_manifest_id: str,
    content_type: str = "text/plain",
    character_encoding: str = "utf-8",
    sanitization_actions: Optional[list[str]] = None,
    injection_signal_codes: Optional[list[str]] = None,
    maximum_character_limit: int = DEFAULT_MAX_ENVELOPE_CHARS,
    original_text_available: bool = False,
    quarantined: bool = False,
) -> UntrustedSourceContentEnvelope:
    """Factory creating a validated UntrustedSourceContentEnvelope."""
    actions = list(sanitization_actions or [])
    signals = list(injection_signal_codes or [])

    # Check truncation
    truncation_applied = False
    normalized = text
    if len(normalized) > maximum_character_limit:
        normalized = normalized[:maximum_character_limit]
        truncation_applied = True
        actions.append("TRUNCATED_TO_MAX_CHARS")

    content_sha256 = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    retrieved_at = datetime.now(timezone.utc).isoformat()

    return UntrustedSourceContentEnvelope(
        schema_version=ENVELOPE_SCHEMA_VERSION,
        source_system=source_system,
        source_record_id=source_record_id,
        provenance_manifest_id=provenance_manifest_id,
        content_sha256=content_sha256,
        content_type=content_type,
        character_encoding=character_encoding,
        retrieved_at=retrieved_at,
        trust_level=TRUST_LEVEL_EXTERNAL,
        normalized_text=normalized,
        original_text_available=original_text_available,
        sanitization_actions=actions,
        injection_signal_codes=signals,
        truncation_applied=truncation_applied,
        maximum_character_limit=maximum_character_limit,
        quarantined=quarantined or len(signals) > 0,
    )
