"""Unit tests for Incident Explorer routes, pagination, epistemic claims, and read-only guarantees.

Governing Charter: Project Constitution (Rules 1, 2, 3, 4, 10, 14, 15, 16),
PRD §2 (UIX-001, UIX-003, AUD-001, AUD-002), Phase 8A Plan.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from ai_incident_monitor.db.base import Base
from ai_incident_monitor.db.models.claim import ClaimRecordModel
from ai_incident_monitor.db.models.evidence import ClaimEvidenceLinkModel, EvidenceRecordModel
from ai_incident_monitor.db.models.incident import IncidentModel
from ai_incident_monitor.db.models.source import SourceReferenceModel
from ai_incident_monitor.ui.app import create_app
from ai_incident_monitor.ui.auth import LocalCredentialManager, ServerSessionManager, SESSION_COOKIE_NAME


@pytest.fixture
def sqlite_test_engine(tmp_path: Path):
    """Create an isolated SQLite database and build the complete relational schema."""
    db_file = tmp_path / "test_ui.db"
    engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def test_setup(sqlite_test_engine, tmp_path: Path):
    """Seed test incidents and claims into the isolated database."""
    cred_file = tmp_path / ".operator_credential"
    cred_mgr = LocalCredentialManager(storage_path=cred_file)
    valid_credential = cred_mgr.generate_or_load_credential()
    sess_mgr = ServerSessionManager()

    # Seed 5 sample incidents
    with Session(sqlite_test_engine) as session:
        # Source 1 (Safe)
        src_safe = SourceReferenceModel(
            id="src_safe_01",
            title="Safe Journal Article",
            publisher="AI Safety Institute",
            url="https://example.com/safe-source",
            source_type="RESEARCH_PAPER",
            retrieval_date=datetime.now(timezone.utc),
            access_status="PUBLIC",
            authority="HIGH",
            reliability="HIGH",
            independence="HIGH",
            content_hash="a" * 64,
        )
        # Source 2 (Dangerous javascript URL)
        src_danger = SourceReferenceModel(
            id="src_danger_02",
            title="Dangerous Link Source",
            publisher="Untrusted Blog",
            url="javascript:alert(document.cookie)",
            source_type="BLOG_POST",
            retrieval_date=datetime.now(timezone.utc),
            access_status="PUBLIC",
            authority="LOW",
            reliability="LOW",
            independence="LOW",
            content_hash="b" * 64,
        )
        session.add_all([src_safe, src_danger])

        # Incident 1: Comprehensive Epistemic Breakdown
        inc1 = IncidentModel(
            id="INC-2026-0001",
            title="Autonomous Trading System Flash Loss <script>alert('xss')</script>",
            summary="Autonomous execution logic caused high-frequency order cancellation cascades.",
            status="VERIFIED",
        )
        session.add(inc1)

        # Evidence records
        ev1 = EvidenceRecordModel(
            id="ev_001",
            source_id="src_safe_01",
            short_summary="Direct log corroboration of execution orders.",
            evidence_type="SYSTEM_LOG",
            directness="DIRECT",
            specificity="SPECIFIC",
            corroboration_status="CORROBORATED",
            ingested_at=datetime.now(timezone.utc),
            payload_hash="c" * 64,
        )
        ev2 = EvidenceRecordModel(
            id="ev_002",
            source_id="src_danger_02",
            short_summary="Blog assertion with dangerous link.",
            evidence_type="MEDIA_REPORT",
            directness="INDIRECT",
            specificity="VAGUE",
            corroboration_status="UNVERIFIED",
            ingested_at=datetime.now(timezone.utc),
            payload_hash="d" * 64,
        )
        session.add_all([ev1, ev2])

        # Claims for Incident 1 (Facts, Allegations, Uncertainties, Disputes)
        c_fact = ClaimRecordModel(
            id="clm_001",
            incident_id="INC-2026-0001",
            claim_text="Order cancellation volume surged by 450% in 12 seconds.",
            claim_type="CONFIRMED_FACT",
            epistemic_status="CONFIRMED",
            confidence="HIGH",
            materiality="HIGH",
            is_causal_claim=True,
        )
        c_allegation = ClaimRecordModel(
            id="clm_002",
            incident_id="INC-2026-0001",
            claim_text="Trading desk ignored internal latency alerts prior to market open.",
            claim_type="UNVERIFIED_ALLEGATION",
            epistemic_status="UNVERIFIED",
            confidence="LOW",
            materiality="MEDIUM",
        )
        c_uncertainty = ClaimRecordModel(
            id="clm_003",
            incident_id="INC-2026-0001",
            claim_text="Exact net dollar loss remains uncalculated by exchange.",
            claim_type="UNCERTAINTY",
            epistemic_status="UNKNOWN",
            confidence="LOW",
            materiality="HIGH",
        )
        c_dispute = ClaimRecordModel(
            id="clm_004",
            incident_id="INC-2026-0001",
            claim_text="Exchange disputed broker claims that network hardware failed.",
            claim_type="DISPUTED",
            epistemic_status="CONTESTED",
            confidence="MEDIUM",
            materiality="HIGH",
        )
        session.add_all([c_fact, c_allegation, c_uncertainty, c_dispute])

        # Evidence links
        link1 = ClaimEvidenceLinkModel(
            claim_id="clm_001",
            evidence_id="ev_001",
            link_type="SUPPORTING",
        )
        link2 = ClaimEvidenceLinkModel(
            claim_id="clm_002",
            evidence_id="ev_002",
            link_type="SUPPORTING",
        )
        session.add_all([link1, link2])

        # Seed additional incidents for pagination testing
        for i in range(2, 6):
            inc = IncidentModel(
                id=f"INC-2026-000{i}",
                title=f"Sample Test Incident {i}",
                summary=f"Summary for sample incident {i}.",
                status="NEW" if i % 2 == 0 else "UNDER_INVESTIGATION",
            )
            session.add(inc)

        session.commit()

    app = create_app(
        db_engine=sqlite_test_engine,
        repo_root=tmp_path,
        credential_manager=cred_mgr,
        session_manager=sess_mgr,
    )
    client = TestClient(app, raise_server_exceptions=False)
    return {
        "client": client,
        "cred_mgr": cred_mgr,
        "sess_mgr": sess_mgr,
        "credential": valid_credential,
        "engine": sqlite_test_engine,
    }


class TestIncidentRoutes:
    """Validate incident listing, filtering, detail inspection, and read-only behavior."""

    def test_unauthenticated_access_redirects_to_login(self, test_setup) -> None:
        client = test_setup["client"]
        res = client.get("/incidents", follow_redirects=False)
        assert res.status_code == 303
        assert res.headers["location"] == "/login"

    def test_authenticated_login_flow_and_listing(self, test_setup) -> None:
        client = test_setup["client"]
        cred = test_setup["credential"]

        # 1. Fetch login page to retrieve login CSRF cookie
        login_page_res = client.get("/login")
        assert login_page_res.status_code == 200
        csrf_cookie = login_page_res.cookies.get("aig_login_csrf")
        assert csrf_cookie is not None

        # 2. Submit credentials with matching CSRF token
        login_res = client.post(
            "/login",
            data={"credential": cred, "csrf_token": csrf_cookie},
            follow_redirects=False,
        )
        assert login_res.status_code == 303
        assert login_res.headers["location"] == "/incidents"
        session_cookie = login_res.cookies.get(SESSION_COOKIE_NAME)
        assert session_cookie is not None

        # 3. Access incidents list with session cookie
        incidents_res = client.get("/incidents")
        assert incidents_res.status_code == 200
        assert "Incidents Explorer" in incidents_res.text
        assert "INC-2026-0001" in incidents_res.text
        assert "LOCAL DEVELOPMENT MODE" in incidents_res.text

    def test_incident_status_filtering_and_pagination(self, test_setup) -> None:
        client = test_setup["client"]
        sess_mgr = test_setup["sess_mgr"]
        session = sess_mgr.create_session()
        client.cookies.set(SESSION_COOKIE_NAME, session.session_id)

        # Filter by status=VERIFIED (only 1 incident)
        res_filtered = client.get("/incidents?status=VERIFIED")
        assert res_filtered.status_code == 200
        assert "INC-2026-0001" in res_filtered.text
        assert "INC-2026-0002" not in res_filtered.text

        # Pagination: page_size=2
        res_p1 = client.get("/incidents?page=1&page_size=2")
        assert res_p1.status_code == 200
        assert "Showing Page 1" in res_p1.text

        res_p2 = client.get("/incidents?page=2&page_size=2")
        assert res_p2.status_code == 200
        assert "Showing Page 2" in res_p2.text

    def test_incident_detail_epistemic_claims_breakdown(self, test_setup) -> None:
        client = test_setup["client"]
        sess_mgr = test_setup["sess_mgr"]
        session = sess_mgr.create_session()
        client.cookies.set(SESSION_COOKIE_NAME, session.session_id)

        res = client.get("/incidents/INC-2026-0001")
        assert res.status_code == 200

        # Facts
        assert "Confirmed Facts" in res.text
        assert "Order cancellation volume surged" in res.text
        assert "[CAUSAL]" in res.text

        # Allegations
        assert "Attributed Allegations" in res.text
        assert "Trading desk ignored internal latency alerts" in res.text

        # Uncertainties
        assert "Technical Uncertainties" in res.text
        assert "Exact net dollar loss remains uncalculated" in res.text

        # Disputes
        assert "Disputed Facts" in res.text
        assert "Exchange disputed broker claims" in res.text

        # Safe link rendered
        assert "https://example.com/safe-source" in res.text

        # Dangerous link sanitized (javascript: scheme not rendered as link)
        assert 'href="javascript:' not in res.text

        # XSS injection in incident title escaped
        assert "<script>alert('xss')</script>" not in res.text
        assert "&lt;script&gt;alert(&#39;xss&#39;)&lt;/script&gt;" in res.text or "&lt;script&gt;" in res.text

    def test_invalid_incident_id_returns_404(self, test_setup) -> None:
        client = test_setup["client"]
        sess_mgr = test_setup["sess_mgr"]
        session = sess_mgr.create_session()
        client.cookies.set(SESSION_COOKIE_NAME, session.session_id)

        # Malformed ID
        res_malformed = client.get("/incidents/invalid..id!")
        assert res_malformed.status_code == 404

        # Non-existent ID
        res_nonexistent = client.get("/incidents/INC-NONEXISTENT-999")
        assert res_nonexistent.status_code == 404

    def test_read_only_guarantee_no_mutations_occur(self, test_setup) -> None:
        client = test_setup["client"]
        sess_mgr = test_setup["sess_mgr"]
        engine = test_setup["engine"]
        session = sess_mgr.create_session()
        client.cookies.set(SESSION_COOKIE_NAME, session.session_id)

        # Snapshot row counts
        with Session(engine) as s:
            initial_incidents = s.scalar(select(func.count(IncidentModel.id)))
            initial_claims = s.scalar(select(func.count(ClaimRecordModel.id)))

        # Navigate through multiple pages
        client.get("/incidents")
        client.get("/incidents/INC-2026-0001")
        client.get("/incidents?status=NEW")

        # Verify row counts unchanged
        with Session(engine) as s:
            final_incidents = s.scalar(select(func.count(IncidentModel.id)))
            final_claims = s.scalar(select(func.count(ClaimRecordModel.id)))

        assert initial_incidents == final_incidents
        assert initial_claims == final_claims
