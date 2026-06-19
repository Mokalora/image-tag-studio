from __future__ import annotations

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QWidget


class StartupPopupSuppressor(QObject):
    """Hide unexpected startup dialogs before the main window is usable."""

    def __init__(self, main_window: QWidget, duration_ms: int = 8000) -> None:
        super().__init__(main_window)
        self.main_window = main_window
        self._remaining = max(1, duration_ms // 80)
        self.timer = QTimer(self)
        self.timer.setInterval(80)
        self.timer.timeout.connect(self._suppress)

    def start(self) -> None:
        self.timer.start()
        self._suppress()

    def _suppress(self) -> None:
        self._remaining -= 1
        for widget in QApplication.topLevelWidgets():
            if widget is self.main_window:
                continue
            if isinstance(widget, QMessageBox):
                widget.done(0)
                widget.hide()
            elif isinstance(widget, QDialog) and widget.isVisible():
                widget.reject()
                widget.hide()
        if self._remaining <= 0:
            self.timer.stop()
