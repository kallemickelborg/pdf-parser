"""English-language invoice template (INVOICE / Invoice No / Due Date / Total Due)."""

from __future__ import annotations

import re

from src.adapters._shared import (
    detect_billing_type,
    extract_amount,
    extract_customer,
    extract_date,
    finalize_currency,
    first_non_empty_line,
)
from src.adapters.base import ExtractionContext
from src.domain import CanonicalInvoice

_INVOICE_NO_RE = re.compile(r"Invoice\s*(?:No|Number|#)\.?\s*:?\s*(\S+)", re.IGNORECASE)
_DUE_DATE_RE = re.compile(r"Due\s*Date\s*:?\s*(\S+)", re.IGNORECASE)
_AMOUNT_RE = re.compile(
    r"(?:Total\s*Due|Amount\s*Due|Grand\s*Total|Total\s*Amount)\s*:?\s*"
    r"(DKK|EUR|USD|GBP|SEK|NOK)?\s*([\d.,]+)\s*(DKK|EUR|USD|GBP|SEK|NOK)?",
    re.IGNORECASE,
)

_SIGNAL_KEYWORDS = ("Invoice No", "Due Date", "Total Due", "Bill To", "PO Ref", "INVOICE")


class EnglishAdapter:
    name = "english"
    language = "en"

    def detect_score(self, text: str) -> float:
        hits = sum(1 for kw in _SIGNAL_KEYWORDS if kw.lower() in text.lower())
        return min(hits / 3, 1.0)

    def extract(self, text: str, ctx: ExtractionContext) -> CanonicalInvoice:
        invoice_no = _first_group(_INVOICE_NO_RE, text)
        raw_due = _first_group(_DUE_DATE_RE, text)

        amount_match = _AMOUNT_RE.search(text)
        amount = None
        parsed_currency: str | None = None
        explicit_currency: str | None = None
        if amount_match:
            amount, parsed_currency = extract_amount(amount_match.group(2), ctx)
            explicit_currency = amount_match.group(1) or amount_match.group(3)

        return CanonicalInvoice(
            invoice_no=invoice_no,
            vendor=first_non_empty_line(text),
            customer=extract_customer(text, anchors=("Bill To", "Billed To", "Customer")),
            due_date=extract_date(raw_due, ctx, "due_date") if raw_due else None,
            gross_total_amount=amount,
            billing_type=detect_billing_type(text),
            currency=finalize_currency(parsed_currency, explicit_currency, ctx),
        )


def _first_group(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    return match.group(1) if match else None
