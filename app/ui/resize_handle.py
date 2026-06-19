from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget


class ResizeHandle(QWidget):
    resize_delta = Signal(int, int)

    def __init__(self, parent=None, mode: str = "corner") -> None:
        super().__init__(parent)
        self.mode = mode
        if mode == "right":
            self.setFixedSize(8, 96)
            self.setCursor(Qt.SizeHorCursor)
        elif mode == "bottom":
            self.setFixedSize(96, 8)
            self.setCursor(Qt.SizeVerCursor)
        else:
            self.setFixedSize(22, 22)
            self.setCursor(Qt.SizeFDiagCursor)
        self._drag_start: QPoint | None = None

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.setPen(QPen(QColor("#93A0B3"), 1))
        if self.mode == "right":
            x = self.width() // 2
            painter.drawLine(x, 18, x, self.height() - 18)
            return
        if self.mode == "bottom":
            y = self.height() // 2
            painter.drawLine(18, y, self.width() - 18, y)
            return
        size = self.width()
        for offset in (7, 11, 15):
            painter.drawLine(offset, size - 3, size - 3, offset)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._drag_start = event.globalPosition().toPoint()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag_start and event.buttons() & Qt.LeftButton:
            current = event.globalPosition().toPoint()
            delta = current - self._drag_start
            if self.mode == "right":
                self.resize_delta.emit(delta.x(), 0)
            elif self.mode == "bottom":
                self.resize_delta.emit(0, delta.y())
            else:
                self.resize_delta.emit(delta.x(), delta.y())
            self._drag_start = current
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._drag_start = None
        super().mouseReleaseEvent(event)
