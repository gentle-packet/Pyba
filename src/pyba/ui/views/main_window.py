"""Main window: 3-pane splitter, toolbar, status bar, service wiring."""

from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal
from PySide6.QtGui import QAction, QGuiApplication, QKeySequence
from PySide6.QtWidgets import (
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ... import __version__
from ...fits import Fit
from ...service import (
    FitStore,
    ItemAnalytics,
    check_for_update,
    download_update,
    encode_fit,
    revert_to_bundled,
)
from ..icons import IconCache
from ..session import BuildSession
from ..dialogs.import_dialog import ImportDialog
from .build_editor import BuildEditor
from .hero_panel import HeroPanel
from .item_palette import ItemPalette
from .range_graph import RangeGraph
from .stats_pane import StatsPane
from .target_bar import TargetBar


class _StatsSignals(QObject):
    done = Signal(object)


class _StatsJob(QRunnable):
    """Win-rate annotations off the main thread; cache makes reruns instant."""

    def __init__(self, analytics: ItemAnalytics, data, signals: _StatsSignals) -> None:
        super().__init__()
        self.analytics, self.data, self.signals = analytics, data, signals

    def run(self) -> None:
        try:
            stats = dict(self.analytics.annotate(self.data))
        except Exception:
            stats = {}  # advisory data; never break the UI
        try:
            self.signals.done.emit(stats)
        except RuntimeError:
            pass  # app closed while fetch was in flight


class _UpdateSignals(QObject):
    checkDone = Signal(object)  # int (newer build) | None
    updateDone = Signal(object)  # UpdateResult | Exception


class _CheckJob(QRunnable):
    """Remote build check off the main thread; failure means 'no update'."""

    def __init__(self, current_build: int, signals: _UpdateSignals) -> None:
        super().__init__()
        self.current_build, self.signals = current_build, signals

    def run(self) -> None:
        try:
            newer = check_for_update(self.current_build)
        except Exception:
            newer = None  # offline or API down; stay quiet
        try:
            self.signals.checkDone.emit(newer)
        except RuntimeError:
            pass  # app closed while check was in flight


class _UpdateJob(QRunnable):
    """Fetch + validate + install the latest dump off the main thread."""

    def __init__(self, signals: _UpdateSignals) -> None:
        super().__init__()
        self.signals = signals

    def run(self) -> None:
        try:
            payload: object = download_update()
        except Exception as exc:
            payload = exc
        try:
            self.signals.updateDone.emit(payload)
        except RuntimeError:
            pass


class MainWindow(QMainWindow):
    def __init__(self, data) -> None:
        super().__init__()
        self.setWindowTitle("Pyba — Deadlock fitting tool")
        self.resize(1440, 900)
        self.data = data
        self.session = BuildSession(data)
        self.store = FitStore()
        self.icons = IconCache()
        self.analytics = ItemAnalytics()

        self.hero_panel = HeroPanel(self.session, self.store)
        self.editor = BuildEditor(self.session, self.icons)
        self.palette_widget = ItemPalette(self.session, self.icons)
        self.stats = StatsPane(self.session)
        self.target_bar = TargetBar(data)
        self.graph = RangeGraph(self.session)
        self.graph.setVisible(False)  # optional panel, off by default

        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.addWidget(self.editor, 2)
        center_layout.addWidget(self.palette_widget, 3)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(self.target_bar)
        right_layout.addWidget(self.stats, 1)
        right_layout.addWidget(self.graph)

        splitter = QSplitter()
        splitter.addWidget(self.hero_panel)
        splitter.addWidget(center)
        splitter.addWidget(right)
        splitter.setSizes([230, 700, 450])
        self.setCentralWidget(splitter)

        self.update_button = QPushButton()
        self.update_button.setObjectName("updateButton")
        self.update_button.setFlat(True)
        self.update_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_button.clicked.connect(self._start_update)
        self.update_button.hide()
        self.statusBar().addPermanentWidget(self.update_button)

        version_label = QLabel(f"v{__version__}  ")
        version_label.setObjectName("versionLabel")
        self.statusBar().addPermanentWidget(version_label)

        self._make_toolbar()
        self._make_menus()
        self.hero_panel.fitLoadRequested.connect(self._load_fit)
        self.target_bar.targetChanged.connect(self.stats.set_target)
        self.session.changed.connect(lambda _res: self._update_status())
        self._update_status()

        self._stats_signals = _StatsSignals()
        self._stats_signals.done.connect(self.palette_widget.set_stats)
        QThreadPool.globalInstance().start(
            _StatsJob(self.analytics, data, self._stats_signals)
        )

        self._update_signals = _UpdateSignals()
        self._update_signals.checkDone.connect(self._on_check_done)
        self._update_signals.updateDone.connect(self._on_update_done)
        self._manual_check = False
        QThreadPool.globalInstance().start(
            _CheckJob(data.build, self._update_signals)
        )

    def _make_toolbar(self) -> None:
        toolbar = self.addToolBar("main")
        toolbar.setMovable(False)

        def action(text: str, slot, shortcut: str | None = None) -> QAction:
            act = QAction(text, self)
            if shortcut:
                act.setShortcut(QKeySequence(shortcut))
            act.triggered.connect(slot)
            toolbar.addAction(act)
            return act

        action("Save fit", self._save_fit, "Ctrl+S")
        action("Import…", self._import, "Ctrl+I")
        action("Copy code", self._copy_code, "Ctrl+E")
        toolbar.addSeparator()
        self.undo_action = action("Undo", self.session.undo, "Ctrl+Z")
        self.redo_action = action("Redo", self.session.redo, "Ctrl+Y")
        toolbar.addSeparator()
        chart_act = QAction("Chart", self)
        chart_act.setCheckable(True)
        chart_act.setChecked(False)
        chart_act.setToolTip("Show/hide the DPS-vs-range chart")
        chart_act.toggled.connect(self.graph.setVisible)
        toolbar.addAction(chart_act)
        self.session.changed.connect(lambda _res: self._update_undo())
        self._update_undo()

    def _make_menus(self) -> None:
        # keep a python ref: shiboken may drop the wrapper-owned QMenu otherwise
        self._help_menu = help_menu = self.menuBar().addMenu("&Help")

        check_act = QAction("Check for game data updates", self)
        check_act.triggered.connect(self._manual_check_for_updates)
        help_menu.addAction(check_act)

        revert_act = QAction("Revert to bundled game data…", self)
        revert_act.triggered.connect(self._revert_bundled)
        help_menu.addAction(revert_act)

    def _update_undo(self) -> None:
        self.undo_action.setEnabled(self.session.can_undo())
        self.redo_action.setEnabled(self.session.can_redo())

    def _update_status(self) -> None:
        res = self.session.resolution
        parts = [f"data build {self.data.build}", f"{len(res.build.items)} items"]
        if res.unmodeled:
            parts.append(f"{len(res.unmodeled)} unmodeled effect(s)")
        if res.unapplied:
            parts.append(f"{len(res.unapplied)} unapplied modifier type(s)")
        self.statusBar().showMessage("  |  ".join(parts))

    # --- toolbar slots -------------------------------------------------------

    def _save_fit(self) -> None:
        name, ok = QInputDialog.getText(self, "Save fit", "Fit name:")
        if not ok or not name.strip():
            return
        self.store.save(Fit(name=name.strip(), build=self.session.build))
        self.hero_panel.fit_model.refresh()

    def _load_fit(self, slug: str) -> None:
        fit = self.store.load(slug)
        self.session.replace(fit.build)

    def _import(self) -> None:
        dialog = ImportDialog(self.data, self)
        if dialog.exec() and dialog.fit is not None:
            self.session.replace(dialog.fit.build)

    def _copy_code(self) -> None:
        code = encode_fit(Fit(name="", build=self.session.build))
        QGuiApplication.clipboard().setText(code)
        self.statusBar().showMessage(f"Pyba code copied ({len(code)} chars)", 4000)

    # --- game-data updater ---------------------------------------------------

    def _manual_check_for_updates(self) -> None:
        self._manual_check = True
        self.statusBar().showMessage("Checking for game data updates…", 4000)
        QThreadPool.globalInstance().start(
            _CheckJob(self.data.build, self._update_signals)
        )

    def _on_check_done(self, newer: object) -> None:
        manual, self._manual_check = self._manual_check, False
        if isinstance(newer, int):
            self.update_button.setText(f"Game data build {newer} available — Update")
            self.update_button.setEnabled(True)
            self.update_button.show()
        elif manual:
            self.statusBar().showMessage(
                f"Game data is up to date (build {self.data.build})", 5000
            )

    def _start_update(self) -> None:
        self.update_button.setEnabled(False)
        self.update_button.setText("Updating game data…")
        QThreadPool.globalInstance().start(_UpdateJob(self._update_signals))

    def _on_update_done(self, payload: object) -> None:
        if isinstance(payload, Exception):
            self.update_button.setText("Update failed — retry")
            self.update_button.setEnabled(True)
            QMessageBox.warning(
                self,
                "Pyba — game data update failed",
                f"The update was not installed; current data is untouched.\n\n{payload}",
            )
            return
        self.update_button.hide()
        if payload.skipped:
            self.statusBar().showMessage(
                f"Game data build {payload.build} already installed — restart Pyba to use it",
                8000,
            )
            return
        message = f"Game data build {payload.build} installed.\n\nRestart Pyba to use it."
        if payload.report.drift:
            message += (
                "\n\nNote: this patch introduced game mechanics unknown to this "
                "Pyba version. Affected effects will show as unmodeled until "
                "Pyba is updated."
            )
        QMessageBox.information(self, "Pyba — game data updated", message)

    def _revert_bundled(self) -> None:
        answer = QMessageBox.question(
            self,
            "Pyba — revert game data",
            "Delete downloaded game data and go back to the data bundled "
            "with this Pyba version?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        removed = revert_to_bundled()
        if removed:
            QMessageBox.information(
                self,
                "Pyba — game data reverted",
                f"Removed {removed} downloaded build(s).\n\nRestart Pyba to "
                "load the bundled data.",
            )
        else:
            self.statusBar().showMessage("No downloaded game data to remove", 5000)
