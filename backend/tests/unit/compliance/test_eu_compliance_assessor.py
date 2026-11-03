"""Unit tests for the EU AI Act Compliance Intelligence engine and timeline alignment.

Specification: AI-incident-AU-Act-Compliance-assessor.pdf
("EU AI Act Compliance Intelligence — LLM API Design", Pages 1-9)

Governing Principles:
1. Two-stage assessment (Article 2 scope check + regulatory inference).
2. November 2026 phased enforcement timeline baseline.
3. Statutory non-advice disclaimer and lack of premature noncompliance accusations.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from starlette.testclient import TestClient

from ai_incident_monitor.compliance.assessor import EUAIActAssessor
from ai_incident_monitor.compliance.schemas import (
    ComplianceGapStatus,
    EnforcementTimelineStatus,
    JurisdictionScope,
    SeriousIncidentDetermination,
    SystemClassification,
)
from ai_incident_monitor.compliance.timeline import (
    adjust_gap_status_for_timeline,
    get_timeline_status_for_article,
)
from ai_incident_monitor.db.base import Base
from ai_incident_monitor.db.models.compliance import EUAIActComplianceAssessmentModel
from ai_incident_monitor.db.models.incident import IncidentModel
from ai_incident_monitor.db.session import get_engine
from ai_incident_monitor.ui.app import create_app
from sqlalchemy.orm import Session


class TestEUComplianceTimeline:
    """Validate statutory timeline milestone calculations under November 2026 baseline."""

    def test_annex_iii_high_risk_is_not_yet_applicable(self) -> None:
        """Annex III obligations (Articles 8-15) are NOT_YET_APPLICABLE in November 2026."""
        status, note = get_timeline_status_for_article("Article 14 (Human Oversight)")
        assert status == EnforcementTimelineStatus.NOT_YET_APPLICABLE
        assert "December 2, 2027" in note

        status9, _ = get_timeline_status_for_article("Article 9 (Risk Management System)")
        assert status9 == EnforcementTimelineStatus.NOT_YET_APPLICABLE

    def test_article_5_prohibitions_are_active_law(self) -> None:
        """Article 5 prohibited practices have been in force since February 2025."""
        status, note = get_timeline_status_for_article("Article 5 (Prohibited AI Practices)")
        assert status == EnforcementTimelineStatus.ACTIVE_LAW
        assert "February 2, 2025" in note

    def test_article_50_transparency_is_active_law(self) -> None:
        """Article 50 transparency has been in force since August 2026."""
        status, note = get_timeline_status_for_article("Article 50 (Transparency)")
        assert status == EnforcementTimelineStatus.ACTIVE_LAW
        assert "August 2, 2026" in note

    def test_gap_status_adjustment_for_future_law(self) -> None:
        """Future obligations cannot declare active unlawful noncompliance."""
        adj = adjust_gap_status_for_timeline(
            ComplianceGapStatus.DOCUMENTED_GAP,
            EnforcementTimelineStatus.NOT_YET_APPLICABLE,
        )
        assert adj == ComplianceGapStatus.NOT_YET_APPLICABLE

        adj_active = adjust_gap_status_for_timeline(
            ComplianceGapStatus.DOCUMENTED_GAP,
            EnforcementTimelineStatus.ACTIVE_LAW,
        )
        assert adj_active == ComplianceGapStatus.DOCUMENTED_GAP


class TestEUAIActAssessor:
    """Validate two-stage evaluation logic, jurisdictional screens, and classification."""

    @pytest.fixture
    def assessor(self) -> EUAIActAssessor:
        return EUAIActAssessor()

    def test_military_defense_exclusion(self, assessor: EUAIActAssessor) -> None:
        """Military systems are excluded under Article 2(3)."""
        result = assessor.evaluate_incident(
            incident_id="INC-MILITARY-01",
            title="Autonomous Defense Drone Targeting Anomaly",
            summary="Military armed forces deployed drone during battlefield combat exercise.",
            category="SAFETY",
        )
        assert result.territorial_scope.jurisdiction == JurisdictionScope.NOT_APPLICABLE
        assert result.territorial_scope.military_defense_exclusion is True
        assert result.system_classification == SystemClassification.EXCLUDED
        assert result.is_legal_advice is False

    def test_scientific_research_exclusion(self, assessor: EUAIActAssessor) -> None:
        """Pure scientific R&D systems are excluded under Article 2(6)."""
        result = assessor.evaluate_incident(
            incident_id="INC-RESEARCH-01",
            title="Model Hallucination in Academic Laboratory",
            summary="Arxiv preprint benchmark study evaluating purely scientific benchmark datasets.",
            category="REPUTATIONAL",
        )
        assert result.territorial_scope.jurisdiction == JurisdictionScope.NOT_APPLICABLE
        assert result.territorial_scope.scientific_research_exclusion is True
        assert result.system_classification == SystemClassification.EXCLUDED

    def test_prohibited_practice_detection(self, assessor: EUAIActAssessor) -> None:
        """Social scoring triggers Article 5 prohibited practice finding."""
        result = assessor.evaluate_incident(
            incident_id="INC-PROHIBITED-01",
            title="Municipal Citizen Social Credit Scoring Deployment",
            summary="Municipal government deployed social scoring algorithm in France to rate trustworthiness of citizens.",
            category="RIGHTS",
        )
        assert result.territorial_scope.jurisdiction == JurisdictionScope.APPLICABLE
        assert result.system_classification == SystemClassification.PROHIBITED_PRACTICE
        assert result.prohibited_practice.is_prohibited is True
        assert "5(1)(c)" in result.prohibited_practice.prohibition_type
        assert result.overall_enforcement_status == EnforcementTimelineStatus.ACTIVE_LAW

    def test_high_risk_critical_infrastructure_and_serious_incident(self, assessor: EUAIActAssessor) -> None:
        """Critical infrastructure failure triggers Annex III point 2 and Article 73 serious incident."""
        result = assessor.evaluate_incident(
            incident_id="INC-CRIT-01",
            title="Electrical Grid Distribution Autonomous Relay Failure",
            summary="AI control agent caused regional electrical power blackout and grid failure across Germany.",
            category="CYBERSECURITY",
            observed_harms=["Electrical grid failure across western grid", "Hospital emergency backup activation"],
        )
        assert result.territorial_scope.jurisdiction == JurisdictionScope.APPLICABLE
        assert result.system_classification == SystemClassification.HIGH_RISK_ANNEX_III
        assert result.high_risk.annex_point is not None
        assert "Annex III, point 2" in result.high_risk.annex_point
        assert result.serious_incident.determination == SeriousIncidentDetermination.SERIOUS_INCIDENT
        assert result.overall_enforcement_status == EnforcementTimelineStatus.NOT_YET_APPLICABLE

        # High-risk gaps must be marked NOT_YET_APPLICABLE under Nov 2026 baseline
        for gap in result.compliance_gaps:
            if "Article 14" in gap.article or "Article 9" in gap.article:
                assert gap.gap_status == ComplianceGapStatus.NOT_YET_APPLICABLE

    def test_transparency_obligation_deepfake(self, assessor: EUAIActAssessor) -> None:
        """Deepfake synthetic media triggers Article 50(2) transparency requirements."""
        result = assessor.evaluate_incident(
            incident_id="INC-DEEPFAKE-01",
            title="Executive Cloned Voice Wire Fraud",
            summary="Deepfake synthetic media and cloned voice utilized in Belgium to authorize unauthorized wire transfer.",
            category="REPUTATIONAL",
        )
        assert result.transparency.applies is True
        assert any("50(2)" in ob for ob in result.transparency.obligations)
        assert result.overall_enforcement_status == EnforcementTimelineStatus.ACTIVE_LAW

    def test_public_route_integration(self, assessor: EUAIActAssessor, tmp_path: Path) -> None:
        """Persisted compliance assessment surfaces correctly in public incident detail route."""
        db_path = tmp_path / "test_compliance_route.db"
        engine = get_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(engine)

        assessment = assessor.evaluate_incident(
            incident_id="INC-ROUTE-01",
            title="Autonomous Trading Halt in Frankfurt",
            summary="Trading algorithm in Germany initiated flash cascade violating exchange circuit breakers.",
            category="FINANCIAL",
        )

        with Session(engine) as session:
            inc = IncidentModel(
                id="INC-ROUTE-01",
                title="Autonomous Trading Halt in Frankfurt",
                summary="Trading algorithm in Germany initiated flash cascade.",
                primary_category="FINANCIAL",
            )
            session.add(inc)

            model = EUAIActComplianceAssessmentModel(
                id="COMP-001",
                incident_id="INC-ROUTE-01",
                status="COMPLETED",
                jurisdiction_status=assessment.territorial_scope.jurisdiction.value,
                system_classification=assessment.system_classification.value,
                annex_reference=assessment.high_risk.annex_point,
                enforcement_status=assessment.overall_enforcement_status.value,
                is_serious_incident=assessment.serious_incident.determination in (
                    SeriousIncidentDetermination.SERIOUS_INCIDENT,
                    SeriousIncidentDetermination.POTENTIAL_SERIOUS_INCIDENT,
                ),
                payload_json=json.dumps(assessment.model_dump()),
            )
            session.add(model)
            session.commit()

        app = create_app(db_engine=engine, repo_root=tmp_path)
        client = TestClient(app)

        response = client.get("/api/v1/public/incidents/INC-ROUTE-01")
        assert response.status_code == 200
        data = response.json()

        eu = data["eu_ai_act_compliance"]
        assert eu is not None
        assert eu["is_available"] is True
        assert eu["jurisdiction_status"] == "APPLICABLE"
        assert eu["classification"] == "HIGH_RISK_ANNEX_III"
        assert eu["enforcement_status"] == "NOT_YET_APPLICABLE"
        assert len(eu["identified_gaps"]) >= 1
        assert "not constitute formal legal advice" in eu["disclaimer"]
