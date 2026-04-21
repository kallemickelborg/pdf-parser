"""Pydantic response schemas for the PDF parser API."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class CanonicalInvoiceResponse(BaseModel):
    invoice_no: str | None
    vendor: str | None
    customer: str | None
    due_date: date | None
    gross_total_amount: Decimal | None
    billing_type: str | None
    currency: str | None


class ParseResultResponse(BaseModel):
    id: str
    source_file: str
    status: Literal["parsed", "partial", "failed"]
    invoice: CanonicalInvoiceResponse
    adapter_used: str | None
    adapters_tried: list[str]
    missing_fields: list[str]
    warnings: list[str]
    error: str | None
    text_preview: str


class SummaryResponse(BaseModel):
    total: int
    parsed: int
    partial: int
    failed: int
    pdf_input_dir: str
    run_id: str | None
    started_at: datetime | None
    completed_at: datetime | None


class InvoicesResponse(BaseModel):
    summary: SummaryResponse
    results: list[ParseResultResponse]
