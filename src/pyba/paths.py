"""User data locations for the desktop app."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def user_data_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA")
        root = Path(base) if base else Path.home() / "AppData" / "Roaming"
        return root / "Pyba"
    return Path.home() / ".local" / "share" / "pyba"


def fits_dir() -> Path:
    path = user_data_dir() / "fits"
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_dir() -> Path:
    path = user_data_dir() / "cache"
    path.mkdir(parents=True, exist_ok=True)
    return path
