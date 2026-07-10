"""Game-data updates: fetch newer dumps into the user data dir.

Thin Qt-free wrapper over deadlock_eos.updater. Dumps land in
<user data dir>/dumps, which data.py's discovery already prefers over the
bundled dump, so an installed update wins on next launch without touching
the frozen app. Reverting just empties that directory — discovery then
falls through to the bundled data again.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from deadlock_eos import UpdateResult, remote_build
from deadlock_eos import update as _engine_update

from .. import paths


def app_dumps_dir() -> Path:
    path = paths.user_data_dir() / "dumps"
    path.mkdir(parents=True, exist_ok=True)
    return path


def check_for_update(current_build: int) -> int | None:
    """Newer remote build number, or None when current is up to date."""
    remote = remote_build()
    return remote if remote > current_build else None


def download_update() -> UpdateResult:
    """Fetch + validate + install the latest build into the user data dir."""
    return _engine_update(app_dumps_dir())


def revert_to_bundled() -> int:
    """Delete downloaded builds so discovery falls back to bundled data.

    Returns the number of build dirs removed. Non-build files (temp dirs,
    stray junk) are left alone; an empty dumps dir no longer counts as a
    discovery candidate.
    """
    removed = 0
    dumps_dir = app_dumps_dir()
    for child in dumps_dir.iterdir():
        if child.is_dir() and child.name.isdigit():
            shutil.rmtree(child)
            removed += 1
    return removed
