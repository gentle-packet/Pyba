"""Service layer tests — offline: network is injected everywhere."""

import json

import pytest

from deadlock_eos import Build, Stat
from pyba.fits import Fit
from pyba.service import (
    FitStore,
    ItemAnalytics,
    decode_fit,
    encode_fit,
    import_any,
    load_game_data,
)


def make_fit(name="Test Abrams"):
    return Fit(
        name=name,
        build=Build(hero="hero_atlas", level=5, items=("upgrade_clip_size",),
                    overrides={Stat.SPIRIT_POWER: 50.0}),
    )


# --- fit store ---------------------------------------------------------------

def test_fitstore_crud(tmp_path):
    store = FitStore(tmp_path)
    info = store.save(make_fit())
    assert info.slug == "test-abrams"
    assert store.load(info.slug) == make_fit()
    assert [i.slug for i in store.list()] == ["test-abrams"]

    # same name overwrites; different fit with colliding slug gets a suffix
    store.save(make_fit())
    assert len(store.list()) == 1
    other = store.save(Fit(name="Test  Abrams!", build=make_fit().build))
    assert other.slug == "test-abrams-2"

    store.delete(info.slug)
    assert [i.slug for i in store.list()] == ["test-abrams-2"]
    with pytest.raises(FileNotFoundError):
        store.load("gone")


# --- build codes ---------------------------------------------------------------

def test_pyba_code_roundtrip():
    fit = make_fit()
    code = encode_fit(fit)
    assert code.startswith("PYBA1.")
    assert decode_fit(code) == fit


def test_import_any_pyba_code(data):
    fit = make_fit()
    assert import_any(encode_fit(fit), data) == fit


def test_import_any_ingame_id(data, abrams_build_payload):
    calls = []

    def fake_fetch(build_id):
        calls.append(build_id)
        return abrams_build_payload

    fit = import_any("393691", data, level=12, fetch=fake_fetch)
    assert calls == [393691]
    assert fit.build.hero == "hero_atlas"
    assert fit.build.level == 12
    assert fit.build.items


def test_import_any_garbage(data):
    with pytest.raises(ValueError, match="Pyba build code or a numeric"):
        import_any("not-a-code", data)
    with pytest.raises(ValueError, match="corrupt"):
        decode_fit("PYBA1.zzzz")


# --- analytics ------------------------------------------------------------------

SAMPLE = [
    {"item_id": None, "wins": 1, "matches": 2},  # bucket rows without id get skipped
    {"item_id": 0, "wins": 0, "losses": 0, "matches": 0, "players": 0},
]


def sample_entries(data):
    clip = data.shop_items["upgrade_clip_size"]
    return SAMPLE + [
        {"item_id": clip.id, "wins": 600, "losses": 400, "matches": 1000,
         "players": 800, "avg_buy_time_s": 500.0}
    ]


def test_analytics_fetch_cache_and_annotate(tmp_path, data):
    fetches = []

    def fake_fetch(hero_id, since):
        fetches.append((hero_id, since))
        return sample_entries(data)

    now = [1_000_000.0]
    analytics = ItemAnalytics(tmp_path, ttl_hours=1, fetch_fn=fake_fetch, clock=lambda: now[0])

    stats = analytics.item_stats()
    clip_id = data.shop_items["upgrade_clip_size"].id
    assert stats[clip_id].win_rate == pytest.approx(0.6)
    assert len(fetches) == 1

    analytics.item_stats()                      # within TTL -> cache hit
    assert len(fetches) == 1

    now[0] += 2 * 3600                          # TTL expired -> refetch
    analytics.item_stats()
    assert len(fetches) == 2

    annotated = analytics.annotate(data)
    assert annotated["upgrade_clip_size"].matches == 1000
    assert "upgrade_berserker" not in annotated  # no stats row -> not annotated


def test_annotate_falls_back_to_global_when_hero_scoped_empty(tmp_path, data):
    def fake_fetch(hero_id, since):
        return [] if hero_id is not None else sample_entries(data)

    analytics = ItemAnalytics(tmp_path, fetch_fn=fake_fetch)
    annotated = analytics.annotate(data, hero_id=6)
    assert annotated["upgrade_clip_size"].matches == 1000
    assert analytics.annotate(data, hero_id=6, fallback_global=False) == {}


def test_analytics_stale_fallback(tmp_path, data):
    good = lambda hero_id, since: sample_entries(data)

    def bad(hero_id, since):
        raise OSError("network down")

    now = [1_000_000.0]
    warm = ItemAnalytics(tmp_path, ttl_hours=1, fetch_fn=good, clock=lambda: now[0])
    warm.item_stats()

    now[0] += 10 * 3600  # cache stale
    offline = ItemAnalytics(tmp_path, ttl_hours=1, fetch_fn=bad, clock=lambda: now[0])
    stats = offline.item_stats()  # stale cache served, no raise
    assert stats

    cold = ItemAnalytics(tmp_path / "empty", ttl_hours=1, fetch_fn=bad, clock=lambda: now[0])
    with pytest.raises(OSError):
        cold.item_stats()


# --- data discovery ----------------------------------------------------------------

def test_load_game_data_discovery(tmp_path, data):
    import deadlock_eos

    with pytest.raises(FileNotFoundError):
        load_game_data(tmp_path / "nowhere")
    # no-arg discovery (env var or sibling checkout) finds the same dump
    loaded = load_game_data()
    assert isinstance(loaded, deadlock_eos.GameData)
    assert loaded.build == data.build


def test_find_dumps_dir_frozen_bundle(tmp_path, monkeypatch):
    from pyba.service import data as data_mod

    bundle = tmp_path / "bundle"
    (bundle / "data" / "dumps" / "6613").mkdir(parents=True)
    appdata_dumps = tmp_path / "appdata" / "dumps"
    appdata_dumps.mkdir(parents=True)  # exists but empty — must not shadow bundle

    monkeypatch.delenv("DEADLOCK_EOS_DATA", raising=False)
    monkeypatch.setattr(data_mod.paths, "user_data_dir", lambda: appdata_dumps.parent)
    monkeypatch.setattr(data_mod, "_REPO_SIBLING", tmp_path / "no-sibling")
    monkeypatch.setattr(data_mod.sys, "frozen", True, raising=False)
    monkeypatch.setattr(data_mod.sys, "_MEIPASS", str(bundle), raising=False)

    assert data_mod.find_dumps_dir() == bundle / "data" / "dumps"

    # user-dir dumps with a real build dir win over the bundle (future updater)
    (appdata_dumps / "7000").mkdir()
    assert data_mod.find_dumps_dir() == appdata_dumps
