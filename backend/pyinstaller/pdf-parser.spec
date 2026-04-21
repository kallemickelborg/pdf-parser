# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

datas: list[tuple[str, str]] = []
binaries: list[tuple[str, str]] = []
hiddenimports: list[str] = [
    "src",
    "src.api",
    "src.api.app",
    "src.api.routes",
    "src.api.schemas",
    "src.config",
    "src.pipeline",
    "src.exporter",
    "src.domain",
    "src.domain.invoice",
    "src.parsers",
    "src.parsers.normalization",
    "src.parsers.pdf_parser",
    "src.adapters",
    "src.adapters.base",
    "src.adapters._shared",
    "src.adapters.danish",
    "src.adapters.english",
    "src.adapters.generic",
    "src.adapters.bilingual_de_en",
    "src.adapters.sap_da",
    "src.adapters.microsoft_dk",
    "src.adapters.kmd_da",
    "src.adapters.crayon_da",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
]

for package in ("fastapi", "uvicorn", "pydantic", "pypdf", "openpyxl"):
    pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hiddenimports

hiddenimports += collect_submodules("src")
hiddenimports += collect_submodules("src.adapters")
hiddenimports += collect_submodules("src.api")
hiddenimports += collect_submodules("src.parsers")

datas.append(("../static", "static"))

a = Analysis(
    ["../src/main.py"],
    pathex=[".."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="pdf-parser",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
