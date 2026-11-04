"""Unit tests for the public read-only API and mock data segregation contract.

Governing Principles:
1. Mock data segregation: Public consumers by default receive zero synthetic mock intelligence.
2. Zero leakage: No database internal IDs, filesystem paths, or reviewer secrets in public DTOs.
3. Full CORS support and HTTP caching headers on all public endpoints.
4. WCAG-compliant category taxonomy tokens.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from starlette.testclient import TestClient

from ai_incident_monitor.db.base import Base
from ai_incident_monitor.db.models.claim import ClaimRecordModel
from ai_incident_monitor.db.models.enrichment import IncidentEnrichmentModel
from ai_incident_monitor.db.models.incident import IncidentModel
from ai_incident_monitor.db.models.severity import SeverityAssessmentModel
from ai_incident_monitor.db.session import get_engine
from ai_incident_monitor.ui.app import create_app
from sqlalchemy.orm import Session


@pytest.fixture
def public_test_app(tmp_path: Path):
    """Create test application with in-memory/test SQLite database."""
    db_path = tmp_path / "test_public.db"
    engine = get_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)

    # Seed test incident with mock enrichment
    with Session(engine) as session:
        inc = IncidentModel(
            id="INC-2026-TEST01",
            title="Automated Test Incident",
            summary="A test incident summary for public API verification.",
            status="UNDER_INVESTIGATION",
            primary_category="CYBERSECURITY",
            incident_date_precision="EXACT",
        )
        session.add(inc)

        # Mock enrichment
        mock_payload = {
            "incident_id": "INC-2026-TEST01",
            "summary": "Synthetic mock summary for testing.",
            "ai_involvement": {
                "role": "PRIMARY",
                "autonomy": "AUTONOMOUS_EXECUTION",
                "human_oversight": "DEFICIENT",
                "assessment": "Synthetic AI involvement assessment.",
            },
            "causal_assessment": {
                "causal_status": "PROBABLE_CONTRIBUTOR",
                "confidence": "MEDIUM",
                "observed_outcomes": ["Temporary service disruption"],
                "reported_mechanisms": ["Automated rate-limiting failure"],
            },
            "atomic_claims": [
                {
                    "claim_id": "CLM-001",
                    "assertion": "AI agent saturated API endpoints.",
                    "classification": "CONFIRMED_FACT",
                    "verification_status": "VERIFIED",
                    "confidence": "HIGH",
                }
            ],
            "organizational_controls": [
                {
                    "risk": "API saturation",
                    "control": "Implement token-bucket throttling",
                    "control_type": "PREVENTIVE",
                    "incident_specific": True,
                }
            ],
            "decision_maker_guidance": {
                "executive_summary": "Executive briefing summary.",
                "board_briefing": "Board strategic briefing.",
                "strategic_priorities": ["Prioritize API security"],
                "budget_allocation_recommendations": ["Allocate budget for WAF"],
            },
            "consultant_guidance": {
                "immediate_actions": ["Isolate offending endpoint"],
                "short_term_hardening": ["Deploy rate limiting"],
                "architectural_guidance": ["Implement circuit breakers"],
                "testing_requirements": ["Chaos engineering load tests"],
            },
        }

        enr = IncidentEnrichmentModel(
            id="ENR-TEST01",
            incident_id="INC-2026-TEST01",
            status="COMPLETED",
            model_provider="mock",
            model_name="mock-intelligence-v2",
            prompt_digest="hash123",
            content_hash="hash456",
            cache_key="cache789",
            payload_json=json.dumps(mock_payload),
            executive_summary="Synthetic mock summary for testing.",
        )
        session.add(enr)

        # Severity assessment
        sev = SeverityAssessmentModel(
            id="SEV-TEST01",
            incident_id="INC-2026-TEST01",
            actual_tier="HIGH",
            potential_tier="CRITICAL",
        )
        session.add(sev)

        # Second incident without enrichment
        inc2 = IncidentModel(
            id="INC-2026-TEST02",
            title="Second Incident Without Intelligence",
            summary="Clean un-enriched incident record.",
            status="OPEN",
            primary_category="SAFETY",
            incident_date_precision="UNKNOWN",
        )
        session.add(inc2)

        # Third incident with live Claude enrichment
        inc3 = IncidentModel(
            id="INC-2026-TEST03",
            title="Live Enriched Drone Incident",
            summary="Autonomous drone incident enriched with Claude Sonnet.",
            status="INVESTIGATED",
            primary_category="SAFETY",
            incident_date_precision="EXACT",
        )
        session.add(inc3)
        claude_payload = {
            "incident_id": "INC-2026-TEST03",
            "incident_summary": {
                "reported_event": "Drone lost telemetry during urban survey flight.",
                "verified_outcome": None,
                "affected_entities": ["City Survey Unit"],
            },
            "claims": [
                {
                    "claim_id": "C001",
                    "statement": "Drone lost telemetry during urban flight.",
                    "classification": "CONFIRMED_FACT",
                    "verification_status": "VERIFIED",
                    "confidence": "HIGH",
                }
            ],
            "ai_involvement": {
                "role": "CONTRIBUTING",
                "autonomy_level": "CONDITIONAL_AUTONOMY",
                "human_oversight": "OPERATOR_IN_THE_LOOP",
                "assessment": "AI path-planning contributed to the loss of telemetry.",
            },
            "causal_assessment": {
                "causal_status": "CONTRIBUTING_FACTOR",
                "confidence": "HIGH",
                "observed_outcomes": ["Safe parachute deployment"],
                "reported_mechanisms": ["Desynchronization of Kalman filter"],
            },
            "organizational_controls": [
                {
                    "risk": "Telemetry loss",
                    "control": "Implement redundant sensor channels",
                    "control_type": "PREVENTIVE",
                    "incident_specific": True,
                }
            ],
            "decision_maker_guidance": {
                "key_implications": ["Upgrade urban flight failsafe standards."],
            },
            "consultant_guidance": {
                "discovery_questions": ["What is the sensor desync threshold?"],
            },
            "quality_review": {
                "advisory_human_review_flag": False,
            },
        }
        enr3 = IncidentEnrichmentModel(
            id="ENR-TEST03",
            incident_id="INC-2026-TEST03",
            status="COMPLETED",
            model_provider="claude",
            model_name="claude-sonnet-4-5-20250929",
            prompt_digest="hash789",
            content_hash="hash999",
            cache_key="cache999",
            payload_json=json.dumps(claude_payload),
            executive_summary="Drone lost telemetry during urban survey flight.",
        )
        session.add(enr3)

        session.commit()

    app = create_app(
        db_engine=engine,
        repo_root=tmp_path,
        allowed_hosts={"testserver", "localhost:8000", "127.0.0.1"},
    )
    return app


@pytest.fixture
def client(public_test_app) -> TestClient:
    return TestClient(public_test_app)


class TestPublicAPI:
    """Verify read-only public API contracts, CORS, and strict mock quarantine."""

    def test_cors_preflight_options(self, client: TestClient) -> None:
        """OPTIONS requests to public routes return 204 with full CORS headers."""
        response = client.options("/api/v1/public/incidents")
        assert response.status_code == 204
        assert response.headers["access-control-allow-origin"] == "*"
        assert "GET" in response.headers["access-control-allow-methods"]

        cat_resp = client.options("/api/v1/public/categories")
        assert cat_resp.status_code == 204
        assert cat_resp.headers["access-control-allow-origin"] == "*"

    def test_list_categories(self, client: TestClient) -> None:
        """GET /categories returns all 7 categories with WCAG AAA/AA tokens and cache headers."""
        response = client.get("/api/v1/public/categories")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "public, max-age=3600"
        assert response.headers["access-control-allow-origin"] == "*"

        categories = response.json()
        assert len(categories) == 7
        keys = {c["category_key"] for c in categories}
        assert "CYBERSECURITY" in keys
        assert "SAFETY" in keys
        assert "RIGHTS" in keys

        cyber = next(c for c in categories if c["category_key"] == "CYBERSECURITY")
        assert cyber["border_hex"].startswith("#")
        assert cyber["bg_hex"].startswith("#")
        assert cyber["text_hex"].startswith("#")
        assert cyber["text_symbol"] == "[CYBER]"

    def test_mock_segregation_in_incident_list_by_default(self, client: TestClient) -> None:
        """By default, incident summaries quarantine mock intelligence."""
        response = client.get("/api/v1/public/incidents")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

        test1 = next(item for item in data["items"] if item["incident_id"] == "INC-2026-TEST01")
        # Under default quarantine, has_intelligence is False, status is PENDING_ANALYSIS, mock is not advertised
        assert test1["has_intelligence"] is False
        assert test1["intelligence_status"] == "PENDING_ANALYSIS"
        assert test1["is_synthetic_mock"] is False
        assert test1["severity"] == "HIGH"
        assert test1["primary_category"] == "CYBERSECURITY"

        test3 = next(item for item in data["items"] if item["incident_id"] == "INC-2026-TEST03")
        assert test3["has_intelligence"] is True
        assert test3["intelligence_status"] == "LIVE_ENRICHED"
        assert test3["is_synthetic_mock"] is False

    def test_mock_opt_in_incident_list(self, client: TestClient) -> None:
        """With include_mock=true, mock intelligence is explicitly advertised as synthetic."""
        response = client.get("/api/v1/public/incidents?include_mock=true")
        assert response.status_code == 200
        data = response.json()

        test1 = next(item for item in data["items"] if item["incident_id"] == "INC-2026-TEST01")
        assert test1["has_intelligence"] is True
        assert test1["intelligence_status"] == "SYNTHETIC_MOCK"
        assert test1["is_synthetic_mock"] is True

    def test_mock_segregation_in_incident_detail(self, client: TestClient) -> None:
        """By default, incident detail returns intelligence=None for mock-enriched records."""
        response = client.get("/api/v1/public/incidents/INC-2026-TEST01")
        assert response.status_code == 200
        data = response.json()
        assert data["incident_id"] == "INC-2026-TEST01"
        assert data["intelligence"] is None
        assert data["has_intelligence"] is False
        assert data["intelligence_status"] == "PENDING_ANALYSIS"

    def test_mock_opt_in_incident_detail(self, client: TestClient) -> None:
        """With include_mock=true, mock intelligence is parsed and flagged as synthetic."""
        response = client.get("/api/v1/public/incidents/INC-2026-TEST01?include_mock=true")
        assert response.status_code == 200
        data = response.json()
        intel = data["intelligence"]
        assert intel is not None
        assert intel["is_available"] is True
        assert intel["is_synthetic_mock"] is True
        assert intel["model_provider"] == "mock"
        assert intel["ai_involvement"]["role"] == "PRIMARY"
        assert intel["causal_assessment"]["causal_status"] == "PROBABLE_CONTRIBUTOR"
        assert len(intel["atomic_claims"]) == 1
        assert intel["atomic_claims"][0]["claim_id"] == "CLM-001"

    def test_category_and_severity_filtering(self, client: TestClient) -> None:
        """Filtering by category and severity returns matching subset."""
        res_cat = client.get("/api/v1/public/incidents?category=SAFETY")
        assert res_cat.status_code == 200
        items_cat = res_cat.json()["items"]
        assert len(items_cat) == 2
        safety_ids = {it["incident_id"] for it in items_cat}
        assert safety_ids == {"INC-2026-TEST02", "INC-2026-TEST03"}

        res_sev = client.get("/api/v1/public/incidents?severity=HIGH")
        assert res_sev.status_code == 200
        items_sev = res_sev.json()["items"]
        assert len(items_sev) == 1
        assert items_sev[0]["incident_id"] == "INC-2026-TEST01"

    def test_invalid_or_missing_incident_returns_404(self, client: TestClient) -> None:
        """Non-existent or malformed incident IDs return clean 404."""
        res_404 = client.get("/api/v1/public/incidents/INC-NONEXISTENT")
        assert res_404.status_code == 404

        res_bad = client.get("/api/v1/public/incidents/INVALID%20ID%20WITH%20SPACES")
        assert res_bad.status_code == 404

    def test_live_claude_enriched_incident_exposure(self, client: TestClient) -> None:
        """Live Claude enrichments are served by default without mock quarantine."""
        response = client.get("/api/v1/public/incidents/INC-2026-TEST03")
        assert response.status_code == 200
        data = response.json()
        assert data["has_intelligence"] is True
        assert data["is_synthetic_mock"] is False
        assert data["intelligence_status"] == "LIVE_ENRICHED"
        intel = data["intelligence"]
        assert intel is not None
        assert intel["model_provider"] == "claude"
        assert intel["model_name"] == "claude-sonnet-4-5-20250929"
        assert len(intel["atomic_claims"]) == 1
        assert intel["atomic_claims"][0]["claim_id"] == "C001"
        assert intel["ai_involvement"]["role"] == "CONTRIBUTING"
        assert intel["ai_involvement"]["autonomy"] == "CONDITIONAL_AUTONOMY"
        assert len(intel["organizational_controls"]) == 1

    def test_zero_secret_or_path_leakage(self, client: TestClient) -> None:
        """Public responses never contain absolute local paths or secret strings."""
        res_det = client.get("/api/v1/public/incidents/INC-2026-TEST01?include_mock=true")
        body_text = res_det.text
        assert "/Users/" not in body_text
        assert "/Volumes/" not in body_text
        assert ".db" not in body_text
        assert "password" not in body_text
        assert "secret" not in body_text.lower() or "circuit breaker" in body_text.lower()

    def test_search_query_filter(self, client: TestClient) -> None:
        """Catalog-wide search matches title, summary, or ID."""
        res_q = client.get("/api/v1/public/incidents?q=Drone")
        assert res_q.status_code == 200
        items = res_q.json()["items"]
        assert len(items) == 1
        assert items[0]["incident_id"] == "INC-2026-TEST03"

        res_id = client.get("/api/v1/public/incidents?q=TEST02")
        assert res_id.status_code == 200
        items_id = res_id.json()["items"]
        assert len(items_id) == 1
        assert items_id[0]["incident_id"] == "INC-2026-TEST02"

    def test_sorting_options(self, client: TestClient) -> None:
        """Sorting by title and discovered_date works with asc/desc order."""
        res_desc = client.get("/api/v1/public/incidents?sort_by=title&sort_order=desc")
        assert res_desc.status_code == 200
        titles_desc = [it["title"] for it in res_desc.json()["items"]]
        assert titles_desc == sorted(titles_desc, reverse=True)

        res_asc = client.get("/api/v1/public/incidents?sort_by=title&sort_order=asc")
        assert res_asc.status_code == 200
        titles_asc = [it["title"] for it in res_asc.json()["items"]]
        assert titles_asc == sorted(titles_asc)

    def test_catalog_freshness_metadata(self, client: TestClient) -> None:
        """Catalog freshness metadata is populated with contract version and environment."""
        res = client.get("/api/v1/public/incidents")
        assert res.status_code == 200
        freshness = res.json()["freshness"]
        assert freshness is not None
        assert freshness["catalog_version"] == "2.0.0"
        assert freshness["database_environment"] in ("development", "production")

    def test_production_mock_opt_in_strictly_forbidden(self, client: TestClient, monkeypatch) -> None:
        """In production environment, setting include_mock=true returns 403 Forbidden."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        res_list = client.get("/api/v1/public/incidents?include_mock=true")
        assert res_list.status_code == 403
        assert "forbidden in production" in res_list.json()["detail"].lower()

        res_det = client.get("/api/v1/public/incidents/INC-2026-TEST01?include_mock=true")
        assert res_det.status_code == 403
        assert "forbidden in production" in res_det.json()["detail"].lower()
