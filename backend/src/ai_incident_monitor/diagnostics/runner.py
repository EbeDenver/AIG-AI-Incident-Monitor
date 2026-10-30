"""Safe, read-only operational diagnostics runner for AI Incident Monitor.

Governing Charter: Project Constitution (Rules 1, 10, 11, 14, 16),
PRD §5 (TST-001, AUD-004), Phase 7B Plan.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any, Optional

from sqlalchemy import Engine, inspect, text

from ai_incident_monitor.db.session import get_database_url, get_engine, get_repo_root
from ai_incident_monitor.diagnostics.enums import CheckCategory, CheckStatus
from ai_incident_monitor.diagnostics.models import DiagnosticCheckResult, DiagnosticReport
from ai_incident_monitor.editorial.renderers import (
    DEFAULT_EXPORT_DIR,
    EditorialJSONRenderer,
    EditorialMarkdownRenderer,
)
from ai_incident_monitor.editorial.validator import EditorialValidator
from ai_incident_monitor.governance.engine import GovernanceMappingEngine
from ai_incident_monitor.governance.reference_loader import compute_file_sha256
from ai_incident_monitor.scoring.engine import calculate_aig_isi_assessment

CORE_SCHEMA_TABLES = [
    "incidents",
    "evidence_records",
    "claim_records",
    "source_references",
    "editorial_dossiers",
    "framework_reference_sets",
    "governance_audit_logs",
]


class LocalDiagnosticsRunner:
    """Executes safe, non-mutating operational diagnostic checks across local subsystems."""

    def __init__(
        self,
        engine: Optional[Engine] = None,
        repo_root: Optional[Path] = None,
        export_dir: Optional[Path] = None,
        staging_dir: Optional[Path] = None,
    ) -> None:
        self.repo_root = repo_root or get_repo_root()
        self._custom_engine = engine
        self.export_dir = export_dir or (self.repo_root / DEFAULT_EXPORT_DIR)
        self.staging_dir = staging_dir or (self.repo_root / ".data" / "raw_feeds")

    def run_all_checks(self) -> DiagnosticReport:
        """Execute all 6 diagnostic checks and synthesize the overall health report."""
        checks: list[DiagnosticCheckResult] = []

        checks.append(self.check_configuration())
        checks.append(self.check_database_connectivity())
        checks.append(self.check_schema_compatibility())
        checks.append(self.check_reference_library())
        checks.append(self.check_storage_paths())
        checks.append(self.check_pipeline_components())

        # Determine overall status and exit code
        if any(c.status == CheckStatus.UNHEALTHY for c in checks):
            overall_status = CheckStatus.UNHEALTHY
            exit_code = 2
        elif any(c.status == CheckStatus.DEGRADED for c in checks):
            overall_status = CheckStatus.DEGRADED
            exit_code = 1
        else:
            overall_status = CheckStatus.HEALTHY
            exit_code = 0

        return DiagnosticReport(
            evaluated_at_utc=datetime.now(timezone.utc),
            overall_status=overall_status,
            exit_code=exit_code,
            checks=checks,
        )

    def check_configuration(self) -> DiagnosticCheckResult:
        """Check presence of required runtime configuration without exposing credentials."""
        try:
            db_url = get_database_url()
            # Mask credentials if present (e.g. postgres://user:pass@host/db -> postgres://user:***@host/db)
            masked_url = re.sub(r"://([^:@]+):([^@]+)@", r"://\1:***@", db_url)
            driver = db_url.split("://")[0]

            return DiagnosticCheckResult(
                name="Configuration Presence",
                category=CheckCategory.CONFIGURATION,
                status=CheckStatus.HEALTHY,
                reason_code="CONFIG_VALID",
                message="Runtime configuration resolved successfully with masked connection parameters.",
                details={"database_driver": driver, "database_url_masked": masked_url},
            )
        except Exception as exc:
            return DiagnosticCheckResult(
                name="Configuration Presence",
                category=CheckCategory.CONFIGURATION,
                status=CheckStatus.UNHEALTHY,
                reason_code="CONFIG_ERROR",
                message=f"Runtime configuration resolution failed: {exc}",
                details={"error": type(exc).__name__},
            )

    def check_database_connectivity(self) -> DiagnosticCheckResult:
        """Execute a read-only query (SELECT 1) to verify database connectivity."""
        try:
            engine = self._custom_engine or get_engine()
            with engine.connect() as conn:
                res = conn.execute(text("SELECT 1")).scalar()
                if res != 1:
                    return DiagnosticCheckResult(
                        name="Database Connectivity",
                        category=CheckCategory.DATABASE,
                        status=CheckStatus.UNHEALTHY,
                        reason_code="UNEXPECTED_PING_RESULT",
                        message=f"Read-only ping query returned unexpected scalar: {res}",
                    )
            return DiagnosticCheckResult(
                name="Database Connectivity",
                category=CheckCategory.DATABASE,
                status=CheckStatus.HEALTHY,
                reason_code="DB_CONNECTED",
                message="Database connectivity verified via read-only ping query (SELECT 1).",
            )
        except Exception as exc:
            return DiagnosticCheckResult(
                name="Database Connectivity",
                category=CheckCategory.DATABASE,
                status=CheckStatus.UNHEALTHY,
                reason_code="DB_CONNECTION_FAILED",
                message=f"Database connection failed: {exc}",
                details={"error": type(exc).__name__},
            )

    def check_schema_compatibility(self) -> DiagnosticCheckResult:
        """Verify presence of core relational schema tables without executing migrations."""
        try:
            engine = self._custom_engine or get_engine()
            inspector = inspect(engine)
            existing_tables = set(inspector.get_table_names())

            missing = [t for t in CORE_SCHEMA_TABLES if t not in existing_tables]
            if missing:
                return DiagnosticCheckResult(
                    name="Schema Compatibility",
                    category=CheckCategory.SCHEMA,
                    status=CheckStatus.UNHEALTHY,
                    reason_code="SCHEMA_TABLES_MISSING",
                    message=(
                        f"Database schema is incomplete; missing required tables: {', '.join(missing)}. "
                        "Run 'make migrate' to upgrade schema to head."
                    ),
                    details={"missing_tables": missing, "existing_tables": sorted(list(existing_tables))},
                )

            return DiagnosticCheckResult(
                name="Schema Compatibility",
                category=CheckCategory.SCHEMA,
                status=CheckStatus.HEALTHY,
                reason_code="SCHEMA_COMPATIBLE",
                message=f"Relational schema contains all {len(CORE_SCHEMA_TABLES)} required core tables.",
                details={"verified_tables": CORE_SCHEMA_TABLES},
            )
        except Exception as exc:
            return DiagnosticCheckResult(
                name="Schema Compatibility",
                category=CheckCategory.SCHEMA,
                status=CheckStatus.UNHEALTHY,
                reason_code="SCHEMA_INSPECTION_FAILED",
                message=f"Schema inspection failed: {exc}",
                details={"error": type(exc).__name__},
            )

    def check_reference_library(self) -> DiagnosticCheckResult:
        """Validate presence and cryptographic SHA-256 integrity of canonical governance frameworks."""
        manifest_path = self.repo_root / "frameworks" / "manifest.json"
        if not manifest_path.exists():
            return DiagnosticCheckResult(
                name="Reference Library Integrity",
                category=CheckCategory.REFERENCE_LIBRARY,
                status=CheckStatus.UNHEALTHY,
                reason_code="MANIFEST_NOT_FOUND",
                message=f"Framework reference manifest missing at expected path: {manifest_path}",
            )

        try:
            manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
            frameworks = manifest_data.get("frameworks", [])
            if not frameworks:
                return DiagnosticCheckResult(
                    name="Reference Library Integrity",
                    category=CheckCategory.REFERENCE_LIBRARY,
                    status=CheckStatus.UNHEALTHY,
                    reason_code="EMPTY_MANIFEST",
                    message="Framework reference manifest contains zero framework entries.",
                )

            verified_entries: list[str] = []
            mismatches: list[dict[str, str]] = []

            for entry in frameworks:
                rel_path = entry.get("file_path", "")
                expected_sha256 = entry.get("content_sha256", "")
                file_path = self.repo_root / rel_path

                if not file_path.exists():
                    mismatches.append({"file": rel_path, "issue": "FILE_MISSING"})
                    continue

                actual_sha256 = compute_file_sha256(file_path)
                if actual_sha256 != expected_sha256:
                    mismatches.append({
                        "file": rel_path,
                        "issue": "DIGEST_MISMATCH",
                        "expected": expected_sha256[:12] + "...",
                        "actual": actual_sha256[:12] + "...",
                    })
                else:
                    verified_entries.append(entry.get("framework_code", rel_path))

            if mismatches:
                return DiagnosticCheckResult(
                    name="Reference Library Integrity",
                    category=CheckCategory.REFERENCE_LIBRARY,
                    status=CheckStatus.UNHEALTHY,
                    reason_code="REFERENCE_INTEGRITY_VIOLATION",
                    message=f"Framework reference library integrity verification failed for {len(mismatches)} file(s).",
                    details={"mismatches": mismatches},
                )

            return DiagnosticCheckResult(
                name="Reference Library Integrity",
                category=CheckCategory.REFERENCE_LIBRARY,
                status=CheckStatus.HEALTHY,
                reason_code="REFERENCE_LIBRARY_VERIFIED",
                message=f"All {len(verified_entries)} canonical governance frameworks verified with matching SHA-256 digests.",
                details={"verified_frameworks": verified_entries},
            )
        except Exception as exc:
            return DiagnosticCheckResult(
                name="Reference Library Integrity",
                category=CheckCategory.REFERENCE_LIBRARY,
                status=CheckStatus.UNHEALTHY,
                reason_code="REFERENCE_CHECK_FAILED",
                message=f"Reference library verification failed: {exc}",
                details={"error": type(exc).__name__},
            )

    def check_storage_paths(self) -> DiagnosticCheckResult:
        """Non-mutating read/traverse check of local export and staging paths (zero files written)."""
        paths_to_check = {
            "export_dir": self.export_dir,
            "staging_dir": self.staging_dir,
        }
        details: dict[str, Any] = {}
        has_degraded = False

        for name, p in paths_to_check.items():
            if p.exists():
                is_readable = os.access(p, os.R_OK)
                is_writable = os.access(p, os.W_OK)
                if not is_readable or not is_writable:
                    return DiagnosticCheckResult(
                        name="Storage Paths Accessibility",
                        category=CheckCategory.STORAGE_PATHS,
                        status=CheckStatus.UNHEALTHY,
                        reason_code="STORAGE_PATH_INACCESSIBLE",
                        message=f"Storage path '{name}' exists at '{p}' but lacks read/write permissions.",
                        details={"path": str(p), "is_readable": is_readable, "is_writable": is_writable},
                    )
                details[name] = {"path": str(p), "exists": True, "accessible": True}
            else:
                # Directory doesn't exist yet: check if parent directory is writable without creating it!
                parent = p.parent
                if parent.exists() and os.access(parent, os.W_OK):
                    has_degraded = True
                    details[name] = {"path": str(p), "exists": False, "creatable": True}
                else:
                    return DiagnosticCheckResult(
                        name="Storage Paths Accessibility",
                        category=CheckCategory.STORAGE_PATHS,
                        status=CheckStatus.UNHEALTHY,
                        reason_code="STORAGE_PARENT_INACCESSIBLE",
                        message=f"Storage path '{name}' parent directory '{parent}' is inaccessible or non-writable.",
                        details={"path": str(p), "parent": str(parent)},
                    )

        if has_degraded:
            return DiagnosticCheckResult(
                name="Storage Paths Accessibility",
                category=CheckCategory.STORAGE_PATHS,
                status=CheckStatus.DEGRADED,
                reason_code="STORAGE_PATHS_PENDING_INITIALIZATION",
                message="One or more local storage paths do not exist yet, but parent directories are accessible for creation.",
                details=details,
            )

        return DiagnosticCheckResult(
            name="Storage Paths Accessibility",
            category=CheckCategory.STORAGE_PATHS,
            status=CheckStatus.HEALTHY,
            reason_code="STORAGE_PATHS_ACCESSIBLE",
            message="All configured local storage paths exist and have valid read/write permissions.",
            details=details,
        )

    def check_pipeline_components(self) -> DiagnosticCheckResult:
        """Verify that core pure-Python pipeline components can be cleanly instantiated."""
        try:
            assert callable(calculate_aig_isi_assessment)
            _ = EditorialValidator()
            _ = EditorialMarkdownRenderer()
            _ = EditorialJSONRenderer()

            return DiagnosticCheckResult(
                name="Pipeline Components Readiness",
                category=CheckCategory.PIPELINE_COMPONENTS,
                status=CheckStatus.HEALTHY,
                reason_code="COMPONENTS_READY",
                message="Core pipeline scoring, validation, and rendering components initialized successfully.",
                details={"verified_components": [
                    "calculate_aig_isi_assessment",
                    "EditorialValidator",
                    "EditorialMarkdownRenderer",
                    "EditorialJSONRenderer",
                ]},
            )
        except Exception as exc:
            return DiagnosticCheckResult(
                name="Pipeline Components Readiness",
                category=CheckCategory.PIPELINE_COMPONENTS,
                status=CheckStatus.UNHEALTHY,
                reason_code="COMPONENT_INIT_FAILED",
                message=f"Pipeline component initialization failed: {exc}",
                details={"error": type(exc).__name__},
            )
