"""Abilities section: a game-style horizontal bar of four ability tiles
(icon + name + AP tier pips) plus a wiki-style detail panel that expands for
the clicked ability (description, active stats with spirit scaling, and the
T1/T2/T3 upgrade bonuses)."""

from __future__ import annotations

import html
import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from deadlock_eos.model import Ability, UpgradeOp

from .. import theme
from ..icons import IconCache

_SVG = re.compile(r"<svg\b.*?</svg>", re.DOTALL | re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t]*\n[ \t]*")

# ETechPower is the in-game name for Spirit; strip the "E" prefix otherwise.
_STAT_LABELS = {"ETechPower": "Spirit"}


def _clean_desc(raw: object) -> str:
    """Flatten an ability description (inline SVG + HTML tokens) to plain text."""
    if not isinstance(raw, str):
        return ""
    text = _SVG.sub(" ", raw)
    text = _TAG.sub("", text)
    text = html.unescape(text)
    text = _WS.sub("\n", text)
    return text.strip()


def _stat_label(stat: str | None) -> str:
    if not stat:
        return ""
    return _STAT_LABELS.get(stat, stat[1:] if stat.startswith("E") else stat)


def _fmt(value: float) -> str:
    return f"{value:g}"


class _TierPips(QWidget):
    """Segmented AP-upgrade control: 0 / 1 / 2 / 3, mirroring the game."""

    def __init__(self, session, class_name: str) -> None:
        super().__init__()
        self.session = session
        self.class_name = class_name
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        current = session.build.ability_tiers.get(class_name, 0)
        for tier in range(4):
            pip = QToolButton()
            pip.setText(str(tier))
            pip.setCheckable(True)
            pip.setFixedSize(20, 20)
            pip.setCursor(Qt.CursorShape.PointingHandCursor)
            pip.setToolTip("No points" if tier == 0 else f"Tier {tier}")
            pip.setChecked(tier == current)
            pip.clicked.connect(lambda _c, t=tier: self._set(t))
            self._group.addButton(pip, tier)
            layout.addWidget(pip)
        self.setStyleSheet(
            f"QToolButton {{ padding: 0; border: 1px solid {theme.BORDER};"
            f" border-radius: 3px; color: {theme.FG_DIM}; }}"
            f"QToolButton:checked {{ background: {theme.ACCENT}; color: {theme.BG};"
            f" border-color: {theme.ACCENT}; font-weight: bold; }}"
        )

    def _set(self, tier: int) -> None:
        if tier != self.session.build.ability_tiers.get(self.class_name, 0):
            self.session.set_tier(self.class_name, tier)


class _AbilityTile(QFrame):
    """Compact ability chip: icon + name + tier pips. Clicking the body (not
    the pips) toggles the detail panel."""

    clicked = Signal(str)  # ability class_name

    def __init__(self, session, ability: Ability, class_name: str,
                 icons: IconCache, active: bool) -> None:
        super().__init__()
        self.class_name = class_name
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        border = theme.ACCENT if active else theme.BORDER
        self.setStyleSheet(
            f"_AbilityTile {{ border: 1px solid {border}; border-radius: 4px;"
            f" background: {theme.BG_FIELD}; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        top = QHBoxLayout()
        top.setSpacing(6)
        icon = QLabel()
        icon.setFixedSize(40, 40)
        icons.bind(icon, ability.raw.get("image_webp") or ability.raw.get("image"))
        top.addWidget(icon)
        name = QLabel(ability.name or class_name)
        name.setWordWrap(True)
        name.setStyleSheet(f"color: {theme.FG}; font-weight: bold;")
        top.addWidget(name, 1)
        layout.addLayout(top)

        pips = _TierPips(session, class_name)
        pip_row = QHBoxLayout()
        pip_row.setContentsMargins(0, 0, 0, 0)
        pip_row.addWidget(pips)
        pip_row.addStretch(1)
        layout.addLayout(pip_row)

    def mousePressEvent(self, event) -> None:
        self.clicked.emit(self.class_name)
        super().mousePressEvent(event)


class _AbilityDetail(QWidget):
    """Wiki-style breakdown for one ability."""

    def __init__(self, ability: Ability, class_name: str, tier: int,
                 icons: IconCache) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 6, 4, 4)
        layout.setSpacing(6)

        header = QHBoxLayout()
        icon = QLabel()
        icon.setFixedSize(48, 48)
        icons.bind(icon, ability.raw.get("image_webp") or ability.raw.get("image"))
        header.addWidget(icon)
        title = QLabel(ability.name or class_name)
        title.setStyleSheet(f"color: {theme.ACCENT}; font-size: 12pt; font-weight: bold;")
        header.addWidget(title, 1)
        if ability.ability_type:
            kind = QLabel(ability.ability_type.capitalize())
            kind.setStyleSheet(f"color: {theme.FG_DIM};")
            header.addWidget(kind)
        layout.addLayout(header)

        desc = _clean_desc((ability.raw.get("description") or {}).get("desc"))
        if desc:
            body = QLabel(desc)
            body.setWordWrap(True)
            body.setStyleSheet(f"color: {theme.FG};")
            layout.addWidget(body)

        stats = self._stats_grid(ability, icons)
        if stats is not None:
            layout.addWidget(stats)

        upgrades = self._upgrades(ability, tier)
        if upgrades is not None:
            layout.addWidget(upgrades)

    def _stats_grid(self, ability: Ability, icons: IconCache) -> QWidget | None:
        raw_props = ability.raw.get("properties") or {}
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(3)
        row = 0
        for name, prop in ability.properties.items():
            if prop.is_disabled or not prop.value or not prop.label:
                continue
            icon = QLabel()
            icon.setFixedSize(18, 18)
            icon_url = (raw_props.get(name) or {}).get("icon")
            if icon_url:
                icons.bind(icon, icon_url)
            grid.addWidget(icon, row, 0)

            label = QLabel(prop.label)
            label.setStyleSheet(f"color: {theme.FG_DIM};")
            grid.addWidget(label, row, 1)

            value = _fmt(prop.value) + (prop.postfix or "")
            val_label = QLabel(value)
            val_label.setStyleSheet(f"color: {theme.FG};")
            grid.addWidget(val_label, row, 2)

            if prop.scale and prop.scale.coeff:
                note = QLabel(f"+{_fmt(prop.scale.coeff)} / {_stat_label(prop.scale.stat)}")
                note.setStyleSheet(f"color: {theme.SLOT_COLORS['spirit']};")
                grid.addWidget(note, row, 3)
            row += 1
        if row == 0:
            return None
        holder = QWidget()
        holder.setLayout(grid)
        return holder

    def _upgrades(self, ability: Ability, tier: int) -> QWidget | None:
        if not ability.tiers:
            return None
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(2)
        heading = QLabel("Upgrades")
        heading.setStyleSheet(f"color: {theme.ACCENT}; font-weight: bold;")
        layout.addWidget(heading)
        for index, tier_data in enumerate(ability.tiers, start=1):
            parts = []
            for up in tier_data.upgrades:
                prop = ability.properties.get(up.property_name)
                name = prop.label if prop and prop.label else up.property_name
                text = f"{up.amount:+g}{up.unit or ''} {name}"
                if up.op in (UpgradeOp.ADD_TO_SCALE, UpgradeOp.MULTIPLY_SCALE):
                    text += " (scaling)"
                parts.append(text)
            active = index <= tier
            color = theme.FG if active else theme.FG_DIM
            weight = "bold" if active else "normal"
            line = QLabel(f"T{index}:  " + ",  ".join(parts) if parts else f"T{index}:  —")
            line.setWordWrap(True)
            line.setStyleSheet(f"color: {color}; font-weight: {weight};")
            layout.addWidget(line)
        t3 = _clean_desc((ability.raw.get("description") or {}).get("t3_desc"))
        if t3:
            t3_label = QLabel(t3)
            t3_label.setWordWrap(True)
            t3_label.setStyleSheet(f"color: {theme.FG_DIM}; font-style: italic;")
            layout.addWidget(t3_label)
        return box


class AbilityBar(QGroupBox):
    """The Abilities group: four tiles in a row + an expandable detail panel."""

    def __init__(self, session, icons: IconCache) -> None:
        super().__init__("Abilities")
        self.session = session
        self.icons = icons
        self._expanded: str | None = None

        self._outer = QVBoxLayout(self)
        self._outer.setSpacing(6)
        self._tiles_row = QHBoxLayout()
        self._tiles_row.setSpacing(6)
        self._outer.addLayout(self._tiles_row)
        self._detail_slot = QVBoxLayout()
        self._outer.addLayout(self._detail_slot)

        session.changed.connect(lambda _res: self.rebuild())
        self.rebuild()

    @staticmethod
    def _clear(layout) -> None:
        while layout.count():
            entry = layout.takeAt(0)
            if entry.widget():
                entry.widget().deleteLater()
            elif entry.layout():
                AbilityBar._clear(entry.layout())

    def _toggle(self, class_name: str) -> None:
        self._expanded = None if self._expanded == class_name else class_name
        self.rebuild()

    def rebuild(self) -> None:
        session = self.session
        build = session.build
        hero = session.data.heroes[build.hero]
        signatures = hero.signatures
        if self._expanded not in signatures:
            self._expanded = None

        self._clear(self._tiles_row)
        for class_name in signatures:
            ability = session.data.abilities.get(class_name)
            if ability is None:
                continue
            tile = _AbilityTile(
                session, ability, class_name, self.icons,
                active=class_name == self._expanded,
            )
            tile.clicked.connect(self._toggle)
            self._tiles_row.addWidget(tile)
        self._tiles_row.addStretch(1)

        self._clear(self._detail_slot)
        if self._expanded is not None:
            ability = session.data.abilities.get(self._expanded)
            if ability is not None:
                detail = _AbilityDetail(
                    ability, self._expanded,
                    build.ability_tiers.get(self._expanded, 0), self.icons,
                )
                self._detail_slot.addWidget(detail)
