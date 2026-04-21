"""SAP Danmark A/S invoice adapter.

SAP emits two distinct Danish/English invoice templates:

* **Legacy Danish (`SAP_INVOICE_Z_INV_SOFT`)** - fields packed into a single
  line, DKK grand total at the bottom::

      Fakturanummer 6011070455 af 11.07.2022 7.858,81 EUR
      ...
      Faktura total 58.488,41 DKK
      Betalingsbetingelser: 30 dage netto.

* **Current English (`SAP_INV_NGBCA4`)** - ordinal English dates and a
  multi-currency total row::

      Invoice No. 10011240000091 issued on 5th of Jan. 2024
       due on 4th of Feb. 2024 203.040,00 EUR
      ...
      Total 203.040,00 EUR 1.514.475,36 DKK

The adapter detects which template is in use and dispatches accordingly.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from decimal import Decimal

from src.adapters._shared import extract_amount, finalize_currency
from src.adapters.base import ExtractionContext
from src.domain import CanonicalInvoice
from src.parsers.normalization import parse_date

# ---------------------------------------------------------------------------
# Legacy Danish template
# ---------------------------------------------------------------------------

_LEGACY_HEADER_LINE = re.compile(
    r"Fakturanummer\s+(\d+)\s+af\s+"
    r"(\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4})\s+"
    r"([\d][\d .,]*[\d])\s+(DKK|EUR|USD|GBP|SEK|NOK|CHF)",
    re.IGNORECASE,
)

_LEGACY_FAKTURA_TOTAL = re.compile(
    r"Faktura\s+total\s+([\d][\d .,]*[\d])\s+(DKK|EUR|USD|GBP|SEK|NOK|CHF)",
    re.IGNORECASE,
)

_LEGACY_PAYMENT_TERMS = re.compile(
    r"Betalingsbetingelser\s*:?\s*(\d+)\s*dage?\s*netto",
    re.IGNORECASE,
)

_LEGACY_SOLGT_TIL = re.compile(
    r"Solgt\s+til\s*:\s*(?:\d+\s*,\s*)?(.+?)(?:\r?\n|$)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Current English template
# ---------------------------------------------------------------------------

_ENGLISH_INVOICE_NO = re.compile(
    r"Invoice\s+No\.?\s+(\d{6,})",
    re.IGNORECASE,
)

_ORDINAL_DATE_TOKEN = r"\d{1,2}(?:st|nd|rd|th)?\s+of\s+[A-Z][a-z]+\.?\s+\d{4}"

_ENGLISH_ISSUED_ON = re.compile(
    r"issued\s+on\s+(" + _ORDINAL_DATE_TOKEN + r")",
    re.IGNORECASE,
)

_ENGLISH_DUE_ON = re.compile(
    r"due\s+(?:on|Date)\s+(" + _ORDINAL_DATE_TOKEN + r")",
    re.IGNORECASE,
)

# A row like "Total 203.040,00 EUR 1.514.475,36 DKK" - grab the DKK side.
_ENGLISH_TOTAL_ROW = re.compile(
    r"^\s*Total\s+([\d][\d .,]*[\d])\s+([A-Z]{3})"
    r"(?:\s+([\d][\d .,]*[\d])\s+(DKK))?\s*$",
    re.IGNORECASE | re.MULTILINE,
)

_ENGLISH_SOLD_TO = re.compile(
    r"Sold-to-Party\s+(?:\d+\s*,\s*)?(.+?)(?:\r?\n|$)",
    re.IGNORECASE,
)

_MONTH_LOOKUP: dict[str, int] = {
    **{
        m: i + 1
        for i, m in enumerate(
            ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
        )
    },
    **{
        m: i + 1
        for i, m in enumerate(
            (
                "january",
                "february",
                "march",
                "april",
                "may",
                "june",
                "july",
                "august",
                "september",
                "october",
                "november",
                "december",
            )
        )
    },
    "sept": 9,
}


def _parse_ordinal_date(raw: str) -> date | None:
    """Parse ``5th of Jan. 2024`` / ``22nd of February 2024``."""
    match = re.match(
        r"(\d{1,2})(?:st|nd|rd|th)?\s+of\s+([A-Za-z]+)\.?\s+(\d{4})",
        raw.strip(),
    )
    if not match:
        return None
    day = int(match.group(1))
    month = _MONTH_LOOKUP.get(match.group(2).lower())
    if month is None:
        return None
    try:
        return date(int(match.group(3)), month, day)
    except ValueError:
        return None


class SAPAdapter:
    name = "sap_da"
    language = "da"

    def detect_score(self, text: str) -> float:
        if "SAP_INVOICE_Z_INV_SOFT" in text:
            return 1.0
        if "SAP_INV_NGBCA4" in text:
            return 1.0
        if "SAP Danmark A/S" in text:
            return 1.0
        return 0.0

    def extract(self, text: str, ctx: ExtractionContext) -> CanonicalInvoice:
        # The English template uses ordinal dates and a multi-currency total
        # row that the legacy regexes won't match; dispatch up front.
        if "SAP_INV_NGBCA4" in text:
            return self._extract_english(text, ctx)
        return self._extract_legacy(text, ctx)

    def _extract_legacy(self, text: str, ctx: ExtractionContext) -> CanonicalInvoice:
        header = _LEGACY_HEADER_LINE.search(text)
        invoice_no: str | None = None
        invoice_date: date | None = None
        header_amount: Decimal | None = None
        header_currency: str | None = None

        if header:
            invoice_no = header.group(1)
            try:
                invoice_date = parse_date(header.group(2))
            except ValueError as exc:
                ctx.warn(f"invoice_date: {exc}")
            header_amount, _ = extract_amount(header.group(3), ctx)
            header_currency = header.group(4).upper()
        else:
            ctx.warn("SAP header line not found")

        totals: list[tuple[Decimal, str]] = []
        for match in _LEGACY_FAKTURA_TOTAL.finditer(text):
            amt, _ = extract_amount(match.group(1), ctx)
            if amt is None:
                continue
            totals.append((amt, match.group(2).upper()))

        gross_total_amount: Decimal | None = None
        currency: str | None = None
        dkk_totals = [t for t in totals if t[1] == "DKK"]
        if dkk_totals:
            gross_total_amount, currency = dkk_totals[-1]
        elif totals:
            gross_total_amount, currency = totals[-1]
        elif header_amount is not None:
            gross_total_amount, currency = header_amount, header_currency

        due_date: date | None = None
        pay_terms = _LEGACY_PAYMENT_TERMS.search(text)
        if pay_terms and invoice_date:
            due_date = invoice_date + timedelta(days=int(pay_terms.group(1)))
        elif invoice_date:
            due_date = invoice_date + timedelta(days=30)
            ctx.warn("due_date inferred from default SAP payment terms (net 30)")

        solgt_til = _LEGACY_SOLGT_TIL.search(text)
        customer = solgt_til.group(1).strip() if solgt_til else None

        return CanonicalInvoice(
            invoice_no=invoice_no,
            vendor="SAP Danmark A/S",
            customer=customer,
            due_date=due_date,
            gross_total_amount=gross_total_amount,
            billing_type="Invoice",
            currency=finalize_currency(None, currency, ctx),
        )

    def _extract_english(self, text: str, ctx: ExtractionContext) -> CanonicalInvoice:
        m_inv = _ENGLISH_INVOICE_NO.search(text)
        invoice_no = m_inv.group(1) if m_inv else None

        due_date: date | None = None
        m_due = _ENGLISH_DUE_ON.search(text)
        if m_due:
            due_date = _parse_ordinal_date(m_due.group(1))
            if due_date is None:
                ctx.warn(f"due_date: could not parse '{m_due.group(1)}'")
        if due_date is None:
            m_iss = _ENGLISH_ISSUED_ON.search(text)
            if m_iss:
                issued = _parse_ordinal_date(m_iss.group(1))
                if issued is not None:
                    # English SAP invoices state "Payment is due Within 30 days".
                    due_date = issued + timedelta(days=30)
                    ctx.warn("due_date inferred from issued date + 30 days")

        # Prefer the DKK column of the "Total" row; fall back to the primary
        # (EUR) column if there is no DKK conversion.
        gross_total_amount: Decimal | None = None
        currency: str | None = None
        for match in _ENGLISH_TOTAL_ROW.finditer(text):
            dkk_amount_raw = match.group(3)
            if dkk_amount_raw is not None:
                amt, _ = extract_amount(dkk_amount_raw, ctx)
                if amt is not None:
                    gross_total_amount = amt
                    currency = "DKK"
                    break
            amt, _ = extract_amount(match.group(1), ctx)
            if amt is not None:
                gross_total_amount = amt
                currency = match.group(2).upper()
                break

        m_cust = _ENGLISH_SOLD_TO.search(text)
        customer = m_cust.group(1).strip() if m_cust else None

        return CanonicalInvoice(
            invoice_no=invoice_no,
            vendor="SAP Danmark A/S",
            customer=customer,
            due_date=due_date,
            gross_total_amount=gross_total_amount,
            billing_type="Invoice",
            currency=finalize_currency(None, currency, ctx),
        )
