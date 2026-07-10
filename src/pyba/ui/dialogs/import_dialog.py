"""Import dialog: paste a PYBA1. code or an in-game build id."""

from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from ...service import import_any


class _Signals(QObject):
    done = Signal(object)    # Fit
    failed = Signal(str)


class _ImportJob(QRunnable):
    def __init__(self, text: str, data, signals: _Signals) -> None:
        super().__init__()
        self.text, self.data, self.signals = text, data, signals

    def run(self) -> None:
        try:
            self.signals.done.emit(import_any(self.text, self.data))
        except Exception as exc:
            self.signals.failed.emit(str(exc))


class ImportDialog(QDialog):
    def __init__(self, data, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Import build")
        self.data = data
        self.fit = None

        self.input = QLineEdit()
        self.input.setPlaceholderText("PYBA1.…  or in-game build id (e.g. 393691)")
        self.status = QLabel("")
        self.status.setWordWrap(True)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self._start)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Paste a Pyba build code or an in-game build id:"))
        layout.addWidget(self.input)
        layout.addWidget(self.status)
        layout.addWidget(buttons)
        self._signals = _Signals()
        self._signals.done.connect(self._on_done)
        self._signals.failed.connect(self._on_failed)

    def _start(self) -> None:
        text = self.input.text().strip()
        if not text:
            return
        self._ok.setEnabled(False)
        self.status.setText("Importing…")
        QThreadPool.globalInstance().start(_ImportJob(text, self.data, self._signals))

    def _on_done(self, fit) -> None:
        self.fit = fit
        self.accept()

    def _on_failed(self, message: str) -> None:
        self._ok.setEnabled(True)
        self.status.setText(f"Import failed: {message}")
