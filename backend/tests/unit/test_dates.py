"""Tests for DateWithPrecision and DateRange."""

from datetime import date
import pytest

from ai_incident_monitor.domain.dates import DateRange, DateWithPrecision
from ai_incident_monitor.domain.vocabularies import DatePrecision


def test_exact_date_valid():
    d = DateWithPrecision(
        precision=DatePrecision.EXACT,
        exact_date=date(2026, 4, 15),
    )
    assert d.exact_date == date(2026, 4, 15)
    assert d.precision == DatePrecision.EXACT


def test_exact_date_missing_raises():
    with pytest.raises(ValueError, match="When DatePrecision is EXACT, 'exact_date' is required"):
        DateWithPrecision(precision=DatePrecision.EXACT)


def test_unknown_date_valid():
    d = DateWithPrecision(precision=DatePrecision.UNKNOWN, note="Date unknown due to audit lag")
    assert d.exact_date is None
    assert d.year is None
    assert d.month is None


def test_unknown_date_with_non_null_fields_raises():
    with pytest.raises(ValueError, match="When DatePrecision is UNKNOWN, all date fields must be null"):
        DateWithPrecision(precision=DatePrecision.UNKNOWN, exact_date=date(2026, 1, 1))


def test_month_precision_valid():
    d = DateWithPrecision(precision=DatePrecision.MONTH, year=2026, month=5)
    assert d.year == 2026
    assert d.month == 5


def test_month_precision_invalid_month():
    with pytest.raises(ValueError, match="Month must be between 1 and 12"):
        DateWithPrecision(precision=DatePrecision.MONTH, year=2026, month=13)


def test_range_precision_valid():
    d = DateWithPrecision(
        precision=DatePrecision.RANGE,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )
    assert d.start_date == date(2026, 1, 1)
    assert d.end_date == date(2026, 1, 31)


def test_range_precision_inverted_dates_raises():
    with pytest.raises(ValueError, match="start_date .* must be on or before end_date"):
        DateWithPrecision(
            precision=DatePrecision.RANGE,
            start_date=date(2026, 2, 1),
            end_date=date(2026, 1, 1),
        )


def test_date_range_model_valid():
    dr = DateRange(start_date=date(2026, 3, 1), end_date=date(2026, 3, 15))
    assert dr.start_date <= dr.end_date


def test_date_range_inverted_raises():
    with pytest.raises(ValueError, match="start_date .* must be on or before end_date"):
        DateRange(start_date=date(2026, 5, 1), end_date=date(2026, 4, 1))
