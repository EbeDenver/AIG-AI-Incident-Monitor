"""CLI tool for bounded, resumable incident intelligence enrichment backfills.

Governing Charter: Project Constitution (Rules 1, 2, 3, 4, 11, 14, 16),
AUD-005, OPS-004.
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_incident_monitor.db.models.incident import IncidentModel
from ai_incident_monitor.db.session import get_engine
from ai_incident_monitor.intelligence.client import MockLLMClient
from ai_incident_monitor.intelligence.service import EnrichmentService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ai_incident_monitor.intelligence.backfill")


def run_enrichment_backfill(
    *,
    limit: int = 10,
    force: bool = False,
    dry_run: bool = False,
    mock: bool = True,
    incident_id: Optional[str] = None,
) -> int:
    """Execute bounded backfill of incident enrichment."""
    engine = get_engine()
    service = EnrichmentService(default_client=MockLLMClient())

    with Session(engine) as session:
        if incident_id:
            incident_ids = [incident_id]
        else:
            query = select(IncidentModel.id).order_by(IncidentModel.created_at.desc())
            if limit > 0:
                query = query.limit(limit)
            incident_ids = list(session.execute(query).scalars().all())

        print(f"\n[ENRICHMENT BACKFILL] Target incidents: {len(incident_ids)} (limit={limit}, force={force}, dry_run={dry_run})")

        if dry_run:
            print("[DRY RUN] Would enrich the following incident IDs:")
            for iid in incident_ids:
                print(f"  - {iid}")
            return 0

        success_count = 0
        failed_count = 0
        total_in_tokens = 0
        total_out_tokens = 0
        total_cost = 0.0

        for iid in incident_ids:
            try:
                enr = service.enrich_incident(session, iid, force=force)
                if enr.status == "COMPLETED":
                    success_count += 1
                    total_in_tokens += enr.token_count_input
                    total_out_tokens += enr.token_count_output
                    total_cost += enr.estimated_cost_usd
                    print(f"  ✓ {iid} -> COMPLETED ({enr.evidence_sufficiency}) [{enr.latency_seconds:.2f}s]")
                else:
                    failed_count += 1
                    print(f"  ✗ {iid} -> FAILED: {enr.error_message}")
            except Exception as exc:
                failed_count += 1
                print(f"  ✗ {iid} -> EXCEPTION: {exc}")

        print(f"\n[ENRICHMENT COMPLETE] Success: {success_count} | Failed: {failed_count}")
        print(f"  Tokens: {total_in_tokens} in / {total_out_tokens} out | Cost: ${total_cost:.6f} USD\n")

        return 0 if failed_count == 0 else 1


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Enrich AI incidents with intelligence and defense guidance.")
    parser.add_argument("--limit", type=int, default=10, help="Maximum number of incidents to process.")
    parser.add_argument("--force", action="store_true", help="Force reprocessing even if cached.")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without writing to database.")
    parser.add_argument("--mock", action="store_true", default=True, help="Use deterministic mock model.")
    parser.add_argument("--incident-id", type=str, default=None, help="Process a specific incident ID.")

    args = parser.parse_args(argv)
    return run_enrichment_backfill(
        limit=args.limit,
        force=args.force,
        dry_run=args.dry_run,
        mock=args.mock,
        incident_id=args.incident_id,
    )


if __name__ == "__main__":
    sys.exit(main())
