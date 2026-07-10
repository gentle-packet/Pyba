"""Application bootstrap."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from deadlock_eos import DriftError

from ..service import load_game_data
from .theme import apply_dark_theme
from .views.main_window import MainWindow


def _app_icon_path() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        return base / "assets" / "icon.ico"
    return Path(__file__).resolve().parents[3] / "packaging" / "assets" / "icon.ico"


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Pyba")
    icon_path = _app_icon_path()
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))
    apply_dark_theme(app)
    try:
        data = load_game_data()
    except FileNotFoundError as exc:
        QMessageBox.critical(None, "Pyba — no game data", str(exc))
        return 1
    except DriftError:
        # A dump installed by the data updater may carry vocabulary this
        # engine version does not know yet — load it anyway, skipping
        # unknown ops, instead of refusing to start.
        data = load_game_data(strict=False)
    window = MainWindow(data)
    window.show()
    if os.environ.get("PYBA_SMOKE_TEST"):
        # frozen-build smoke test: construct the full UI, then exit cleanly
        QTimer.singleShot(0, app.quit)
    return app.exec()
