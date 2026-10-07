"""Temporal representations with explicit precision tiers.

Supports exact dates, month/year precision, approximate dates, date ranges,
and unknown dates.
"""

from datetime import date
from typing import Optional

from pydantic import model_validator

from ai_incident_monitor.domain.common import BaseEntity, SchemaVersioned
from ai_incident_monitor.domain.identifiers import EvidenceId
from ai_incident_monitor.domain.vocabularies import DatePrecision


class DateWithPrecision(SchemaVersioned):
    """Date representation capturing explicit temporal precision.

    Unknown dates must have all date attributes set to None.
    """

    precision: DatePrecision
    exact_date: Optional[date] = None
    year: Optional[int] = None
    month: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    supporting_evidence_ids: list[EvidenceId] = []
    note: Optional[str] = None

    @model_validator(mode="after")
    def validate_precision_fields(self) -> "DateWithPrecision":
        if self.precision == DatePrecision.UNKNOWN:
            if any(
                [
                    self.exact_date is not None,
                    self.year is not None,
                    self.month is not None,
                    self.start_date is not None,
                    self.end_date is not None,
                ]
            ):
                raise ValueError("When DatePrecision is UNKNOWN, all date fields must be null.")

        elif self.precision == DatePrecision.EXACT:
            if self.exact_date is None:
                raise ValueError("When DatePrecision is EXACT, 'exact_date' is required.")

        elif self.precision == DatePrecision.MONTH:
            if self.year is None or self.month is None:
                raise ValueError(
                    "When DatePrecision is MONTH, both 'year' and 'month' are required."
                )
            if not (1 <= self.month <= 12):
                raise ValueError(f"Month must be between 1 and 12, got {self.month}")

        elif self.precision == DatePrecision.YEAR:
            if self.year is None:
                raise ValueError("When DatePrecision is YEAR, 'year' is required.")

        elif self.precision == DatePrecision.RANGE:
            if self.start_date is None or self.end_date is None:
                raise ValueError(
                    "When DatePrecision is RANGE, both 'start_date' and 'end_date' are required."
                )
            if self.start_date > self.end_date:
                raise ValueError(
                    f"start_date ({self.start_date}) must be on or before end_date ({self.end_date})."
                )

        return self


class DateRange(SchemaVersioned):
    """Explicit bounded date range with supporting evidence."""

    start_date: date
    end_date: date
    supporting_evidence_ids: list[EvidenceId] = []
    note: Optional[str] = None

    @model_validator(mode="after")
    def validate_order(self) -> "DateRange":
        if self.start_date > self.end_date:
            raise ValueError(
                f"start_date ({self.start_date}) must be on or before end_date ({self.end_date})."
            )
        return self
