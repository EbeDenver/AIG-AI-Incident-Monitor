"""Ingestion security, SSRF defense, and connection pinning subsystem.

Governing Charter: Project Constitution (Rules 1, 9, 11, 14, 15, 16),
ADR-008, SEC-002 (Connector Security Model).
"""

from ai_incident_monitor.security.content_limits import (
    DEFAULT_MAX_BYTES,
    DEFAULT_MAX_DECOMPRESSION_RATIO,
    ContentLimits,
)
from ai_incident_monitor.security.dns_validation import (
    BLOCKED_HOSTNAMES,
    BLOCKED_IPV4_RANGES,
    BLOCKED_IPV6_RANGES,
    DNSValidator,
    is_ip_blocked,
    parse_and_normalize_ip,
    validate_ip,
)
from ai_incident_monitor.security.exceptions import (
    BlockedHostnameError,
    BlockedIPError,
    DecompressionBombError,
    DNSRebindingDetectedError,
    DNSResolutionError,
    InvalidURLError,
    MaxRedirectsExceededError,
    PayloadTooLargeError,
    ProtocolDowngradeError,
    SecurityError,
    SNIVerificationError,
    SSRFError,
)
from ai_incident_monitor.security.envelope import (
    DEFAULT_MAX_ENVELOPE_CHARS,
    ENVELOPE_SCHEMA_VERSION,
    TRUST_LEVEL_EXTERNAL,
    UntrustedSourceContentEnvelope,
    create_untrusted_envelope,
)
from ai_incident_monitor.security.injection_detector import (
    CODE_CONTROL_CHARS,
    CODE_EXEC_TOOL,
    CODE_HTML_HIDING,
    CODE_OBFUSCATION,
    CODE_OVERRIDE_INSTRUCTION,
    CODE_REVEAL_SECRET,
    CODE_ROLE_CONFUSION,
    HIGH_RISK_SIGNAL_CODES,
    InjectionDetectionResult,
    detect_prompt_injection_signals,
)
from ai_incident_monitor.security.llm_contract import (
    FORBIDDEN_AUTOMATED_ACTIONS,
    LLMBoundaryViolationError,
    PrivilegedActionBlockedError,
    QuarantinedContentError,
    StaticPromptTemplate,
    assert_privileged_action_forbidden,
    validate_envelope_for_model_ingestion,
)
from ai_incident_monitor.security.redirects import (
    DEFAULT_MAX_REDIRECTS,
    RedirectHop,
    RedirectInspector,
)
from ai_incident_monitor.security.sanitizer import (
    SanitizationResult,
    neutralize_formula_injection,
    normalize_unicode_and_control_chars,
    safe_log_snippet,
    sanitize_feed_text,
    strip_html_safely,
)
from ai_incident_monitor.security.ssrf import (
    PinnedHTTPConnection,
    PinnedHTTPSConnection,
    SecureHTTPClient,
    SecureHTTPResponse,
)
from ai_incident_monitor.security.url_policy import NormalizedURL, URLPolicy
from ai_incident_monitor.security.xml_containment import (
    DEFAULT_MAX_TEXT_FIELD_CHARS,
    DEFAULT_MAX_TOTAL_NORMALIZED_CHARS,
    DEFAULT_MAX_URL_CHARS,
    DEFAULT_MAX_XML_ATTRIBUTES_PER_ELEMENT,
    DEFAULT_MAX_XML_BYTES,
    DEFAULT_MAX_XML_ELEMENT_COUNT,
    DEFAULT_MAX_XML_NESTING_DEPTH,
    XMLParseProfile,
    XMLResourceLimitExceededError,
    XMLSecurityViolationError,
    XMLValidationResult,
    inspect_xml_structure_and_bounds,
)

__all__ = [
    # Exceptions
    "SecurityError",
    "SSRFError",
    "InvalidURLError",
    "BlockedIPError",
    "BlockedHostnameError",
    "DNSResolutionError",
    "DNSRebindingDetectedError",
    "SNIVerificationError",
    "MaxRedirectsExceededError",
    "ProtocolDowngradeError",
    "PayloadTooLargeError",
    "DecompressionBombError",
    "XMLResourceLimitExceededError",
    "XMLSecurityViolationError",
    "LLMBoundaryViolationError",
    "QuarantinedContentError",
    "PrivilegedActionBlockedError",
    # DNS Validation & IP Blocklist
    "BLOCKED_IPV4_RANGES",
    "BLOCKED_IPV6_RANGES",
    "BLOCKED_HOSTNAMES",
    "DNSValidator",
    "is_ip_blocked",
    "validate_ip",
    "parse_and_normalize_ip",
    # URL Policy
    "NormalizedURL",
    "URLPolicy",
    # Redirects
    "DEFAULT_MAX_REDIRECTS",
    "RedirectHop",
    "RedirectInspector",
    # Content Limits
    "DEFAULT_MAX_BYTES",
    "DEFAULT_MAX_DECOMPRESSION_RATIO",
    "ContentLimits",
    # SSRF & Connection Pinning
    "PinnedHTTPConnection",
    "PinnedHTTPSConnection",
    "SecureHTTPClient",
    "SecureHTTPResponse",
    # Untrusted Content Envelope
    "UntrustedSourceContentEnvelope",
    "create_untrusted_envelope",
    "DEFAULT_MAX_ENVELOPE_CHARS",
    "ENVELOPE_SCHEMA_VERSION",
    "TRUST_LEVEL_EXTERNAL",
    # Sanitization & Normalization
    "SanitizationResult",
    "strip_html_safely",
    "normalize_unicode_and_control_chars",
    "neutralize_formula_injection",
    "sanitize_feed_text",
    "safe_log_snippet",
    # Injection Detection
    "detect_prompt_injection_signals",
    "InjectionDetectionResult",
    "CODE_OVERRIDE_INSTRUCTION",
    "CODE_REVEAL_SECRET",
    "CODE_EXEC_TOOL",
    "CODE_OBFUSCATION",
    "CODE_CONTROL_CHARS",
    "CODE_HTML_HIDING",
    "CODE_ROLE_CONFUSION",
    "HIGH_RISK_SIGNAL_CODES",
    # XML Containment & Resource Bounds
    "XMLParseProfile",
    "XMLValidationResult",
    "inspect_xml_structure_and_bounds",
    "DEFAULT_MAX_XML_BYTES",
    "DEFAULT_MAX_XML_NESTING_DEPTH",
    "DEFAULT_MAX_XML_ELEMENT_COUNT",
    "DEFAULT_MAX_XML_ATTRIBUTES_PER_ELEMENT",
    "DEFAULT_MAX_TEXT_FIELD_CHARS",
    "DEFAULT_MAX_URL_CHARS",
    "DEFAULT_MAX_TOTAL_NORMALIZED_CHARS",
    # Future LLM Boundary Contract
    "FORBIDDEN_AUTOMATED_ACTIONS",
    "StaticPromptTemplate",
    "validate_envelope_for_model_ingestion",
    "assert_privileged_action_forbidden",
]
