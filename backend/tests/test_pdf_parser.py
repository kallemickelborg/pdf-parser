"""Smoke tests for PDF invoice parsing pipeline.

These tests verify architectural behavior (adapter cascade, fallback,
status classification) on synthetic text fixtures, plus a non-strict smoke
test on whatever PDFs happen to sit in `data/pdf_invoices/` at test time.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from src.adapters import (
    ALL_ADAPTERS,
    BilingualGermanEnglishAdapter,
    CrayonAdapter,
    DanishAdapter,
    EnglishAdapter,
    GenericKeywordAdapter,
)
from src.adapters.base import ExtractionContext
from src.parsers.pdf_parser import parse_folder, summarize

PDF_DIR = Path(__file__).parent.parent.parent / "data" / "pdf_invoices"


# ---------------------------------------------------------------------------
# Adapter unit tests (text-only, no PDF IO).
# ---------------------------------------------------------------------------


class TestDanishAdapter:
    def test_basic_danish_invoice(self) -> None:
        text = (
            "Vestjysk Industri A/S\n"
            "Fabriksvej 3\n"
            "Faktura\n"
            "Fakturanr:   AF-2026-058\n"
            "Dato:        2026-02-15\n"
            "Forfald:     2026-03-15\n"
            "Til: Cue ApS, S\u00f8ndergade 12, 8000 Aarhus C\n"
            "I alt  15,250.00 DKK\n"
        )
        ctx = ExtractionContext()
        inv = DanishAdapter().extract(text, ctx)

        assert inv.invoice_no == "AF-2026-058"
        assert inv.vendor == "Vestjysk Industri A/S"
        assert "Cue ApS" in (inv.customer or "")
        assert inv.due_date == date(2026, 3, 15)
        assert inv.gross_total_amount == Decimal("15250.00")
        assert inv.currency == "DKK"
        assert inv.billing_type == "Invoice"

    def test_reversed_label_microsoft_style(self) -> None:
        text = (
            "Microsoft Danmark ApS\n"
            "Kanalvej 7, 2800 Kongens Lyngby\n"
            "Faktura\n"
            "2015603265Faktura nr:\n"
            "2024/01/30Forfalds dato:\n"
            "K\u00f8ber adresse: Energinet DK, Fredericia\n"
            "Total Incl. Moms: 4.014.125,00\n"
        )
        ctx = ExtractionContext()
        inv = DanishAdapter().extract(text, ctx)

        assert inv.invoice_no == "2015603265"
        assert inv.due_date == date(2024, 1, 30)
        assert inv.gross_total_amount == Decimal("4014125.00")


class TestCrayonAdapter:
    def test_stacked_footer(self) -> None:
        text = (
            "Leverand\u00f8r\n"
            "Crayon A/S\n"
            "FAKTURA 1/2\n"
            "Fakturanummer Vores Reference\n"
            "4139526 Sarah Norengaard\n"
            "Leverand\u00f8r Kontonummer Betalingsinformation Forfaldsdato Fakturatotal\n"
            "40734073040663 +71<000413952607+87830764 26.05.2022 DKK      7 237 127,76\n"
        )
        ctx = ExtractionContext()
        inv = CrayonAdapter().extract(text, ctx)

        assert inv.invoice_no == "4139526"
        assert inv.vendor == "Crayon A/S"
        assert inv.due_date == date(2022, 5, 26)
        assert inv.gross_total_amount == Decimal("7237127.76")
        assert inv.currency == "DKK"

    def test_detect_score_requires_crayon_signature(self) -> None:
        assert CrayonAdapter().detect_score("Fakturanummer 12345\n") == 0.0
        assert CrayonAdapter().detect_score("Crayon A/S\nFakturanummer 1\n") == 1.0


class TestEnglishAdapter:
    def test_basic_english_invoice(self) -> None:
        text = (
            "Nordic Parts A/S\n"
            "Industrivej 42, 8000 Aarhus C\n"
            "INVOICE\n"
            "Invoice No: INV-2026-0041\n"
            "Due Date: 2026-03-03\n"
            "Bill To: Cue ApS, S\u00f8ndergade 12\n"
            "Total Due: DKK 12,450.00\n"
        )
        ctx = ExtractionContext()
        inv = EnglishAdapter().extract(text, ctx)

        assert inv.invoice_no == "INV-2026-0041"
        assert inv.vendor == "Nordic Parts A/S"
        assert "Cue ApS" in (inv.customer or "")
        assert inv.due_date == date(2026, 3, 3)
        assert inv.gross_total_amount == Decimal("12450.00")
        assert inv.currency == "DKK"
        assert inv.billing_type == "Invoice"


class TestBilingualAdapter:
    def test_bilingual_de_en_invoice(self) -> None:
        text = (
            "Schmidt & S\u00f8n Metals GmbH\n"
            "Metallstra\u00dfe 15, 20095 Hamburg\n"
            "Rechnung / Invoice\n"
            "Rechnungsnr. / Invoice No.\n"
            "SM-DE-2026-088\n"
            "F\u00e4llig / Due\n"
            "2026-03-04\n"
            "W\u00e4hrung / Currency\n"
            "DKK\n"
            "Empf\u00e4nger / Bill To:\n"
            "Cue ApS\n"
            "S\u00f8ndergade 12\n"
            "Gesamtbetrag / Total Amount\n"
            "DKK 67,830.00\n"
        )
        ctx = ExtractionContext()
        inv = BilingualGermanEnglishAdapter().extract(text, ctx)

        assert inv.invoice_no == "SM-DE-2026-088"
        assert inv.vendor == "Schmidt & S\u00f8n Metals GmbH"
        assert "Cue ApS" in (inv.customer or "")
        assert inv.due_date == date(2026, 3, 4)
        assert inv.gross_total_amount == Decimal("67830.00")
        assert inv.currency == "DKK"


class TestGenericFallback:
    def test_extracts_fields_on_unseen_french_template(self) -> None:
        text = (
            "Acme Widgets SARL\n"
            "123 Rue Principale, 75001 Paris\n"
            "FACTURE\n"
            "Facture N\u00b0: FR-2026-999\n"
            "Date d'\u00e9ch\u00e9ance: 2026-03-10\n"
            "Client: Cue ApS, Aarhus\n"
            "Montant total EUR 1.234,56\n"
        )
        ctx = ExtractionContext()
        inv = GenericKeywordAdapter().extract(text, ctx)

        assert inv.invoice_no == "FR-2026-999"
        assert inv.vendor == "Acme Widgets SARL"
        assert inv.gross_total_amount == Decimal("1234.56")
        assert inv.currency == "EUR"
        assert inv.due_date == date(2026, 3, 10)


class TestAdapterRegistry:
    def test_all_adapters_exported(self) -> None:
        names = {a.name for a in ALL_ADAPTERS}
        assert names == {
            "sap_da",
            "microsoft_dk",
            "kmd_da",
            "crayon_da",
            "danish",
            "english",
            "bilingual_de_en",
            "generic",
        }


# ---------------------------------------------------------------------------
# Pipeline smoke tests against whatever PDFs are in data/pdf_invoices/.
# Tests are tolerant: real-world corpus has many templates; we only assert
# that the pipeline runs without crashing and produces a consistent summary.
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not PDF_DIR.exists(), reason="PDF folder not present")
class TestPipelineSmoke:
    def test_parse_folder_does_not_crash(self) -> None:
        results = parse_folder(PDF_DIR)
        assert isinstance(results, list)
        assert all(r.source_file.endswith(".pdf") for r in results)

    def test_summary_is_consistent(self) -> None:
        results = parse_folder(PDF_DIR)
        counts = summarize(results)
        assert counts["total"] == len(results)
        assert counts["parsed"] + counts["partial"] + counts["failed"] == counts["total"]

    def test_every_result_has_valid_status(self) -> None:
        for r in parse_folder(PDF_DIR):
            assert r.status in {"parsed", "partial", "failed"}
            if r.status == "parsed":
                assert not r.missing_fields
            if r.status == "failed":
                # Either nothing was extracted or a hard error occurred.
                assert not r.invoice.invoice_no or r.error is not None
