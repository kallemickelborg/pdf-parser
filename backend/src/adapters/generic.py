"""Last-resort adapter that searches for canonical fields across many languages.

Used when no template-specific adapter returned usable fields, e.g. because the
PDF is in a language/template we haven't seen before. It casts a wide keyword
net and is intentionally permissive -- anything it extracts is still surfaced
alongside warnings so the user can review quality.
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

# Broad label synonyms per field, across languages we've encountered.
_INVOICE_NO_RE = re.compile(
    r"(?:invoice\s*(?:no|number|#)\.?|fakturanr\.?|rechnungsnr\.?|"
    r"facture\s*n[°o]|n[°o]\s*facture|n[úu]mero\s*(?:de\s*)?factura|"
    r"factuurnummer|fattura\s*n[°o])\s*[:\-]?\s*(\S+)",
    re.IGNORECASE,
)

_DUE_DATE_RE = re.compile(
    r"(?:due\s*date|payment\s*due|forfald|f(?:\u00e4|ae)llig(?:\s*/\s*due)?|"
    r"vencimiento|(?:date\s+d['\u2019]\s*)?[e\u00e9]ch[e\u00e9]ance|"
    r"scadenza|vervaldatum)\s*[:\-]?\s*"
    r"([0-9]{1,4}[-/.\s][0-9]{1,2}[-/.\s][0-9]{1,4}|\d{1,2}\s+\w+\s+\d{2,4})",
    re.IGNORECASE,
)

_AMOUNT_RE = re.compile(
    r"(?:i\s*alt|total\s*due|grand\s*total|total\s*amount|amount\s*due|"
    r"gesamtbetrag|montant\s*total|importe\s*total|totale|totaal)\s*[:\-]?\s*"
    r"(DKK|EUR|USD|GBP|SEK|NOK|CHF|JPY)?\s*([\d.,]+)\s*"
    r"(DKK|EUR|USD|GBP|SEK|NOK|CHF|JPY)?",
    re.IGNORECASE,
)

_CURRENCY_LABEL_RE = re.compile(
    r"(?:currency|w(?:\u00e4|ae)hrung|devise|moneda|valuta)\s*[:\-/]*\s*"
    r"(DKK|EUR|USD|GBP|SEK|NOK|CHF|JPY)",
    re.IGNORECASE,
)

_CUSTOMER_ANCHORS: tuple[str, ...] = (
    "Bill To",
    "Billed To",
    "Customer",
    "Til",
    "Empf\u00e4nger",
    "Cliente",
    "Client",
    "Kunde",
    "Afnemer",
)


class GenericKeywordAdapter:
    name = "generic"
    language = "multi"

    def detect_score(self, text: str) -> float:
        # Always a viable fallback if we can see any text at all.
        return 0.25 if text.strip() else 0.0

    def extract(self, text: str, ctx: ExtractionContext) -> CanonicalInvoice:
        invoice_no_match = _INVOICE_NO_RE.search(text)
        invoice_no = invoice_no_match.group(1) if invoice_no_match else None

        due_match = _DUE_DATE_RE.search(text)
        raw_due = due_match.group(1) if due_match else None

        amount_match = _AMOUNT_RE.search(text)
        amount = None
        parsed_currency: str | None = None
        explicit_currency: str | None = None
        if amount_match:
            amount, parsed_currency = extract_amount(amount_match.group(2), ctx)
            explicit_currency = amount_match.group(1) or amount_match.group(3)

        label_currency_match = _CURRENCY_LABEL_RE.search(text)
        if label_currency_match and not explicit_currency:
            explicit_currency = label_currency_match.group(1)

        return CanonicalInvoice(
            invoice_no=invoice_no,
            vendor=first_non_empty_line(text),
            customer=extract_customer(text, anchors=_CUSTOMER_ANCHORS),
            due_date=extract_date(raw_due, ctx, "due_date") if raw_due else None,
            gross_total_amount=amount,
            billing_type=detect_billing_type(text),
            currency=finalize_currency(parsed_currency, explicit_currency, ctx),
        )
