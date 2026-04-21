"""KMD A/S invoice adapter.

KMD invoices come in two layouts:

* **Inline layout** - labels and values on the same line, block-aligned::

    KMD A/S - Lautrupparken 40 - 2750 Ballerup
    CVR nr.: DK26911745
    Fakturanr. 97612447
    Fakturadato 10.05.2022
    Forfaldsdato 09.06.2022

* **Stacked layout** - all labels first, values below in the same order::

    Fakturadato 23.01.2024
    Forfaldsdato
    Kundenr.
    22.02.2024
    12425
    Fakturanr. 700000007451

The grand total also has two layouts. In the stacked layout the value is on
the line directly after ``Pris i alt (DKK)``. In the inline layout the values
appear as a single whitespace-separated row after the column headers, with
the total being the largest amount on that row.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from src.adapters._shared import finalize_currency
from src.adapters.base import ExtractionContext
from src.domain import CanonicalInvoice
from src.parsers.normalization import clean_line, parse_amount, parse_date

_DATE_TOKEN = r"\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4}"
# Strict: no internal whitespace, so that a single findall on an
# inline data row (``0,00  1.366,00 25,00``) yields separate tokens.
_AMOUNT_TOKEN = r"\d[\d.,]*\d"

_INVOICE_NO_INLINE = re.compile(
    r"Fakturanr\.?[^\S\n]+(\d{4,})",
    re.IGNORECASE,
)

_INVOICE_DATE_INLINE = re.compile(
    r"Fakturadato[^\S\n]+(" + _DATE_TOKEN + r")",
    re.IGNORECASE,
)

_DUE_DATE_INLINE = re.compile(
    r"Forfaldsdato[^\S\n]+(" + _DATE_TOKEN + r")",
    re.IGNORECASE,
)

_PRIS_I_ALT_LABEL = re.compile(
    r"Pris\s+i\s+alt\s*\(\s*DKK\s*\)",
    re.IGNORECASE,
)


def _extract_due_date_stacked(text: str, ctx: ExtractionContext) -> date | None:
    """Handle the stacked KMD layout where labels and values are separated.

    We anchor on ``Forfaldsdato`` followed by ``Kundenr.`` on the next
    non-empty line; the two values then appear in the same order::

        Forfaldsdato
        Kundenr.
        22.02.2024   <- due date
        12425        <- customer number
    """
    lines = [clean_line(line) for line in text.splitlines()]
    for idx, line in enumerate(lines):
        if not line.lower().startswith("forfaldsdato"):
            continue
        if idx + 1 >= len(lines):
            continue
        next_label = lines[idx + 1].lower()
        if "kundenr" not in next_label:
            continue
        # Walk forward to find the next two numeric/date tokens.
        for follow_idx in range(idx + 2, min(len(lines), idx + 8)):
            candidate = lines[follow_idx]
            if not candidate:
                continue
            m = re.match(r"(" + _DATE_TOKEN + r")", candidate)
            if not m:
                continue
            try:
                return parse_date(m.group(1))
            except ValueError as exc:
                ctx.warn(f"due_date: {exc}")
                return None
    return None


def _extract_gross_total(text: str, ctx: ExtractionContext) -> Decimal | None:
    """Return the KMD grand total (``Pris i alt (DKK)``)."""
    match = _PRIS_I_ALT_LABEL.search(text)
    if not match:
        return None

    tail = text[match.end() :]
    # Take the next ~6 non-empty lines for the data window.
    window: list[str] = []
    for raw in tail.splitlines():
        cleaned = clean_line(raw)
        if not cleaned:
            if window:
                # Stop at the first blank line after collecting some content.
                break
            continue
        window.append(cleaned)
        if len(window) >= 6:
            break

    candidates: list[Decimal] = []
    for line in window:
        # Only take lines that are purely amounts / whitespace (data rows),
        # ignoring column header prose.
        amount_tokens = re.findall(_AMOUNT_TOKEN, line)
        if not amount_tokens:
            continue
        stripped = re.sub(_AMOUNT_TOKEN, "", line).strip()
        if stripped and re.search(r"[A-Za-zÆØÅæøå]", stripped):
            continue
        for tok in amount_tokens:
            try:
                amt, _ = parse_amount(tok)
            except ValueError as exc:
                ctx.warn(f"gross_total_amount: {exc}")
                continue
            if amt is None:
                continue
            candidates.append(amt)

    if not candidates:
        return None
    # The grand total is always the largest amount in the summary block.
    return max(candidates)


def _extract_customer(text: str) -> str | None:
    """KMD invoices are all billed to 'Energinet...' variants."""
    for raw in text.splitlines():
        cleaned = clean_line(raw)
        if cleaned.lower().startswith("energinet"):
            return cleaned
    return None


class KMDAdapter:
    name = "kmd_da"
    language = "da"

    def detect_score(self, text: str) -> float:
        if "KMD A/S" in text and "Fakturanr" in text:
            return 1.0
        return 0.0

    def extract(self, text: str, ctx: ExtractionContext) -> CanonicalInvoice:
        invoice_no_match = _INVOICE_NO_INLINE.search(text)
        invoice_no = invoice_no_match.group(1) if invoice_no_match else None

        due_match = _DUE_DATE_INLINE.search(text)
        due_date: date | None = None
        if due_match:
            try:
                due_date = parse_date(due_match.group(1))
            except ValueError as exc:
                ctx.warn(f"due_date: {exc}")
        else:
            due_date = _extract_due_date_stacked(text, ctx)

        amount = _extract_gross_total(text, ctx)

        customer = _extract_customer(text)

        return CanonicalInvoice(
            invoice_no=invoice_no,
            vendor="KMD A/S",
            customer=customer,
            due_date=due_date,
            gross_total_amount=amount,
            billing_type="Invoice",
            currency=finalize_currency(None, "DKK", ctx),
        )
