"""Executable launcher for packaged desktop-style runtime.

This module is the PyInstaller entrypoint. It prepares runtime paths,
configures environment variables, opens the browser, then starts uvicorn.
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
PDF_DIR_NAME = "pdf_invoices"


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
        time.sleep(delay_s)
        webbrowser.open(url)

    threading.Thread(target=_worker, daemon=True).start()


def main() -> None:
    host = DEFAULT_HOST
    port = _pick_port(host, DEFAULT_PORT)

    base_dir, bundle_dir = _runtime_dirs()
    _set_runtime_env(base_dir, bundle_dir)
    _ensure_import_paths(base_dir, bundle_dir)
    _open_browser_when_ready(f"http://{host}:{port}")

    uvicorn.run(
        "src.api.app:app",
        host=host,
        port=port,
        log_level=os.environ.get("LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    main()
