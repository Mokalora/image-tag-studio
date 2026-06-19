from __future__ import annotations

import hashlib
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QSize, Qt, QThreadPool, Signal
from PySide6.QtGui import QImage, QImageReader

from app.constants import THUMB_CACHE_DIR
from app.logging_utils import log_exception


class ThumbSignals(QObject):
    ready = Signal(object, object)


def _cache_path(image_path: Path, size: QSize) -> Path:
    stat = image_path.stat()
    key = f"{image_path}|{stat.st_mtime_ns}|{stat.st_size}|{size.width()}x{size.height()}".encode("utf-8")
    return THUMB_CACHE_DIR / f"{hashlib.sha1(key).hexdigest()}.png"


def load_thumbnail(image_path: Path | None, size: QSize) -> QImage:
    if not image_path or not image_path.exists():
        return QImage()
    try:
        THUMB_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cached = _cache_path(image_path, size)
        if cached.exists():
            cached_image = QImage(str(cached))
            if not cached_image.isNull():
                return cached_image
        reader = QImageReader(str(image_path))
        reader.setAutoTransform(True)
        source_size = reader.size()
        if source_size.isValid() and source_size.width() > 0 and source_size.height() > 0:
            scaled = source_size.scaled(size, Qt.KeepAspectRatio)
            reader.setScaledSize(scaled)
        image = reader.read()
        if image.isNull():
            return QImage()
        image.save(str(cached), "PNG")
        return image
    except Exception as exc:  # noqa: BLE001
        log_exception(f"load thumbnail failed: {image_path}", exc)
        return QImage()


class ThumbTask(QRunnable):
    def __init__(self, key: Path, image_path: Path | None, size: QSize, signals: ThumbSignals) -> None:
        super().__init__()
        self.key = key
        self.image_path = image_path
        self.size = size
        self.signals = signals

    def run(self) -> None:
        image = load_thumbnail(self.image_path, self.size)
        try:
            self.signals.ready.emit(self.key, image)
        except RuntimeError:
            return


class ThumbnailService(QObject):
    ready = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._pool = QThreadPool.globalInstance()
        self._pool.setMaxThreadCount(max(2, min(4, self._pool.maxThreadCount())))
        self._signals = ThumbSignals(self)
        self._signals.ready.connect(self._on_ready)
        self._images: dict[Path, QImage] = {}
        self._pending: set[Path] = set()
        self._image_paths: dict[Path, Path | None] = {}
        self.size = QSize(320, 240)

    def set_items(self, mapping: dict[Path, Path | None]) -> None:
        self._image_paths = dict(mapping)
        valid = set(mapping)
        self._images = {path: image for path, image in self._images.items() if path in valid}
        self._pending.intersection_update(valid)

    def image(self, key: Path) -> QImage:
        return self._images.get(key, QImage())

    def request(self, key: Path, front: bool = False) -> None:
        del front
        if key in self._images or key in self._pending:
            return
        self._pending.add(key)
        self._pool.start(ThumbTask(key, self._image_paths.get(key), self.size, self._signals))

    def warmup(self, keys: list[Path], limit: int = 96) -> None:
        for key in keys[:limit]:
            self.request(key)

    def _on_ready(self, key: Path, image: QImage) -> None:
        self._pending.discard(key)
        self._images[key] = image
        self.ready.emit(key)
