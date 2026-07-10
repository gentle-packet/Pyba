"""Async icon loading with a disk cache.

bind(label, url) shows the pixmap when available; downloads happen on the
global QThreadPool and land in paths.cache_dir()/icons keyed by URL hash.
Failures are cached as misses for the session so we never hammer the CDN.
"""

from __future__ import annotations

import hashlib
import urllib.request
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QAbstractButton, QLabel

from .. import paths


class _Fetcher(QRunnable):
    def __init__(self, url: str, path: Path, signals: "_Signals") -> None:
        super().__init__()
        self.url, self.path, self.signals = url, path, signals

    def run(self) -> None:
        try:
            req = urllib.request.Request(self.url, headers={"User-Agent": "pyba-ui"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = resp.read()
            self.path.write_bytes(payload)
            self._emit(True)
        except Exception:
            self._emit(False)

    def _emit(self, ok: bool) -> None:
        # A download can still be in flight when the app tears down and Qt
        # deletes the receiving _Signals object; emitting then raises
        # "Signal source has been deleted". Nothing left to notify — drop it.
        try:
            self.signals.done.emit(self.url, ok)
        except RuntimeError:
            pass


class _Signals(QObject):
    done = Signal(str, bool)


class IconCache(QObject):
    def __init__(self, directory: Path | None = None) -> None:
        super().__init__()
        self.directory = directory or (paths.cache_dir() / "icons")
        self.directory.mkdir(parents=True, exist_ok=True)
        self._signals = _Signals()
        self._signals.done.connect(self._on_done)
        self._pending: dict[str, list[QLabel]] = {}
        self._failed: set[str] = set()

    def _path(self, url: str) -> Path:
        suffix = ".webp" if ".webp" in url else ".png"
        return self.directory / (hashlib.sha1(url.encode()).hexdigest() + suffix)

    def bind(self, label: QLabel | QAbstractButton, url: str | None) -> None:
        """Show the image on a QLabel (pixmap) or button (icon) — now if
        cached, else async when the download lands."""
        if not url:
            return
        path = self._path(url)
        if path.exists():
            self._apply(label, path)
            return
        if url in self._failed:
            return
        listeners = self._pending.setdefault(url, [])
        listeners.append(label)
        if len(listeners) == 1:
            QThreadPool.globalInstance().start(_Fetcher(url, path, self._signals))

    def _apply(self, widget: QLabel | QAbstractButton, path: Path) -> None:
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return
        if isinstance(widget, QAbstractButton):
            widget.setIcon(QIcon(pixmap))
        else:
            widget.setPixmap(
                pixmap.scaled(
                    widget.width() or 26,
                    widget.height() or 26,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

    def _on_done(self, url: str, ok: bool) -> None:
        labels = self._pending.pop(url, [])
        if not ok:
            self._failed.add(url)
            return
        path = self._path(url)
        for label in labels:
            try:
                self._apply(label, path)
            except RuntimeError:
                pass  # label deleted while download in flight
