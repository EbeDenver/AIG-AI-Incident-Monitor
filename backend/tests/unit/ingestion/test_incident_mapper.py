"""Unit tests for IngestionIncidentMapper epistemic mapping and deduplication."""

from datetime import datetime, timezone
from pathlib import Path
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from ai_incident_monitor.db.base import Base
from ai_incident_monitor.db.models.claim import ClaimRecordModel
from ai_incident_monitor.db.models.incident import IncidentModel
from ai_incident_monitor.db.models.source import SourceReferenceModel
from ai_incident_monitor.domain.vocabularies import EpistemicStatus
from ai_incident_monitor.ingestion.incident_mapper import (
    IngestionIncidentMapper,
    parse_date_string,
)
from ai_incident_monitor.ingestion.models import ConnectorType, IngestedItem
from ai_incident_monitor.ingestion.sources import SourceConfig, SourceRole


@pytest.fixture
def in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


class TestIncidentMapper:
    """Validate epistemic separation, database persistence, and deduplication during mapping."""

    def test_parse_date_strings(self) -> None:
        # RFC 2822
        prec, dt, y, m = parse_date_string("Mon, 20 Oct 2026 08:30:00 GMT")
        assert prec == "EXACT"
        assert y == 2026
        assert m == 10
        assert dt.day == 20

        # ISO
        prec, dt, y, m = parse_date_string("2026-11-05")
        assert prec == "EXACT"
        assert y == 2026
        assert m == 11
        assert dt.day == 5

        # Unknown / Empty (Rule 2)
        prec, dt, y, m = parse_date_string(None)
        assert prec == "UNKNOWN"
        assert dt is None

    def test_primary_incident_source_persists_incident_and_claim(self, in_memory_db: Session) -> None:
        mapper = IngestionIncidentMapper(in_memory_db)
        src_cfg = SourceConfig(
            source_id="news_feed",
            name="AI News Feed",
            connector_type=ConnectorType.RSS,
            role=SourceRole.PRIMARY_INCIDENT_REPORT,
            endpoint_url="https://example.com/feed.xml",
            enabled=True,
        )
        item = IngestedItem(
            source_id="item_01",
            connector_name="rss",
            title="Autonomous Delivery Robot Collision",
            canonical_url="https://news.example.com/robot-crash-2026",
            published_date="2026-10-25",
            summary_snippet="Autonomous delivery robot collided with pedestrian barrier.",
            content_sha256="abc123sha",
            raw_item_dict={"publisher": "City Tech News"},
        )

        inc_id, outcome = mapper.process_item(item, src_cfg)
        assert outcome == "CREATED"
        assert inc_id is not None
        assert inc_id.startswith("INC-2026-")

        # Verify incident in DB
        inc = in_memory_db.execute(select(IncidentModel).where(IncidentModel.id == inc_id)).scalar_one()
        assert inc.title == "Autonomous Delivery Robot Collision"
        assert inc.status == "NEW"

        # Verify claim in DB has epistemic status UNVERIFIED_ALLEGATION (Rule 3)
        claim = in_memory_db.execute(select(ClaimRecordModel).where(ClaimRecordModel.incident_id == inc_id)).scalar_one()
        assert claim.epistemic_status == EpistemicStatus.UNVERIFIED_ALLEGATION.value

        # Verify source reference in DB
        source = in_memory_db.execute(select(SourceReferenceModel).where(SourceReferenceModel.url == "https://news.example.com/robot-crash-2026")).scalar_one()
        assert source.publisher == "City Tech News"

    def test_supplementary_research_context_does_not_create_incident(self, in_memory_db: Session) -> None:
        mapper = IngestionIncidentMapper(in_memory_db)
        src_cfg = SourceConfig(
            source_id="arxiv_research",
            name="arXiv Research",
            connector_type=ConnectorType.ARXIV,
            role=SourceRole.SUPPLEMENTARY_RESEARCH_CONTEXT,
            endpoint_url="https://export.arxiv.org/api/query",
            enabled=True,
        )
        item = IngestedItem(
            source_id="arxiv_2610.12345",
            connector_name="arxiv",
            title="Analyzing Failure Modes in Frontier Models",
            canonical_url="https://arxiv.org/abs/2610.12345",
            published_date="2026-10-28",
            summary_snippet="We explore adversarial prompts that cause misaligned behaviors.",
            content_sha256="paper123sha",
            raw_item_dict={},
            is_research_context=True,
        )

        inc_id, outcome = mapper.process_item(item, src_cfg)
        assert outcome == "RESEARCH_CONTEXT"
        assert inc_id is None

        # Verify zero incidents were created in the database!
        inc_count = in_memory_db.execute(select(IncidentModel)).scalars().all()
        assert len(inc_count) == 0

        # Verify research paper is cataloged as a source reference
        source = in_memory_db.execute(select(SourceReferenceModel).where(SourceReferenceModel.url == "https://arxiv.org/abs/2610.12345")).scalar_one()
        assert "arXiv" in source.publisher

    def test_deduplication_prevents_duplicate_incident(self, in_memory_db: Session) -> None:
        mapper = IngestionIncidentMapper(in_memory_db)
        src_cfg = SourceConfig(
            source_id="news_feed",
            name="AI News Feed",
            connector_type=ConnectorType.RSS,
            role=SourceRole.PRIMARY_INCIDENT_REPORT,
            endpoint_url="https://example.com/feed.xml",
            enabled=True,
        )
        item = IngestedItem(
            source_id="item_duplicate_test",
            connector_name="rss",
            title="Surgical Robot Actuator Lockup",
            canonical_url="https://news.example.com/surgical-robot-2026",
            published_date="2026-10-15",
            summary_snippet="Surgical arm locked during procedure due to sensor fault.",
            content_sha256="sha_surg_1",
            raw_item_dict={"publisher": "MedNews"},
        )

        # 1. First run creates the incident
        inc_id1, outcome1 = mapper.process_item(item, src_cfg)
        assert outcome1 == "CREATED"

        # 2. Second run with same canonical URL must deduplicate (Tier 2 AUTO_LINK_URL)
        inc_id2, outcome2 = mapper.process_item(item, src_cfg)
        assert outcome2 == "AUTO_LINKED"
        assert inc_id2 == inc_id1

        # Verify total incidents in DB remains exactly 1
        all_incidents = in_memory_db.execute(select(IncidentModel)).scalars().all()
        assert len(all_incidents) == 1
