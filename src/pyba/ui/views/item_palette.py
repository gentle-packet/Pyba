"""Shop-style item grid: four sections (Weapon / Vitality / Spirit /
Legendary), tier rows of icon cells — the in-game shop's periodic-table
layout instead of a long list. Hover previews deltas, click adds."""

from __future__ import annotations

from collections import Counter

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from deadlock_eos.components import effective_cost, owned_components
from deadlock_eos.model import ShopItem

from .. import theme
from ..icons import IconCache

CELL = 40
ICON = 34
COLUMNS = 4
LEGENDARY_TIER = 5  # cost-9999 street-brawl legendaries


class _ItemCell(QToolButton):
    def __init__(self, session, item: ShopItem, icons: IconCache) -> None:
        super().__init__()
        self.session = session
        self.item = item
        self.setFixedSize(CELL, CELL)
        self.setIconSize(QSize(ICON, ICON))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        icons.bind(self, item.raw.get("shop_image_webp") or item.raw.get("shop_image")
                   or item.raw.get("image_webp") or item.raw.get("image"))
        self._state = "normal"
        self._discount_line: str | None = None
        self._win_rate_line: str | None = None
        self._update_tooltip()
        self.clicked.connect(self._on_clicked)

    def _on_clicked(self) -> None:
        if self._state == "owned":
            return
        self.session.add_item(self.item.class_name)

    def set_state(self, state: str) -> None:
        """state: "normal" | "owned" | "upgrade". Owned dims via opacity
        effect (icon included, survives async icon load) but stays enabled
        so hover previews keep working; click is a no-op."""
        if state == self._state:
            return
        self._state = state
        self.setProperty("shopState", state)
        self.style().unpolish(self)
        self.style().polish(self)
        if state == "owned":
            effect = QGraphicsOpacityEffect(self)
            effect.setOpacity(0.4)
            self.setGraphicsEffect(effect)
            self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            self.setGraphicsEffect(None)
            self.setCursor(Qt.CursorShape.PointingHandCursor)

    @property
    def shop_state(self) -> str:
        return self._state

    def set_discount(self, effective: int | None, consumed_names: str | None) -> None:
        if effective is None:
            self._discount_line = None
        else:
            self._discount_line = (
                f"{self.item.cost:,} → {effective:,} souls ({consumed_names} owned)"
            )
        self._update_tooltip()

    def set_win_rate(self, win_rate: float | None, matches: int | None) -> None:
        if win_rate is None:
            self._win_rate_line = None
        else:
            self._win_rate_line = f"{win_rate:.1%} win rate ({matches:,} matches)"
        self._update_tooltip()

    def _update_tooltip(self) -> None:
        cost_line = self._discount_line or f"{self.item.cost:,} souls"
        lines = [self.item.name or self.item.class_name, cost_line]
        if self._win_rate_line:
            lines.append(self._win_rate_line)
        self.setToolTip("\n".join(lines))

    def enterEvent(self, event) -> None:
        self.session.preview_add_item(self.item.class_name)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.session.clear_preview()
        super().leaveEvent(event)


class ItemPalette(QWidget):
    def __init__(self, session, icons: IconCache) -> None:
        super().__init__()
        self.session = session
        self._icons = icons
        self.cells: list[_ItemCell] = []

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search items…")
        self.search.textChanged.connect(self._filter)

        columns = QHBoxLayout()
        columns.setSpacing(8)
        shopable = [i for i in session.data.shop_items.values() if i.shopable]
        for slot in ("weapon", "vitality", "spirit"):
            items = [i for i in shopable if i.slot == slot and (i.tier or 0) < LEGENDARY_TIER]
            columns.addWidget(self._section(slot.capitalize(),
                                            theme.SLOT_COLORS[slot], items, by_tier=True))
        legendary = [i for i in shopable if (i.tier or 0) >= LEGENDARY_TIER]
        columns.addWidget(
            self._section("Legendary", theme.ACCENT, legendary, by_tier=False, columns=2)
        )
        columns.addStretch(1)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addLayout(columns)
        content_layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidget(content)
        scroll.setWidgetResizable(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.search)
        layout.addWidget(scroll)

        session.changed.connect(lambda _res: self._refresh_states())
        self._refresh_states()

    # --- section construction -------------------------------------------------

    def _section(
        self, title: str, color: str, items: list[ShopItem], by_tier: bool,
        columns: int = COLUMNS,
    ) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(2)
        header = QLabel(title)
        header.setStyleSheet(f"color: {color}; font-weight: bold;")
        layout.addWidget(header)

        def add_grid(bucket: list[ShopItem]) -> None:
            grid = QGridLayout()
            grid.setSpacing(2)
            for position, item in enumerate(
                sorted(bucket, key=lambda i: (i.cost or 0, i.name or ""))
            ):
                cell = _ItemCell(self.session, item, self._icons)
                self.cells.append(cell)
                grid.addWidget(cell, position // columns, position % columns)
            holder = QWidget()
            holder.setLayout(grid)
            layout.addWidget(holder, 0, Qt.AlignmentFlag.AlignLeft)

        if by_tier:
            for tier in sorted({i.tier or 0 for i in items}):
                bucket = [i for i in items if (i.tier or 0) == tier]
                cost = Counter(i.cost for i in bucket).most_common(1)[0][0]
                tier_label = QLabel(f"{cost:,}")
                tier_label.setStyleSheet(f"color: {theme.FG_DIM}; font-size: 8pt;")
                layout.addWidget(tier_label)
                add_grid(bucket)
        else:
            add_grid(items)
        layout.addStretch(1)
        return box

    # --- behavior -------------------------------------------------------------

    def _filter(self, needle: str) -> None:
        needle = needle.lower().strip()
        for cell in self.cells:
            cell.setVisible(not needle or needle in (cell.item.name or "").lower())

    def _refresh_states(self) -> None:
        """Mirror in-game shop: owned items dim, items whose direct
        component is owned highlight and show discounted cost."""
        owned = set(self.session.build.items)
        data = self.session.data
        for cell in self.cells:
            item = cell.item
            if item.class_name in owned:
                cell.set_state("owned")
                cell.set_discount(None, None)
                continue
            consumed = owned_components(item, owned)
            if consumed:
                names = ", ".join(data.shop_items[c].name or c for c in consumed)
                cell.set_state("upgrade")
                cell.set_discount(effective_cost(data, item, owned), names)
            else:
                cell.set_state("normal")
                cell.set_discount(None, None)

    def set_stats(self, stats: dict) -> None:
        for cell in self.cells:
            stat = stats.get(cell.item.class_name)
            if stat is not None:
                cell.set_win_rate(stat.win_rate, stat.matches)
