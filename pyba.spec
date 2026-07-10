# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Pyba onedir build.

Build with:  pyinstaller pyba.spec --noconfirm
Env vars:
  PYBA_DUMPS_SRC  path to deadlock-eos data/dumps (default: ../deadlock-eos/data/dumps)
  PYBA_CONSOLE    set to any value for a console (debug) build
"""

import os
import re
from pathlib import Path

from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

_init = Path("src/pyba/__init__.py").read_text(encoding="utf-8")
version = re.search(r'^__version__ = "([^"]+)"', _init, re.M).group(1)
# "0.1.0" -> (0, 1, 0, 0): numeric-only parts, padded to 4
version_tuple = tuple(
    (list(map(int, re.findall(r"\d+", version))) + [0, 0, 0, 0])[:4]
)

version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=version_tuple, prodvers=version_tuple),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    "040904B0",  # US English, Unicode
                    [
                        StringStruct("ProductName", "Pyba"),
                        StringStruct("FileDescription", "Pyba — Deadlock build editor"),
                        StringStruct("FileVersion", version),
                        StringStruct("ProductVersion", version),
                        StringStruct("OriginalFilename", "Pyba.exe"),
                        StringStruct("InternalName", "Pyba"),
                        StringStruct("CompanyName", "Pyba project"),
                        StringStruct(
                            "LegalCopyright",
                            "Copyright (C) 2026 Pyba contributors. GPL-3.0-or-later.",
                        ),
                    ],
                )
            ]
        ),
        VarFileInfo([VarStruct("Translation", [0x0409, 0x04B0])]),
    ],
)

dumps_src = Path(os.environ.get("PYBA_DUMPS_SRC", "../deadlock-eos/data/dumps")).resolve()
if not dumps_src.is_dir() or not any(d.is_dir() and d.name.isdigit() for d in dumps_src.iterdir()):
    raise SystemExit(f"PYBA_DUMPS_SRC has no build dumps: {dumps_src}")

icon_src = Path("packaging/assets/icon.ico").resolve()
if not icon_src.is_file():
    raise SystemExit(f"app icon missing: {icon_src}")

datas = [
    (str(dumps_src), "data/dumps"),
    (str(icon_src), "assets"),
]

a = Analysis(
    ["packaging/launch.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "PySide6.QtNetwork",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtQuick3D",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets",
        "PySide6.Qt3DCore",
        "PySide6.Qt3DRender",
        "PySide6.QtPdf",
        "PySide6.QtSql",
        "PySide6.QtTest",
        "PySide6.QtDesigner",
        "PySide6.QtSvg",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="Pyba",
    icon=str(icon_src),
    version=version_info,
    console=bool(os.environ.get("PYBA_CONSOLE")),
    upx=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="Pyba",
    upx=False,
)
