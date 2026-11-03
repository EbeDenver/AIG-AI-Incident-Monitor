"""CLI tool for bounded, resumable incident intelligence enrichment backfills.

Governing Charter: Project Constitution (Rules 1, 2, 3, 4, 11, 14, 16),
AUD-005, OPS-004, Ai-incident-manager-guide.pdf (§1–§3),
amended by Section B (No-Approval Amendment: advisory quality warnings only).
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_incident_monitor.config import get_pilot_budget_cap_usd
from ai_incident_monitor.db.models.enrichment import IncidentEnrichmentModel
from ai_incident_monitor.db.models.incident import IncidentModel
from ai_incident_monitor.db.session import get_engine
from ai_incident_monitor.intelligence.client import (
    BudgetExceededError,
    PilotBudgetGuard,
    get_llm_client,
)
from ai_incident_monitor.intelligence.service import EnrichmentService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ai_incident_monitor.intelligence.backfill")


def run_enrichment_backfill(
    *,
    limit: int = 10,
    force: bool = False,
    dry_run: bool = False,
    provider: str = "mock",
    incident_id: Optional[str] = None,
    max_budget_usd: Optional[float] = None,
) -> int:
    """Execute bounded backfill of incident enrichment with pilot safety controls."""
    engine = get_engine()
    client = get_llm_client(provider)
    budget_cap = max_budget_usd if max_budget_usd is not None else get_pilot_budget_cap_usd()
    guard = PilotBudgetGuard(max_budget_usd=budget_cap)
    service = EnrichmentService(default_client=client, budget_guard=guard)

    model_name = getattr(client, "model_name", "unknown-model")

    with Session(engine) as session:
        if incident_id:
            incident_ids = [incident_id]
        else:
            query = select(IncidentModel.id).order_by(IncidentModel.created_at.desc())
            if not force:
                # Select only incidents that have not yet been successfully enriched
                completed_subq = select(IncidentEnrichmentModel.incident_id).where(
                    IncidentEnrichmentModel.status == "COMPLETED"
                )
                query = query.where(IncidentModel.id.not_in(completed_subq))
            if limit > 0:
                query = query.limit(limit)
            incident_ids = list(session.execute(query).scalars().all())

        print(f"\n================================================================================")
        print(f" AI INCIDENT MONITOR — ENRICHMENT PILOT DISPATCH")
        print(f"================================================================================")
        print(f" Provider:       {provider.upper()}")
        print(f" Model ID:       {model_name}")
        print(f" Target Records: {len(incident_ids)} (limit={limit}, force={force})")
        print(f" Spending Limit: ${budget_cap:.2f} USD")
        print(f" Dry Run Mode:   {dry_run}")
        print(f"================================================================================\n")

        # Estimate cost bounds: ~9,500 in, ~5,500 out per record (comprehensive 12-section dossier)
        unit_est = client.calculate_cost(9500, 5500)
        total_est = round(unit_est * len(incident_ids), 4)
        print(f"[PRE-FLIGHT ESTIMATE]")
        print(f"  Estimated cost per incident: ${unit_est:.6f} USD")
        print(f"  Maximum total pilot estimate: ${total_est:.4f} USD (Ceiling: ${budget_cap:.2f} USD)")

        if dry_run:
            print("\n[DRY RUN] Target incident IDs:")
            for iid in incident_ids:
                print(f"  - {iid}")
            print("\nDry run completed. No API calls or database mutations executed.\n")
            return 0

        success_count = 0
        failed_count = 0
        total_in_tokens = 0
        total_out_tokens = 0
        total_cost = 0.0

        for idx, iid in enumerate(incident_ids, start=1):
            print(f"[{idx}/{len(incident_ids)}] Processing {iid}...")
            try:
                enr = service.enrich_incident(
                    session, iid, force=force, client=client, budget_guard=guard
                )
                if enr.status == "COMPLETED":
                    success_count += 1
                    total_in_tokens += enr.token_count_input
                    total_out_tokens += enr.token_count_output
                    total_cost += enr.estimated_cost_usd
                    print(
                        f"  ✓ {iid} -> COMPLETED ({enr.assessment_status}) "
                        f"[{enr.token_count_input} in / {enr.token_count_output} out] "
                        f"Cost: ${enr.estimated_cost_usd:.6f} USD [{enr.latency_seconds:.2f}s]"
                    )
                else:
                    failed_count += 1
                    print(f"  ✗ {iid} -> FAILED: {enr.error_message}")
            except BudgetExceededError as b_err:
                print(f"  ⛔ HALT: {b_err}")
                failed_count += 1
                break
            except Exception as exc:
                failed_count += 1
                print(f"  ✗ {iid} -> EXCEPTION: {exc}")

        print(f"\n================================================================================")
        print(f" ENRICHMENT RUN SUMMARY")
        print(f"================================================================================")
        print(f" Success:     {success_count} / {len(incident_ids)}")
        print(f" Failed:      {failed_count}")
        print(f" Total Tokens:{total_in_tokens} input / {total_out_tokens} output")
        print(f" Total Cost:  ${total_cost:.6f} USD (Remaining budget: ${max(0.0, budget_cap - total_cost):.4f} USD)")
        print(f"================================================================================\n")

        return 0 if failed_count == 0 else 1


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Enrich AI incidents with intelligence and defense guidance.")
    parser.add_argument("--limit", type=int, default=10, help="Maximum number of incidents to process.")
    parser.add_argument("--force", action="store_true", help="Force reprocessing even if cached.")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without writing to database or calling APIs.")
    parser.add_argument(
        "--provider",
        type=str,
        default="mock",
        choices=["mock", "claude", "gemini"],
        help="LLM provider adapter (mock, claude, gemini).",
    )
    parser.add_argument("--incident-id", type=str, default=None, help="Process a specific incident ID.")
    parser.add_argument("--max-budget", type=float, default=None, help="Maximum spending limit in USD.")

    args = parser.parse_args(argv)
    return run_enrichment_backfill(
        limit=args.limit,
        force=args.force,
        dry_run=args.dry_run,
        provider=args.provider,
        incident_id=args.incident_id,
        max_budget_usd=args.max_budget,
    )


if __name__ == "__main__":
    sys.exit(main())
