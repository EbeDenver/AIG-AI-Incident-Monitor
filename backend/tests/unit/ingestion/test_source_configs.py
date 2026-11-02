"""Unit tests for ingestion source configurations and epistemic role classification."""

from pathlib import Path
import pytest

from ai_incident_monitor.ingestion.models import ConnectorType
from ai_incident_monitor.ingestion.sources import (
    SourceConfig,
    SourceRole,
    get_default_sources,
    load_source_configs,
)


class TestSourceConfiguration:
    """Validate source configuration rules, schema constraints, and role separation."""

    def test_default_sources_integrity(self) -> None:
        sources = get_default_sources()
        assert len(sources) >= 3

        roles = {s.role for s in sources}
        assert SourceRole.SUPPLEMENTARY_RESEARCH_CONTEXT in roles
        assert SourceRole.PRIMARY_INCIDENT_REPORT in roles
        assert SourceRole.OFFICIAL_MANUAL_EXPORT in roles

    def test_arxiv_role_is_supplementary_research(self) -> None:
        sources = get_default_sources()
        arxiv = next(s for s in sources if s.source_id == "arxiv_research")
        assert arxiv.role == SourceRole.SUPPLEMENTARY_RESEARCH_CONTEXT
        assert not arxiv.is_primary_incident_source
        assert arxiv.rate_limit_seconds >= 3.0
        assert "export.arxiv.org" in arxiv.allowed_hosts

    def test_rss_role_is_primary_incident_source(self) -> None:
        sources = get_default_sources()
        rss = next(s for s in sources if s.source_id == "rss_incident_feed")
        assert rss.role == SourceRole.PRIMARY_INCIDENT_REPORT
        assert rss.is_primary_incident_source

    def test_oecd_aim_role_is_primary_incident_source(self) -> None:
        sources = get_default_sources()
        oecd_aim = next(s for s in sources if s.source_id == "oecd_aim_live")
        assert oecd_aim.role == SourceRole.PRIMARY_INCIDENT_REPORT
        assert oecd_aim.is_primary_incident_source
        assert oecd_aim.endpoint_url == "https://fail.ticker.io/data/wire.json"
        assert "fail.ticker.io" in oecd_aim.allowed_hosts
        assert oecd_aim.enabled is True

    def test_oecd_role_is_offline_export(self) -> None:
        sources = get_default_sources()
        oecd = next(s for s in sources if s.source_id == "oecd_export")
        assert oecd.role == SourceRole.OFFICIAL_MANUAL_EXPORT
        assert not oecd.is_live_feed

    def test_load_source_configs_from_file(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "test_sources.json"
        cfg_file.write_text(
            """[
                {
                    "source_id": "test_feed",
                    "name": "Test Incident Feed",
                    "connector_type": "rss",
                    "role": "primary_incident_report",
                    "endpoint_url": "https://test.example.com/feed.xml",
                    "allowed_hosts": ["test.example.com"],
                    "rate_limit_seconds": 2.0,
                    "enabled": true
                }
            ]""",
            encoding="utf-8",
        )

        loaded = load_source_configs(cfg_file)
        assert len(loaded) == 1
        src = loaded[0]
        assert src.source_id == "test_feed"
        assert src.is_live_feed
        assert src.is_primary_incident_source
        assert src.rate_limit_seconds == 2.0
