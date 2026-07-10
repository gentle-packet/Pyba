---
name: verify
description: Drive the Pyba desktop UI headless and capture screenshots to verify changes end-to-end.
---

# Verifying Pyba UI changes

The surface is a PySide6 desktop app (`Pyba\.venv\Scripts\python -m pyba.ui`).
For headless verification, drive the real MainWindow offscreen:

```python
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")  # else text renders as tofu boxes
from PySide6.QtWidgets import QApplication
from pyba.service import load_game_data
from pyba.ui.theme import apply_dark_theme
from pyba.ui.views.main_window import MainWindow

app = QApplication(sys.argv)
apply_dark_theme(app)
window = MainWindow(load_game_data())
window.resize(1500, 950); window.show()
```

- Mutations: `window.session.set_hero/add_item/preview_add_item/undo` — the same
  funnel every UI control calls.
- Screenshots: `app.processEvents(); window.grab().save(path)` (or grab a child
  widget like `window.graph` for closeups; `window.graph.canvas.setFixedHeight(220)`
  for a taller chart).
- Sidebar readout without pixels: iterate `window.stats._rows` →
  `(StatRow, extractor, stat)`; `row.name.text() / row.value.text() / row.delta.text()`.
  Honesty footer: `window.stats.honesty.text()`.
- Key widgets: `window.session`, `window.stats` (StatsPane), `window.graph` (RangeGraph).

Gotchas:
- QT_QPA_FONTDIR must point at real fonts under offscreen or every label is boxes.
- At interpreter teardown the async icon loader (`pyba.ui.icons`) spews
  "Signal source has been deleted" tracebacks — pre-existing shutdown race,
  harmless in scripts; ignore.
- `load_game_data()` needs the deadlock-eos dump repo checked out next to Pyba
  (or DEADLOCK_EOS_DATA set) — same convention as tests/conftest.py.
