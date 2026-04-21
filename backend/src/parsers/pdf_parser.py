"""Parse PDFs into `ParseResult`s using a cascade of adapters.

Pipeline per PDF:
  1. Read text via pypdf.
  2. Score each adapter via `detect_score(text)`; try them highest-first.
  3. The primary adapter's output is the base. If any canonical field is still
     missing, subsequent adapters are run as fallbacks and merged in.
  4. Compute a status: `parsed` (all canonical fields present), `partial`
     (some present), or `failed` (none / unreadable).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from pathlib import Path

from pypdf import PdfReader

from src.adapters import ALL_ADAPTERS
from src.adapters.base import ExtractionContext, InvoiceAdapter
from src.domain import CANONICAL_FIELDS, CanonicalInvoice, ParseResult, ParseStatus

logger = logging.getLogger(__name__)

_TEXT_PREVIEW_CHARS = 500


def _read_pdf_text(path: Path) -> str:
    reader = PdfReader(path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _rank_adapters(
    text: str, adapters: Sequence[InvoiceAdapter]
) -> list[tuple[InvoiceAdapter, float]]:
    scored = [(a, a.detect_score(text)) for a in adapters]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored


def _status_for(invoice: CanonicalInvoice) -> ParseStatus:
    missing = invoice.missing_fields()
    if len(missing) == len(CANONICAL_FIELDS):
        return "failed"
    return "parsed" if not missing else "partial"


def parse_pdf(
    pdf_path: Path,
    adapters: Sequence[InvoiceAdapter] = ALL_ADAPTERS,
) -> ParseResult:
    """Parse a single PDF into a `ParseResult`."""
    source_file = pdf_path.name

    try:
        text = _read_pdf_text(pdf_path)
    except Exception as exc:
        logger.exception("Failed to read PDF %s", pdf_path)
        return ParseResult(
            source_file=source_file,
            status="failed",
            invoice=CanonicalInvoice(),
            missing_fields=list(CANONICAL_FIELDS),
            error=f"Could not read PDF: {exc}",
        )

    if not text.strip():
        return ParseResult(
            source_file=source_file,
            status="failed",
            invoice=CanonicalInvoice(),
            missing_fields=list(CANONICAL_FIELDS),
            error="PDF has no extractable text (may be scanned/image-only)",
            text_preview="",
        )

    ctx = ExtractionContext()
    ranked = _rank_adapters(text, adapters)
    adapters_tried: list[str] = []
    merged = CanonicalInvoice()
    primary_adapter: str | None = None

    for adapter, score in ranked:
        if score <= 0:
            continue
        adapters_tried.append(adapter.name)

        try:
            extracted = adapter.extract(text, ctx)
        except Exception as exc:
            ctx.warn(f"adapter '{adapter.name}' crashed: {exc}")
            continue

        merged = merged.merged_with(extracted)

        if primary_adapter is None and any(
            getattr(extracted, f) not in (None, "") for f in CANONICAL_FIELDS
        ):
            primary_adapter = adapter.name

        if not merged.missing_fields():
            # All canonical fields filled -- no need to try further adapters.
            break

    status = _status_for(merged)

    if status == "failed":
        ctx.warn("No adapter produced any canonical fields")

    return ParseResult(
        source_file=source_file,
        status=status,
        invoice=merged,
        adapter_used=primary_adapter,
        adapters_tried=adapters_tried,
        missing_fields=merged.missing_fields(),
        warnings=ctx.warnings,
        text_preview=text[:_TEXT_PREVIEW_CHARS],
    )


def parse_folder(
    folder: Path,
    adapters: Sequence[InvoiceAdapter] = ALL_ADAPTERS,
) -> list[ParseResult]:
    """Parse every `*.pdf` in `folder` (non-recursive) into `ParseResult`s."""
    if not folder.exists():
        raise FileNotFoundError(f"PDF input folder does not exist: {folder}")
    if not folder.is_dir():
        raise NotADirectoryError(f"Not a directory: {folder}")

    pdfs = sorted(folder.glob("*.pdf"))
    logger.info("Parsing %d PDFs from %s", len(pdfs), folder)

    results: list[ParseResult] = []
    for pdf in pdfs:
        result = parse_pdf(pdf, adapters)
        if result.status == "failed":
            logger.warning(
                "FAILED to parse %s: error=%s warnings=%s",
                result.source_file,
                result.error,
                result.warnings,
            )
        elif result.status == "partial":
            logger.info(
                "PARTIAL parse %s: missing=%s",
                result.source_file,
                result.missing_fields,
            )
        results.append(result)

    return results


def summarize(results: Iterable[ParseResult]) -> dict[str, int]:
    counts = {"total": 0, "parsed": 0, "partial": 0, "failed": 0}
    for r in results:
        counts["total"] += 1
        counts[r.status] += 1
    return counts
