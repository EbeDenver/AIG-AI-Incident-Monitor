"""Standalone, deterministic reference set loader and manifest verification engine.

Provides zero-dependency pure-Python YAML parsing for framework reference files,
canonical manifest hashing, and cryptographic integrity verification.
"""

from __future__ import annotations

from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Optional

from ai_incident_monitor.governance.models import (
    FrameworkManifestSchema,
    FrameworkReferenceSetSchema,
    ManifestEntrySchema,
)


def compute_file_sha256(path: Path) -> str:
    """Compute the SHA-256 hex digest of raw UTF-8 bytes of a file on disk."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def canonical_json_dumps(obj: Any) -> str:
    """Serialize an object into deterministic canonical JSON (RFC 8785 subset)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_manifest_hash(manifest_dict: dict[str, Any]) -> str:
    """Compute deterministic SHA-256 over canonical JSON representation of manifest."""
    canonical_str = canonical_json_dumps(manifest_dict)
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()


def _parse_scalar(raw_val: str) -> Any:
    """Parse a scalar string into native Python types (str, int, float, bool, None)."""
    val = raw_val.strip()
    if not val:
        return ""
    if val == "null" or val == "~":
        return None
    if val.lower() == "true":
        return True
    if val.lower() == "false":
        return False
    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
        return val[1:-1]
    # Check integer
    if re.match(r"^-?\d+$", val):
        return int(val)
    # Check float
    if re.match(r"^-?\d+\.\d+$", val):
        return float(val)
    return val


def parse_block_yaml(text: str) -> dict[str, Any]:
    """Pure-Python deterministic parser for the subset of block YAML used in framework reference files.

    Handles:
    - Top-level key-values
    - Nested maps and sequences with standard 2-space indentation
    - Multiline folded (>) and literal (|) string blocks
    - Quoted and unquoted strings, numbers, booleans, and nulls
    - Inline and full-line comments (#)
    """
    lines = text.splitlines()
    root: dict[str, Any] = {}
    current_key: Optional[str] = None
    in_controls: bool = False
    current_control: Optional[dict[str, Any]] = None
    controls_list: list[dict[str, Any]] = []

    in_multiline: bool = False
    multiline_style: str = ""  # ">" or "|"
    multiline_buf: list[str] = []
    multiline_target_dict: Optional[dict[str, Any]] = None
    multiline_target_key: Optional[str] = None
    multiline_indent: int = 0

    in_control_metadata: bool = False

    for line_idx, raw_line in enumerate(lines):
        line = raw_line.rstrip()
        stripped = line.strip()

        # Handle multiline scalar collection
        if in_multiline:
            line_indent = len(raw_line) - len(raw_line.lstrip())
            if stripped == "" or line_indent >= multiline_indent:
                # Add content (preserving indentation beyond base indent)
                content = raw_line[multiline_indent:] if len(raw_line) >= multiline_indent else ""
                multiline_buf.append(content)
                continue
            else:
                # End of multiline block
                if multiline_style == ">":
                    # Folded: join with space, single trailing newline stripped
                    joined = " ".join(part.strip() for part in multiline_buf if part.strip())
                else:
                    joined = "\n".join(multiline_buf)
                if multiline_target_dict is not None and multiline_target_key is not None:
                    multiline_target_dict[multiline_target_key] = joined
                in_multiline = False
                multiline_buf = []

        # Skip empty lines and comment lines
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip())

        # Check for multiline indicator start
        if ":" in stripped:
            k, v = stripped.split(":", 1)
            k = k.strip()
            v = v.strip()
            # Strip trailing comments from value if not quoted
            if "#" in v and not (v.startswith('"') or v.startswith("'")):
                v = v.split("#", 1)[0].strip()

            if v in (">", "|"):
                in_multiline = True
                multiline_style = v
                multiline_buf = []
                multiline_target_key = k
                multiline_indent = indent + 2
                if in_controls and current_control is not None:
                    multiline_target_dict = current_control
                else:
                    multiline_target_dict = root
                continue

        # Top level fields (indent == 0)
        if indent == 0:
            in_control_metadata = False
            if current_control is not None:
                controls_list.append(current_control)
                current_control = None

            if ":" in stripped:
                k, v = stripped.split(":", 1)
                k = k.strip()
                v = v.strip()
                if "#" in v and not (v.startswith('"') or v.startswith("'")):
                    v = v.split("#", 1)[0].strip()

                if k == "controls":
                    in_controls = True
                    root["controls"] = controls_list
                else:
                    in_controls = False
                    root[k] = _parse_scalar(v)
            continue

        # Within controls list
        if in_controls:
            # Check for new control list item starting with "- "
            if stripped.startswith("- "):
                in_control_metadata = False
                if current_control is not None:
                    controls_list.append(current_control)
                current_control = {}

                item_content = stripped[2:].strip()
                if ":" in item_content:
                    sub_k, sub_v = item_content.split(":", 1)
                    sub_k = sub_k.strip()
                    sub_v = sub_v.strip()
                    if "#" in sub_v and not (sub_v.startswith('"') or sub_v.startswith("'")):
                        sub_v = sub_v.split("#", 1)[0].strip()
                    current_control[sub_k] = _parse_scalar(sub_v)
                continue

            # Key-values inside current control
            if current_control is not None and ":" in stripped:
                k, v = stripped.split(":", 1)
                k = k.strip()
                v = v.strip()
                if "#" in v and not (v.startswith('"') or v.startswith("'")):
                    v = v.split("#", 1)[0].strip()

                if k == "metadata":
                    in_control_metadata = True
                    current_control.setdefault("metadata", {})
                    continue

                if in_control_metadata and indent >= 6:
                    current_control.setdefault("metadata", {})[k] = _parse_scalar(v)
                else:
                    in_control_metadata = False
                    current_control[k] = _parse_scalar(v)

    # Flush any open multiline block
    if in_multiline and multiline_target_dict is not None and multiline_target_key is not None:
        if multiline_style == ">":
            joined = " ".join(part.strip() for part in multiline_buf if part.strip())
        else:
            joined = "\n".join(multiline_buf)
        multiline_target_dict[multiline_target_key] = joined

    # Flush final control if present
    if current_control is not None and current_control not in controls_list:
        controls_list.append(current_control)

    return root


def load_reference_set(file_path: Path) -> FrameworkReferenceSetSchema:
    """Load, parse, and strictly validate a framework reference YAML file."""
    if not file_path.exists():
        raise FileNotFoundError(f"Reference file not found: {file_path}")

    raw_text = file_path.read_text(encoding="utf-8")
    parsed_data = parse_block_yaml(raw_text)
    return FrameworkReferenceSetSchema.model_validate(parsed_data)


def load_framework_manifest(manifest_path: Path) -> FrameworkManifestSchema:
    """Load and validate the top-level frameworks/manifest.json."""
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest file not found: {manifest_path}")

    raw_text = manifest_path.read_text(encoding="utf-8")
    data = json.loads(raw_text)
    return FrameworkManifestSchema.model_validate(data)


def verify_framework_manifest(
    manifest_path: Path,
    repo_root: Path,
) -> tuple[bool, list[str]]:
    """Cryptographically verify all referenced framework files against the manifest.

    Returns:
        (is_valid, list_of_errors)
    """
    errors: list[str] = []
    try:
        manifest = load_framework_manifest(manifest_path)
    except Exception as exc:
        return False, [f"Manifest validation error: {exc}"]

    for entry in manifest.frameworks:
        target_path = repo_root / entry.file_path
        if not target_path.exists():
            errors.append(f"Referenced file not found: {entry.file_path}")
            continue

        actual_hash = compute_file_sha256(target_path)
        if actual_hash != entry.content_sha256:
            errors.append(
                f"SHA-256 mismatch for {entry.file_path}: "
                f"expected {entry.content_sha256}, got {actual_hash}"
            )
            continue

        # Also strictly validate that the file parses and passes domain schema
        try:
            load_reference_set(target_path)
        except Exception as exc:
            errors.append(f"Schema validation failure for {entry.file_path}: {exc}")

    return len(errors) == 0, errors
