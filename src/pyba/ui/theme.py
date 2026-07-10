"""Dark game-tool theme: palette + stylesheet + shared color constants."""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette

# slot colors follow the in-game shop categories
SLOT_COLORS = {
    "weapon": "#d78e4f",
    "vitality": "#79c748",
    "spirit": "#c78aeb",
}
DELTA_POSITIVE = "#6fd66f"
DELTA_NEGATIVE = "#e06c5f"
ACCENT = "#d7a86e"          # deadlock-ish brass
BG = "#1d1a17"
BG_PANEL = "#26221e"
BG_FIELD = "#141210"
FG = "#e8e0d2"
FG_DIM = "#9a917f"
BORDER = "#3a342c"


def apply_dark_theme(app) -> None:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(BG))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(FG))
    palette.setColor(QPalette.ColorRole.Base, QColor(BG_FIELD))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(BG_PANEL))
    palette.setColor(QPalette.ColorRole.Text, QColor(FG))
    palette.setColor(QPalette.ColorRole.Button, QColor(BG_PANEL))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(FG))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(BG))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(BG_PANEL))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(FG))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(FG_DIM))
    app.setPalette(palette)
    app.setStyleSheet(
        f"""
        QMainWindow, QDialog {{ background: {BG}; }}
        QGroupBox {{
            border: 1px solid {BORDER}; border-radius: 4px;
            margin-top: 1.1em; padding-top: 0.4em; background: {BG_PANEL};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin; left: 8px; color: {ACCENT};
            font-weight: bold;
        }}
        QLineEdit, QSpinBox, QComboBox, QListView, QTreeView, QTableView {{
            background: {BG_FIELD}; border: 1px solid {BORDER}; border-radius: 3px;
            padding: 2px 4px; selection-background-color: {ACCENT};
            selection-color: {BG};
        }}
        QPushButton, QToolButton {{
            background: {BG_PANEL}; border: 1px solid {BORDER}; border-radius: 3px;
            padding: 4px 10px;
        }}
        QPushButton:hover, QToolButton:hover {{ border-color: {ACCENT}; }}
        QToolButton[shopState="upgrade"] {{ border: 1px solid {ACCENT}; }}
        QPushButton:pressed, QToolButton:pressed {{ background: {BG_FIELD}; }}
        QToolTip {{
            background: {BG_PANEL}; color: {FG}; border: 1px solid {ACCENT};
        }}
        QSplitter::handle {{ background: {BORDER}; width: 2px; }}
        QStatusBar {{ color: {FG_DIM}; }}
        QLabel#versionLabel {{ color: {FG_DIM}; font-size: 11px; }}
        QTabBar::tab {{
            background: {BG_PANEL}; border: 1px solid {BORDER};
            padding: 4px 12px; border-top-left-radius: 3px; border-top-right-radius: 3px;
        }}
        QTabBar::tab:selected {{ color: {ACCENT}; border-bottom-color: {BG_PANEL}; }}
        QScrollArea {{ border: none; }}
        """
    )
