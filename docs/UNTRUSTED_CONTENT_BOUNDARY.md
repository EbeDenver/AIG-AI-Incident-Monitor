# UNTRUSTED CONTENT BOUNDARY AND PROMPT SERIALIZATION
**Project:** AI Incident Monitor  
**Organization:** AI Guardians LLC  
**Document Identifier:** SPEC-007  
**Version:** 1.0.0  
**Effective Date:** 2026-10-20  
**Governing Charter:** [Project Constitution](PROJECT_CONSTITUTION.md) (Rules 1, 3, 11, 12, 13, 14), [ADR-008](DECISIONS.md#adr-008), [ADR-011](DECISIONS.md#adr-011)  

---

## 1. Architectural Philosophy: The Untrusted Data Boundary

All external text, RSS summaries, XML elements, titles, URLs, and metadata retrieved from external sources are treated as **untrusted data**.

> [!CAUTION]
> The XML tag `<untrusted_source_content>` is an envelope for **data provenance and serialization formatting only**. It is **not** an authorization control, sandbox, or magical defense against prompt injection. True security is enforced through structural isolation, deterministic preprocessing, read-only sandboxing, and non-delegable human approval.

---

## 2. Canonical Envelope: `UntrustedSourceContentEnvelope`

Every ingested item is encapsulated within a typed `UntrustedSourceContentEnvelope`:

```python
@dataclass(frozen=True)
class UntrustedSourceContentEnvelope:
    schema_version: str             # "1.0.0"
    source_system: str              # e.g. "RSS_NEWS", "ARXIV_API", "OECD_AIM"
    source_record_id: str           # Stable record ID
    provenance_manifest_id: str     # Cryptographic link to IngestionManifest
    content_sha256: str             # SHA-256 of normalized text
    content_type: str               # MIME type
    character_encoding: str         # "utf-8"
    retrieved_at: str               # UTC ISO 8601 timestamp
    trust_level: str                # Strictly "UNTRUSTED_EXTERNAL"
    normalized_text: str            # Cleaned, stripped, bounded text
    original_text_available: bool   # True if staged payload exists
    sanitization_actions: list[str] # Audit record of cleaning steps
    injection_signal_codes: list[str] # Triage detection flags
    truncation_applied: bool        # True if capped at character limit
    maximum_character_limit: int    # Max allowed characters
    quarantined: bool               # True if high-risk injection signals detected
```

### Prompt Enclosure Format
When serialized for future model consumption, the envelope renders strictly escaped XML:
```xml
<untrusted_source_content
  source="RSS_NEWS"
  record_id="SRC-RSS-8842af12"
  manifest_id="man_b42f9e12"
  trust="untrusted_external"
  quarantined="false">
  [Escaped, length-bounded normalized text here]
</untrusted_source_content>
```

**Escaping Invariant**: Any occurrences of `</untrusted_source_content>` or other markup inside `normalized_text` are strictly escaped (`&lt;/untrusted_source_content&gt;`), mathematically preventing adversarial payloads from terminating the enclosure block prematurely.

---

## 3. Strict Deterministic Boundary Constraints

External source content is strictly forbidden from influencing or modifying:
1. **System & Developer Prompts**: Prompts are static, versioned, and immutable.
2. **Tool Definitions & Permissions**: Untrusted content cannot define tools, grant permissions, or alter tool signatures.
3. **Connector Policies & Allowlists**: External content cannot expand domain allowlists or alter rate limits.
4. **Severity Scores (AIG-ISI)**: Incident severity is computed deterministically by the evaluation engine, never parsed from source suggestions.
5. **Publication State**: Publishing incident briefs strictly requires explicit Human-in-the-Loop authorization (`Rule 13`).
6. **Execution Destinations**: No external content can set database queries, file paths, shell commands, or outbound network URLs.

---

## 4. Normalization and Display Safety

Prior to storage or prompt serialization, content passes through three deterministic filters:
1. **HTML & Executable Markup Stripping**:
   - Complete removal of `<script>`, `<style>`, `<iframe>`, `<object>`, `<embed>`, `<form>`, `<svg>`, `<canvas>`, event handlers (`onload=`, `onerror=`), and HTML comments.
   - Removal of tracking pixels (`<img width="1" height="1">`).
   - Removal of dangerous URI schemes (`javascript:`, `data:`, `vbscript:`).
2. **Unicode Normalization & Invisible Character Filtering**:
   - Normalized to Unicode NFKC.
   - ASCII control characters (0–31 except `\n`, `\r`, `\t`) and DEL (127) removed.
   - Bidirectional override characters (`U+202A`..`U+202E`, `U+2066`..`U+2069`) detected and removed.
   - Zero-width spaces (`U+200B`, `U+200C`, `U+200D`, `U+FEFF`) detected and removed.
3. **Formula Injection Neutralization (CWE-1236)**:
   - If text begins with dangerous triggers (`=`, `+`, `-`, `@`, `\t`, `\r`), a single quote (`'`) is prepended to ensure spreadsheet software treats the cell as inert text.

---

## 5. Future LLM Boundary Contract

While no LLM execution occurs in Phase 4, the deterministic boundary establishes the following non-negotiable contract for future phases:
- **Read-Only Model Sandboxing**: Model inference components operate without file write rights, tool-calling permissions, or outbound socket access.
- **Quarantine Hold**: Any item assigned `quarantined = True` by the injection detector cannot be dispatched to an LLM without an explicit, cryptographically logged human override token.
- **Unadjudicated Legal Determinations**: Models cannot assert statutory violations without authoritative judicial rulings cited in evidence (`Rule 10`).
