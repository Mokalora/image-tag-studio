from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QKeyEvent, QPainter
from PySide6.QtWidgets import QLineEdit


class TabCompleteLineEdit(QLineEdit):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._suggestions: list[str] = []
        self._matches: list[str] = []
        self._match_index = 0
        self.textEdited.connect(lambda _: self._refresh_matches())

    def set_suggestions(self, suggestions: list[str]) -> None:
        seen: set[str] = set()
        self._suggestions = []
        for item in suggestions:
            if item and item not in seen:
                seen.add(item)
                self._suggestions.append(item)
        self._refresh_matches()

    def event(self, event) -> bool:  # noqa: ANN001
        if event.type() == event.Type.KeyPress and event.key() == Qt.Key_Tab:
            if self.accept_current_completion():
                event.accept()
                return True
            event.accept()
            return True
        return super().event(event)

    def focusNextPrevChild(self, next: bool) -> bool:  # noqa: A002, N802
        return False

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() in {Qt.Key_Down, Qt.Key_Up}:
            if self._matches:
                step = 1 if event.key() == Qt.Key_Down else -1
                self._match_index = (self._match_index + step) % len(self._matches)
                self.update()
                event.accept()
                return
        if event.key() in {Qt.Key_Tab, Qt.Key_Right}:
            if self.accept_current_completion():
                event.accept()
                return
        super().keyPressEvent(event)

    def complete_first_match(self) -> bool:
        return self.accept_current_completion()

    def accept_current_completion(self) -> bool:
        self._refresh_matches()
        if not self._matches:
            return False
        self._apply_completion(self._matches[self._match_index])
        return True

    def current_completion(self) -> str:
        self._refresh_matches()
        return self._matches[self._match_index] if self._matches else ""

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        completion = self._matches[self._match_index] if self._matches else ""
        prefix = self._current_prefix()
        if not completion or not prefix or completion.casefold() == prefix.casefold():
            return
        suffix = completion[len(prefix) :]
        if not suffix:
            return
        painter = QPainter(self)
        painter.setPen(QColor("#6F7D93"))
        margin = self.textMargins().left() + 10
        x = margin + self.fontMetrics().horizontalAdvance(self.text())
        y = (self.height() + self.fontMetrics().ascent() - self.fontMetrics().descent()) // 2
        painter.drawText(x, y, suffix)

    def _refresh_matches(self) -> None:
        prefix = self._current_prefix().casefold()
        if not prefix:
            self._matches = []
            self._match_index = 0
            self.update()
            return
        matches = [item for item in self._suggestions if item.casefold().startswith(prefix) and item.casefold() != prefix]
        if matches != self._matches:
            self._matches = matches[:20]
            self._match_index = 0
        elif self._matches:
            self._match_index %= len(self._matches)
        self.update()

    def _current_prefix(self) -> str:
        return self.text().split(",")[-1].strip()

    def _apply_completion(self, match: str) -> None:
        text = self.text()
        if "," in text:
            head = text[: text.rfind(",") + 1]
            self.setText(f"{head} {match}")
        else:
            self.setText(match)
        self.setCursorPosition(len(self.text()))
        self._refresh_matches()
