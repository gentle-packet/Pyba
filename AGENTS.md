# Agent notes for Pyba

Pyba is a PySide6 desktop app: a build simulator for the game Deadlock.
All stat math lives in the sibling repo `deadlock-eos`. Do not add stat
math here; if a number is wrong, the fix belongs in the engine.

## Commands

```
python -m venv .venv
.venv\Scripts\pip install -e ..\deadlock-eos -e ".[dev]"
.venv\Scripts\python -m pyba.ui        # run the app
.venv\Scripts\python -m pytest         # run tests
```

Needs Python 3.12+ and a sibling checkout of deadlock-eos, which carries
the game data. `DEADLOCK_EOS_DATA` overrides the data location.

## Architecture

- `src/pyba/port/` — converts published in-game builds (deadlock-api JSON)
  into engine `Build` objects
- `src/pyba/fits.py` — fit save/load as plain JSON, no I/O
- `src/pyba/service/` — the only layer allowed side effects: game data
  discovery and updates, fit library under `%APPDATA%/Pyba`, `PYBA1.`
  share codes, win rate analytics with disk cache
- `src/pyba/ui/` — the app. `session.py` holds `BuildSession`, the single
  mutation funnel: every state change goes through it, it re-resolves and
  emits `changed`/`previewChanged`. Widgets in `views/`, colors in
  `theme.py`

## Rules

- Route every build mutation through `BuildSession`. Never mutate a
  `Build` from a widget.
- No network or disk access outside `src/pyba/service/`.
- Tests run offline. UI tests must skip cleanly when PySide6 is missing.
- Fixtures: a real build payload is committed under `tests/fixtures/`.

## Gotchas

- Headless UI verification: follow `.claude/skills/verify/SKILL.md`
  (offscreen platform + `QT_QPA_FONTDIR=C:\Windows\Fonts`). Also call
  `app.setFont(QFont("Segoe UI"))` before showing anything, otherwise
  some glyphs render as boxes.
- Never call `QAction.menu()`. PySide6 deletes the QMenu wrapper on the
  C++ side. Keep menus as attributes (see `self._help_menu` in
  `main_window.py`).
- deadlock-api quirks: the builds endpoint needs `only_latest=true`
  (versions come ascending); the item-stats endpoint needs
  `min_unix_timestamp` or it times out; hero-scoped stats can be empty,
  fall back to global.
- Packaging does a non-editable `pip install`, which clobbers the editable
  dev install. Restore with `pip install -e` afterwards.
- `PYBA_SMOKE_TEST=1` starts the full UI offscreen and exits 0. CI uses it
  to smoke-test the frozen exe.

## Releasing

See the Releasing section in README.md. Version is single-sourced in
`src/pyba/__init__.py`; tags matching `v*` trigger the release workflow.
