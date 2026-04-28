"""Async QPixmap cache for Character Mode images."""

from __future__ import annotations

import requests
from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QPixmap


class ImageLoadSignals(QObject):
    finished = pyqtSignal(str, object, str)


class ImageLoadTask(QRunnable):
    def __init__(self, url: str, timeout: int = 12):
        super().__init__()
        self.setAutoDelete(False)
        self.url = url
        self.timeout = timeout
        self.signals = ImageLoadSignals()

    @pyqtSlot()
    def run(self):
        data = None
        error = ""
        try:
            response = requests.get(self.url, timeout=self.timeout)
            response.raise_for_status()
            data = response.content
        except Exception as exc:
            error = str(exc)
        try:
            self.signals.finished.emit(self.url, data, error)
        except RuntimeError:
            pass


class CharacterImageCache(QObject):
    pixmap_loaded = pyqtSignal(str, QPixmap, bool)

    def __init__(self, parent=None, timeout: int = 12):
        super().__init__(parent)
        self.timeout = timeout
        self._cache: dict[str, QPixmap] = {}
        self._loading: set[str] = set()
        self._failed: set[str] = set()
        self._tasks: dict[str, ImageLoadTask] = {}
        self._pool = QThreadPool.globalInstance()

    def get(self, url: str) -> QPixmap:
        url = str(url or "").strip()
        if not url:
            return QPixmap()
        return self._cache.get(url, QPixmap())

    def has(self, url: str) -> bool:
        return str(url or "").strip() in self._cache

    def request(self, url: str, force: bool = False) -> QPixmap:
        url = str(url or "").strip()
        if not url:
            return QPixmap()

        if url in self._cache:
            return self._cache[url]

        if not force and (url in self._loading or url in self._failed):
            return QPixmap()

        self._loading.add(url)
        task = ImageLoadTask(url, timeout=self.timeout)
        task.signals.finished.connect(self._on_loaded)
        self._tasks[url] = task
        self._pool.start(task)
        return QPixmap()

    def clear_failures(self):
        self._failed.clear()

    def clear(self):
        self._cache.clear()
        self._loading.clear()
        self._failed.clear()
        self._tasks.clear()

    def _on_loaded(self, url: str, data: object, error: str):
        self._loading.discard(url)
        self._tasks.pop(url, None)

        success = False
        pixmap = QPixmap()

        if data:
            loaded = QPixmap()
            if loaded.loadFromData(data):
                pixmap = loaded
                self._cache[url] = pixmap
                success = True

        if not success:
            self._failed.add(url)

        self.pixmap_loaded.emit(url, pixmap, success)
