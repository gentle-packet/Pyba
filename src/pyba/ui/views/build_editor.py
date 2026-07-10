"""Center panel: hero header, abilities bar, current items."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .. import theme
from ..icons import IconCache
from .ability_bar import AbilityBar


class _ItemRow(QWidget):
    """One equipped item: slot chip, name, optional stack spinner, remove.
    Hovering shows the removal delta (what the build loses)."""

    def __init__(self, session, class_name: str, icons: IconCache) -> None:
        super().__init__()
        self.session = session
        self.class_name = class_name
        item = session.data.shop_items[class_name]
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 1, 4, 1)

        icon_label = QLabel()
        icon_label.setFixedSize(26, 26)
        icons.bind(icon_label, item.raw.get("shop_image_webp") or item.raw.get("shop_image"))
        layout.addWidget(icon_label)

        color = theme.SLOT_COLORS.get(item.slot or "", theme.FG_DIM)
        name = QLabel(item.name or class_name)
        name.setStyleSheet(f"color: {color};")
        layout.addWidget(name, 1)

        max_stacks = session.max_stacks_for(class_name)
        if max_stacks is not None:
            layout.addWidget(QLabel("stacks"))
            spin = QSpinBox()
            spin.setRange(0, max_stacks)
            state = session.build.item_states.get(class_name)
            spin.setValue(state.stacks if state else 0)
            spin.valueChanged.connect(
                lambda stacks: session.set_stacks(class_name, stacks)
            )
            layout.addWidget(spin)

        remove = QPushButton("X")
        remove.setFixedWidth(26)
        remove.setToolTip("Remove item")
        remove.clicked.connect(lambda: session.remove_item(class_name))
        layout.addWidget(remove)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def enterEvent(self, event) -> None:  # removal delta preview
        self.session.preview_remove_item(self.class_name)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.session.clear_preview()
        super().leaveEvent(event)


class BuildEditor(QWidget):
    heroChangeRequested = Signal()

    def __init__(self, session, icons: IconCache) -> None:
        super().__init__()
        self.session = session
        self.icons = icons

        self.hero_label = QLabel()
        self.hero_label.setStyleSheet(f"font-size: 14pt; color: {theme.ACCENT}; font-weight: bold;")
        self.portrait = QLabel()
        self.portrait.setFixedSize(48, 48)
        self.level = QSpinBox()
        self.level.setRange(1, 30)
        self.level.valueChanged.connect(self._on_level)
        header = QHBoxLayout()
        header.addWidget(self.portrait)
        header.addWidget(self.hero_label, 1)
        header.addWidget(QLabel("Level"))
        header.addWidget(self.level)

        self.ability_bar = AbilityBar(session, icons)
        self.items_box = QGroupBox("Items")
        self.items_layout = QVBoxLayout(self.items_box)
        self.items_layout.setSpacing(1)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.addLayout(header)
        content_layout.addWidget(self.ability_bar)
        content_layout.addWidget(self.items_box)
        content_layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidget(content)
        scroll.setWidgetResizable(True)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        session.changed.connect(lambda _res: self.rebuild())
        self.rebuild()

    def _on_level(self, value: int) -> None:
        if value != self.session.build.level:
            try:
                self.session.set_level(value)
            except ValueError:
                self.level.setValue(self.session.build.level)  # over max for hero

    @staticmethod
    def _clear(layout) -> None:
        while layout.count():
            entry = layout.takeAt(0)
            if entry.widget():
                entry.widget().deleteLater()

    def rebuild(self) -> None:
        session = self.session
        build = session.build
        hero = session.data.heroes[build.hero]
        self.hero_label.setText(hero.name)
        images = hero.raw.get("images") or {}
        self.icons.bind(self.portrait, images.get("icon_hero_card_webp") or images.get("icon_image_small_webp"))
        self.level.blockSignals(True)
        self.level.setMaximum(max(hero.level_curve))
        self.level.setValue(build.level)
        self.level.blockSignals(False)

        self._clear(self.items_layout)
        by_slot: dict[str, list[str]] = {}
        for class_name in build.items:
            slot = session.data.shop_items[class_name].slot or "?"
            by_slot.setdefault(slot, []).append(class_name)
        for slot in ("weapon", "vitality", "spirit", "?"):
            for class_name in by_slot.get(slot, ()):
                self.items_layout.addWidget(_ItemRow(session, class_name, self.icons))
        count = len(build.items)
        self.items_box.setTitle(f"Items ({count})")
