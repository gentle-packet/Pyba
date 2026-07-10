"""Target selector: naked-hero presets or custom resists, plus damage mix."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
)

from deadlock_eos import Build, resolve
from deadlock_eos.combat import DamageMix, TargetProfile


class TargetBar(QGroupBox):
    targetChanged = Signal(object, object)   # TargetProfile | None, DamageMix

    def __init__(self, data) -> None:
        super().__init__("Target")
        self.data = data
        layout = QHBoxLayout(self)

        self.hero_combo = QComboBox()
        self.hero_combo.addItem("— none —", None)
        for hero in sorted(data.playable_heroes(), key=lambda h: h.name):
            self.hero_combo.addItem(hero.name, hero.class_name)
        self.level = QSpinBox()
        self.level.setRange(1, 30)
        self.level.setValue(12)
        self.bonus_resist = QDoubleSpinBox()
        self.bonus_resist.setRange(-100, 100)
        self.bonus_resist.setSuffix("% br")
        self.bonus_resist.setToolTip("Extra bullet resist on top of the naked hero (items)")

        self.mix_combo = QComboBox()
        for label, mix in (
            ("Bullets", DamageMix(bullet=1)),
            ("Spirit", DamageMix(spirit=1)),
            ("50/50", DamageMix(bullet=1, spirit=1)),
        ):
            self.mix_combo.addItem(label, mix)

        layout.addWidget(QLabel("vs"))
        layout.addWidget(self.hero_combo, 1)
        layout.addWidget(QLabel("lvl"))
        layout.addWidget(self.level)
        layout.addWidget(self.bonus_resist)
        layout.addWidget(self.mix_combo)

        for signal in (self.hero_combo.currentIndexChanged, self.level.valueChanged,
                       self.mix_combo.currentIndexChanged):
            signal.connect(self._emit)
        self.bonus_resist.valueChanged.connect(self._emit)

    def _emit(self, *_args) -> None:
        self.targetChanged.emit(self.profile(), self.mix())

    def profile(self) -> TargetProfile | None:
        hero = self.hero_combo.currentData()
        if hero is None:
            return None
        max_level = max(self.data.heroes[hero].level_curve)
        level = min(self.level.value(), max_level)
        naked = resolve(self.data, Build(hero=hero, level=level), strict=False)
        profile = TargetProfile.from_resolution(naked)
        if self.bonus_resist.value():
            profile = TargetProfile(
                max_health=profile.max_health,
                bullet_resist=profile.bullet_resist + self.bonus_resist.value(),
                spirit_resist=profile.spirit_resist,
                melee_resist=profile.melee_resist,
            )
        return profile

    def mix(self) -> DamageMix:
        return self.mix_combo.currentData()
