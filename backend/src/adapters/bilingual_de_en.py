"""Bilingual German/English template (Rechnung / Invoice).

Labels and their values are split across adjacent lines, e.g.:

    Rechnungsnr. / Invoice No.
    SM-DE-2026-088
"""

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
from src.parsers.normalization import clean_line, normalize_currency

_LABELS: dict[str, str] = {
    "invoice_no": r"Rechnungsnr\.?\s*/\s*Invoice\s*No\.?",
    "due_date": r"F(?:\u00e4|ae)llig\s*/\s*Due",
    "currency": r"W(?:\u00e4|ae)hrung\s*/\s*Currency",
    "gross_total_amount": r"Gesamtbetrag\s*/\s*Total\s*(?:Amount|Due)",
}

_SIGNAL_KEYWORDS = (
    "Rechnungsnr",
    "Rechnung",
    "Gesamtbetrag",
    "Bestellnr",
    "F\u00e4llig",
    "W\u00e4hrung",
)


def _next_value_line(lines: list[str], label_idx: int) -> str | None:
    for raw in lines[label_idx + 1 :]:
        cleaned = clean_line(raw)
        if cleaned:
            return cleaned
    return None


def _find_value_after_label(text: str, label_pattern: str) -> str | None:
    lines = text.splitlines()
    regex = re.compile(label_pattern, re.IGNORECASE)
    for i, raw in enumerate(lines):
        if regex.search(raw):
            return _next_value_line(lines, i)
    return None


class BilingualGermanEnglishAdapter:
    name = "bilingual_de_en"
    language = "de/en"

    def detect_score(self, text: str) -> float:
        hits = sum(1 for kw in _SIGNAL_KEYWORDS if kw in text)
        return min(hits / 3, 1.0)

    def extract(self, text: str, ctx: ExtractionContext) -> CanonicalInvoice:
        invoice_no = _find_value_after_label(text, _LABELS["invoice_no"])
        raw_due = _find_value_after_label(text, _LABELS["due_date"])
        explicit_currency_raw = _find_value_after_label(text, _LABELS["currency"])

        raw_amount = _find_value_after_label(text, _LABELS["gross_total_amount"])
        amount = None
        parsed_currency: str | None = None
        if raw_amount:
            amount, parsed_currency = extract_amount(raw_amount, ctx)

        return CanonicalInvoice(
            invoice_no=invoice_no,
            vendor=first_non_empty_line(text),
            customer=extract_customer(
                text, anchors=("Empf\u00e4nger / Bill To", "Empf\u00e4nger", "Bill To")
            ),
            due_date=extract_date(raw_due, ctx, "due_date") if raw_due else None,
            gross_total_amount=amount,
            billing_type=detect_billing_type(text),
            currency=finalize_currency(
                parsed_currency, normalize_currency(explicit_currency_raw), ctx
            ),
        )
