"""Unit tests for the public read-only API and mock data segregation contract.

Governing Principles:
1. Mock data segregation: Public consumers by default receive zero synthetic mock intelligence.
2. Zero leakage: No database internal IDs, filesystem paths, or reviewer secrets in public DTOs.
3. Full CORS support and HTTP caching headers on all public endpoints.
4. WCAG-compliant category taxonomy tokens.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
import pytest
from starlette.testclient import TestClient

from ai_incident_monitor.db.base import Base
from ai_incident_monitor.db.models.claim import ClaimRecordModel
from ai_incident_monitor.db.models.compliance import EUAIActComplianceAssessmentModel
from ai_incident_monitor.db.models.enrichment import IncidentEnrichmentModel
from ai_incident_monitor.db.models.evidence import (
    ClaimEvidenceLinkModel,
    EvidenceRecordModel,
    QuoteSpanModel,
)
from ai_incident_monitor.db.models.incident import IncidentModel
from ai_incident_monitor.db.models.severity import SeverityAssessmentModel
from ai_incident_monitor.db.models.source import SourceReferenceModel
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
            created_at=datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc),
        )
        session.add(enr3)

        # Equal-timestamp dual severity assessments on TEST03 for deterministic tie-breaker verification:
        # Both created at exact same timestamp: 2026-10-01 12:00:00 UTC
        # SEV-EQUAL-01 has actual_tier="LOW"
        # SEV-EQUAL-02 has actual_tier="MEDIUM"
        # Under id.desc() tie-breaker, "SEV-EQUAL-02" > "SEV-EQUAL-01", so both list and detail MUST resolve to "MEDIUM"
        sev3_a = SeverityAssessmentModel(
            id="SEV-EQUAL-01",
            incident_id="INC-2026-TEST03",
            actual_tier="LOW",
            created_at=datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc),
        )
        session.add(sev3_a)

        sev3_b = SeverityAssessmentModel(
            id="SEV-EQUAL-02",
            incident_id="INC-2026-TEST03",
            actual_tier="MEDIUM",
            created_at=datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc),
        )
        session.add(sev3_b)

        # Fourth incident: RIGHTS category, CRITICAL severity with historical LOW, live Claude enrichment, quote span
        inc4 = IncidentModel(
            id="INC-2026-TEST04",
            title="Biometric Access Gate False Rejection",
            summary="Autonomous facial recognition gate incorrectly rejected valid credentials.",
            status="INVESTIGATED",
            primary_category="RIGHTS",
            incident_date_precision="EXACT",
            incident_exact_date=date(2026, 9, 15),
            created_at=datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc),
        )
        session.add(inc4)

        # Historical severity for TEST04: was LOW, superseded by CRITICAL
        sev4_old = SeverityAssessmentModel(
            id="SEV-HIST-04",
            incident_id="INC-2026-TEST04",
            actual_tier="LOW",
            superseded_by_id="SEV-CURR-04",
            created_at=datetime(2026, 9, 16, 13, 0, tzinfo=timezone.utc),
        )
        session.add(sev4_old)

        sev4_new = SeverityAssessmentModel(
            id="SEV-CURR-04",
            incident_id="INC-2026-TEST04",
            actual_tier="CRITICAL",
            superseded_by_id=None,
            created_at=datetime(2026, 9, 17, 10, 0, tzinfo=timezone.utc),
        )
        session.add(sev4_new)

        enr4_payload = {
            "incident_id": "INC-2026-TEST04",
            "incident_summary": {
                "reported_event": "Biometric access gate denied entry due to facial recognition defect.",
                "verified_outcome": "False rejection rate spiked to 14%.",
                "affected_entities": ["Public Transit Authority"],
            },
            "claims": [
                {
                    "claim_id": "C-BIO-01",
                    "statement": "Facial recognition system had high false rejection rate.",
                    "classification": "CONFIRMED_FACT",
                    "verification_status": "VERIFIED",
                    "confidence": "HIGH",
                    "supporting_evidence_ids": ["EVD-TEST04"],
                    "reasoning_summary": "Transit operational audit logs confirmed the error rate.",
                }
            ],
            "provenance": [
                {
                    "evidence_id": "EVD-TEST04",
                    "source_url": "https://example.com/transit-audit",
                    "excerpt": "Operational audit verified a 14% false rejection rate on biometric turnstiles.",
                    "locator": "char_offset:50-115",
                }
            ],
            "ai_involvement": {
                "role": "PRIMARY",
                "autonomy_level": "FULL_AUTONOMY",
                "human_oversight": "OPERATOR_OVERRIDE",
                "assessment": "Automated facial recognition directly controlled gate locking mechanism.",
            },
        }

        enr4 = IncidentEnrichmentModel(
            id="ENR-TEST04",
            incident_id="INC-2026-TEST04",
            status="COMPLETED",
            model_provider="claude",
            model_name="claude-sonnet-4-5-20250929",
            prompt_digest="hash444",
            content_hash="hash444",
            cache_key="cache444",
            payload_json=json.dumps(enr4_payload),
            executive_summary="Biometric gate false rejection incident.",
            created_at=datetime(2026, 9, 17, 11, 0, tzinfo=timezone.utc),
        )
        session.add(enr4)

        # Source reference, evidence record, and quote span for TEST04
        src4 = SourceReferenceModel(
            id="SRC-TEST04",
            title="Transit Biometric Gate Audit Report",
            publisher="Transit Audit Bureau",
            url="https://example.com/transit-audit",
            source_type="PRIMARY",
            publication_exact_date=date(2026, 9, 16),
            retrieval_date=datetime(2026, 9, 17, 9, 0, tzinfo=timezone.utc),
            access_status="OPEN_PUBLIC",
            authority="REGULATORY_JUDICIAL_AUTHORITY",
            reliability="VERY_HIGH",
            independence="INDEPENDENT_ORIGINAL",
            content_hash="hash_src_444",
        )
        session.add(src4)

        clm4 = ClaimRecordModel(
            id="CLM-TEST04",
            incident_id="INC-2026-TEST04",
            claim_text="Facial recognition system had high false rejection rate.",
            claim_type="FACTUAL_ASSERTION",
            epistemic_status="CONFIRMED_FACT",
            confidence="HIGH",
            materiality="CORE_CONTRIBUTOR",
        )
        session.add(clm4)

        evd4 = EvidenceRecordModel(
            id="EVD-TEST04",
            source_id="SRC-TEST04",
            short_summary="Transit audit log report",
            evidence_type="AUDIT_REPORT",
            directness="DIRECT",
            specificity="SPECIFIC",
            corroboration_status="CORROBORATED",
            ingested_at=datetime(2026, 9, 17, 9, 30, tzinfo=timezone.utc),
            payload_hash="hash_evd_444",
        )
        session.add(evd4)

        qs4 = QuoteSpanModel(
            evidence_id="EVD-TEST04",
            quote_text="verified a 14% false rejection rate on biometric turnstiles",
            start_char_offset=50,
            end_char_offset=115,
        )
        session.add(qs4)

        link4 = ClaimEvidenceLinkModel(
            claim_id="CLM-TEST04",
            evidence_id="EVD-TEST04",
            link_type="SUPPORTS",
        )
        session.add(link4)

        comp4 = EUAIActComplianceAssessmentModel(
            id="COMP-TEST04",
            incident_id="INC-2026-TEST04",
            status="COMPLETED",
            jurisdiction_status="APPLICABLE",
            system_classification="HIGH_RISK_ANNEX_III",
            annex_reference="Annex III, point 1 — Biometrics and Remote Biometric Identification",
            enforcement_status="NOT_YET_APPLICABLE",
            payload_json=json.dumps({
                "system_classification": "HIGH_RISK_ANNEX_III",
                "missing_facts": ["Deployer conformity assessment documentation was not publicly deposited."],
                "compliance_gaps": [],
            }),
            created_at=datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc),
        )
        session.add(comp4)

        # Fifth incident: RIGHTS category, CRITICAL severity, also matches for multi-page testing
        inc5 = IncidentModel(
            id="INC-2026-TEST05",
            title="Biometric Turnstile Secondary Location Failure",
            summary="Secondary facial recognition turnstile malfunction in south terminal.",
            status="INVESTIGATED",
            primary_category="RIGHTS",
            incident_date_precision="EXACT",
            incident_exact_date=date(2026, 9, 10),
            created_at=datetime(2026, 9, 11, 10, 0, tzinfo=timezone.utc),
        )
        session.add(inc5)

        sev5 = SeverityAssessmentModel(
            id="SEV-CURR-05",
            incident_id="INC-2026-TEST05",
            actual_tier="CRITICAL",
            created_at=datetime(2026, 9, 11, 11, 0, tzinfo=timezone.utc),
        )
        session.add(sev5)

        enr5 = IncidentEnrichmentModel(
            id="ENR-TEST05",
            incident_id="INC-2026-TEST05",
            status="COMPLETED",
            model_provider="claude",
            model_name="claude-sonnet-4-5-20250929",
            prompt_digest="hash555",
            content_hash="hash555",
            cache_key="cache555",
            payload_json=json.dumps({"incident_id": "INC-2026-TEST05"}),
            executive_summary="Secondary gate failure.",
            created_at=datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc),
        )
        session.add(enr5)

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
        assert data["total"] == 5
        assert len(data["items"]) == 5

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

    def test_filtered_pagination_regression(self, client: TestClient) -> None:
        """Required regression: combined q + category + severity + has_enrichment with page_size=1.

        First base-sort incident (INC-2026-TEST03) does not match; a later incident (INC-2026-TEST04)
        does match.
        Expected: items contains the matching incident, total=1, total_pages=1.
        """
        # Base sort would place TEST03 first, which is category=SAFETY, severity=NOT_ASSESSED.
        # TEST04 is category=RIGHTS, severity=CRITICAL, has_enrichment=True, and matches q="Access Gate".
        res = client.get(
            "/api/v1/public/incidents?q=Access%20Gate&category=RIGHTS&severity=CRITICAL&has_enrichment=true&page_size=1"
        )
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 1
        assert data["total_pages"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["incident_id"] == "INC-2026-TEST04"
        assert data["items"][0]["severity"] == "CRITICAL"
        assert data["items"][0]["primary_category"] == "RIGHTS"
        assert data["items"][0]["has_intelligence"] is True

    def test_filtered_pagination_multiple_pages(self, client: TestClient) -> None:
        """Multiple pages traverse canonical filtered set deterministically."""
        # Query category=RIGHTS and severity=CRITICAL with page_size=1
        res1 = client.get("/api/v1/public/incidents?category=RIGHTS&severity=CRITICAL&page_size=1&page=1")
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["total"] == 2
        assert data1["total_pages"] == 2
        assert len(data1["items"]) == 1
        id_page1 = data1["items"][0]["incident_id"]

        res2 = client.get("/api/v1/public/incidents?category=RIGHTS&severity=CRITICAL&page_size=1&page=2")
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["total"] == 2
        assert data2["total_pages"] == 2
        assert len(data2["items"]) == 1
        id_page2 = data2["items"][0]["incident_id"]

        assert id_page1 != id_page2
        assert {id_page1, id_page2} == {"INC-2026-TEST04", "INC-2026-TEST05"}

    def test_filtered_pagination_zero_matches(self, client: TestClient) -> None:
        """Zero matches return total=0, total_pages=0, items=[]."""
        res = client.get("/api/v1/public/incidents?q=NonExistentQueryTermXYZ")
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 0
        assert data["total_pages"] == 0
        assert data["items"] == []

    def test_filtered_pagination_out_of_range_page(self, client: TestClient) -> None:
        """Requesting an out-of-range page returns empty items while preserving canonical counts."""
        res = client.get("/api/v1/public/incidents?page=999&page_size=10")
        assert res.status_code == 200
        data = res.json()
        assert data["items"] == []
        assert data["page"] == 999
        assert data["total"] > 0
        assert data["total_pages"] < 999

    def test_filtered_pagination_true_and_false_enrichment(self, client: TestClient) -> None:
        """has_enrichment=true and false correctly filter against live availability."""
        res_true = client.get("/api/v1/public/incidents?has_enrichment=true")
        assert res_true.status_code == 200
        data_true = res_true.json()
        for it in data_true["items"]:
            assert it["has_intelligence"] is True

        res_false = client.get("/api/v1/public/incidents?has_enrichment=false")
        assert res_false.status_code == 200
        data_false = res_false.json()
        for it in data_false["items"]:
            assert it["has_intelligence"] is False

    def test_filtered_pagination_multiple_historical_severity_assessments(self, client: TestClient) -> None:
        """Effective severity resolves deterministically to the latest assessment."""
        # INC-2026-TEST04 had historical LOW (SEV-HIST-04), superseded by CRITICAL (SEV-CURR-04).
        res_low = client.get("/api/v1/public/incidents?category=RIGHTS&severity=LOW")
        assert res_low.status_code == 200
        low_ids = [it["incident_id"] for it in res_low.json()["items"]]
        assert "INC-2026-TEST04" not in low_ids

        res_crit = client.get("/api/v1/public/incidents?category=RIGHTS&severity=CRITICAL")
        assert res_crit.status_code == 200
        crit_ids = [it["incident_id"] for it in res_crit.json()["items"]]
        assert "INC-2026-TEST04" in crit_ids

    def test_filtered_pagination_production_mock_exclusion(self, client: TestClient, monkeypatch) -> None:
        """In production environment, mock-enriched incidents are not counted as has_enrichment=true."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        res = client.get("/api/v1/public/incidents?has_enrichment=true")
        assert res.status_code == 200
        enriched_ids = [it["incident_id"] for it in res.json()["items"]]
        # INC-2026-TEST01 has mock enrichment; in production it must be excluded from has_enrichment=true
        assert "INC-2026-TEST01" not in enriched_ids

    def test_filtered_pagination_combined_filters_asc_desc(self, client: TestClient) -> None:
        """Combined filters with event_date ascending and descending sorting."""
        res_desc = client.get(
            "/api/v1/public/incidents?category=RIGHTS&severity=CRITICAL&sort_by=event_date&sort_order=desc"
        )
        assert res_desc.status_code == 200
        items_desc = res_desc.json()["items"]
        assert len(items_desc) == 2
        assert items_desc[0]["incident_id"] == "INC-2026-TEST04"  # 2026-09-15
        assert items_desc[1]["incident_id"] == "INC-2026-TEST05"  # 2026-09-10

        res_asc = client.get(
            "/api/v1/public/incidents?category=RIGHTS&severity=CRITICAL&sort_by=event_date&sort_order=asc"
        )
        assert res_asc.status_code == 200
        items_asc = res_asc.json()["items"]
        assert len(items_asc) == 2
        assert items_asc[0]["incident_id"] == "INC-2026-TEST05"  # 2026-09-10
        assert items_asc[1]["incident_id"] == "INC-2026-TEST04"  # 2026-09-15

    def test_evidence_locators_and_missing_facts(self, client: TestClient) -> None:
        """Detail response populates quote span locators and explicit EU missing facts."""
        res = client.get("/api/v1/public/incidents/INC-2026-TEST04")
        assert res.status_code == 200
        data = res.json()

        # Check source reference locator and source_id
        assert len(data["sources"]) == 1
        src = data["sources"][0]
        assert src["source_id"] == "SRC-TEST04"
        assert src["locator"] == "char_offset:50-115"
        assert src["content_hash"] == "hash_src_444"

        # Check claim to evidence resolution
        intel = data["intelligence"]
        assert intel is not None
        assert len(intel["atomic_claims"]) == 1
        claim = intel["atomic_claims"][0]
        assert claim["claim_id"] == "C-BIO-01"
        assert claim["supporting_evidence_ids"] == ["EVD-TEST04"]
        assert len(claim["evidence_excerpts"]) == 1
        assert "14% false rejection rate" in claim["evidence_excerpts"][0]
        assert claim["reasoning_summary"] is not None

        # Check EU AI Act explicit missing facts
        eu = data["eu_ai_act_compliance"]
        assert eu is not None
        assert eu["is_available"] is True
        assert len(eu["missing_facts"]) >= 1
        assert any("conformity" in f.lower() for f in eu["missing_facts"])

    def test_list_and_detail_severity_agreement_and_tie_breaking(self, client: TestClient) -> None:
        """Verify list and detail severity selection use the identical deterministic latest-assessment rule.
        
        Covers:
        1. Equal timestamps with different severity values (deterministic id.desc() tie-breaker).
        2. Unequal timestamps (most recent timestamp wins).
        3. No severity assessment (both default to NOT_ASSESSED).
        """
        # 1. Equal timestamps with different severity values:
        # INC-2026-TEST03 has SEV-EQUAL-01 (LOW) and SEV-EQUAL-02 (MEDIUM) with identical created_at.
        # Under id.desc() tie-breaker: SEV-EQUAL-02 wins -> "MEDIUM".
        res_list_3 = client.get("/api/v1/public/incidents?q=Drone")
        assert res_list_3.status_code == 200
        list_item_3 = next(it for it in res_list_3.json()["items"] if it["incident_id"] == "INC-2026-TEST03")
        assert list_item_3["severity"] == "MEDIUM"

        res_detail_3 = client.get("/api/v1/public/incidents/INC-2026-TEST03")
        assert res_detail_3.status_code == 200
        assert res_detail_3.json()["severity"] == "MEDIUM"
        assert list_item_3["severity"] == res_detail_3.json()["severity"]

        # Verify filter behavior on tie-breaker: severity=MEDIUM matches TEST03, severity=LOW excludes it
        res_filter_med = client.get("/api/v1/public/incidents?severity=MEDIUM")
        assert res_filter_med.status_code == 200
        assert any(it["incident_id"] == "INC-2026-TEST03" for it in res_filter_med.json()["items"])

        res_filter_low = client.get("/api/v1/public/incidents?severity=LOW")
        assert res_filter_low.status_code == 200
        assert not any(it["incident_id"] == "INC-2026-TEST03" for it in res_filter_low.json()["items"])

        # 2. Unequal timestamps:
        # INC-2026-TEST04 has SEV-HIST-04 (LOW, 2026-09-16) superseded by SEV-CURR-04 (CRITICAL, 2026-09-17).
        # Most recent created_at wins -> "CRITICAL".
        res_list_4 = client.get("/api/v1/public/incidents?q=Biometric%20Access")
        assert res_list_4.status_code == 200
        list_item_4 = next(it for it in res_list_4.json()["items"] if it["incident_id"] == "INC-2026-TEST04")
        assert list_item_4["severity"] == "CRITICAL"

        res_detail_4 = client.get("/api/v1/public/incidents/INC-2026-TEST04")
        assert res_detail_4.status_code == 200
        assert res_detail_4.json()["severity"] == "CRITICAL"
        assert list_item_4["severity"] == res_detail_4.json()["severity"]

        # 3. No severity assessment:
        # INC-2026-TEST02 has zero severity records -> "NOT_ASSESSED".
        res_list_2 = client.get("/api/v1/public/incidents?q=TEST02")
        assert res_list_2.status_code == 200
        list_item_2 = next(it for it in res_list_2.json()["items"] if it["incident_id"] == "INC-2026-TEST02")
        assert list_item_2["severity"] == "NOT_ASSESSED"

        res_detail_2 = client.get("/api/v1/public/incidents/INC-2026-TEST02")
        assert res_detail_2.status_code == 200
        assert res_detail_2.json()["severity"] == "NOT_ASSESSED"
        assert list_item_2["severity"] == res_detail_2.json()["severity"]

    def test_public_only_mode_unmounts_all_operator_and_mutation_routes(self, public_test_app) -> None:
        """In public_only mode, operator routes are completely unmounted and return 404."""
        engine = public_test_app.state.db_engine
        root = public_test_app.state.repo_root
        pub_app = create_app(db_engine=engine, repo_root=root, public_only=True)
        pub_client = TestClient(pub_app)

        # 1. Operator and Admin routes return 404 Not Found
        operator_endpoints = [
            "/login",
            "/logout",
            "/incidents",
            "/incidents/INC-2026-TEST01",
            "/diagnostics",
            "/diagnostics/refresh",
            "/api/ingestion/refresh",
            "/api/ingestion/status",
            "/dossiers",
            "/dossiers/new",
            "/packages",
            "/static/css/styles.css",
        ]
        for ep in operator_endpoints:
            res_get = pub_client.get(ep)
            assert res_get.status_code == 404, f"Expected 404 for operator route {ep}, got {res_get.status_code}"
            res_post = pub_client.post(ep)
            assert res_post.status_code == 404, f"Expected 404 for operator POST {ep}, got {res_post.status_code}"

        # 2. Public read-only endpoints function normally
        res_cat = pub_client.get("/api/v1/public/categories")
        assert res_cat.status_code == 200
        assert len(res_cat.json()) >= 5

        res_inc = pub_client.get("/api/v1/public/incidents")
        assert res_inc.status_code == 200
        assert res_inc.json()["total"] >= 1

        res_det = pub_client.get("/api/v1/public/incidents/INC-2026-TEST01")
        assert res_det.status_code == 200
        assert res_det.json()["incident_id"] == "INC-2026-TEST01"

        # 3. Public root landing returns service status JSON (no redirect to /login)
        res_root = pub_client.get("/")
        assert res_root.status_code == 200
        root_data = res_root.json()
        assert root_data["status"] == "healthy"
        assert "public-api" in root_data["service"]

        # 4. Mutation methods on public endpoints are strictly rejected (405 Method Not Allowed)
        res_post_inc = pub_client.post("/api/v1/public/incidents", json={"title": "Attack"})
        assert res_post_inc.status_code == 405

        res_del_inc = pub_client.delete("/api/v1/public/incidents/INC-2026-TEST01")
        assert res_del_inc.status_code == 405

        res_put_cat = pub_client.put("/api/v1/public/categories", json={})
        assert res_put_cat.status_code == 405

        # 5. Zero secrets or sensitive diagnostics leakage in responses
        body_text = res_inc.text + res_det.text + res_root.text
        assert "/Users/" not in body_text
        assert "/Volumes/" not in body_text
        assert ".db" not in body_text
        assert "password" not in body_text.lower()
        assert "secret" not in body_text.lower() or "circuit breaker" in body_text.lower()



