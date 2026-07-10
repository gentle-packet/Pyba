"""Shareable build codes.

Two kinds, one entry point (import_any):
- In-game builds: shared by numeric hero_build_id, fetched from
  deadlock-api (publishing back into the game is only possible from the
  game client, so export targets the Pyba code instead).
- Pyba codes: "PYBA1." + urlsafe-base64(zlib(fit JSON)) — compact strings
  for sharing fits between Pyba users, versioned by the prefix.
"""

from __future__ import annotations

import base64
import json
import zlib
from typing import Callable

from deadlock_eos import GameData

from ..fits import Fit, fit_from_dict, fit_to_dict
from ..port import fetch_build, parse_hero_build

PREFIX = "PYBA1."


def encode_fit(fit: Fit) -> str:
    payload = json.dumps(fit_to_dict(fit), separators=(",", ":")).encode()
    return PREFIX + base64.urlsafe_b64encode(zlib.compress(payload, 9)).decode()


def decode_fit(code: str) -> Fit:
    if not code.startswith(PREFIX):
        raise ValueError(f"not a Pyba build code (expected {PREFIX!r} prefix)")
    try:
        payload = zlib.decompress(base64.urlsafe_b64decode(code[len(PREFIX):]))
        return fit_from_dict(json.loads(payload))
    except (ValueError, zlib.error, json.JSONDecodeError) as exc:
        raise ValueError(f"corrupt Pyba build code: {exc}") from exc


def import_any(
    code: str | int,
    data: GameData,
    level: int = 1,
    fetch: Callable[[int], dict] = fetch_build,
) -> Fit:
    """Import from whatever the user pasted: a Pyba code or an in-game
    hero_build_id (bare number)."""
    text = str(code).strip()
    if text.startswith(PREFIX):
        return decode_fit(text)
    if text.isdigit():
        imported = parse_hero_build(fetch(int(text)), data)
        return Fit(
            name=imported.name,
            notes=f"imported in-game build {imported.hero_build_id} v{imported.version}",
            build=imported.to_build(level=level),
        )
    raise ValueError("expected a Pyba build code or a numeric in-game build id")
