"""Game-data updater service — offline: engine fetch layer is injected."""

import json

import pytest

from deadlock_eos import fetch
from pyba import paths
from pyba.service import (
    check_for_update,
    download_update,
    find_dumps_dir,
    latest_build_dir,
    revert_to_bundled,
)
from pyba.service import update as update_mod

from conftest import _dumps_dir


@pytest.fixture
def user_dir(tmp_path, monkeypatch):
    """Point every user_data_dir() at tmp_path (paths + service modules)."""
    monkeypatch.setattr(paths, "user_data_dir", lambda: tmp_path)
    return tmp_path


@pytest.fixture
def fake_api(monkeypatch):
    """Serve the committed engine dump as API payloads; no network."""
    dumps = _dumps_dir()
    builds = sorted(
        (d for d in dumps.iterdir() if d.name.isdigit()), key=lambda d: int(d.name)
    ) if dumps.exists() else []
    if not builds:
        pytest.skip(f"no deadlock-eos dump found under {dumps}")
    src = builds[-1]
    build = int(src.name)
    responses = {
        "/v2/client-versions": json.dumps([build]).encode(),
        "/v2/heroes": (src / "heroes.json").read_bytes(),
        "/v2/items": (src / "items.json").read_bytes(),
    }
    monkeypatch.setattr(fetch, "_get", lambda path: responses[path])
    return build


# --- check_for_update --------------------------------------------------------


def test_check_for_update_newer(monkeypatch):
    monkeypatch.setattr(update_mod, "remote_build", lambda: 7000)
    assert check_for_update(6613) == 7000


def test_check_for_update_current_and_older(monkeypatch):
    monkeypatch.setattr(update_mod, "remote_build", lambda: 6613)
    assert check_for_update(6613) is None
    assert check_for_update(9999) is None


# --- download_update ---------------------------------------------------------


def test_download_update_installs_discoverable_dump(user_dir, fake_api, monkeypatch):
    monkeypatch.delenv("DEADLOCK_EOS_DATA", raising=False)
    result = download_update()

    assert not result.skipped
    assert result.report.ok
    assert result.dump_dir == user_dir / "dumps" / str(fake_api)
    # discovery now picks the user dir over any sibling/bundled candidate
    assert find_dumps_dir() == user_dir / "dumps"
    assert latest_build_dir(find_dumps_dir()) == result.dump_dir


# --- revert_to_bundled -------------------------------------------------------


def test_revert_removes_only_build_dirs(user_dir):
    dumps = user_dir / "dumps"
    (dumps / "6613").mkdir(parents=True)
    (dumps / "7000").mkdir()
    (dumps / ".tmp-7000-junk").mkdir()

    assert revert_to_bundled() == 2
    assert not (dumps / "6613").exists()
    assert not (dumps / "7000").exists()
    assert (dumps / ".tmp-7000-junk").exists()  # non-build content untouched


def test_reverted_dir_no_longer_wins_discovery(user_dir, monkeypatch):
    from pyba.service import data as data_mod

    dumps = user_dir / "dumps"
    (dumps / "9999").mkdir(parents=True)
    monkeypatch.delenv("DEADLOCK_EOS_DATA", raising=False)
    monkeypatch.setattr(data_mod.paths, "user_data_dir", lambda: user_dir)

    assert data_mod.find_dumps_dir() == dumps
    revert_to_bundled()
    # empty user dumps dir must fall through to the next candidate
    assert data_mod.find_dumps_dir() != dumps
