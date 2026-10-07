"""Tests for MonetaryAmount and CurrencyConversionRecord enforcing constitutional rules."""

from decimal import Decimal
from pydantic import ValidationError
import pytest

from ai_incident_monitor.domain.dates import DateWithPrecision
from ai_incident_monitor.domain.money import CurrencyConversionRecord, MonetaryAmount
from ai_incident_monitor.domain.vocabularies import DatePrecision, MonetaryAmountStatus


def test_unknown_money_valid():
    m = MonetaryAmount(amount_status=MonetaryAmountStatus.UNKNOWN)
    assert m.exact_amount is None
    assert m.min_amount is None
    assert m.max_amount is None


def test_unknown_money_as_zero_rejected():
    # Constitutional Rule 1: Unknown cannot be coerced to 0
    with pytest.raises(ValidationError, match="Unknown monetary amount must be null, not zero"):
        MonetaryAmount(
            amount_status=MonetaryAmountStatus.UNKNOWN,
            exact_amount=Decimal("0.00"),
        )


def test_unknown_money_with_numeric_amount_rejected():
    with pytest.raises(ValidationError, match="Unknown monetary amount must be null, not zero"):
        MonetaryAmount(
            amount_status=MonetaryAmountStatus.UNKNOWN,
            exact_amount=Decimal("1500.00"),
        )


def test_confirmed_zero_with_evidence_valid():
    # Constitutional Rule 2: Zero permitted ONLY when evidence confirms measured absence
    m = MonetaryAmount(
        amount_status=MonetaryAmountStatus.CONFIRMED_ZERO,
        exact_amount=Decimal("0.00"),
        currency="USD",
        supporting_evidence_ids=["EVD-evidence-01"],
    )
    assert m.exact_amount == Decimal("0.00")
    assert m.amount_status == MonetaryAmountStatus.CONFIRMED_ZERO


def test_confirmed_zero_without_evidence_rejected():
    with pytest.raises(ValidationError, match="Confirmed zero monetary impact requires at least one"):
        MonetaryAmount(
            amount_status=MonetaryAmountStatus.CONFIRMED_ZERO,
            exact_amount=Decimal("0.00"),
            currency="USD",
            supporting_evidence_ids=[],
        )


def test_exact_zero_with_exact_known_status_rejected():
    # Exact 0 must use CONFIRMED_ZERO status, not EXACT_KNOWN
    with pytest.raises(ValidationError, match="An exact amount of 0 must use status CONFIRMED_ZERO"):
        MonetaryAmount(
            amount_status=MonetaryAmountStatus.EXACT_KNOWN,
            exact_amount=Decimal("0.00"),
            currency="USD",
            supporting_evidence_ids=["EVD-123"],
        )


def test_exact_known_missing_currency_rejected():
    with pytest.raises(ValidationError, match="Currency is required when monetary amount is known"):
        MonetaryAmount(
            amount_status=MonetaryAmountStatus.EXACT_KNOWN,
            exact_amount=Decimal("50000.00"),
        )


def test_range_known_valid():
    m = MonetaryAmount(
        amount_status=MonetaryAmountStatus.RANGE_KNOWN,
        min_amount=Decimal("100000.00"),
        max_amount=Decimal("250000.00"),
        currency="EUR",
        supporting_evidence_ids=["EVD-range-01"],
    )
    assert m.min_amount == Decimal("100000.00")
    assert m.max_amount == Decimal("250000.00")


def test_range_known_inverted_rejected():
    with pytest.raises(ValidationError, match="min_amount .* must be <= max_amount"):
        MonetaryAmount(
            amount_status=MonetaryAmountStatus.RANGE_KNOWN,
            min_amount=Decimal("300000.00"),
            max_amount=Decimal("100000.00"),
            currency="EUR",
        )


def test_currency_conversion_record_valid():
    conv = CurrencyConversionRecord(
        original_currency="JPY",
        original_amount=Decimal("15000000"),
        exchange_rate=Decimal("0.0067"),
        conversion_date=DateWithPrecision(
            precision=DatePrecision.EXACT,
            exact_date="2026-03-01",
        ),
        rate_source="Bank of Japan Historical Reference Rate",
    )
    assert conv.original_currency == "JPY"
    assert conv.original_amount == Decimal("15000000")


def test_currency_conversion_invalid_currency_code():
    with pytest.raises(ValidationError, match="Must be 3 uppercase letters"):
        CurrencyConversionRecord(
            original_currency="japan_yen",
            original_amount=Decimal("1000"),
            exchange_rate=Decimal("1.0"),
            conversion_date=DateWithPrecision(precision=DatePrecision.EXACT, exact_date="2026-01-01"),
            rate_source="Test",
        )
