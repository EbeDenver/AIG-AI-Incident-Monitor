"""Cryptographic provenance manifests and sequential hash-chain verification.

Governing Charter: Project Constitution (Rules 1, 4, 11, 14, 15, 16),
ADR-008, ADR-010, SRC-002, AUD-004, DEC-P4-002, DEC-P4-004.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Optional
import uuid


class ManifestRunStatus(str, Enum):
    """Categorical status of an ingestion run represented by a manifest."""

    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    PURGED = "PURGED"
    VERIFIED = "VERIFIED"
    SUPERSEDED = "SUPERSEDED"
    CORRECTION = "CORRECTION"


DEFAULT_CHAIN_SCOPE = "global_environment_default"
MANIFEST_SCHEMA_VERSION = "1.0.0"


def canonical_json_dumps(data: Any) -> str:
    """Serialize data to a deterministic, canonical JSON string.

    Specifications:
    - Deterministic key ordering (sort_keys=True)
    - No insignificant whitespace (separators=(',', ':'))
    - Unicode characters preserved (ensure_ascii=False)
    - UTF-8 encoding standard
    """
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_json_bytes(data: Any) -> bytes:
    """Return UTF-8 encoded bytes of canonical JSON representation."""
    return canonical_json_dumps(data).encode("utf-8")


def normalize_iso_utc(dt: datetime | str | None) -> str:
    """Normalize timestamp to canonical UTC ISO 8601 string format."""
    if dt is None:
        return datetime.now(timezone.utc).isoformat()
    if isinstance(dt, str):
        # Verify parseability and ensure UTC representation
        try:
            parsed = datetime.fromisoformat(dt.replace("Z", "+00:00"))
            return parsed.astimezone(timezone.utc).isoformat()
        except ValueError:
            return dt
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    return str(dt)


@dataclass(frozen=True)
class IngestionManifest:
    """Authoritative, tamper-evident cryptographic record for an ingestion run.

    Constitutional Primacy:
    - Never mutated after finalization.
    - Sequentially chained via previous_manifest_sha256.
    - Zero raw article text or secret material contained in manifest.
    - Application-level audit chain: DBA with direct write access could alter,
      so external anchoring remains a future planned extension.
    """

    manifest_id: str
    schema_version: str
    environment: str
    chain_scope: str
    ingestion_run_id: str
    run_status: ManifestRunStatus
    connector_id: str
    connector_version: str
    connector_policy_version: str
    parser_version: str
    build_identifier: str
    started_at: str
    finalized_at: str
    approved_source_host: str
    source_url: str
    final_url: str
    redirect_chain_summary: list[dict[str, Any]]
    request_method: str
    http_status: str | int
    content_type: str
    response_bytes: int
    response_sha256: str
    staged_payload_ref: dict[str, Any]
    parse_status: str
    parser_warning_codes: list[str]
    normalized_record_ids: list[str]
    normalized_record_count: int
    duplicate_summary: dict[str, int]
    retry_summary: dict[str, Any]
    validation_warning_codes: list[str]
    previous_manifest_sha256: Optional[str]
    manifest_sha256: str

    def to_canonical_dict(self, include_hash: bool = False) -> dict[str, Any]:
        """Convert manifest to deterministic dictionary for canonical serialization.

        Args:
            include_hash: If True, includes 'manifest_sha256' (for export/storage).
                         If False, excludes 'manifest_sha256' (for computing hash).
        """
        payload: dict[str, Any] = {
            "approved_source_host": self.approved_source_host,
            "build_identifier": self.build_identifier,
            "chain_scope": self.chain_scope,
            "connector_id": self.connector_id,
            "connector_policy_version": self.connector_policy_version,
            "connector_version": self.connector_version,
            "content_type": self.content_type,
            "duplicate_summary": dict(sorted(self.duplicate_summary.items())),
            "environment": self.environment,
            "final_url": self.final_url,
            "finalized_at": self.finalized_at,
            "http_status": self.http_status,
            "ingestion_run_id": self.ingestion_run_id,
            "manifest_id": self.manifest_id,
            "normalized_record_count": self.normalized_record_count,
            "normalized_record_ids": sorted(self.normalized_record_ids),
            "parse_status": self.parse_status,
            "parser_version": self.parser_version,
            "parser_warning_codes": sorted(self.parser_warning_codes),
            "previous_manifest_sha256": self.previous_manifest_sha256,
            "redirect_chain_summary": self.redirect_chain_summary,
            "request_method": self.request_method,
            "response_bytes": self.response_bytes,
            "response_sha256": self.response_sha256,
            "retry_summary": dict(sorted(self.retry_summary.items())),
            "run_status": self.run_status.value if isinstance(self.run_status, ManifestRunStatus) else str(self.run_status),
            "schema_version": self.schema_version,
            "source_url": self.source_url,
            "staged_payload_ref": dict(sorted(self.staged_payload_ref.items())),
            "started_at": self.started_at,
            "validation_warning_codes": sorted(self.validation_warning_codes),
        }
        if include_hash:
            payload["manifest_sha256"] = self.manifest_sha256
        return payload

    def compute_sha256(self) -> str:
        """Compute SHA-256 digest over the canonical manifest payload without hash."""
        canonical_bytes = canonical_json_bytes(self.to_canonical_dict(include_hash=False))
        return hashlib.sha256(canonical_bytes).hexdigest()

    def verify_self_hash(self) -> bool:
        """Verify that the stored manifest_sha256 matches computed hash."""
        return self.compute_sha256() == self.manifest_sha256


class ManifestBuilder:
    """Builder class for constructing finalized, tamper-evident IngestionManifests."""

    def __init__(
        self,
        *,
        environment: str = "development",
        chain_scope: str = DEFAULT_CHAIN_SCOPE,
        build_identifier: str = "unknown",
        schema_version: str = MANIFEST_SCHEMA_VERSION,
    ) -> None:
        self.manifest_id: str = f"man_{uuid.uuid4().hex[:16]}"
        self.schema_version = schema_version
        self.environment = environment
        self.chain_scope = chain_scope
        self.ingestion_run_id: str = f"run_{uuid.uuid4().hex[:12]}"
        self.run_status: ManifestRunStatus = ManifestRunStatus.STARTED
        self.connector_id: str = "unknown"
        self.connector_version: str = "1.0.0"
        self.connector_policy_version: str = "1.0.0"
        self.parser_version: str = "1.0.0"
        self.build_identifier = build_identifier
        self.started_at: str = datetime.now(timezone.utc).isoformat()
        self.finalized_at: str = datetime.now(timezone.utc).isoformat()
        self.approved_source_host: str = ""
        self.source_url: str = ""
        self.final_url: str = ""
        self.redirect_chain_summary: list[dict[str, Any]] = []
        self.request_method: str = "GET"
        self.http_status: str | int = 0
        self.content_type: str = "unknown"
        self.response_bytes: int = 0
        self.response_sha256: str = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"  # empty sha256
        self.staged_payload_ref: dict[str, Any] = {}
        self.parse_status: str = "PENDING"
        self.parser_warning_codes: list[str] = []
        self.normalized_record_ids: list[str] = []
        self.normalized_record_count: int = 0
        self.duplicate_summary: dict[str, int] = {
            "tier_1_matches": 0,
            "tier_2_matches": 0,
            "tier_3_candidates": 0,
            "tier_4_distinct": 0,
        }
        self.retry_summary: dict[str, Any] = {
            "attempts": 1,
            "cumulative_wait_seconds": 0.0,
            "retried": False,
        }
        self.validation_warning_codes: list[str] = []
        self.previous_manifest_sha256: Optional[str] = None

    def finalize(self, previous_manifest_sha256: Optional[str]) -> IngestionManifest:
        """Finalize and seal the manifest with cryptographic hash chaining."""
        self.finalized_at = datetime.now(timezone.utc).isoformat()
        self.previous_manifest_sha256 = previous_manifest_sha256

        # Construct temporary manifest to compute canonical hash
        temp_manifest = IngestionManifest(
            manifest_id=self.manifest_id,
            schema_version=self.schema_version,
            environment=self.environment,
            chain_scope=self.chain_scope,
            ingestion_run_id=self.ingestion_run_id,
            run_status=self.run_status,
            connector_id=self.connector_id,
            connector_version=self.connector_version,
            connector_policy_version=self.connector_policy_version,
            parser_version=self.parser_version,
            build_identifier=self.build_identifier,
            started_at=self.started_at,
            finalized_at=self.finalized_at,
            approved_source_host=self.approved_source_host,
            source_url=self.source_url,
            final_url=self.final_url,
            redirect_chain_summary=self.redirect_chain_summary,
            request_method=self.request_method,
            http_status=self.http_status,
            content_type=self.content_type,
            response_bytes=self.response_bytes,
            response_sha256=self.response_sha256,
            staged_payload_ref=self.staged_payload_ref,
            parse_status=self.parse_status,
            parser_warning_codes=self.parser_warning_codes,
            normalized_record_ids=self.normalized_record_ids,
            normalized_record_count=len(self.normalized_record_ids),
            duplicate_summary=self.duplicate_summary,
            retry_summary=self.retry_summary,
            validation_warning_codes=self.validation_warning_codes,
            previous_manifest_sha256=previous_manifest_sha256,
            manifest_sha256="",
        )
        calculated_sha = temp_manifest.compute_sha256()

        return IngestionManifest(
            manifest_id=temp_manifest.manifest_id,
            schema_version=temp_manifest.schema_version,
            environment=temp_manifest.environment,
            chain_scope=temp_manifest.chain_scope,
            ingestion_run_id=temp_manifest.ingestion_run_id,
            run_status=temp_manifest.run_status,
            connector_id=temp_manifest.connector_id,
            connector_version=temp_manifest.connector_version,
            connector_policy_version=temp_manifest.connector_policy_version,
            parser_version=temp_manifest.parser_version,
            build_identifier=temp_manifest.build_identifier,
            started_at=temp_manifest.started_at,
            finalized_at=temp_manifest.finalized_at,
            approved_source_host=temp_manifest.approved_source_host,
            source_url=temp_manifest.source_url,
            final_url=temp_manifest.final_url,
            redirect_chain_summary=temp_manifest.redirect_chain_summary,
            request_method=temp_manifest.request_method,
            http_status=temp_manifest.http_status,
            content_type=temp_manifest.content_type,
            response_bytes=temp_manifest.response_bytes,
            response_sha256=temp_manifest.response_sha256,
            staged_payload_ref=temp_manifest.staged_payload_ref,
            parse_status=temp_manifest.parse_status,
            parser_warning_codes=temp_manifest.parser_warning_codes,
            normalized_record_ids=temp_manifest.normalized_record_ids,
            normalized_record_count=temp_manifest.normalized_record_count,
            duplicate_summary=temp_manifest.duplicate_summary,
            retry_summary=temp_manifest.retry_summary,
            validation_warning_codes=temp_manifest.validation_warning_codes,
            previous_manifest_sha256=previous_manifest_sha256,
            manifest_sha256=calculated_sha,
        )


class ManifestStorageError(Exception):
    """Raised when an operation on the manifest store fails."""


class ManifestForkError(ManifestStorageError):
    """Raised when an append would fork an existing hash chain."""


class ManifestChainStore:
    """Persistent storage for sequential IngestionManifest hash chains.

    Supports append-only JSONL files or in-memory lists, partitioned by chain_scope.
    """

    def __init__(self, storage_dir: Optional[Path] = None) -> None:
        if storage_dir is None:
            # Default to .data/manifests/
            repo_root = Path(os.environ.get("REPO_ROOT", "."))
            self.storage_dir = repo_root / ".data" / "manifests"
        else:
            self.storage_dir = storage_dir

        self._in_memory_chains: dict[str, list[IngestionManifest]] = {}

    def _get_chain_file(self, chain_scope: str) -> Path:
        clean_scope = "".join(c for c in chain_scope if c.isalnum() or c in ("-", "_"))
        return self.storage_dir / f"chain_{clean_scope}.jsonl"

    def get_latest_manifest(self, chain_scope: str = DEFAULT_CHAIN_SCOPE) -> Optional[IngestionManifest]:
        """Retrieve the most recently appended manifest in the specified scope."""
        chain = self.get_chain(chain_scope)
        return chain[-1] if chain else None

    def get_chain(self, chain_scope: str = DEFAULT_CHAIN_SCOPE) -> list[IngestionManifest]:
        """Retrieve the full sequence of manifests for a given chain scope."""
        # 1. Check in-memory store
        if chain_scope in self._in_memory_chains and self._in_memory_chains[chain_scope]:
            return list(self._in_memory_chains[chain_scope])

        # 2. Check JSONL file on disk
        chain_file = self._get_chain_file(chain_scope)
        if not chain_file.exists():
            return []

        manifests: list[IngestionManifest] = []
        with open(chain_file, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                clean_line = line.strip()
                if not clean_line:
                    continue
                try:
                    data = json.loads(clean_line)
                    manifest = IngestionManifest(
                        manifest_id=data["manifest_id"],
                        schema_version=data["schema_version"],
                        environment=data["environment"],
                        chain_scope=data["chain_scope"],
                        ingestion_run_id=data["ingestion_run_id"],
                        run_status=ManifestRunStatus(data["run_status"]),
                        connector_id=data["connector_id"],
                        connector_version=data["connector_version"],
                        connector_policy_version=data["connector_policy_version"],
                        parser_version=data["parser_version"],
                        build_identifier=data["build_identifier"],
                        started_at=data["started_at"],
                        finalized_at=data["finalized_at"],
                        approved_source_host=data["approved_source_host"],
                        source_url=data["source_url"],
                        final_url=data["final_url"],
                        redirect_chain_summary=data.get("redirect_chain_summary", []),
                        request_method=data["request_method"],
                        http_status=data["http_status"],
                        content_type=data["content_type"],
                        response_bytes=data["response_bytes"],
                        response_sha256=data["response_sha256"],
                        staged_payload_ref=data.get("staged_payload_ref", {}),
                        parse_status=data["parse_status"],
                        parser_warning_codes=data.get("parser_warning_codes", []),
                        normalized_record_ids=data.get("normalized_record_ids", []),
                        normalized_record_count=data["normalized_record_count"],
                        duplicate_summary=data.get("duplicate_summary", {}),
                        retry_summary=data.get("retry_summary", {}),
                        validation_warning_codes=data.get("validation_warning_codes", []),
                        previous_manifest_sha256=data.get("previous_manifest_sha256"),
                        manifest_sha256=data["manifest_sha256"],
                    )
                    manifests.append(manifest)
                except Exception as e:
                    raise ManifestStorageError(f"Error parsing manifest line {line_no} in {chain_file}: {e}") from e

        return manifests

    def append_manifest(self, manifest: IngestionManifest) -> None:
        """Append a newly finalized manifest to the chain after verifying linkage.

        Enforces:
        - Genesis manifest has previous_manifest_sha256 = None (if chain is empty)
        - Sequential manifest must link to latest manifest's manifest_sha256
        - No self-referencing manifests
        - No forking of existing chains
        """
        chain_scope = manifest.chain_scope
        latest = self.get_latest_manifest(chain_scope)

        if latest is None:
            # Genesis manifest
            if manifest.previous_manifest_sha256 is not None:
                raise ManifestStorageError(
                    f"Genesis manifest for scope '{chain_scope}' must have previous_manifest_sha256=None"
                )
        else:
            # Sequential manifest
            if manifest.previous_manifest_sha256 != latest.manifest_sha256:
                raise ManifestForkError(
                    f"Chain linkage error for scope '{chain_scope}': expected previous_manifest_sha256="
                    f"'{latest.manifest_sha256}', but got '{manifest.previous_manifest_sha256}'"
                )

        if manifest.previous_manifest_sha256 == manifest.manifest_sha256:
            raise ManifestStorageError("Self-referential manifest detected: previous hash equals self hash")

        # In-memory append
        if chain_scope not in self._in_memory_chains:
            self._in_memory_chains[chain_scope] = []
        self._in_memory_chains[chain_scope].append(manifest)

        # File append
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        chain_file = self._get_chain_file(chain_scope)
        canonical_line = canonical_json_dumps(manifest.to_canonical_dict(include_hash=True))
        with open(chain_file, "a", encoding="utf-8") as f:
            f.write(canonical_line + "\n")


@dataclass
class AnomalyRecord:
    """Record of an anomaly or discrepancy detected during chain verification."""

    manifest_id: str
    manifest_index: int
    anomaly_type: str
    description: str
    expected_value: Optional[str] = None
    actual_value: Optional[str] = None


@dataclass
class VerificationReport:
    """Safe, redacted verification report for an ingestion provenance chain."""

    chain_scope: str
    total_manifests: int
    is_valid: bool
    verified_at_utc: str
    genesis_manifest_id: Optional[str] = None
    head_manifest_id: Optional[str] = None
    head_manifest_sha256: Optional[str] = None
    anomalies: list[AnomalyRecord] = field(default_factory=list)

    def to_safe_summary_dict(self) -> dict[str, Any]:
        """Produce safe summary dictionary excluding sensitive internal details."""
        return {
            "chain_scope": self.chain_scope,
            "total_manifests": self.total_manifests,
            "is_valid": self.is_valid,
            "verified_at_utc": self.verified_at_utc,
            "genesis_manifest_id": self.genesis_manifest_id,
            "head_manifest_id": self.head_manifest_id,
            "head_manifest_sha256": self.head_manifest_sha256,
            "anomaly_count": len(self.anomalies),
            "anomalies": [
                {
                    "manifest_id": a.manifest_id,
                    "index": a.manifest_index,
                    "type": a.anomaly_type,
                    "description": a.description,
                }
                for a in self.anomalies
            ],
        }


def verify_provenance_chain(
    chain: list[IngestionManifest],
    chain_scope: str = DEFAULT_CHAIN_SCOPE,
    dry_run: bool = False,
) -> VerificationReport:
    """Audit and verify the integrity of an IngestionManifest hash chain.

    Checks:
    1. Canonical serialization validity.
    2. Computed SHA-256 matches manifest_sha256.
    3. Sequential hash linkage (manifest[N].previous == manifest[N-1].hash).
    4. Genesis manifest has previous = None.
    5. Zero self-references (previous != self).
    6. Monotonic timestamps (finalized >= started).
    7. Schema version compatibility.

    Returns:
        VerificationReport with is_valid=True if all checks pass.
    """
    now_utc = datetime.now(timezone.utc).isoformat()
    if not chain:
        return VerificationReport(
            chain_scope=chain_scope,
            total_manifests=0,
            is_valid=True,
            verified_at_utc=now_utc,
            genesis_manifest_id=None,
            head_manifest_id=None,
            head_manifest_sha256=None,
            anomalies=[],
        )

    anomalies: list[AnomalyRecord] = []
    seen_ids: set[str] = set()
    seen_hashes: set[str] = set()

    for idx, manifest in enumerate(chain):
        # 1. Duplicate Manifest ID check
        if manifest.manifest_id in seen_ids:
            anomalies.append(
                AnomalyRecord(
                    manifest_id=manifest.manifest_id,
                    manifest_index=idx,
                    anomaly_type="DUPLICATE_MANIFEST_ID",
                    description=f"Manifest ID '{manifest.manifest_id}' appeared more than once in chain",
                )
            )
        seen_ids.add(manifest.manifest_id)

        # 2. Schema version check
        if manifest.schema_version != MANIFEST_SCHEMA_VERSION:
            anomalies.append(
                AnomalyRecord(
                    manifest_id=manifest.manifest_id,
                    manifest_index=idx,
                    anomaly_type="SCHEMA_VERSION_MISMATCH",
                    description=f"Unsupported schema version: '{manifest.schema_version}'",
                    expected_value=MANIFEST_SCHEMA_VERSION,
                    actual_value=manifest.schema_version,
                )
            )

        # 3. Canonical Hash Integrity check
        computed_sha = manifest.compute_sha256()
        if computed_sha != manifest.manifest_sha256:
            anomalies.append(
                AnomalyRecord(
                    manifest_id=manifest.manifest_id,
                    manifest_index=idx,
                    anomaly_type="ALTERED_MANIFEST_HASH",
                    description="Computed canonical SHA-256 does not match stored manifest_sha256",
                    expected_value=computed_sha,
                    actual_value=manifest.manifest_sha256,
                )
            )

        # 4. Self-link check
        if manifest.previous_manifest_sha256 == manifest.manifest_sha256:
            anomalies.append(
                AnomalyRecord(
                    manifest_id=manifest.manifest_id,
                    manifest_index=idx,
                    anomaly_type="SELF_LINK_DETECTED",
                    description="Manifest previous_manifest_sha256 points to its own manifest_sha256",
                )
            )

        # 5. Linkage verification
        if idx == 0:
            if manifest.previous_manifest_sha256 is not None:
                anomalies.append(
                    AnomalyRecord(
                        manifest_id=manifest.manifest_id,
                        manifest_index=idx,
                        anomaly_type="GENESIS_PREVIOUS_HASH_NOT_NULL",
                        description="Genesis manifest must have previous_manifest_sha256=None",
                        expected_value=None,
                        actual_value=manifest.previous_manifest_sha256,
                    )
                )
        else:
            prev_manifest = chain[idx - 1]
            if manifest.previous_manifest_sha256 != prev_manifest.manifest_sha256:
                anomalies.append(
                    AnomalyRecord(
                        manifest_id=manifest.manifest_id,
                        manifest_index=idx,
                        anomaly_type="BROKEN_CHAIN_LINKAGE",
                        description=f"Linkage broken at index {idx}: expected previous hash from index {idx-1}",
                        expected_value=prev_manifest.manifest_sha256,
                        actual_value=manifest.previous_manifest_sha256,
                    )
                )

        # 6. Timestamp monotonicity check
        try:
            started = datetime.fromisoformat(manifest.started_at.replace("Z", "+00:00"))
            finalized = datetime.fromisoformat(manifest.finalized_at.replace("Z", "+00:00"))
            if finalized < started:
                anomalies.append(
                    AnomalyRecord(
                        manifest_id=manifest.manifest_id,
                        manifest_index=idx,
                        anomaly_type="TIMESTAMP_ANOMALY",
                        description=f"finalized_at ({manifest.finalized_at}) is earlier than started_at ({manifest.started_at})",
                    )
                )
        except Exception as e:
            anomalies.append(
                AnomalyRecord(
                    manifest_id=manifest.manifest_id,
                    manifest_index=idx,
                    anomaly_type="INVALID_TIMESTAMP_FORMAT",
                    description=f"Timestamp parsing error: {e}",
                )
            )

        seen_hashes.add(manifest.manifest_sha256)

    is_valid = len(anomalies) == 0
    return VerificationReport(
        chain_scope=chain_scope,
        total_manifests=len(chain),
        is_valid=is_valid,
        verified_at_utc=now_utc,
        genesis_manifest_id=chain[0].manifest_id if chain else None,
        head_manifest_id=chain[-1].manifest_id if chain else None,
        head_manifest_sha256=chain[-1].manifest_sha256 if chain else None,
        anomalies=anomalies,
    )
