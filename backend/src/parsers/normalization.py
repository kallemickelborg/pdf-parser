"""Normalization helpers for messy invoice data (amounts, dates, strings)."""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

_CURRENCY_PREFIX_RE = re.compile(r"^(DKK|EUR|USD|GBP|SEK|NOK|CHF|JPY)\s*", re.IGNORECASE)
_CURRENCY_SUFFIX_RE = re.compile(r"\s*(DKK|EUR|USD|GBP|SEK|NOK|CHF|JPY)\s*$", re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"\s+")

VALID_CURRENCIES: frozenset[str] = frozenset(
    {"DKK", "EUR", "USD", "GBP", "SEK", "NOK", "CHF", "JPY"}
)

_DATE_FORMATS: tuple[str, ...] = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%m/%d/%Y",
    "%d %b %Y",
    "%d %B %Y",
)


def parse_amount(raw: str) -> tuple[Decimal, str | None]:
    """Parse an amount string into `(Decimal, currency_or_None)`.

    Handles US (1,234.56) and EU (1.234,56) number formats and optional
    currency prefix/suffix (e.g. "DKK 12,450.00" or "12 450,00 EUR").
    """
    text = raw.strip()
    extracted_currency: str | None = None

    prefix_match = _CURRENCY_PREFIX_RE.match(text)
    if prefix_match:
        extracted_currency = prefix_match.group(1).upper()
        text = text[prefix_match.end() :].strip()
    else:
        suffix_match = _CURRENCY_SUFFIX_RE.search(text)
        if suffix_match:
            extracted_currency = suffix_match.group(1).upper()
            text = text[: suffix_match.start()].strip()

    text = text.strip('"').replace(" ", "")

    if "," in text and "." in text:
        # Whichever separator appears last is the decimal separator.
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        parts = text.split(",")
        if len(parts) == 2 and len(parts[1]) == 2:
            # Treat two-digit comma suffix as EU decimal (e.g. 1234,56).
            text = text.replace(",", ".")
        else:
            text = text.replace(",", "")

    try:
        return Decimal(text), extracted_currency
    except InvalidOperation as exc:
        raise ValueError(f"Cannot parse amount: '{raw}'") from exc


def parse_date(raw: str) -> date:
    """Parse a date string using a range of common invoice date formats."""
    text = raw.strip()
    if not text:
        raise ValueError("Empty date string")

    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    raise ValueError(f"Cannot parse date: '{raw}'")


def clean_line(raw: str) -> str:
    """Collapse whitespace and strip leading/trailing punctuation/whitespace."""
    return _WHITESPACE_RE.sub(" ", raw).strip(" \t\r\n·|,:;")


def normalize_currency(raw: str | None) -> str | None:
    if not raw:
        return None
    upper = raw.strip().upper()
    return upper if upper in VALID_CURRENCIES else None
