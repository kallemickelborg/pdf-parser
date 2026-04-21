"""Helpers shared across adapters (vendor/customer detection, amount+date parsing)."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from src.adapters.base import ExtractionContext
from src.parsers.normalization import clean_line, normalize_currency, parse_amount, parse_date

_DOC_TYPE_KEYWORDS: tuple[tuple[str, str], ...] = (
    # Order matters: more specific matches first.
    ("credit note", "Credit Note"),
    ("kreditnota", "Credit Note"),
    ("gutschrift", "Credit Note"),
    ("proforma", "Proforma Invoice"),
    ("receipt", "Receipt"),
    ("kvittering", "Receipt"),
    ("quittung", "Receipt"),
    ("rechnung", "Invoice"),
    ("faktura", "Invoice"),
    ("invoice", "Invoice"),
)


def first_non_empty_line(text: str) -> str | None:
    """Return the first non-blank line of the PDF text (usually the vendor)."""
    for raw in text.splitlines():
        cleaned = clean_line(raw)
        if cleaned:
            return cleaned
    return None


def extract_amount(
    raw: str,
    ctx: ExtractionContext,
    field_name: str = "gross_total_amount",
) -> tuple[Decimal | None, str | None]:
    """Parse an amount match, reporting a warning if it fails."""
    try:
        amount, currency = parse_amount(raw)
    except ValueError as exc:
        ctx.warn(f"{field_name}: {exc}")
        return None, None
    return amount, currency


def extract_date(raw: str, ctx: ExtractionContext, field_name: str) -> date | None:
    try:
        return parse_date(raw)
    except ValueError as exc:
        ctx.warn(f"{field_name}: {exc}")
        return None


def detect_billing_type(text: str) -> str | None:
    """Infer the document type (Invoice / Credit Note / Receipt / ...)."""
    lowered = text.lower()
    for keyword, label in _DOC_TYPE_KEYWORDS:
        if keyword in lowered:
            return label
    return None


def extract_customer(
    text: str,
    anchors: tuple[str, ...],
    max_lines: int = 2,
) -> str | None:
    """Find customer name/address by anchoring on 'Bill To:', 'Til:', 'Empfänger:' etc.

    Returns the first non-empty line(s) following the anchor, joined with a comma.
    `max_lines` controls how many lines after the anchor we consider.
    """
    lines = text.splitlines()
    pattern = re.compile(
        r"(?:" + "|".join(re.escape(a) for a in anchors) + r")\s*:?\s*(.*)",
        re.IGNORECASE,
    )

    for i, raw in enumerate(lines):
        match = pattern.match(raw.strip())
        if not match:
            continue

        collected: list[str] = []
        inline = clean_line(match.group(1))
        if inline:
            collected.append(inline)

        # Pull following lines (some templates put customer info on the next line).
        remaining = max_lines - len(collected)
        for follow in lines[i + 1 : i + 1 + remaining]:
            cleaned = clean_line(follow)
            if not cleaned:
                break
            collected.append(cleaned)

        if collected:
            return ", ".join(collected)

    return None


def finalize_currency(
    parsed_currency: str | None,
    explicit_currency: str | None,
    ctx: ExtractionContext,
) -> str | None:
    """Pick the best currency signal (explicit label > amount-inline > None)."""
    for candidate in (explicit_currency, parsed_currency):
        normalized = normalize_currency(candidate)
        if normalized:
            return normalized
    if explicit_currency or parsed_currency:
        ctx.warn(f"Unknown currency: {explicit_currency or parsed_currency}")
    return None
