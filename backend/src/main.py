"""Executable launcher for packaged desktop-style runtime.

This module is the PyInstaller entrypoint. It prepares runtime paths,
configures environment variables, opens the browser, then starts uvicorn.
"""

from __future__ import annotations

import logging
import os
import socket
import sys
import threading
import time
import webbrowser
from copy import deepcopy
from pathlib import Path

import uvicorn
from uvicorn.config import LOGGING_CONFIG

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
PDF_DIR_NAME = "pdf_invoices"
LOG_FILE_NAME = "pdf-parser.log"


def _repo_root_from_source() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _runtime_dirs() -> tuple[Path, Path]:
    """Return (base_dir, bundle_dir)."""
    if getattr(sys, "frozen", False):
        base_dir = Path(sys.executable).resolve().parent
        bundle_dir = Path(getattr(sys, "_MEIPASS", base_dir)).resolve()
        return base_dir, bundle_dir

    repo_root = _repo_root_from_source()
    return repo_root, repo_root / "frontend" / "dist"


def _try_bind(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def _pick_port(host: str, preferred_port: int) -> int:
    if _try_bind(host, preferred_port):
        return preferred_port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def _set_runtime_env(base_dir: Path, bundle_dir: Path) -> None:
    if "PDF_INPUT_DIR" not in os.environ:
        pdf_dir = base_dir / PDF_DIR_NAME
        pdf_dir.mkdir(parents=True, exist_ok=True)
        os.environ["PDF_INPUT_DIR"] = str(pdf_dir)

    static_dir = bundle_dir / "static"
    if static_dir.exists():
        os.environ.setdefault("STATIC_DIR", str(static_dir))


def _ensure_import_paths(base_dir: Path, bundle_dir: Path) -> None:
    for candidate in (bundle_dir, base_dir):
        src_dir = candidate / "src"
        if src_dir.exists():
            candidate_str = str(candidate)
            if candidate_str not in sys.path:
                sys.path.insert(0, candidate_str)


def _open_browser_when_ready(url: str, delay_s: float = 1.5) -> None:
    def _worker() -> None:
        try:
            time.sleep(delay_s)
            opened = webbrowser.open(url)
            logging.getLogger("launcher").info(
                "Browser open attempted for %s (success=%s)", url, opened
            )
        except Exception:
            logging.getLogger("launcher").exception("Failed to open browser for %s", url)

    threading.Thread(target=_worker, daemon=True).start()


def _setup_launcher_logging(base_dir: Path) -> Path:
    log_file = base_dir / LOG_FILE_NAME
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("launcher")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return log_file


def _uvicorn_log_config(log_file: Path) -> dict[str, object]:
    config = deepcopy(LOGGING_CONFIG)

    handlers = config.setdefault("handlers", {})
    if isinstance(handlers, dict):
        handlers["file"] = {
            "class": "logging.FileHandler",
            "formatter": "default",
            "filename": str(log_file),
            "encoding": "utf-8",
        }

    loggers = config.setdefault("loggers", {})
    if isinstance(loggers, dict):
        for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
            logger_config = loggers.get(logger_name, {})
            if isinstance(logger_config, dict):
                existing_handlers = logger_config.get("handlers", [])
                if isinstance(existing_handlers, list) and "file" not in existing_handlers:
                    logger_config["handlers"] = [*existing_handlers, "file"]
                logger_config["propagate"] = False

    return config


def main() -> None:
    host = DEFAULT_HOST

    base_dir, bundle_dir = _runtime_dirs()
    log_file = _setup_launcher_logging(base_dir)
    logger = logging.getLogger("launcher")
    logger.info("Launcher starting")
    logger.info("Log file: %s", log_file)
    logger.info("Base dir: %s", base_dir)
    logger.info("Bundle dir: %s", bundle_dir)

    port = _pick_port(host, DEFAULT_PORT)
    if port != DEFAULT_PORT:
        logger.warning("Default port %s unavailable, selected %s", DEFAULT_PORT, port)

    _set_runtime_env(base_dir, bundle_dir)
    _ensure_import_paths(base_dir, bundle_dir)
    logger.info("PDF_INPUT_DIR=%s", os.environ.get("PDF_INPUT_DIR", "unset"))
    logger.info("STATIC_DIR=%s", os.environ.get("STATIC_DIR", "unset"))
    _open_browser_when_ready(f"http://{host}:{port}")
    logger.info("Starting server on http://%s:%s", host, port)

    try:
        uvicorn.run(
            "src.api.app:app",
            host=host,
            port=port,
            log_level=os.environ.get("LOG_LEVEL", "info").lower(),
            log_config=_uvicorn_log_config(log_file),
        )
    except Exception:
        logger.exception("Fatal launcher error")
        raise


if __name__ == "__main__":
    main()
