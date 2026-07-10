"""Left panel: hero picker + saved fits library."""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QSortFilterProxyModel, Qt, Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QLineEdit,
    QListView,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..models import CLASS_NAME_ROLE, FitListModel, HeroListModel


class HeroPanel(QWidget):
    fitLoadRequested = Signal(str)   # slug

    def __init__(self, session, store) -> None:
        super().__init__()
        self.session = session
        self.store = store

        hero_box = QGroupBox("Heroes")
        hero_layout = QVBoxLayout(hero_box)
        self.hero_search = QLineEdit()
        self.hero_search.setPlaceholderText("Filter heroes…")
        self.hero_model = HeroListModel(session.data)
        self.hero_proxy = QSortFilterProxyModel()
        self.hero_proxy.setSourceModel(self.hero_model)
        self.hero_proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.hero_search.textChanged.connect(self.hero_proxy.setFilterFixedString)
        self.hero_view = QListView()
        self.hero_view.setModel(self.hero_proxy)
        self.hero_view.doubleClicked.connect(self._on_hero)
        hero_layout.addWidget(self.hero_search)
        hero_layout.addWidget(self.hero_view)

        fits_box = QGroupBox("Saved fits")
        fits_layout = QVBoxLayout(fits_box)
        self.fit_model = FitListModel(store)
        self.fit_view = QListView()
        self.fit_view.setModel(self.fit_model)
        self.fit_view.doubleClicked.connect(self._on_fit)
        delete_button = QPushButton("Delete selected fit")
        delete_button.clicked.connect(self._on_delete)
        fits_layout.addWidget(self.fit_view)
        fits_layout.addWidget(delete_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(hero_box, 2)
        layout.addWidget(fits_box, 1)

    def _on_hero(self, index: QModelIndex) -> None:
        class_name = self.hero_proxy.data(index, CLASS_NAME_ROLE)
        if class_name and class_name != self.session.build.hero:
            confirm = QMessageBox.question(
                self, "Switch hero",
                "Switching hero clears items and tiers. Continue?",
            )
            if confirm == QMessageBox.StandardButton.Yes:
                self.session.set_hero(class_name)

    def _on_fit(self, index: QModelIndex) -> None:
        slug = self.fit_model.data(index, CLASS_NAME_ROLE)
        if slug:
            self.fitLoadRequested.emit(slug)

    def _on_delete(self) -> None:
        index = self.fit_view.currentIndex()
        slug = self.fit_model.data(index, CLASS_NAME_ROLE) if index.isValid() else None
        if not slug:
            return
        if QMessageBox.question(self, "Delete fit", f"Delete saved fit {slug!r}?") == \
                QMessageBox.StandardButton.Yes:
            self.store.delete(slug)
            self.fit_model.refresh()
