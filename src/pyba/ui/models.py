"""Qt item models over game data and the fit library."""

from __future__ import annotations

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt

from deadlock_eos import GameData

from ..service import FitStore

CLASS_NAME_ROLE = Qt.ItemDataRole.UserRole + 1


class HeroListModel(QAbstractListModel):
    def __init__(self, data: GameData) -> None:
        super().__init__()
        self._heroes = sorted(data.playable_heroes(), key=lambda h: h.name)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._heroes)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        hero = self._heroes[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return hero.name
        if role == CLASS_NAME_ROLE:
            return hero.class_name
        return None


class FitListModel(QAbstractListModel):
    def __init__(self, store: FitStore) -> None:
        super().__init__()
        self.store = store
        self._infos = store.list()

    def refresh(self) -> None:
        self.beginResetModel()
        self._infos = self.store.list()
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._infos)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        info = self._infos[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return f"{info.name or info.slug}"
        if role == CLASS_NAME_ROLE:
            return info.slug
        return None
