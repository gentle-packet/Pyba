"""Always-visible stats sidebar: collapsible sections, ledger tooltips,
delta labels during hover preview."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from deadlock_eos import Resolution, Stat, debuffed_profile, effective_dps, effective_hp
from deadlock_eos.combat import DamageMix, TargetProfile

from .. import theme

Extractor = Callable[[Resolution, "StatsContext"], float | None]


class StatsContext:
    """Target profile + damage mix shared by extractors (set by TargetBar)."""

    def __init__(self) -> None:
        self.data = None  # GameData, set by StatsPane
        self.profile: TargetProfile | None = None
        self.mix = DamageMix(bullet=1.0)


class StatRow:
    def __init__(self, grid: QGridLayout, row: int, label: str, fmt: str = "{:.1f}") -> None:
        self.fmt = fmt
        self.name = QLabel(label)
        self.value = QLabel("—")
        self.value.setMinimumWidth(56)
        self.value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.delta = QLabel("")
        self.delta.setMinimumWidth(52)
        self.delta.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        grid.addWidget(self.name, row, 0)
        grid.addWidget(self.value, row, 1)
        grid.addWidget(self.delta, row, 2)

    def update(self, current: float | None, preview: float | None) -> None:
        self.value.setText("—" if current is None else self.fmt.format(current))
        if preview is None or current is None or abs(preview - current) < 1e-9:
            self.delta.setText("")
            return
        diff = preview - current
        color = theme.DELTA_POSITIVE if diff > 0 else theme.DELTA_NEGATIVE
        self.delta.setText(f"{'+' if diff > 0 else ''}{self.fmt.format(diff)}")
        self.delta.setStyleSheet(f"color: {color};")

    def set_tooltip(self, text: str) -> None:
        for widget in (self.name, self.value):
            widget.setToolTip(text)


def _ledger_tooltip(resolution: Resolution, stat: Stat) -> str:
    value = resolution.stats[stat]
    lines = [f"base {value.base:g}"]
    for c in value.contributions:
        sign = "+" if c.amount >= 0 else ""
        kind = "%" if c.bucket.value == "pct" else ""
        lines.append(f"{sign}{c.amount:g}{kind}  —  {c.source}")
    if value.overridden:
        lines.append("OVERRIDDEN by user")
    return "\n".join(lines)


def _stat(stat: Stat) -> Extractor:
    return lambda res, ctx: res.stats[stat].final


def _gun(attr: str) -> Extractor:
    return lambda res, ctx: getattr(res.gun, attr) if res.gun else None


def _dps_at(distance_m: float) -> Extractor:
    """Burst DPS at a distance: range-gated item bonuses + (stretched) falloff."""
    return lambda res, ctx: res.gun.damage_per_second_at(distance_m) if res.gun else None


def _ehp(res: Resolution, ctx: StatsContext) -> float | None:
    profile = TargetProfile.from_resolution(res)
    try:
        return effective_hp(profile, ctx.mix)
    except ValueError:
        return None


def _edps(res: Resolution, ctx: StatsContext) -> float | None:
    """Gun dps into the selected target, after this build's resist shreds."""
    if res.gun is None or ctx.profile is None or ctx.data is None:
        return None
    shredded = debuffed_profile(ctx.data, res.build, ctx.profile)
    return effective_dps(res.gun.damage_per_second, shredded)


def _target_ehp(res: Resolution, ctx: StatsContext) -> float | None:
    if ctx.profile is None or ctx.data is None:
        return None
    shredded = debuffed_profile(ctx.data, res.build, ctx.profile)
    try:
        return effective_hp(shredded, ctx.mix)
    except ValueError:
        return None


SECTIONS: list[tuple[str, list[tuple[str, Extractor, str, Stat | None]]]] = [
    ("Vitality", [
        ("Max HP", _stat(Stat.MAX_HEALTH), "{:.0f}", Stat.MAX_HEALTH),
        ("HP Regen", _stat(Stat.HEALTH_REGEN), "{:.1f}", Stat.HEALTH_REGEN),
        ("Bullet Resist %", _stat(Stat.BULLET_RESIST), "{:.1f}", Stat.BULLET_RESIST),
        ("Spirit Resist %", _stat(Stat.SPIRIT_RESIST), "{:.1f}", Stat.SPIRIT_RESIST),
        ("Own EHP (vs mix)", _ehp, "{:.0f}", None),
    ]),
    ("Weapon", [
        ("Bullet Damage", _gun("bullet_damage"), "{:.2f}", None),
        ("Clip Size", _gun("clip_size"), "{:.1f}", Stat.CLIP_SIZE),
        ("DPS (burst)", _gun("damage_per_second"), "{:.1f}", None),
        ("DPS (sustained)", _gun("sustained_damage_per_second"), "{:.1f}", None),
        # reference distances: 5m sits inside every close-range gate and
        # before typical falloff start; 20m is beyond the 15m long-range
        # gates. Headline DPS rows above stay unconditional/falloff-free.
        ("DPS @ 5m", _dps_at(5.0), "{:.1f}", None),
        ("DPS @ 20m", _dps_at(20.0), "{:.1f}", None),
        ("eDPS vs target", _edps, "{:.1f}", None),
        ("Target EHP", _target_ehp, "{:.0f}", None),
        ("Weapon Damage %", _stat(Stat.WEAPON_DAMAGE_PCT), "{:.1f}", Stat.WEAPON_DAMAGE_PCT),
        # "15m" is the current data constant for all four range-gated items;
        # dynamic labels from gun.range_bonuses are follow-up polish (the
        # ledger tooltip already names the contributing items)
        ("WD % (within 15m)", _stat(Stat.CLOSE_RANGE_WEAPON_DAMAGE_PCT), "{:.1f}",
         Stat.CLOSE_RANGE_WEAPON_DAMAGE_PCT),
        ("WD % (beyond 15m)", _stat(Stat.LONG_RANGE_WEAPON_DAMAGE_PCT), "{:.1f}",
         Stat.LONG_RANGE_WEAPON_DAMAGE_PCT),
        ("Fall-off Range %", _stat(Stat.WEAPON_FALLOFF_RANGE_PCT), "{:.1f}",
         Stat.WEAPON_FALLOFF_RANGE_PCT),
        ("Fire Rate %", _stat(Stat.FIRE_RATE), "{:.1f}", Stat.FIRE_RATE),
        ("Bullet Lifesteal %", _stat(Stat.BULLET_LIFESTEAL), "{:.1f}", Stat.BULLET_LIFESTEAL),
    ]),
    ("Spirit", [
        ("Spirit Power", _stat(Stat.SPIRIT_POWER), "{:.1f}", Stat.SPIRIT_POWER),
        ("Spirit Amp %", _stat(Stat.SPIRIT_AMP_PCT), "{:.1f}", Stat.SPIRIT_AMP_PCT),
        ("Cooldown Reduction %", _stat(Stat.COOLDOWN_REDUCTION), "{:.1f}", Stat.COOLDOWN_REDUCTION),
        ("Item CDR %", _stat(Stat.ITEM_COOLDOWN_REDUCTION), "{:.1f}", Stat.ITEM_COOLDOWN_REDUCTION),
        ("Duration %", _stat(Stat.ABILITY_DURATION_PCT), "{:.1f}", Stat.ABILITY_DURATION_PCT),
        ("Range %", _stat(Stat.ABILITY_RANGE_PCT), "{:.1f}", Stat.ABILITY_RANGE_PCT),
    ]),
    ("Movement", [
        ("Move Speed", _stat(Stat.MOVE_SPEED), "{:.2f}", Stat.MOVE_SPEED),
        ("Sprint Bonus", _stat(Stat.SPRINT_SPEED), "{:.2f}", Stat.SPRINT_SPEED),
        ("Stamina", _stat(Stat.STAMINA), "{:.0f}", Stat.STAMINA),
    ]),
]

ABILITY_PROPS = ("AbilityCooldown", "AbilityDuration", "DPS", "Damage", "Radius", "HealingFactor")


def _config_grid(grid: QGridLayout) -> None:
    """Cluster name/value/delta left; trailing spacer column (3) eats slack."""
    grid.setColumnStretch(0, 0)
    grid.setColumnStretch(3, 1)
    grid.setHorizontalSpacing(8)
    grid.setVerticalSpacing(2)
    grid.setContentsMargins(8, 4, 8, 4)


class StatsPane(QWidget):
    def __init__(self, session) -> None:
        super().__init__()
        self.session = session
        self.ctx = StatsContext()
        self.ctx.data = session.data
        self._preview: Resolution | None = None
        self._rows: list[tuple[StatRow, Extractor, Stat | None]] = []
        self._ability_box: QGroupBox | None = None
        self._ability_rows: list[tuple[StatRow, str, str]] = []
        self._columns = 1

        # build section boxes once; placement into columns happens in _relayout
        self._section_boxes: list[QGroupBox] = []
        for title, rows in SECTIONS:
            box = QGroupBox(title)
            grid = QGridLayout(box)
            _config_grid(grid)
            for i, (label, extractor, fmt, stat) in enumerate(rows):
                self._rows.append((StatRow(grid, i, label, fmt), extractor, stat))
            self._section_boxes.append(box)
        self._ability_box = QGroupBox("Abilities")
        self._ability_grid = QGridLayout(self._ability_box)
        _config_grid(self._ability_grid)
        self.honesty = QLabel("")
        self.honesty.setWordWrap(True)
        self.honesty.setStyleSheet(f"color: {theme.FG_DIM}; font-size: 8pt;")

        # two column containers inside the scroll; _relayout distributes boxes
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(6, 6, 6, 6)
        content_layout.setSpacing(4)
        cols_row = QWidget()
        cols = QHBoxLayout(cols_row)
        cols.setContentsMargins(0, 0, 0, 0)
        cols.setSpacing(6)
        self._column_widgets: list[QWidget] = []
        self._column_layouts: list[QVBoxLayout] = []
        for _ in range(2):
            cw = QWidget()
            cl = QVBoxLayout(cw)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setSpacing(6)
            cl.setAlignment(Qt.AlignmentFlag.AlignTop)
            cols.addWidget(cw, 1)
            self._column_widgets.append(cw)
            self._column_layouts.append(cl)
        content_layout.addWidget(cols_row)
        content_layout.addWidget(self.honesty)  # footnote spans full width

        scroll = QScrollArea()
        scroll.setWidget(content)
        scroll.setWidgetResizable(True)

        # top-left density toggle
        header = QHBoxLayout()
        header.setContentsMargins(6, 4, 6, 0)
        self._col_toggle = QToolButton()
        self._col_toggle.setCheckable(True)
        self._col_toggle.setText("▮ 1 col")
        self._col_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self._col_toggle.setToolTip("Toggle 1/2 column layout")
        self._col_toggle.toggled.connect(self._on_toggle_columns)
        header.addWidget(self._col_toggle)
        header.addStretch(1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addLayout(header)
        outer.addWidget(scroll)
        self._relayout_sections()

        session.changed.connect(self._on_changed)
        session.previewChanged.connect(self._on_preview)
        self._rebuild_ability_rows()
        self.refresh()

    # --- layout ------------------------------------------------------------

    def _on_toggle_columns(self, checked: bool) -> None:
        self._columns = 2 if checked else 1
        self._col_toggle.setText("▮▮ 2 col" if checked else "▮ 1 col")
        self._relayout_sections()

    def _relayout_sections(self) -> None:
        """Detach every section box, then re-place per column count.

        2-col mode balances by greedy bin packing on sizeHint heights so
        neither column runs much longer (ability box height varies per hero).
        """
        for cl in self._column_layouts:
            while cl.count():
                item = cl.takeAt(0)
                if item.widget():
                    item.widget().setParent(None)
        boxes = [*self._section_boxes, self._ability_box]

        if self._columns == 1:
            self._column_widgets[1].hide()
            for box in boxes:
                self._column_layouts[0].addWidget(box)
        else:
            self._column_widgets[1].show()
            heights = [0, 0]
            for box in sorted(boxes, key=lambda b: b.sizeHint().height(), reverse=True):
                col = 0 if heights[0] <= heights[1] else 1
                self._column_layouts[col].addWidget(box)
                heights[col] += box.sizeHint().height()
        for cl in self._column_layouts:
            cl.addStretch(1)
        for box in boxes:
            box.show()  # setParent(None) hides; re-adding does not re-show

    # --- wiring ------------------------------------------------------------

    def set_target(self, profile: TargetProfile | None, mix: DamageMix) -> None:
        self.ctx.profile = profile
        self.ctx.mix = mix
        self.refresh()

    def _on_changed(self, resolution: Resolution) -> None:
        self._rebuild_ability_rows()
        if self._columns == 2:
            self._ability_grid.activate()  # refresh sizeHint before balancing
            self._relayout_sections()
        self.refresh()

    def _on_preview(self, resolution: Resolution | None) -> None:
        self._preview = resolution
        self.refresh()

    def _rebuild_ability_rows(self) -> None:
        while self._ability_grid.count():
            item = self._ability_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._ability_rows = []
        res = self.session.resolution
        row = 0
        for class_name in sorted(res.abilities):
            ability = res.abilities[class_name]
            if class_name not in self.session.data.heroes[res.build.hero].signatures:
                continue
            name = self.session.data.abilities[class_name].name or class_name
            header = QLabel(f"{name}  (T{ability.tier})")
            header.setStyleSheet(f"color: {theme.ACCENT};")
            self._ability_grid.addWidget(header, row, 0, 1, 4)
            row += 1
            for prop in ABILITY_PROPS:
                if prop in ability.properties:
                    stat_row = StatRow(self._ability_grid, row, f"  {prop}", "{:.2f}")
                    self._ability_rows.append((stat_row, class_name, prop))
                    row += 1

    # --- refresh --------------------------------------------------------------

    def refresh(self) -> None:
        current = self.session.resolution
        preview = self._preview
        for stat_row, extractor, stat in self._rows:
            cur = extractor(current, self.ctx)
            pre = extractor(preview, self.ctx) if preview is not None else None
            stat_row.update(cur, pre)
            if stat is not None:
                stat_row.set_tooltip(_ledger_tooltip(current, stat))
        for stat_row, class_name, prop in self._ability_rows:
            cur_ability = current.abilities.get(class_name)
            cur = cur_ability.properties[prop].value if cur_ability and prop in cur_ability.properties else None
            pre = None
            if preview is not None:
                pre_ability = preview.abilities.get(class_name)
                if pre_ability and prop in pre_ability.properties:
                    pre = pre_ability.properties[prop].value
            stat_row.update(cur, pre)
        notes = []
        if current.unapplied:
            notes.append(f"unapplied: {len(current.unapplied)} modifier type(s)")
        if current.unmodeled:
            notes.append(f"unmodeled effects: {', '.join(current.unmodeled)}")
        self.honesty.setText("\n".join(notes))
