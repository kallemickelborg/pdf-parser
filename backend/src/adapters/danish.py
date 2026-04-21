"""Generic Danish-language invoice adapter.

Acts as a fallback for Danish PDFs that don't match any vendor-specific
adapter (Crayon, SAP, KMD, Microsoft DK). Handles the common inline label
patterns only: ``Fakturanr. 12345``, ``Forfaldsdato 09.06.2022``,
``Faktura total 58.488,41 DKK``, etc.

Vendor-specific layouts (stacked footers, reversed labels, etc.) belong in
their own adapter modules.
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
from src.parsers.normalization import clean_line

_NUMBER_TOKEN = r"[A-Z0-9][A-Z0-9\-/]*"
_DATE_TOKEN = r"\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4}|\d{4}[./\-]\d{1,2}[./\-]\d{1,2}"
_AMOUNT_TOKEN = r"[\d][\d .,]*[\d]"
_CURRENCY_TOKEN = r"DKK|EUR|USD|GBP|SEK|NOK|CHF"

# Reversed layout: "12345Faktura nr:" - value precedes the label.
_INVOICE_NO_REVERSED = re.compile(
    r"(\d{4,})\s*Faktura(?:nr|\s*nr)\.?\s*:",
    re.IGNORECASE,
)
# Forward inline: "Fakturanr: AF-123" / "Fakturanummer 12345"
_INVOICE_NO_FORWARD = re.compile(
    r"Faktura(?:nr|nummer|\s*nr)\.?\s*[:.]?[^\S\n]*(" + _NUMBER_TOKEN + r")",
    re.IGNORECASE,
)

_DUE_DATE_REVERSED = re.compile(
    r"(" + _DATE_TOKEN + r")\s*Forfalds?\s*dato\s*:",
    re.IGNORECASE,
)
_DUE_DATE_FORWARD = re.compile(
    r"(?:Forfaldsdato|Forfalds?\s*dato|Forfald)\s*[:.]?[^\S\n]*(" + _DATE_TOKEN + r")",
    re.IGNORECASE,
)

# Amount labels in Danish invoices, ordered most-specific first. All use
# ``[^\S\n]*`` (whitespace except newline) so the value must sit on the same
# line as its label.
_AMOUNT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"(?:Faktura\s*total(?:\s*\([^)]*\))?|Fakturatotal)[^\S\n]*[:.]?[^\S\n]*"
        r"(?:(" + _CURRENCY_TOKEN + r")[^\S\n]*)?(" + _AMOUNT_TOKEN + r")"
        r"(?:[^\S\n]*(" + _CURRENCY_TOKEN + r"))?",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:Total\s*Incl\.?\s*Moms|I\s*alt\s*incl\.?\s*moms)[^\S\n]*[:.]?[^\S\n]*"
        r"(?:(" + _CURRENCY_TOKEN + r")[^\S\n]*)?(" + _AMOUNT_TOKEN + r")"
        r"(?:[^\S\n]*(" + _CURRENCY_TOKEN + r"))?",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:Pris\s*i\s*alt(?:\s*\(("
        + _CURRENCY_TOKEN
        + r")\))?)[^\S\n]*[:.]?[^\S\n]*("
        + _AMOUNT_TOKEN
        + r")",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bI\s*alt\b[^\S\n]*(?:(" + _CURRENCY_TOKEN + r")[^\S\n]*)?(" + _AMOUNT_TOKEN + r")"
        r"(?:[^\S\n]*(" + _CURRENCY_TOKEN + r"))?",
        re.IGNORECASE,
    ),
)

_SIGNAL_KEYWORDS = (
    "Faktura",
    "Fakturanr",
    "Fakturanummer",
    "Forfald",
    "Forfaldsdato",
    "Betaling",
    "I alt",
    "Pris i alt",
    "Moms",
    "Leverand\u00f8r",
)

_CUSTOMER_ANCHORS: tuple[str, ...] = (
    "Faktureringsadresse",
    "Fakturering til",
    "K\u00f8ber adresse",
    "Solgt til",
    "Til",
)

# Words that frequently appear adjacent to "Faktura" labels but are not
# invoice numbers (e.g. "Fakturanr. bedes opgivet..." = "Please state inv.").
_BAD_INVOICE_TOKENS: frozenset[str] = frozenset(
    {
        "bedes",
        "vores",
        "reference",
        "cms",
        "kontrakt",
        "ordrenummer",
        "ordre",
        "debitorkonto",
        "vat",
        "betalingsbetingelser",
        "deres",
        "dato",
        "nummer",
        "nr",
        "af",
    }
)

_PAGE_NUMBER_LINE = re.compile(
    r"^\s*(?:Side\s+\d+\s+af\s+\d+|Page\s+\d+\s+of\s+\d+|\d+\s*/\s*\d+)\s*$",
    re.IGNORECASE,
)


def _is_plausible_invoice_no(token: str) -> bool:
    lowered = token.lower()
    if lowered in _BAD_INVOICE_TOKENS:
        return False
    return bool(re.search(r"\d", token))


def _extract_invoice_no(text: str) -> str | None:
    reversed_match = _INVOICE_NO_REVERSED.search(text)
    if reversed_match:
        return reversed_match.group(1).strip()

    for match in _INVOICE_NO_FORWARD.finditer(text):
        candidate = match.group(1).strip()
        if _is_plausible_invoice_no(candidate):
            return candidate
    return None


def _extract_due_date_raw(text: str) -> str | None:
    match = _DUE_DATE_REVERSED.search(text) or _DUE_DATE_FORWARD.search(text)
    return match.group(1) if match else None


def _extract_total_amount(
    text: str, ctx: ExtractionContext
) -> tuple[object, str | None, str | None]:
    for pattern in _AMOUNT_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        groups = match.groups()
        currency_pre: str | None = None
        currency_post: str | None = None
        raw_amount: str | None = None
        if len(groups) == 3:
            currency_pre, raw_amount, currency_post = groups
        elif len(groups) == 2:
            currency_pre, raw_amount = groups
        if not raw_amount:
            continue
        amount, parsed_currency = extract_amount(raw_amount, ctx)
        return amount, parsed_currency, currency_pre or currency_post
    return None, None, None


def _extract_vendor(text: str) -> str | None:
    lines = text.splitlines()
    for i, raw in enumerate(lines):
        if re.match(r"\s*Leverand\u00f8r\s*:?\s*$", raw, re.IGNORECASE):
            for follow in lines[i + 1 : i + 2]:
                cleaned = clean_line(follow)
                if cleaned:
                    return cleaned

    for raw in lines:
        cleaned = clean_line(raw)
        if cleaned and not _PAGE_NUMBER_LINE.match(cleaned):
            return cleaned
    return first_non_empty_line(text)


class DanishAdapter:
    name = "danish"
    language = "da"

    def detect_score(self, text: str) -> float:
        hits = sum(1 for kw in _SIGNAL_KEYWORDS if kw.lower() in text.lower())
        return min(hits / 4, 1.0)

    def extract(self, text: str, ctx: ExtractionContext) -> CanonicalInvoice:
        invoice_no = _extract_invoice_no(text)
        due_date_raw = _extract_due_date_raw(text)
        due_date = extract_date(due_date_raw, ctx, "due_date") if due_date_raw else None

        amount, parsed_currency, explicit_currency = _extract_total_amount(text, ctx)

        return CanonicalInvoice(
            invoice_no=invoice_no,
            vendor=_extract_vendor(text),
            customer=extract_customer(text, anchors=_CUSTOMER_ANCHORS, max_lines=3),
            due_date=due_date,
            gross_total_amount=amount,
            billing_type=detect_billing_type(text),
            currency=finalize_currency(parsed_currency, explicit_currency, ctx),
        )
