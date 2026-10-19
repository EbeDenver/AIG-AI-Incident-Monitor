"""Manual import batch workflow orchestrating parsing, staging, deduplication, and audit."""

from __future__ import annotations

from pathlib import Path
from typing import Optional
import uuid

from sqlalchemy.orm import Session

from ai_incident_monitor.db.models.claim import ClaimRecordModel
from ai_incident_monitor.db.models.evidence import ClaimEvidenceLinkModel, EvidenceRecordModel
from ai_incident_monitor.db.models.source import SourceReferenceModel
from ai_incident_monitor.deduplication.engine import DeduplicationEngine
from ai_incident_monitor.domain.identifiers import new_evidence_id
from ai_incident_monitor.domain.vocabularies import (
    CorroborationStatus,
    EvidenceDirectness,
    EvidenceSpecificity,
    EvidenceType,
    ReviewStatus,
)
from ai_incident_monitor.importers.base import (
    BaseImporter,
    ImportBatchSummary,
    ImportRecordResult,
    compute_file_sha256,
    stage_raw_upload,
)
from ai_incident_monitor.importers.csv_importer import CSVImporter
from ai_incident_monitor.importers.json_importer import JSONImporter
from ai_incident_monitor.importers.oecd_mapper import OECDIncidentMapper
from ai_incident_monitor.importers.xlsx_importer import XLSXImporter
from ai_incident_monitor.repositories.audit_repo import AuditRepository
from ai_incident_monitor.repositories.claim_repo import ClaimRepository
from ai_incident_monitor.repositories.import_repo import ImportRepository
from ai_incident_monitor.repositories.incident_repo import IncidentRepository
from ai_incident_monitor.repositories.source_repo import SourceRepository


def get_importer_for_format(source_format: str) -> BaseImporter:
    """Instantiate appropriate parser for target format."""
    fmt = source_format.strip().upper()
    if fmt == "CSV":
        return CSVImporter()
    if fmt == "JSON" or fmt == "NDJSON":
        return JSONImporter()
    if fmt == "XLSX" or fmt == "EXCEL":
        return XLSXImporter()
    raise ValueError(f"Unsupported import format: '{source_format}'. Supported: CSV, JSON, XLSX.")


def run_manual_import_workflow(
    session: Session,
    file_path: Path | str,
    source_format: str,
    actor_id: str,
    batch_id: Optional[str] = None,
    demonstration_notice: Optional[str] = None,
) -> ImportBatchSummary:
    """Execute complete end-to-end manual incident import workflow."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Target import file not found: {file_path}")

    fmt = source_format.strip().upper()
    active_batch_id = batch_id or f"BATCH-{uuid.uuid4().hex[:8].upper()}"

    # 1. Cryptographic digest & workspace staging (DEC-P3-002)
    content_hash = compute_file_sha256(path)
    staged_path = stage_raw_upload(path, active_batch_id, path.name)

    # 2. Parse and sanitize input file
    importer = get_importer_for_format(fmt)
    raw_rows = importer.parse_rows(path)

    # Repositories
    import_repo = ImportRepository(session)
    incident_repo = IncidentRepository(session)
    claim_repo = ClaimRepository(session)
    source_repo = SourceRepository(session)
    audit_repo = AuditRepository(session)

    summary = ImportBatchSummary(
        batch_id=active_batch_id,
        filename=path.name,
        source_format=fmt,
        content_hash=content_hash,
        total_rows=len(raw_rows),
        staged_path=str(staged_path),
    )

    # 3. Process each row through the 4-tier deduplication waterfall
    for row_idx, raw_row in enumerate(raw_rows, start=1):
        # A. Preserve raw payload and hash
        raw_rec = import_repo.create_raw_record(
            batch_id=active_batch_id,
            source_filename=path.name,
            source_format=fmt,
            content_hash=content_hash,
            row_index=row_idx,
            raw_payload=raw_row,
            staged_file_path=str(staged_path),
        )

        try:
            # B. Map OECD export row to internal entities
            incident, claims, sources = OECDIncidentMapper.map_row(
                row=raw_row,
                batch_id=active_batch_id,
                demonstration_notice=demonstration_notice,
            )

            source_urls = [s.url for s in sources]

            # C. Evaluate through 4-tier deduplication waterfall (DEC-P3-003)
            decision = DeduplicationEngine.evaluate(
                session=session,
                proposed_incident_id=incident.id,
                proposed_title=incident.title,
                proposed_date=incident.incident_exact_date,
                source_urls=source_urls,
            )

            if decision.outcome in ("AUTO_LINK_ID", "AUTO_LINK_URL"):
                # Tier 1 or 2: Link to existing incident
                import_repo.update_raw_record_status(
                    record_id=raw_rec.id,
                    status="PROCESSED",
                    incident_id=decision.matched_incident_id,
                )
                summary.duplicate_count += 1
                summary.records.append(
                    ImportRecordResult(
                        row_index=row_idx,
                        status="AUTO_LINKED",
                        incident_id=decision.matched_incident_id,
                    )
                )

            elif decision.outcome == "FLAG_FOR_REVIEW":
                # Tier 3: Queue near-duplicate candidate for human review (Rule 14)
                import_repo.create_dedup_candidate(
                    raw_import_id=raw_rec.id,
                    existing_incident_id=decision.matched_incident_id or "UNKNOWN",
                    tier=3,
                    similarity_score=decision.similarity_score,
                    match_rationale=decision.rationale,
                )
                import_repo.update_raw_record_status(
                    record_id=raw_rec.id,
                    status="POTENTIAL_DUPLICATE",
                    incident_id=decision.matched_incident_id,
                )
                summary.duplicate_count += 1
                summary.records.append(
                    ImportRecordResult(
                        row_index=row_idx,
                        status="POTENTIAL_DUPLICATE",
                        incident_id=decision.matched_incident_id,
                    )
                )

            else:
                # Tier 4: Distinct incident -> Persist new dossier
                incident_repo.create(incident)

                for src in sources:
                    source_repo.create(src)

                for clm in claims:
                    claim_repo.create(clm)

                import_repo.update_raw_record_status(
                    record_id=raw_rec.id,
                    status="IMPORTED",
                    incident_id=incident.id,
                )
                summary.imported_count += 1
                summary.records.append(
                    ImportRecordResult(
                        row_index=row_idx,
                        status="IMPORTED",
                        incident_id=incident.id,
                    )
                )

        except Exception as exc:
            import_repo.update_raw_record_status(
                record_id=raw_rec.id,
                status="ERROR",
                error_message=str(exc),
            )
            summary.error_count += 1
            summary.records.append(
                ImportRecordResult(
                    row_index=row_idx,
                    status="ERROR",
                    error=str(exc),
                )
            )

    # 4. Append audit record for the batch (AUD-003, Rule 16)
    audit_repo.record_action(
        entity_type="IMPORT_BATCH",
        entity_id=active_batch_id,
        action="IMPORT",
        actor_id=actor_id,
        payload_after={
            "filename": path.name,
            "format": fmt,
            "content_hash": content_hash,
            "total_rows": summary.total_rows,
            "imported_count": summary.imported_count,
            "duplicate_count": summary.duplicate_count,
            "error_count": summary.error_count,
        },
    )

    session.flush()
    return summary
