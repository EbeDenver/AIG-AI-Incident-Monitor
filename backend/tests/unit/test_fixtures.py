"""Tests proving all golden fixtures validate and all negative fixtures fail for the intended reason."""

import json
from pathlib import Path
import pytest

from ai_incident_monitor.domain import (
    AIInvolvementAssessment,
    AuditMetadata,
    CausalAssessment,
    ClaimRecord,
    DateWithPrecision,
    EvidenceRecord,
    HumanReviewRecord,
    InvalidMonetaryStateError,
    MonetaryAmount,
    SourceReference,
    UncertaintyRecord,
    UngroundedClaimError,
    UnverifiedLegalConclusionError,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
GOLDEN_DIR = FIXTURES_DIR / "golden"
INVALID_DIR = FIXTURES_DIR / "invalid"
EXPECTED_NOTICE = "DEMONSTRATION DATA — NOT A REAL INCIDENT"

MODEL_MAP = {
    "01_confirmed_fact_with_evidence.json": ClaimRecord,
    "02_single_source_allegation.json": ClaimRecord,
    "03_primary_and_independent_reporting.json": SourceReference,
    "04_disputed_claim_bilateral_evidence.json": ClaimRecord,
    "05_unknown_financial_impact.json": MonetaryAmount,
    "06_confirmed_zero_financial_impact.json": MonetaryAmount,
    "07_monetary_range_original_currency.json": MonetaryAmount,
    "08_currency_converted_with_provenance.json": MonetaryAmount,
    "09_possible_ai_causal_contribution.json": CausalAssessment,
    "10_ai_involvement_alleged_unestablished.json": AIInvolvementAssessment,
    "11_corrected_source_report.json": ClaimRecord,
    "12_superseded_claim_reference.json": ClaimRecord,
    "13_syndicated_reports_shared_origin.json": SourceReference,
    "14_paywalled_source_reference.json": SourceReference,
    "15_broken_source_with_archive.json": SourceReference,
    "16_approximate_incident_date.json": DateWithPrecision,
    "17_unknown_incident_date.json": DateWithPrecision,
    "18_material_numeric_claim_with_evidence.json": ClaimRecord,
    "19_human_approved_record.json": HumanReviewRecord,
    "20_machine_recommended_unapproved.json": AuditMetadata,
    "21_multi_type_uncertainty_record.json": UncertaintyRecord,
    "22_inert_prompt_injection_content.json": EvidenceRecord,
}


@pytest.mark.parametrize("fixture_filename,model_cls", list(MODEL_MAP.items()))
def test_golden_fixture_validates_successfully(fixture_filename, model_cls):
    """Test proving that every golden fixture is valid and labeled with demonstration notice."""
    fixture_path = GOLDEN_DIR / fixture_filename
    assert fixture_path.exists(), f"Fixture file not found: {fixture_filename}"

    with open(fixture_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("demonstration_notice") == EXPECTED_NOTICE, (
        f"Fixture {fixture_filename} must contain demonstration notice banner"
    )

    # Validate against corresponding model
    instance = model_cls.model_validate(data)
    assert instance is not None


from pydantic import ValidationError

def test_invalid_numeric_claim_missing_evidence_fails():
    """Negative Test: Material numeric claim without evidence must fail validation."""
    fixture_path = INVALID_DIR / "invalid_numeric_claim_missing_evidence.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("demonstration_notice") == EXPECTED_NOTICE
    # Remove metadata fields used for test documentation
    test_data = {k: v for k, v in data.items() if k not in ("expected_error", "expected_rule")}

    with pytest.raises(ValidationError, match="requires at least one supporting evidence ID"):
        ClaimRecord.model_validate(test_data)


def test_invalid_confirmed_claim_missing_evidence_fails():
    """Negative Test: Confirmed claim without evidence must fail validation."""
    fixture_path = INVALID_DIR / "invalid_confirmed_claim_missing_evidence.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("demonstration_notice") == EXPECTED_NOTICE
    test_data = {k: v for k, v in data.items() if k not in ("expected_error", "expected_rule")}

    with pytest.raises(ValidationError, match="must have at least one supporting evidence ID"):
        ClaimRecord.model_validate(test_data)


def test_invalid_causal_claim_missing_status_fails():
    """Negative Test: Causal claim without attached CausalAssessment must fail validation."""
    fixture_path = INVALID_DIR / "invalid_causal_claim_missing_status.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("demonstration_notice") == EXPECTED_NOTICE
    test_data = {k: v for k, v in data.items() if k not in ("expected_error", "expected_rule")}

    with pytest.raises(ValidationError, match="requires an attached CausalAssessment record"):
        ClaimRecord.model_validate(test_data)


def test_invalid_unknown_money_as_zero_fails():
    """Negative Test: Unknown monetary amount with amount=0 must fail validation."""
    fixture_path = INVALID_DIR / "invalid_unknown_money_as_zero.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("demonstration_notice") == EXPECTED_NOTICE
    test_data = {k: v for k, v in data.items() if k not in ("expected_error", "expected_rule")}

    with pytest.raises(ValidationError, match="Unknown monetary amount must be null, not zero"):
        MonetaryAmount.model_validate(test_data)


def test_invalid_llm_confirmed_legal_claim_fails():
    """Negative Test: Legal conclusion marked confirmed without human review must fail validation."""
    fixture_path = INVALID_DIR / "invalid_llm_confirmed_legal_claim.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("demonstration_notice") == EXPECTED_NOTICE
    test_data = {k: v for k, v in data.items() if k not in ("expected_error", "expected_rule")}

    with pytest.raises(ValidationError, match="cannot be marked CONFIRMED_FACT without explicit human review"):
        ClaimRecord.model_validate(test_data)


def test_invalid_superseded_missing_replacement_fails():
    """Negative Test: Superseded claim without superseded_by must fail validation."""
    fixture_path = INVALID_DIR / "invalid_superseded_missing_replacement.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("demonstration_notice") == EXPECTED_NOTICE
    test_data = {k: v for k, v in data.items() if k not in ("expected_error", "expected_rule")}

    with pytest.raises(ValidationError, match="must declare a valid 'superseded_by' reference"):
        ClaimRecord.model_validate(test_data)


def test_invalid_syndicated_missing_origin_fails():
    """Negative Test: Syndicated copy without syndication_origin must fail validation."""
    fixture_path = INVALID_DIR / "invalid_syndicated_missing_origin.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("demonstration_notice") == EXPECTED_NOTICE
    test_data = {k: v for k, v in data.items() if k not in ("expected_error", "expected_rule")}

    with pytest.raises(ValidationError, match="must specify syndication_origin"):
        SourceReference.model_validate(test_data)
