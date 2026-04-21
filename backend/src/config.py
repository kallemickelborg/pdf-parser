"""Runtime configuration for the PDF invoice parser."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


_DEFAULT_PDF_DIR = _base_dir() / "pdf_invoices"


@dataclass(frozen=True)
class AppConfig:
    pdf_input_dir: Path = _DEFAULT_PDF_DIR
    log_level: str = "INFO"
    parse_on_startup: bool = True

    @classmethod
    def from_env(cls) -> AppConfig:
        pdf_dir_env = os.environ.get("PDF_INPUT_DIR")
        pdf_dir = Path(pdf_dir_env).expanduser().resolve() if pdf_dir_env else _DEFAULT_PDF_DIR
        return cls(
            pdf_input_dir=pdf_dir,
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
            parse_on_startup=os.environ.get("PARSE_ON_STARTUP", "1") != "0",
        )
