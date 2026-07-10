"""Port tests against a committed real build fixture (offline)."""

import pytest

from deadlock_eos import resolve
from pyba.port import parse_hero_build


@pytest.fixture()
def imported(data, abrams_build_payload):
    return parse_hero_build(abrams_build_payload, data)


def test_parse_basics(imported, abrams_build_payload):
    hero_build = abrams_build_payload["hero_build"]
    assert imported.hero == "hero_atlas"
    assert imported.hero_build_id == hero_build["hero_build_id"]
    assert imported.version == hero_build["version"]
    assert imported.categories  # at least one shopping category


def test_items_map_or_surface(imported, data, abrams_build_payload):
    mapped = sum(len(items) for _, items in imported.categories)
    raw_total = sum(
        len(c.get("mods") or ())
        for c in abrams_build_payload["hero_build"]["details"]["mod_categories"]
    )
    assert mapped + len(imported.unknown_ids) >= raw_total  # nothing silently dropped
    for _, class_names in imported.categories:
        for class_name in class_names:
            assert class_name in data.shop_items


def test_tiers_derived_from_ap_spend(imported, data):
    assert imported.ability_tiers, "expected AP spends in a real build"
    hero_abilities = set(data.heroes["hero_atlas"].slots.values())
    for class_name, tier in imported.ability_tiers.items():
        assert 0 <= tier <= 3
        assert class_name in hero_abilities


def test_to_build_resolves(imported, data):
    build = imported.to_build()
    assert len(build.items) == len(set(build.items))  # deduped
    res = resolve(data, build, strict=False)
    assert res.stats  # engine accepts the imported build end to end


def test_category_selection(imported):
    first_name, first_items = next(
        (name, items) for name, items in imported.categories if items
    )
    build = imported.to_build(categories=[first_name])
    assert set(build.items) == set(dict.fromkeys(first_items))
    with pytest.raises(ValueError, match="unknown categories"):
        imported.to_build(categories=["Nonexistent Category"])


def test_unknown_hero_rejected(data, abrams_build_payload):
    broken = {
        "hero_build": {**abrams_build_payload["hero_build"], "hero_id": 999999}
    }
    with pytest.raises(ValueError, match="hero_id 999999"):
        parse_hero_build(broken, data)
