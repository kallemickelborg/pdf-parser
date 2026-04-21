"""Adapter protocol and shared extraction helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from src.domain import CanonicalInvoice


@dataclass
class ExtractionContext:
    """Passed to adapters so they can record non-fatal warnings."""

    warnings: list[str] = field(default_factory=list)

    def warn(self, message: str) -> None:
        self.warnings.append(message)


@runtime_checkable
class InvoiceAdapter(Protocol):
    """Strategy for extracting canonical invoice fields from PDF text."""

    name: str
    language: str

    def detect_score(self, text: str) -> float:
        """Return a 0..1 confidence that this adapter fits the given text."""
        ...

    def extract(self, text: str, ctx: ExtractionContext) -> CanonicalInvoice:
        """Extract whatever fields the adapter can find. Missing → None."""
        ...
