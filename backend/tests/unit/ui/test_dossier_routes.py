"""Unit tests for Editorial Dossier Workbench, Validation & Review routes (Phase 8B).

Governing Charter: Project Constitution (Rules 1, 4, 12, 14, 15, 16),
PRD §2 (UIX-001, UIX-002, UIX-003, AUD-001, AUD-002), Phase 8B Plan.
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
from ai_incident_monitor.db.models.editorial import (
    EditorialDossierModel,
    EditorialDossierReviewModel,
)
from ai_incident_monitor.db.models.evidence import ClaimEvidenceLinkModel, EvidenceRecordModel
from ai_incident_monitor.db.models.incident import IncidentModel
from ai_incident_monitor.db.models.source import SourceReferenceModel
from ai_incident_monitor.db.models.uncertainty import UncertaintyRecordModel
from ai_incident_monitor.editorial.enums import EditorialDossierStatus, EditorialScopeType
from ai_incident_monitor.editorial.models import EDITORIAL_ATTESTATION_STATEMENT
from ai_incident_monitor.repositories.editorial_repo import EditorialRepository
from ai_incident_monitor.ui.app import create_app
from ai_incident_monitor.ui.auth import (
    LocalCredentialManager,
    ServerSessionManager,
    SESSION_COOKIE_NAME,
)
from ai_incident_monitor.ui.reviewer_auth import (
    ReviewerKeystore,
    ReviewerRateLimiter,
)


@pytest.fixture
def sqlite_test_engine(tmp_path: Path):
    """Create an isolated SQLite database and build the complete relational schema."""
    db_file = tmp_path / "test_dossiers_ui.db"
    engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def dossier_test_setup(sqlite_test_engine, tmp_path: Path):
    """Seed test incidents and reviewers into isolated environment."""
    cred_file = tmp_path / ".operator_credential"
    cred_mgr = LocalCredentialManager(storage_path=cred_file)
    cred_mgr.generate_or_load_credential()
    sess_mgr = ServerSessionManager()

    # Enrolled reviewer
    keystore_path = tmp_path / ".reviewers.json"
    keystore = ReviewerKeystore(storage_path=keystore_path)
    reviewer_rec, reviewer_key = keystore.enroll_reviewer(
        reviewer_id="ebe",
        reviewer_name="Ebe Rolston",
        reviewer_role="Lead Editor",
    )

    # Seed data
    with Session(sqlite_test_engine) as session:
        # Source
        src = SourceReferenceModel(
            id="src_01",
            title="AI Trading Flash Crash Report",
            publisher="Market Oversight Board",
            url="https://example.com/trading-crash",
            source_type="INVESTIGATIVE_REPORT",
            retrieval_date=datetime.now(timezone.utc),
            access_status="PUBLIC",
            authority="HIGH",
            reliability="HIGH",
            independence="HIGH",
            content_hash="a" * 64,
        )
        session.add(src)

        # Incident 1 (Eligible - with evidence)
        inc1 = IncidentModel(
            id="INC-2026-0001",
            title="High-Frequency Algorithm Cascading Selloff",
            summary="Autonomous order cancellation triggered cascading circuit breakers across trading venues.",
            status="VERIFIED",
            incident_exact_date=datetime(2026, 3, 15, tzinfo=timezone.utc),
        )
        session.add(inc1)

        # Evidence for Inc 1
        ev1 = EvidenceRecordModel(
            id="ev_01",
            source_id="src_01",
            short_summary="Order cancellation volume surged to 400,000 orders/sec within 200 milliseconds.",
            evidence_type="DIRECT_OBSERVATION",
            directness="DIRECT",
            specificity="SPECIFIC",
            corroboration_status="CORROBORATED",
            ingested_at=datetime.now(timezone.utc),
            payload_hash="c" * 64,
        )
        session.add(ev1)

        # Claim for Inc 1
        claim1 = ClaimRecordModel(
            id="claim_01",
            incident_id="INC-2026-0001",
            claim_text="Rapid automated cancellation exhausted order book liquidity.",
            claim_type="CONFIRMED_FACT",
            epistemic_status="CONFIRMED",
            confidence="HIGH",
            materiality="HIGH",
            is_causal_claim=True,
        )
        session.add(claim1)

        # Link claim to evidence
        link1 = ClaimEvidenceLinkModel(
            claim_id="claim_01",
            evidence_id="ev_01",
            link_type="SUPPORTING",
        )
        session.add(link1)

        # Incident 2 (Eligible - with evidence)
        inc2 = IncidentModel(
            id="INC-2026-0002",
            title="Autonomous Freight Braking Disconnection",
            summary="Sensor confusion during heavy precipitation led to automatic brake release on freight locomotive.",
            status="ANALYZED",
            incident_exact_date=datetime(2026, 4, 10, tzinfo=timezone.utc),
        )
        session.add(inc2)

        ev2 = EvidenceRecordModel(
            id="ev_02",
            source_id="src_01",
            short_summary="Locomotive telemetry indicated radar signal attenuation above 85% prior to brake release.",
            evidence_type="LOG_FILE",
            directness="DIRECT",
            specificity="SPECIFIC",
            corroboration_status="CORROBORATED",
            ingested_at=datetime.now(timezone.utc),
            payload_hash="d" * 64,
        )
        session.add(ev2)

        claim2 = ClaimRecordModel(
            id="claim_02",
            incident_id="INC-2026-0002",
            claim_text="Brake pressure dropped to zero during severe rain conditions.",
            claim_type="CONFIRMED_FACT",
            epistemic_status="CONFIRMED",
            confidence="HIGH",
            materiality="HIGH",
            is_causal_claim=True,
        )
        session.add(claim2)

        link2 = ClaimEvidenceLinkModel(
            claim_id="claim_02",
            evidence_id="ev_02",
            link_type="SUPPORTING",
        )
        session.add(link2)

        # Incident 3 (Ineligible - zero evidence linked)
        inc3 = IncidentModel(
            id="INC-2026-0003",
            title="Unsubstantiated Social Media Rumor",
            summary="Uncorroborated claims of autonomous drone collision.",
            status="NEW",
        )
        session.add(inc3)

        session.commit()

    rev_limiter = ReviewerRateLimiter()
    app = create_app(
        db_engine=sqlite_test_engine,
        repo_root=tmp_path,
        credential_manager=cred_mgr,
        session_manager=sess_mgr,
        reviewer_keystore=keystore,
        reviewer_rate_limiter=rev_limiter,
    )
    client = TestClient(app)

    return {
        "client": client,
        "sess_mgr": sess_mgr,
        "keystore": keystore,
        "reviewer_rec": reviewer_rec,
        "reviewer_key": reviewer_key,
        "engine": sqlite_test_engine,
        "tmp_path": tmp_path,
    }


class TestDossierWorkbenchRoutes:
    """Test suite covering Phase 8B Dossier Workbench web routes and workflows."""

    def test_unauthenticated_dossier_routes_redirect_to_login(self, dossier_test_setup) -> None:
        """Unauthenticated requests to any dossier route redirect to /login."""
        client = dossier_test_setup["client"]

        assert client.get("/dossiers", follow_redirects=False).status_code == 303
        assert client.get("/dossiers/new", follow_redirects=False).status_code == 303
        assert client.get("/dossiers/dos_123", follow_redirects=False).status_code == 303
        assert client.get("/dossiers/dos_123/review", follow_redirects=False).status_code == 303

    def test_candidate_selection_without_per_incident_approval(self, dossier_test_setup) -> None:
        """Candidate selector renders eligible and ineligible incidents without per-incident human sign-off."""
        client = dossier_test_setup["client"]
        sess_mgr = dossier_test_setup["sess_mgr"]
        session = sess_mgr.create_session()
        client.cookies.set(SESSION_COOKIE_NAME, session.session_id)

        res = client.get("/dossiers/new")
        assert res.status_code == 200
        assert "Candidate Incident Selector" in res.text
        assert "INC-2026-0001" in res.text
        assert "INC-2026-0002" in res.text

        # Ineligible incident is listed under exclusion accordion
        assert "INC-2026-0003" in res.text
        assert "zero evidence" in res.text.lower() or "ineligible" in res.text.lower()

    def test_assemble_draft_dossier_and_inspection(self, dossier_test_setup) -> None:
        """Assembling draft dossier creates DRAFT version and redirects to detail inspection."""
        client = dossier_test_setup["client"]
        sess_mgr = dossier_test_setup["sess_mgr"]
        session = sess_mgr.create_session()
        client.cookies.set(SESSION_COOKIE_NAME, session.session_id)

        # 1. Post to create dossier
        post_data = {
            "title": "Autonomous Systems Failure Review Q1 2026",
            "scope_type": "CUSTOM",
            "incident_ids": ["INC-2026-0001", "INC-2026-0002"],
            "methodology_notes": "Compiled under deterministic assembly rules.",
            "csrf_token": session.csrf_token,
        }
        res_post = client.post("/dossiers", data=post_data, follow_redirects=False)
        assert res_post.status_code == 303
        redirect_url = res_post.headers["location"]
        assert redirect_url.startswith("/dossiers/dossier_")

        # 2. Inspect created dossier
        res_detail = client.get(redirect_url)
        assert res_detail.status_code == 200
        assert "Autonomous Systems Failure Review Q1 2026" in res_detail.text
        assert ("DRAFT" in res_detail.text or "ASSEMBLED" in res_detail.text)
        assert "v1" in res_detail.text
        assert "INC-2026-0001" in res_detail.text
        assert "INC-2026-0002" in res_detail.text
        assert "Confirmed Facts" in res_detail.text
        assert "Validation Findings" in res_detail.text
        assert "Preview Artifacts" in res_detail.text
        assert "Create New Revision (Supersede)" in res_detail.text

    def test_csrf_protection_on_all_state_changing_actions(self, dossier_test_setup) -> None:
        """Missing or forged CSRF tokens reject state-changing POST requests with 403 Forbidden."""
        client = dossier_test_setup["client"]
        sess_mgr = dossier_test_setup["sess_mgr"]
        session = sess_mgr.create_session()
        client.cookies.set(SESSION_COOKIE_NAME, session.session_id)

        # Bad CSRF token
        bad_post = client.post(
            "/dossiers",
            data={"title": "Test", "incident_ids": ["INC-2026-0001"], "csrf_token": "forged_csrf_token"},
        )
        assert bad_post.status_code == 403

    def test_legacy_editorial_review_endpoints_return_410_gone(self, dossier_test_setup) -> None:
        """Legacy review and approval endpoints return 410 Gone under the design correction."""
        client = dossier_test_setup["client"]
        sess_mgr = dossier_test_setup["sess_mgr"]
        session = sess_mgr.create_session()
        client.cookies.set(SESSION_COOKIE_NAME, session.session_id)

        # 1. Assemble draft dossier
        res_create = client.post(
            "/dossiers",
            data={
                "title": "Financial Algorithms Liability Synthesis",
                "scope_type": "CUSTOM",
                "incident_ids": ["INC-2026-0001"],
                "csrf_token": session.csrf_token,
            },
            follow_redirects=False,
        )
        dossier_url = res_create.headers["location"]
        dossier_id = dossier_url.split("/")[-1]

        # 2. Legacy submit returns 410 Gone
        res_submit = client.post(
            f"/dossiers/{dossier_id}/submit",
            data={"csrf_token": session.csrf_token},
            follow_redirects=False,
        )
        assert res_submit.status_code == 410
        assert "retired under design correction" in res_submit.json()["detail"]

        # 3. Legacy review returns 410 Gone
        res_review = client.get(f"/dossiers/{dossier_id}/review")
        assert res_review.status_code == 410
        assert "retired under design correction" in res_review.json()["detail"]

        # 4. Legacy approve returns 410 Gone
        res_approve = client.post(
            f"/dossiers/{dossier_id}/approve",
            data={
                "reviewer_id": "ebe",
                "reviewer_key": "some_key",
                "expected_version": 1,
                "expected_content_hash": "a" * 64,
                "statement_confirmed": "true",
                "csrf_token": session.csrf_token,
            },
        )
        assert res_approve.status_code == 410
        assert "retired under design correction" in res_approve.json()["detail"]

        # 5. Legacy reject returns 410 Gone
        res_reject = client.post(
            f"/dossiers/{dossier_id}/reject",
            data={"rejection_reason": "Testing rejection retirement", "csrf_token": session.csrf_token},
        )
        assert res_reject.status_code == 410
        assert "retired under design correction" in res_reject.json()["detail"]

        # 6. Verify zero approval records created in db
        engine = dossier_test_setup["engine"]
        with Session(engine) as s:
            repo = EditorialRepository(s)
            dos = repo.get_dossier(dossier_id)
            assert dos.status.value in ["DRAFT", "ASSEMBLED"]
            assert dos.reviewed_by is None

    def test_supersede_lifecycle(self, dossier_test_setup) -> None:
        """Superseding a dossier creates a new v2 DRAFT and marks v1 SUPERSEDED without approval gates."""
        client = dossier_test_setup["client"]
        sess_mgr = dossier_test_setup["sess_mgr"]
        session = sess_mgr.create_session()
        client.cookies.set(SESSION_COOKIE_NAME, session.session_id)

        # Create
        res_create = client.post(
            "/dossiers",
            data={"title": "Original Dossier", "incident_ids": ["INC-2026-0001"], "csrf_token": session.csrf_token},
            follow_redirects=False,
        )
        dossier_id = res_create.headers["location"].split("/")[-1]

        # Supersede directly without review/approval
        res_supersede = client.post(
            f"/dossiers/{dossier_id}/supersede",
            data={"rationale": "Updated with additional post-hearing findings.", "csrf_token": session.csrf_token},
            follow_redirects=False,
        )
        assert res_supersede.status_code == 303
        new_dossier_url = res_supersede.headers["location"]
        new_dossier_id = new_dossier_url.split("/")[-1]
        assert new_dossier_id != dossier_id

        # Verify new dossier is v2 DRAFT
        res_new = client.get(new_dossier_url)
        assert res_new.status_code == 200
        assert "v2" in res_new.text
        assert "DRAFT" in res_new.text
        assert dossier_id in res_new.text

        # Verify old dossier is SUPERSEDED
        res_old = client.get(f"/dossiers/{dossier_id}")
        assert "SUPERSEDED" in res_old.text
        assert new_dossier_id in res_old.text

    def test_read_only_guarantee_no_mutations_on_get(self, dossier_test_setup) -> None:
        """GET routes execute zero database row mutations."""
        client = dossier_test_setup["client"]
        sess_mgr = dossier_test_setup["sess_mgr"]
        session = sess_mgr.create_session()
        client.cookies.set(SESSION_COOKIE_NAME, session.session_id)
        engine = dossier_test_setup["engine"]

        # Snapshot row counts before
        with Session(engine) as s:
            dossiers_before = s.scalar(select(func.count(EditorialDossierModel.id)))
            incidents_before = s.scalar(select(func.count(IncidentModel.id)))

        # Navigate through GET routes
        client.get("/dossiers")
        client.get("/dossiers/new")

        # Snapshot row counts after
        with Session(engine) as s:
            dossiers_after = s.scalar(select(func.count(EditorialDossierModel.id)))
            incidents_after = s.scalar(select(func.count(IncidentModel.id)))

        assert dossiers_before == dossiers_after
        assert incidents_before == incidents_after
