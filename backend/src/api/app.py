"""FastAPI application factory for the PDF invoice parser."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.routes import configure, router
from src.config import AppConfig
from src.pipeline import ParseStore, run_parse

logger = logging.getLogger(__name__)


class SPAStaticFiles(StaticFiles):
    """Static files with SPA-style fallback to index.html."""

    async def get_response(self, path: str, scope: dict[str, object]):  # type: ignore[override]
        response = await super().get_response(path, scope)
        if response.status_code != 404:
            return response
        return await super().get_response("index.html", scope)


def _resolve_static_dir() -> Path | None:
    env_dir = os.environ.get("STATIC_DIR")
    if env_dir:
        path = Path(env_dir).expanduser().resolve()
        index_file = path / "index.html"
        return path if index_file.exists() else None

    backend_root = Path(__file__).resolve().parents[2]
    fallback_dirs = (
        backend_root / "static",
        backend_root.parent / "frontend" / "dist",
    )
    for path in fallback_dirs:
        index_file = path / "index.html"
        if index_file.exists():
            return path
    return None


def create_app(*, config: AppConfig | None = None) -> FastAPI:
    cfg = config or AppConfig.from_env()
    logging.basicConfig(
        level=cfg.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    store = ParseStore()
    configure(store, cfg)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if cfg.parse_on_startup:
            logger.info("Running parse on startup against %s", cfg.pdf_input_dir)
            try:
                run_parse(cfg.pdf_input_dir, store)
            except FileNotFoundError:
                logger.warning(
                    "PDF input dir %s missing -- skipping startup parse", cfg.pdf_input_dir
                )
        yield

    app = FastAPI(
        title="PDF Invoice Parser API",
        description=(
            "Parses PDF invoices into a canonical model using language-specific adapters "
            "with a keyword-bag fallback for unknown templates."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)
    static_dir = _resolve_static_dir()
    if static_dir:
        app.mount("/", SPAStaticFiles(directory=static_dir, html=True), name="frontend")

    return app


app = create_app()
