"""Item win/usage statistics from deadlock-api, with a file cache.

The item-stats endpoint aggregates over all matches unless time-bounded
and times out unbounded, so always pass min_unix_timestamp. Responses are
cached on disk (default 24 h TTL); on network failure the stale cache is
served.
"""

from __future__ import annotations

import json
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from deadlock_eos import GameData

from .. import paths

API_URL = "https://api.deadlock-api.com/v1/analytics/item-stats"


@dataclass(frozen=True, slots=True)
class ItemStat:
    item_id: int
    wins: int
    losses: int
    matches: int
    players: int
    avg_buy_time_s: float | None

    @property
    def win_rate(self) -> float:
        return self.wins / self.matches if self.matches else 0.0


def _default_fetch(hero_id: int | None, since_unix: int) -> list[dict]:
    query = f"min_unix_timestamp={since_unix}"
    if hero_id is not None:
        query += f"&hero_id={hero_id}"
    req = urllib.request.Request(
        f"{API_URL}?{query}", headers={"User-Agent": "pyba-service"}
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())


class ItemAnalytics:
    def __init__(
        self,
        cache_directory: Path | str | None = None,
        ttl_hours: float = 24.0,
        fetch_fn: Callable[[int | None, int], list[dict]] = _default_fetch,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.cache_directory = Path(cache_directory) if cache_directory else paths.cache_dir()
        self.cache_directory.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_hours * 3600
        self._fetch = fetch_fn
        self._clock = clock

    def _cache_path(self, hero_id: int | None, days: int) -> Path:
        scope = "all" if hero_id is None else f"hero{hero_id}"
        return self.cache_directory / f"item_stats_{scope}_{days}d.json"

    def item_stats(self, hero_id: int | None = None, days: int = 7) -> dict[int, ItemStat]:
        path = self._cache_path(hero_id, days)
        cached = None
        if path.exists():
            cached = json.loads(path.read_text(encoding="utf-8"))
            if self._clock() - cached["fetched_at"] < self.ttl_seconds:
                return self._parse(cached["entries"])
        since = int(self._clock()) - days * 86400
        try:
            entries = self._fetch(hero_id, since)
        except Exception:
            if cached is not None:  # stale beats nothing — annotations are advisory
                return self._parse(cached["entries"])
            raise
        path.write_text(
            json.dumps({"fetched_at": self._clock(), "entries": entries}), encoding="utf-8"
        )
        return self._parse(entries)

    @staticmethod
    def _parse(entries: list[dict]) -> dict[int, ItemStat]:
        stats = {}
        for entry in entries:
            item_id = entry.get("item_id")
            if item_id is None:
                continue
            stats[item_id] = ItemStat(
                item_id=item_id,
                wins=entry.get("wins") or 0,
                losses=entry.get("losses") or 0,
                matches=entry.get("matches") or 0,
                players=entry.get("players") or 0,
                avg_buy_time_s=entry.get("avg_buy_time_s"),
            )
        return stats

    def annotate(
        self,
        data: GameData,
        hero_id: int | None = None,
        days: int = 7,
        fallback_global: bool = True,
    ) -> Mapping[str, ItemStat]:
        """Item stats keyed by shop item class_name for the loaded dump.

        Hero-scoped queries can come back empty (hero disabled this patch,
        tiny sample window); with fallback_global the all-heroes stats are
        served instead of an empty annotation set.
        """
        by_id = self.item_stats(hero_id=hero_id, days=days)
        if not by_id and hero_id is not None and fallback_global:
            by_id = self.item_stats(hero_id=None, days=days)
        return {
            item.class_name: by_id[item.id]
            for item in data.shop_items.values()
            if item.id in by_id
        }
