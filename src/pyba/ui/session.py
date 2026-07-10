"""BuildSession, the single mutation funnel between UI and engine.

Every edit derives a new frozen Build, re-resolves, pushes an undo
snapshot, and emits changed(Resolution). Undo/redo is a snapshot stack.
preview() resolves a candidate build without touching session state;
stats views diff it against current for hover deltas.
"""

from __future__ import annotations

import dataclasses

from PySide6.QtCore import QObject, Signal

from deadlock_eos import Build, GameData, ItemState, Resolution, resolve
from deadlock_eos import effects
from deadlock_eos.components import owned_components


class BuildSession(QObject):
    changed = Signal(object)          # Resolution — current build re-resolved
    previewChanged = Signal(object)   # Resolution | None — hover candidate

    def __init__(self, data: GameData, build: Build | None = None) -> None:
        super().__init__()
        self.data = data
        self._build = build or Build(hero=next(iter(sorted(
            h.class_name for h in data.playable_heroes()))))
        self._undo: list[Build] = []
        self._redo: list[Build] = []
        self._resolution = self._resolve(self._build)

    # --- read side ---------------------------------------------------------

    @property
    def build(self) -> Build:
        return self._build

    @property
    def resolution(self) -> Resolution:
        return self._resolution

    def _resolve(self, build: Build) -> Resolution:
        return resolve(self.data, build, strict=False)

    # --- mutation funnel ---------------------------------------------------

    def _apply(self, build: Build) -> None:
        if build == self._build:
            return
        resolution = self._resolve(build)  # validate before committing
        self._undo.append(self._build)
        self._redo.clear()
        self._build = build
        self._resolution = resolution
        self.changed.emit(resolution)

    def replace(self, build: Build) -> None:
        self._apply(build)

    def set_hero(self, hero: str) -> None:
        # switching hero resets hero-specific choices, keeps level
        self._apply(Build(hero=hero, level=self._build.level))

    def set_level(self, level: int) -> None:
        self._apply(dataclasses.replace(self._build, level=level))

    def _with_item(self, class_name: str) -> Build:
        """Candidate build with class_name added; owned direct components are
        consumed (removed, their item_states dropped) — in-game shop rule."""
        item = self.data.shop_items.get(class_name)
        consumed = set(owned_components(item, self._build.items)) if item else set()
        items = tuple(i for i in self._build.items if i not in consumed) + (class_name,)
        states = {k: v for k, v in self._build.item_states.items() if k not in consumed}
        return dataclasses.replace(self._build, items=items, item_states=states)

    def add_item(self, class_name: str) -> None:
        if class_name in self._build.items:
            return
        self._apply(self._with_item(class_name))

    def remove_item(self, class_name: str) -> None:
        if class_name not in self._build.items:
            return
        states = {k: v for k, v in self._build.item_states.items() if k != class_name}
        self._apply(
            dataclasses.replace(
                self._build,
                items=tuple(i for i in self._build.items if i != class_name),
                item_states=states,
            )
        )

    def set_tier(self, ability: str, tier: int) -> None:
        tiers = dict(self._build.ability_tiers)
        tiers[ability] = tier
        self._apply(dataclasses.replace(self._build, ability_tiers=tiers))

    def set_stacks(self, class_name: str, stacks: int) -> None:
        states = dict(self._build.item_states)
        if stacks:
            states[class_name] = ItemState(stacks=stacks)
        else:
            states.pop(class_name, None)
        self._apply(dataclasses.replace(self._build, item_states=states))

    # --- undo / redo ---------------------------------------------------------

    def can_undo(self) -> bool:
        return bool(self._undo)

    def can_redo(self) -> bool:
        return bool(self._redo)

    def undo(self) -> None:
        if self._undo:
            self._redo.append(self._build)
            self._build = self._undo.pop()
            self._resolution = self._resolve(self._build)
            self.changed.emit(self._resolution)

    def redo(self) -> None:
        if self._redo:
            self._undo.append(self._build)
            self._build = self._redo.pop()
            self._resolution = self._resolve(self._build)
            self.changed.emit(self._resolution)

    # --- hover preview ---------------------------------------------------------

    def preview_add_item(self, class_name: str) -> None:
        if class_name in self._build.items:
            self.clear_preview()
            return
        candidate = self._with_item(class_name)
        try:
            self.previewChanged.emit(self._resolve(candidate))
        except ValueError:
            self.clear_preview()

    def preview_remove_item(self, class_name: str) -> None:
        if class_name not in self._build.items:
            self.clear_preview()
            return
        states = {k: v for k, v in self._build.item_states.items() if k != class_name}
        candidate = dataclasses.replace(
            self._build,
            items=tuple(i for i in self._build.items if i != class_name),
            item_states=states,
        )
        self.previewChanged.emit(self._resolve(candidate))

    def clear_preview(self) -> None:
        self.previewChanged.emit(None)

    # --- helpers for views ---------------------------------------------------------

    def max_stacks_for(self, class_name: str) -> int | None:
        handler = effects.HANDLERS.get(class_name)
        if handler is None:
            return None
        return effects.max_stacks(self.data.shop_items[class_name])
