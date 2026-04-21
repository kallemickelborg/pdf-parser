"""Microsoft Danmark ApS invoice adapter.

Microsoft's Danish invoice template emits *reversed* label/value pairs, where
the value appears before the label on the same physical line::

    2015603265Faktura nr:
    2023/12/31Faktura dato:
    2024/01/30Forfalds dato:
    4.014.125,00Faktura Total Incl. Moms:

The grand total appears both as ``Total Incl. Moms:`` (summary block) and as
``Faktura Total Incl. Moms:`` (detail block); the latter is the authoritative
grand total.
"""

from __future__ import annotations

import re
from decimal import Decimal

from src.adapters._shared import extract_amount, finalize_currency
from src.adapters.base import ExtractionContext
from src.domain import CanonicalInvoice
from src.parsers.normalization import clean_line, parse_date

_DATE_TOKEN = r"[\d]{1,4}[./\-][\d]{1,2}[./\-][\d]{1,4}"
_AMOUNT_TOKEN = r"[\d][\d .,]*[\d]"

_INVOICE_NO_RE = re.compile(r"(\d{6,})\s*Faktura\s*nr\s*:", re.IGNORECASE)
_DUE_DATE_RE = re.compile(
    r"(" + _DATE_TOKEN + r")\s*Forfalds?\s*dato\s*:",
    re.IGNORECASE,
)
_INVOICE_DATE_RE = re.compile(
    r"(" + _DATE_TOKEN + r")\s*Faktura\s*dato\s*:",
    re.IGNORECASE,
)
_TOTAL_INCL_RE = re.compile(
    r"(" + _AMOUNT_TOKEN + r")\s*(?:Faktura\s+)?Total\s*Incl\.?\s*Moms\s*:?",
    re.IGNORECASE,
)
_CURRENCY_HEADER_RE = re.compile(
    r"(DKK|EUR|USD|GBP|SEK|NOK|CHF)\s*(?:Resum[eé]|Dokument\s*valuta)",
    re.IGNORECASE,
)

_CUSTOMER_ANCHOR = re.compile(
    r"Fakturerings?\s*adresse\s*:",
    re.IGNORECASE,
)


def _extract_customer_block(text: str) -> str | None:
    """The Microsoft template places the Fakturerings adresse label AFTER the
    address block. The customer is always exactly the 3 non-empty lines
    directly above the anchor (company, street, postcode+city)."""
    lines = text.splitlines()
    for idx, raw in enumerate(lines):
        if not _CUSTOMER_ANCHOR.search(raw):
            continue
        collected: list[str] = []
        back = idx - 1
        while back >= 0 and len(collected) < 3:
            line = clean_line(lines[back])
            back -= 1
            if not line:
                if collected:
                    break
                continue
            collected.append(line)
        collected.reverse()
        if collected:
            return ", ".join(collected)
    return None


class MicrosoftDKAdapter:
    name = "microsoft_dk"
    language = "da"

    def detect_score(self, text: str) -> float:
        if "Microsoft Danmark ApS" in text:
            return 1.0
        return 0.0

    def extract(self, text: str, ctx: ExtractionContext) -> CanonicalInvoice:
        invoice_no_match = _INVOICE_NO_RE.search(text)
        invoice_no = invoice_no_match.group(1) if invoice_no_match else None

        due_match = _DUE_DATE_RE.search(text)
        due_date = None
        if due_match:
            try:
                due_date = parse_date(due_match.group(1))
            except ValueError as exc:
                ctx.warn(f"due_date: {exc}")

        # Prefer the "Faktura Total Incl. Moms" grand total; fall back to any
        # "Total Incl. Moms" match if the explicit one is missing.
        gross_total_amount: Decimal | None = None
        faktura_totals: list[Decimal] = []
        summary_totals: list[Decimal] = []
        for match in _TOTAL_INCL_RE.finditer(text):
            prefix = text[max(0, match.start() - 40) : match.start()].lower()
            amt, _ = extract_amount(match.group(1), ctx)
            if amt is None:
                continue
            if "faktura" in prefix or "faktura" in match.group(0).lower():
                faktura_totals.append(amt)
            else:
                summary_totals.append(amt)
        if faktura_totals:
            gross_total_amount = faktura_totals[-1]
        elif summary_totals:
            gross_total_amount = summary_totals[-1]

        currency: str | None = None
        cur_match = _CURRENCY_HEADER_RE.search(text)
        if cur_match:
            currency = cur_match.group(1).upper()

        customer = _extract_customer_block(text)

        return CanonicalInvoice(
            invoice_no=invoice_no,
            vendor="Microsoft Danmark ApS",
            customer=customer,
            due_date=due_date,
            gross_total_amount=gross_total_amount,
            billing_type="Invoice",
            currency=finalize_currency(None, currency, ctx),
        )
