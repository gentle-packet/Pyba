"""Import in-game Deadlock hero builds.

Builds are published in-game and served by api.deadlock-api.com. Parsing is
pure (payload dict + GameData -> ImportedBuild); network fetch is isolated
in fetch_build/search_builds.

Format notes:
- details.mod_categories[].mods[].ability_id == ShopItem.id
- details.ability_order.currency_changes: currency_type 1 = ability point
  spend (deltas -1/-2/-5 == the three tier purchases), 2 = ability unlock
- an in-game build is a *shopping guide*: categories often hold more items
  than fit in 12 slots. to_build() defaults to everything (deduped); pass
  category names to select until an engine slot model exists.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Iterable, Mapping

from deadlock_eos import Build, GameData

API_URL = "https://api.deadlock-api.com/v1/builds"


@dataclass(frozen=True, slots=True)
class ImportedBuild:
    name: str
    hero: str                     # hero class_name
    hero_build_id: int
    version: int
    author_account_id: int | None
    categories: tuple[tuple[str, tuple[str, ...]], ...]  # (category, item class_names)
    ability_tiers: Mapping[str, int]
    unknown_ids: tuple[int, ...]  # ids not in the loaded dump — surfaced, never dropped

    def to_build(
        self,
        categories: Iterable[str] | None = None,
        level: int = 1,
    ) -> Build:
        wanted = None if categories is None else set(categories)
        if wanted is not None:
            known = {name for name, _ in self.categories}
            missing = wanted - known
            if missing:
                raise ValueError(f"unknown categories: {sorted(missing)}; have {sorted(known)}")
        items: list[str] = []
        for name, class_names in self.categories:
            if wanted is not None and name not in wanted:
                continue
            for class_name in class_names:
                if class_name not in items:  # shopping lists may repeat items
                    items.append(class_name)
        return Build(
            hero=self.hero,
            level=level,
            items=tuple(items),
            ability_tiers=dict(self.ability_tiers),
        )


def parse_hero_build(payload: Mapping, data: GameData) -> ImportedBuild:
    """Parse one build payload — either a bare hero_build object or an API
    entry wrapping it ({"hero_build": {...}, "num_favorites": ...})."""
    hero_build = payload.get("hero_build", payload)

    heroes_by_id = {hero.id: hero.class_name for hero in data.heroes.values()}
    items_by_id = {item.id: item.class_name for item in data.shop_items.values()}
    abilities_by_id = {ability.id: ability.class_name for ability in data.abilities.values()}

    hero_id = hero_build["hero_id"]
    hero = heroes_by_id.get(hero_id)
    if hero is None:
        raise ValueError(f"hero_id {hero_id} not in loaded dump")

    unknown: list[int] = []
    categories: list[tuple[str, tuple[str, ...]]] = []
    details = hero_build.get("details") or {}
    for category in details.get("mod_categories") or ():
        class_names: list[str] = []
        for mod in category.get("mods") or ():
            item_id = mod.get("ability_id")
            class_name = items_by_id.get(item_id)
            if class_name is None:
                if item_id is not None and item_id not in unknown:
                    unknown.append(item_id)
                continue
            class_names.append(class_name)
        categories.append((category.get("name") or "", tuple(class_names)))

    tiers: dict[str, int] = {}
    ability_order = details.get("ability_order") or {}
    for change in ability_order.get("currency_changes") or ():
        if change.get("currency_type") != 1:
            continue  # type 2 = unlock, no tier
        class_name = abilities_by_id.get(change.get("ability_id"))
        if class_name is None:
            continue  # non-signature or unknown; tiers only exist for abilities
        tiers[class_name] = min(3, tiers.get(class_name, 0) + 1)

    return ImportedBuild(
        name=hero_build.get("name") or "",
        hero=hero,
        hero_build_id=hero_build.get("hero_build_id") or 0,
        version=hero_build.get("version") or 0,
        author_account_id=hero_build.get("author_account_id"),
        categories=tuple(categories),
        ability_tiers=tiers,
        unknown_ids=tuple(unknown),
    )


def _get(params: dict) -> list:
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    req = urllib.request.Request(
        f"{API_URL}?{query}", headers={"User-Agent": "pyba-port"}
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def fetch_build(build_id: int, version: int | None = None) -> dict:
    """Fetch one published build by its in-game build id (latest version
    unless pinned). Without only_latest the API returns versions in
    ascending order — v1 first."""
    params: dict = {"build_id": build_id, "limit": 1}
    if version is None:
        params["only_latest"] = "true"
    else:
        params["version"] = version
    entries = _get(params)
    if not entries:
        raise LookupError(f"no published build with id {build_id}")
    return entries[0]


def search_builds(
    hero_id: int | None = None,
    name: str | None = None,
    sort_by: str = "weekly_favorites",
    limit: int = 10,
) -> list[dict]:
    return _get(
        {
            "hero_id": hero_id,
            "search_name": name,
            "sort_by": sort_by,
            "sort_direction": "desc",
            "limit": limit,
        }
    )
