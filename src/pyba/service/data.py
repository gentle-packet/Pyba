"""Game data discovery + loading for the app.

Search order for the dump directory: explicit argument, DEADLOCK_EOS_DATA
env var, <user data dir>/dumps, dumps bundled into a frozen build, then
the development sibling checkout (../deadlock-eos/data/dumps relative to
this package's repo). The user data dir wins over bundled dumps so the
data updater can drop newer builds there without touching the
installed package. A candidate only counts if it holds at least one
numeric build directory, so an empty leftover dir cannot shadow real data.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from deadlock_eos import GameData, load_dump

from .. import paths

_REPO_SIBLING = Path(__file__).resolve().parents[3].parent / "deadlock-eos" / "data" / "dumps"


def _bundled_dumps_dir() -> Path | None:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "data" / "dumps"
    return None


def _has_build_dirs(dumps_dir: Path) -> bool:
    return dumps_dir.is_dir() and any(
        d.is_dir() and d.name.isdigit() for d in dumps_dir.iterdir()
    )


def find_dumps_dir(explicit: Path | str | None = None) -> Path:
    if explicit is not None:
        path = Path(explicit)
        if not path.is_dir():  # an explicit path is authoritative — never fall back
            raise FileNotFoundError(f"dumps directory does not exist: {path}")
        return path
    candidates = [
        Path(os.environ["DEADLOCK_EOS_DATA"]) if os.environ.get("DEADLOCK_EOS_DATA") else None,
        paths.user_data_dir() / "dumps",
        _bundled_dumps_dir(),
        _REPO_SIBLING,
    ]
    for candidate in candidates:
        if candidate is not None and _has_build_dirs(candidate):
            return candidate
    raise FileNotFoundError(
        "no game-data dumps directory found; set DEADLOCK_EOS_DATA or pass a path"
    )


def latest_build_dir(dumps_dir: Path) -> Path:
    builds = sorted(
        (d for d in dumps_dir.iterdir() if d.is_dir() and d.name.isdigit()),
        key=lambda d: int(d.name),
    )
    if not builds:
        raise FileNotFoundError(f"no build dumps under {dumps_dir}")
    return builds[-1]


def load_game_data(explicit: Path | str | None = None, strict: bool = True) -> GameData:
    return load_dump(latest_build_dir(find_dumps_dir(explicit)), strict=strict)
