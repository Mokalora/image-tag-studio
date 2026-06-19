from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


class AppDialog(QDialog):
    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setModal(True)
        self.setProperty("panel", True)
        self._drag_origin: QPoint | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        title_row = QHBoxLayout()
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-size: 18px; font-weight: 600;")
        self.close_button = QPushButton("×")
        self.close_button.setProperty("titleButton", True)
        self.close_button.setFixedSize(34, 30)
        self.close_button.clicked.connect(self.reject)
        title_row.addWidget(self.title_label)
        title_row.addStretch(1)
        title_row.addWidget(self.close_button)
        root.addLayout(title_row)

        self.body = QFrame(self)
        self.body.setProperty("section", True)
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(14, 14, 14, 14)
        self.body_layout.setSpacing(12)
        root.addWidget(self.body)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._drag_origin = event.globalPosition().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_origin and event.buttons() & Qt.LeftButton:
            current = event.globalPosition().toPoint()
            self.move(self.pos() + current - self._drag_origin)
            self._drag_origin = current
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._drag_origin = None
        super().mouseReleaseEvent(event)


class ConfirmDialog(AppDialog):
    def __init__(self, title: str, message: str, yes_text: str, no_text: str, parent=None) -> None:
        super().__init__(title, parent)
        self.setMinimumWidth(420)
        self.message = QLabel(message)
        self.message.setWordWrap(True)
        self.body_layout.addWidget(self.message)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.no_button = QPushButton(no_text)
        self.yes_button = QPushButton(yes_text)
        self.no_button.setProperty("primary", True)
        self.no_button.setDefault(True)
        self.no_button.setAutoDefault(True)
        self.yes_button.setAutoDefault(False)
        self.no_button.clicked.connect(self.reject)
        self.yes_button.clicked.connect(self.accept)
        buttons.addWidget(self.yes_button)
        buttons.addWidget(self.no_button)
        self.body_layout.addLayout(buttons)
