"""API routes for the PDF invoice parser dashboard."""

from __future__ import annotations

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from src.api.schemas import (
    CanonicalInvoiceResponse,
    InvoicesResponse,
    ParseResultResponse,
    SummaryResponse,
)
from src.config import AppConfig
from src.domain import ParseResult
from src.exporter import EXPORT_COLUMNS, export_to_xlsx
from src.pipeline import ParseStore, run_parse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

_store: ParseStore | None = None
_config: AppConfig | None = None


def configure(store: ParseStore, config: AppConfig) -> None:
    """Wire runtime state in from the app factory."""
    global _store, _config  # noqa: PLW0603
    _store = store
    _config = config


def _require_store() -> ParseStore:
    if _store is None:
        raise HTTPException(status_code=500, detail="Parse store not configured")
    return _store


def _require_config() -> AppConfig:
    if _config is None:
        raise HTTPException(status_code=500, detail="Config not configured")
    return _config


def _to_result_response(r: ParseResult) -> ParseResultResponse:
    return ParseResultResponse(
        id=str(r.id),
        source_file=r.source_file,
        status=r.status,
        invoice=CanonicalInvoiceResponse(**r.invoice.model_dump()),
        adapter_used=r.adapter_used,
        adapters_tried=r.adapters_tried,
        missing_fields=r.missing_fields,
        warnings=r.warnings,
        error=r.error,
        text_preview=r.text_preview,
    )


def _build_summary(store: ParseStore, config: AppConfig) -> SummaryResponse:
    run = store.run
    counts = run.counts if run else {"total": 0, "parsed": 0, "partial": 0, "failed": 0}
    return SummaryResponse(
        total=counts.get("total", 0),
        parsed=counts.get("parsed", 0),
        partial=counts.get("partial", 0),
        failed=counts.get("failed", 0),
        pdf_input_dir=str(config.pdf_input_dir),
        run_id=str(run.id) if run else None,
        started_at=run.started_at if run else None,
        completed_at=run.completed_at if run else None,
    )


StatusFilter = Literal["all", "parsed", "partial", "failed"]


@router.get("/invoices", response_model=InvoicesResponse)
def list_invoices(
    status: Annotated[
        StatusFilter,
        Query(description="Filter by parse status"),
    ] = "all",
) -> InvoicesResponse:
    store = _require_store()
    config = _require_config()

    results = store.results
    if status != "all":
        results = [r for r in results if r.status == status]

    return InvoicesResponse(
        summary=_build_summary(store, config),
        results=[_to_result_response(r) for r in results],
    )


@router.get("/invoices/failed", response_model=list[ParseResultResponse])
def list_failed() -> list[ParseResultResponse]:
    """Shortcut endpoint: PDFs that produced zero canonical fields or errored out."""
    store = _require_store()
    return [_to_result_response(r) for r in store.results if r.status == "failed"]


@router.get("/summary", response_model=SummaryResponse)
def get_summary() -> SummaryResponse:
    return _build_summary(_require_store(), _require_config())


@router.post("/reparse", response_model=SummaryResponse)
def reparse() -> SummaryResponse:
    """Re-run the parser against the configured PDF folder."""
    config = _require_config()
    store = _require_store()
    run_parse(config.pdf_input_dir, store)
    return _build_summary(store, config)


@router.get("/export.xlsx")
def export_xlsx(
    include_partial: Annotated[
        bool,
        Query(description="Include partial rows too (default: only fully validated)"),
    ] = False,
) -> Response:
    """Export validated canonical invoice rows as an XLSX file."""
    store = _require_store()
    payload = export_to_xlsx(store.results, include_partial=include_partial)
    return Response(
        content=payload,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=invoices.xlsx",
            "X-Export-Columns": ",".join(EXPORT_COLUMNS),
        },
    )
