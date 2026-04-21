"""Canonical invoice domain models.

`CanonicalInvoice` is the target shape we try to extract from every PDF
regardless of template/language. `ParseResult` wraps it with per-file
diagnostics (which adapter was used, which fields are missing, warnings, etc.)
so the dashboard can surface parse quality.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

# Keep this list in sync with the XLSX export columns in `exporter.py`.
CANONICAL_FIELDS: tuple[str, ...] = (
    "invoice_no",
    "vendor",
    "customer",
    "due_date",
    "gross_total_amount",
    "billing_type",
    "currency",
)

ParseStatus = Literal["parsed", "partial", "failed"]


class CanonicalInvoice(BaseModel):
    """Canonical invoice fields inferred from any PDF template.

    All fields are optional. The canonical shape is shared across templates
    and languages; adapters populate what they can and leave the rest None.
    """

    invoice_no: str | None = None
    vendor: str | None = None
    customer: str | None = None
    due_date: date | None = None
    gross_total_amount: Decimal | None = None
    billing_type: str | None = None
    currency: str | None = None

    @field_validator("currency")
    @classmethod
    def _uppercase_currency(cls, v: str | None) -> str | None:
        return v.upper().strip() if v else v

    @field_validator("gross_total_amount")
    @classmethod
    def _amount_must_be_non_negative(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and v < 0:
            raise ValueError("gross_total_amount must be non-negative")
        return v

    def missing_fields(self) -> list[str]:
        return [f for f in CANONICAL_FIELDS if getattr(self, f) in (None, "")]

    def merged_with(self, other: CanonicalInvoice) -> CanonicalInvoice:
        """Return a new invoice where missing fields are filled from `other`."""
        data = self.model_dump()
        for field in CANONICAL_FIELDS:
            if data.get(field) in (None, "") and getattr(other, field) not in (None, ""):
                data[field] = getattr(other, field)
        return CanonicalInvoice(**data)


class ParseResult(BaseModel):
    """Outcome of parsing one PDF, including diagnostics."""

    id: UUID = Field(default_factory=uuid4)
    source_file: str
    status: ParseStatus
    invoice: CanonicalInvoice
    adapter_used: str | None = None
    adapters_tried: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
    text_preview: str = ""
