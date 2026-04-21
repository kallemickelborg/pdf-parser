"""Crayon A/S invoice adapter (Danish + English variants).

Crayon issues invoices in two languages with an identical layout; only the
labels differ:

    Danish                 English
    ------                 -------
    Leverand\u00f8r              Supplier
    Fakturanummer          Invoice Number
    Forfaldsdato           Due Date
    Fakturatotal           Invoice Total

The layout places each label in a column header row and its value in the
row directly below, e.g.::

    Fakturanummer Vores Reference           <- label row
    4139526       Sarah Norengaard          <- value row

and the totals/due date live in a stacked footer::

    Leverand\u00f8r Kontonummer ... Forfaldsdato Fakturatotal
    40734073040663 +71<...> 26.05.2022 DKK      7 759 745,18
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from src.adapters._shared import (
    detect_billing_type,
    extract_amount,
    extract_customer,
    extract_date,
    finalize_currency,
)
from src.adapters.base import ExtractionContext
from src.domain import CanonicalInvoice
from src.parsers.normalization import clean_line

_DATE_TOKEN = r"\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4}"
_AMOUNT_TOKEN = r"[\d][\d .,]*[\d]"
_CURRENCY_TOKEN = r"DKK|EUR|USD|GBP|SEK|NOK|CHF"
_NUMBER_TOKEN = r"[A-Z0-9][A-Z0-9\-/]*"

# Column-header label rows. These labels appear on their own (as a row of
# column titles); the values sit on the next non-empty line.
_INVOICE_NO_LABEL_ROW = re.compile(
    r"^\s*(?:Fakturanummer|Invoice\s+Number)\b",
    re.IGNORECASE,
)
_DUE_TOTAL_FOOTER_HEADER = re.compile(
    r"(?:Forfaldsdato|Due\s+Date)\s+(?:Fakturatotal|Invoice\s+Total)",
    re.IGNORECASE,
)

_FAKTURA_TOTAL_INLINE = re.compile(
    r"(?:Fakturatotal|Invoice\s+Total)(?:\s*\([^)]*\))?[^\S\n]*[:.]?[^\S\n]*"
    r"(?:(" + _CURRENCY_TOKEN + r")[^\S\n]*)?(" + _AMOUNT_TOKEN + r")"
    r"(?:[^\S\n]*(" + _CURRENCY_TOKEN + r"))?",
    re.IGNORECASE,
)

_STACKED_FOOTER_VALUES = re.compile(
    r"(" + _DATE_TOKEN + r")\s+(?:(" + _CURRENCY_TOKEN + r")\s+)?(" + _AMOUNT_TOKEN + r")",
)

_CUSTOMER_ANCHORS: tuple[str, ...] = (
    "Faktureringsadresse",
    "Fakturering til",
    "K\u00f8ber adresse",
    "Receiver",
    "Bill To",
    "Billing Address",
    "Solgt til",
)

# Tokens commonly sitting in the value column of "Invoice Number / Supplier
# Contact" rows - not actual invoice numbers.
_BAD_INVOICE_TOKENS: frozenset[str] = frozenset(
    {
        "vores",
        "deres",
        "reference",
        "salgsordre",
        "nr",
        "nummer",
        "supplier",
        "customer",
        "contact",
        "number",
    }
)


def _is_plausible_invoice_no(token: str) -> bool:
    lowered = token.lower()
    if lowered in _BAD_INVOICE_TOKENS:
        return False
    # Real Crayon invoice numbers are numeric (sometimes with dashes).
    return bool(re.fullmatch(r"[A-Z0-9][A-Z0-9\-/]*", token)) and bool(re.search(r"\d", token))


def _extract_invoice_no(text: str) -> str | None:
    """Crayon places the label and its value in adjacent columns of the same
    table, so values sit on the line *after* the label row."""
    lines = text.splitlines()
    for i, raw in enumerate(lines):
        if not _INVOICE_NO_LABEL_ROW.match(raw):
            continue
        for follow in lines[i + 1 : i + 3]:
            cleaned = clean_line(follow)
            if not cleaned:
                continue
            tokens = cleaned.split()
            for tok in tokens:
                if _is_plausible_invoice_no(tok):
                    return tok
            break
    return None


def _extract_stacked_footer(
    text: str, ctx: ExtractionContext
) -> tuple[date | None, Decimal | None, str | None] | None:
    lines = text.splitlines()
    for i, raw in enumerate(lines):
        if not _DUE_TOTAL_FOOTER_HEADER.search(raw):
            continue
        for follow in lines[i + 1 : i + 4]:
            value_line = clean_line(follow)
            if not value_line:
                continue
            m = _STACKED_FOOTER_VALUES.search(value_line)
            if not m:
                continue
            due = extract_date(m.group(1), ctx, "due_date")
            amount, _ = extract_amount(m.group(3), ctx)
            return due, amount, m.group(2)
        return None
    return None


def _extract_vendor(text: str) -> str | None:
    # Crayon invoices have "Leverandør" (da) or "Supplier" (en) as a standalone
    # label, with the vendor name on the next non-empty line.
    lines = text.splitlines()
    for i, raw in enumerate(lines):
        if re.match(r"\s*(?:Leverand\u00f8r|Supplier)\s*:?\s*$", raw, re.IGNORECASE):
            for follow in lines[i + 1 : i + 3]:
                cleaned = clean_line(follow)
                if cleaned:
                    return cleaned
    return "Crayon A/S"


class CrayonAdapter:
    name = "crayon_da"
    language = "da"

    def detect_score(self, text: str) -> float:
        return 1.0 if "Crayon A/S" in text else 0.0

    def extract(self, text: str, ctx: ExtractionContext) -> CanonicalInvoice:
        invoice_no = _extract_invoice_no(text)

        due_date: date | None = None
        gross_total_amount: Decimal | None = None
        parsed_currency: str | None = None
        explicit_currency: str | None = None

        # Prefer the inline "Fakturatotal (... DKK) 7 237 127,76 DKK" line
        # for the grand total, then the stacked footer for the due date.
        total_match = _FAKTURA_TOTAL_INLINE.search(text)
        if total_match:
            currency_pre, raw_amount, currency_post = total_match.groups()
            amt, pc = extract_amount(raw_amount, ctx)
            gross_total_amount = amt
            parsed_currency = pc
            explicit_currency = currency_pre or currency_post

        if due_date is None or gross_total_amount is None:
            stacked = _extract_stacked_footer(text, ctx)
            if stacked:
                sd, sa, sc = stacked
                if due_date is None and sd is not None:
                    due_date = sd
                if gross_total_amount is None and sa is not None:
                    gross_total_amount = sa
                    if explicit_currency is None:
                        explicit_currency = sc

        return CanonicalInvoice(
            invoice_no=invoice_no,
            vendor=_extract_vendor(text),
            customer=extract_customer(text, anchors=_CUSTOMER_ANCHORS, max_lines=3),
            due_date=due_date,
            gross_total_amount=gross_total_amount,
            billing_type=detect_billing_type(text),
            currency=finalize_currency(parsed_currency, explicit_currency, ctx),
        )
