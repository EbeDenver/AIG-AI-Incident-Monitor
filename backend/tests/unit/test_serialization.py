"""Tests for JSON serialization round-trips and JSON Schema generation."""

from decimal import Decimal

from ai_incident_monitor.domain.claims import ClaimRecord
from ai_incident_monitor.domain.export_schemas import get_all_json_schemas
from ai_incident_monitor.domain.money import MonetaryAmount
from ai_incident_monitor.domain.vocabularies import (
    ClaimMateriality,
    ClaimType,
    ConfidenceLevel,
    EpistemicStatus,
    MonetaryAmountStatus,
)


def test_claim_record_json_round_trip():
    claim = ClaimRecord(
        id="CLM-ser-01",
        incident_id="INC-ser-01",
        claim_text="Round trip test claim for serialization.",
        claim_type=ClaimType.FACTUAL_EVENT,
        epistemic_status=EpistemicStatus.CONFIRMED_FACT,
        supporting_evidence_ids=["EVD-123"],
        confidence=ConfidenceLevel.VERY_HIGH,
        materiality=ClaimMateriality.CORE_IMPACT,
    )
    json_str = claim.model_dump_json()
    reconstructed = ClaimRecord.model_validate_json(json_str)
    assert reconstructed.id == claim.id
    assert reconstructed.claim_text == claim.claim_text
    assert reconstructed.epistemic_status == EpistemicStatus.CONFIRMED_FACT


def test_monetary_amount_json_round_trip():
    money = MonetaryAmount(
        amount_status=MonetaryAmountStatus.EXACT_KNOWN,
        exact_amount=Decimal("1234567.89"),
        currency="USD",
        supporting_evidence_ids=["EVD-123"],
    )
    json_str = money.model_dump_json()
    reconstructed = MonetaryAmount.model_validate_json(json_str)
    assert reconstructed.exact_amount == Decimal("1234567.89")
    assert reconstructed.currency == "USD"


def test_json_schema_generation():
    schemas = get_all_json_schemas()
    assert len(schemas) >= 10
    assert "SourceReference" in schemas
    assert "ClaimRecord" in schemas
    assert "MonetaryAmount" in schemas
    assert "properties" in schemas["ClaimRecord"]
    assert "properties" in schemas["MonetaryAmount"]
