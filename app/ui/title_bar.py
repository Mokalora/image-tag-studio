from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton
from qframelesswindow.utils import startSystemMove

from app.constants import APP_NAME


class WindowButton(QPushButton):
    def __init__(self, kind: str, parent=None) -> None:
        super().__init__("", parent)
        self.kind = kind
        self.theme = "dark"
        self.setProperty("titleButton", True)
        self.setFixedSize(38, 32)

    def set_kind(self, kind: str) -> None:
        self.kind = kind
        self.update()

    def set_theme(self, theme: str) -> None:
        self.theme = theme
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor("#172033" if self.theme == "light" else "#E7ECF3"), 1.6)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        cx, cy = self.width() / 2, self.height() / 2
        if self.kind == "min":
            painter.drawLine(int(cx - 6), int(cy + 5), int(cx + 6), int(cy + 5))
        elif self.kind == "max":
            painter.drawRect(QRectF(cx - 5, cy - 5, 10, 10))
        elif self.kind == "restore":
            painter.drawRect(QRectF(cx - 2, cy - 6, 9, 9))
            painter.drawRect(QRectF(cx - 6, cy - 2, 9, 9))
        elif self.kind == "close":
            painter.drawLine(int(cx - 5), int(cy - 5), int(cx + 5), int(cy + 5))
            painter.drawLine(int(cx + 5), int(cy - 5), int(cx - 5), int(cy + 5))


class ToolButton(QPushButton):
    def __init__(self, kind: str, parent=None) -> None:
        super().__init__("", parent)
        self.kind = kind
        self.theme = "dark"
        self.setProperty("titleButton", True)
        self.setFixedSize(34, 32)

    def set_theme(self, theme: str) -> None:
        self.theme = theme
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        color = QColor("#172033" if self.theme == "light" else "#E7ECF3")
        pen = QPen(color, 1.5)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        cx, cy = self.width() / 2, self.height() / 2
        if self.kind == "theme":
            painter.drawEllipse(QRectF(cx - 7, cy - 7, 14, 14))
            painter.setBrush(color)
            painter.drawPie(QRectF(cx - 7, cy - 7, 14, 14), 90 * 16, 180 * 16)
            painter.setBrush(Qt.NoBrush)
            painter.drawLine(int(cx), int(cy - 10), int(cx), int(cy - 13))
            painter.drawLine(int(cx + 9), int(cy), int(cx + 12), int(cy))
        elif self.kind == "lang":
            painter.drawRoundedRect(QRectF(cx - 11, cy - 8, 22, 16), 5, 5)
            painter.drawLine(int(cx), int(cy - 8), int(cx), int(cy + 8))
            font = painter.font()
            font.setPointSize(7)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(QRectF(cx - 10, cy - 8, 10, 16), Qt.AlignCenter, "中")
            painter.drawText(QRectF(cx, cy - 8, 10, 16), Qt.AlignCenter, "A")


class TitleBar(QFrame):
    minimize_requested = Signal()
    maximize_requested = Signal()
    close_requested = Signal()
    theme_toggle_requested = Signal()
    language_toggle_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setProperty("panel", True)
        self.setFixedHeight(44)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 6, 8, 6)
        layout.setSpacing(10)
        self.icon_label = QLabel()
        icon_path = Path(__file__).resolve().parents[1] / "assets" / "app_icon.ico"
        if icon_path.exists():
            self.icon_label.setPixmap(QIcon(str(icon_path)).pixmap(24, 24))
        self.icon_label.setFixedSize(26, 26)
        self.title_label = QLabel(APP_NAME)
        self.path_label = QLabel("")
        self.path_label.setProperty("muted", True)
        self.theme_button = ToolButton("theme", self)
        self.language_button = ToolButton("lang", self)
        self.min_button = WindowButton("min", self)
        self.max_button = WindowButton("max", self)
        self.close_button = WindowButton("close", self)
        self.close_button.setProperty("closeButton", True)
        self.theme_button.clicked.connect(self.theme_toggle_requested.emit)
        self.language_button.clicked.connect(self.language_toggle_requested.emit)
        self.min_button.clicked.connect(self.minimize_requested.emit)
        self.max_button.clicked.connect(self.maximize_requested.emit)
        self.close_button.clicked.connect(self.close_requested.emit)
        layout.addWidget(self.icon_label)
        layout.addWidget(self.title_label)
        layout.addWidget(self.path_label, 1)
        layout.addWidget(self.theme_button)
        layout.addWidget(self.language_button)
        layout.addWidget(self.min_button)
        layout.addWidget(self.max_button)
        layout.addWidget(self.close_button)

    def set_path(self, text: str) -> None:
        self.path_label.setText(text or "")

    def set_maximized(self, maximized: bool) -> None:
        self.max_button.set_kind("restore" if maximized else "max")

    def set_theme(self, theme: str) -> None:
        for button in [self.theme_button, self.language_button, self.min_button, self.max_button, self.close_button]:
            button.set_theme(theme)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if event.buttons() & Qt.LeftButton and self._is_caption_point(event.position().toPoint()):
            startSystemMove(self.window(), event.globalPosition().toPoint())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.maximize_requested.emit()
        super().mouseDoubleClickEvent(event)

    def _is_caption_point(self, point: QPoint) -> bool:
        for button in [self.theme_button, self.language_button, self.min_button, self.max_button, self.close_button]:
            top_left = button.mapTo(self, QPoint(0, 0))
            if QRectF(top_left, button.size()).contains(point):
                return False
        return True
