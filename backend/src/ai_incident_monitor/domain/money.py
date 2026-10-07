"""Financial and monetary value modeling with strict epistemic integrity.

Constitutional Rules 2 & 9:
- Unknown monetary amount must be null, never zero.
- Zero is permitted only when evidence supports a measured absence (CONFIRMED_ZERO).
- Currency conversions preserve original values and conversion sources.
"""

from decimal import Decimal
import re
from typing import Optional

from pydantic import field_validator, model_validator

from ai_incident_monitor.domain.common import (
    BaseEntity,
    InvalidMonetaryStateError,
    SchemaVersioned,
    UngroundedClaimError,
)
from ai_incident_monitor.domain.dates import DateWithPrecision
from ai_incident_monitor.domain.identifiers import EvidenceId
from ai_incident_monitor.domain.vocabularies import MonetaryAmountStatus

CURRENCY_REGEX = re.compile(r"^[A-Z]{3}$")


class CurrencyConversionRecord(SchemaVersioned):
    """Preserves original value and provenance for converted monetary amounts."""

    original_currency: str
    original_amount: Decimal
    exchange_rate: Decimal
    conversion_date: DateWithPrecision
    rate_source: str

    @field_validator("original_currency")
    @classmethod
    def validate_currency_code(cls, v: str) -> str:
        if not CURRENCY_REGEX.match(v):
            raise ValueError(f"Invalid currency code '{v}'. Must be 3 uppercase letters (ISO 4217).")
        return v

    @model_validator(mode="after")
    def validate_rate(self) -> "CurrencyConversionRecord":
        if self.exchange_rate <= Decimal(0):
            raise ValueError(f"Exchange rate must be positive, got {self.exchange_rate}")
        return self


class MonetaryAmount(SchemaVersioned):
    """Monetary amount representation enforcing non-negotiable unknown-is-not-zero rules."""

    amount_status: MonetaryAmountStatus
    exact_amount: Optional[Decimal] = None
    min_amount: Optional[Decimal] = None
    max_amount: Optional[Decimal] = None
    currency: Optional[str] = None
    value_date: Optional[DateWithPrecision] = None
    conversion: Optional[CurrencyConversionRecord] = None
    supporting_evidence_ids: list[EvidenceId] = []

    @field_validator("currency")
    @classmethod
    def validate_currency_format(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not CURRENCY_REGEX.match(v):
            raise ValueError(f"Invalid currency code '{v}'. Must be 3 uppercase letters (ISO 4217).")
        return v

    @model_validator(mode="after")
    def validate_amount_status_invariants(self) -> "MonetaryAmount":
        # Rule 1: Unknown must remain null, never zero
        if self.amount_status == MonetaryAmountStatus.UNKNOWN:
            if any(
                [
                    self.exact_amount is not None,
                    self.min_amount is not None,
                    self.max_amount is not None,
                ]
            ):
                raise InvalidMonetaryStateError(
                    "Unknown monetary amount must be null, not zero or any numeric value."
                )

        # Rule 2: Zero is permitted ONLY when evidence confirms measured absence
        elif self.amount_status == MonetaryAmountStatus.CONFIRMED_ZERO:
            if self.exact_amount != Decimal(0):
                raise InvalidMonetaryStateError(
                    f"When status is CONFIRMED_ZERO, exact_amount must be exactly 0, got {self.exact_amount}"
                )
            if not self.supporting_evidence_ids:
                raise UngroundedClaimError(
                    "Confirmed zero monetary impact requires at least one supporting evidence ID."
                )
            if self.currency is None:
                raise ValueError("Confirmed zero amount requires a declared currency.")

        elif self.amount_status == MonetaryAmountStatus.EXACT_KNOWN:
            if self.exact_amount is None:
                raise InvalidMonetaryStateError("When status is EXACT_KNOWN, 'exact_amount' is required.")
            if self.exact_amount == Decimal(0):
                raise InvalidMonetaryStateError(
                    "An exact amount of 0 must use status CONFIRMED_ZERO with supporting evidence."
                )
            if self.currency is None:
                raise ValueError("Currency is required when monetary amount is known.")

        elif self.amount_status == MonetaryAmountStatus.RANGE_KNOWN:
            if self.min_amount is None or self.max_amount is None:
                raise InvalidMonetaryStateError(
                    "When status is RANGE_KNOWN, both 'min_amount' and 'max_amount' are required."
                )
            if self.min_amount > self.max_amount:
                raise InvalidMonetaryStateError(
                    f"min_amount ({self.min_amount}) must be <= max_amount ({self.max_amount})."
                )
            if self.currency is None:
                raise ValueError("Currency is required when monetary range is known.")

        elif self.amount_status == MonetaryAmountStatus.ESTIMATE_KNOWN:
            if self.exact_amount is None and self.min_amount is None:
                raise InvalidMonetaryStateError(
                    "When status is ESTIMATE_KNOWN, either exact_amount or min_amount must be provided."
                )
            if self.currency is None:
                raise ValueError("Currency is required when monetary estimate is known.")

        elif self.amount_status == MonetaryAmountStatus.NOT_APPLICABLE:
            if any(
                [
                    self.exact_amount is not None,
                    self.min_amount is not None,
                    self.max_amount is not None,
                ]
            ):
                raise InvalidMonetaryStateError("When status is NOT_APPLICABLE, amount fields must be null.")

        return self
