"""Parse-folder pipeline + in-memory store backing the API."""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from src.domain import ParseResult
from src.parsers.pdf_parser import parse_folder, summarize

logger = logging.getLogger(__name__)


class RunSummary(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    started_at: datetime
    completed_at: datetime | None = None
    pdf_input_dir: str
    counts: dict[str, int] = Field(default_factory=dict)


class ParseStore:
    """Thread-safe in-memory store of the latest parse run."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._results: list[ParseResult] = []
        self._run: RunSummary | None = None

    def replace(self, results: list[ParseResult], run: RunSummary) -> None:
        with self._lock:
            self._results = results
            self._run = run

    def update_result(self, updated: ParseResult) -> bool:
        with self._lock:
            for i, r in enumerate(self._results):
                if r.id == updated.id:
                    self._results[i] = updated
                    return True
        return False

    @property
    def results(self) -> list[ParseResult]:
        with self._lock:
            return list(self._results)

    @property
    def run(self) -> RunSummary | None:
        with self._lock:
            return self._run


def run_parse(pdf_input_dir: Path, store: ParseStore) -> RunSummary:
    """Parse every PDF in `pdf_input_dir` and publish the result to `store`."""
    started_at = datetime.now()
    run = RunSummary(started_at=started_at, pdf_input_dir=str(pdf_input_dir))

    logger.info("Parse run %s started for %s", run.id, pdf_input_dir)

    results = parse_folder(pdf_input_dir)
    run.counts = summarize(results)
    run.completed_at = datetime.now()

    store.replace(results, run)

    logger.info(
        "Parse run %s complete: %s (%d PDFs, %d failed, %d partial, %d parsed)",
        run.id,
        run.counts,
        run.counts.get("total", 0),
        run.counts.get("failed", 0),
        run.counts.get("partial", 0),
        run.counts.get("parsed", 0),
    )

    return run
