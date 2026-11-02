"""Integration test verifying end-to-end OECD AIM syndicated live feed ingestion.

Governing Charter: Project Constitution (Rules 1, 2, 3, 7, 9, 11, 14, 15, 16),
ADR-008, ADR-009, DEC-P4-001.
"""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ai_incident_monitor.db.base import Base
from ai_incident_monitor.db.models.claim import ClaimRecordModel
from ai_incident_monitor.db.models.incident import IncidentModel
from ai_incident_monitor.db.models.source import SourceReferenceModel
from ai_incident_monitor.ingestion.checkpoints import CheckpointStore
from ai_incident_monitor.ingestion.cycle import run_ingestion_cycle
from ai_incident_monitor.ingestion.manifest import ManifestChainStore
from ai_incident_monitor.ingestion.models import ConnectorType
from ai_incident_monitor.ingestion.sources import SourceConfig, SourceRole
from ai_incident_monitor.security import SecureHTTPClient, SecureHTTPResponse

SAMPLE_WIRE_JSON = json.dumps(
    {
        "updated": "2026-11-02T05:30:15Z",
        "sources": {
            "oecd": {
                "name": "OECD AI Incidents and Hazards Monitor (AIM)",
                "url": "https://oecd.ai/en/incidents",
                "terms": "Free to use with attribution and linkback to oecd.ai.",
            }
        },
        "items": [
            {
                "id": "2026-10-31-cc4f",
                "title": "19-year-old arrested in Bulgaria over alleged AI-assisted cyberattacks",
                "date": "2026-10-31",
                "summary": "A 19-year-old was arrested in Bulgaria for allegedly using AI in cyberattacks.",
                "summary_full": "A 19-year-old, Mariyan Parushev, was arrested in Bulgaria for allegedly using AI in cyberattacks.",
                "tags": ["RIGHTS", "SAFETY"],
                "level": "incident",
                "country": "BGR",
                "url": "https://oecd.ai/en/incidents/2026-10-31-cc4f",
                "aiid": None,
                "curated": True,
            },
            {
                "id": "2026-10-31-42b0",
                "title": "Study finds Gemini and GPT-4o paired with smart glasses can answer SAT questions",
                "date": "2026-10-31",
                "summary": "German researchers showed AI models can solve over 80% of SAT questions.",
                "summary_full": "Research by German scientists demonstrated that AI models can solve over 80% of SAT questions.",
                "tags": ["REPUTATIONAL", "SAFETY"],
                "level": "incident",
                "country": "USA",
                "url": "https://oecd.ai/en/incidents/2026-10-31-42b0",
                "aiid": None,
                "curated": True,
            },
        ],
    }
).encode("utf-8")


@pytest.fixture
def oecd_test_env(tmp_path: Path):
    db_file = tmp_path / "test_oecd.db"
    engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(engine)

    data_dir = tmp_path / ".data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "manifests").mkdir(parents=True, exist_ok=True)
    (data_dir / "raw_feeds").mkdir(parents=True, exist_ok=True)

    yield {
        "engine": engine,
        "repo_root": tmp_path,
    }

    engine.dispose()


class TestOECDAIMLiveIntegration:
    """Test full cycle execution with the OECD AIM syndicated feed."""

    def test_live_feed_cycle_ingests_and_deduplicates(self, oecd_test_env) -> None:
        root = oecd_test_env["repo_root"]
        engine = oecd_test_env["engine"]

        mock_http = MagicMock(spec=SecureHTTPClient)
        mock_http.get.return_value = SecureHTTPResponse(
            status_code=200,
            headers={"Content-Type": "application/json", "ETag": '"wire-etag-v1"'},
            body=SAMPLE_WIRE_JSON,
            final_url="https://fail.ticker.io/data/wire.json",
            pinned_ip="66.96.88.176",
        )

        source_config = SourceConfig(
            source_id="oecd_aim_live",
            name="OECD AI Incidents and Hazards Monitor (Live Feed)",
            connector_type=ConnectorType.OECD_AIM_FEED,
            role=SourceRole.PRIMARY_INCIDENT_REPORT,
            endpoint_url="https://fail.ticker.io/data/wire.json",
            allowed_hosts=["fail.ticker.io"],
            rate_limit_seconds=0.0,
            enabled=True,
        )

        # 1. First execution: Ingest new incidents
        summary1 = run_ingestion_cycle(
            trigger="cli",
            repo_root=root,
            custom_sources=[source_config],
            custom_http_client=mock_http,
            db_engine=engine,
        )

        assert summary1.overall_status == "SUCCESS"
        assert summary1.total_created == 2
        assert summary1.total_updated == 0

        # Verify DB records
        with Session(engine) as session:
            incidents = session.query(IncidentModel).all()
            assert len(incidents) == 2
            inc1 = next(i for i in incidents if "Bulgaria" in i.title)
            assert inc1.status == "NEW"
            assert inc1.incident_exact_date == date(2026, 10, 31)

            sources = session.query(SourceReferenceModel).all()
            assert len(sources) == 2
            src1 = next(s for s in sources if "Bulgaria" in s.title)
            assert src1.publisher == "OECD AI Incidents and Hazards Monitor (AIM)"
            assert src1.canonical_url == "https://oecd.ai/en/incidents/2026-10-31-cc4f"

            claims = session.query(ClaimRecordModel).all()
            assert len(claims) == 2

        # Verify checkpoint
        cp_store = CheckpointStore(root / ".data" / "ingestion_checkpoints.json")
        cp = cp_store.get_checkpoint("oecd_aim_live")
        assert cp.etag == '"wire-etag-v1"'
        assert cp.last_status == "SUCCESS"
        assert cp.last_success_utc is not None

        # Verify provenance chain
        chain_store = ManifestChainStore(root / ".data" / "manifests")
        chain = chain_store.get_chain()
        assert len(chain) == 1
        assert chain[0].connector_id == "oecd_aim_feed_connector"
        assert chain[0].source_url == "https://fail.ticker.io/data/wire.json"

        # 2. Second execution with modified ETag: deduplication prevents duplicate incidents
        mock_http.get.return_value = SecureHTTPResponse(
            status_code=200,
            headers={"Content-Type": "application/json", "ETag": '"wire-etag-v2"'},
            body=SAMPLE_WIRE_JSON,
            final_url="https://fail.ticker.io/data/wire.json",
            pinned_ip="66.96.88.176",
        )

        summary2 = run_ingestion_cycle(
            trigger="scheduled",
            repo_root=root,
            custom_sources=[source_config],
            custom_http_client=mock_http,
            db_engine=engine,
        )

        assert summary2.overall_status == "SUCCESS"
        assert summary2.total_created == 0  # Zero duplicate incidents!
        assert summary2.total_updated == 2  # Both matched via Tier 2 URL deduplication

        with Session(engine) as session:
            incidents_after = session.query(IncidentModel).all()
            assert len(incidents_after) == 2  # Total incident count unchanged!

        # 3. Third execution with matching ETag: 304 Not Modified
        mock_http.get.return_value = SecureHTTPResponse(
            status_code=304,
            headers={"ETag": '"wire-etag-v2"'},
            body=b"",
            final_url="https://fail.ticker.io/data/wire.json",
            pinned_ip="66.96.88.176",
        )

        summary3 = run_ingestion_cycle(
            trigger="portal",
            repo_root=root,
            custom_sources=[source_config],
            custom_http_client=mock_http,
            db_engine=engine,
        )

        assert summary3.overall_status == "NOT_MODIFIED"
        assert summary3.total_created == 0
        assert summary3.total_updated == 0
