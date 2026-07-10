"""Fit persistence as plain JSON.

A fit is an engine Build plus user metadata. Everything serializes to
primitives; Stat enum keys round-trip via their string values.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from deadlock_eos import Build, ItemState, Stat

FORMAT_VERSION = 1


@dataclass(frozen=True, slots=True)
class Fit:
    build: Build
    name: str = ""
    notes: str = ""


def fit_to_dict(fit: Fit) -> dict:
    build = fit.build
    return {
        "format_version": FORMAT_VERSION,
        "name": fit.name,
        "notes": fit.notes,
        "build": {
            "hero": build.hero,
            "level": build.level,
            "items": list(build.items),
            "ability_tiers": dict(build.ability_tiers),
            "item_states": {
                class_name: {"stacks": state.stacks}
                for class_name, state in build.item_states.items()
            },
            "overrides": {str(stat): value for stat, value in build.overrides.items()},
        },
    }


def fit_from_dict(payload: Mapping) -> Fit:
    version = payload.get("format_version")
    if version != FORMAT_VERSION:
        raise ValueError(f"unsupported fit format_version {version!r}")
    raw = payload["build"]
    return Fit(
        name=payload.get("name") or "",
        notes=payload.get("notes") or "",
        build=Build(
            hero=raw["hero"],
            level=raw.get("level", 1),
            items=tuple(raw.get("items") or ()),
            ability_tiers=dict(raw.get("ability_tiers") or {}),
            item_states={
                class_name: ItemState(stacks=state.get("stacks", 0))
                for class_name, state in (raw.get("item_states") or {}).items()
            },
            overrides={
                Stat(stat): float(value)
                for stat, value in (raw.get("overrides") or {}).items()
            },
        ),
    )


def save_fit(fit: Fit, path: Path | str) -> None:
    Path(path).write_text(json.dumps(fit_to_dict(fit), indent=2), encoding="utf-8")


def load_fit(path: Path | str) -> Fit:
    return fit_from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
