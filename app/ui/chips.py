from __future__ import annotations

from PySide6.QtCore import QEvent, QMimeData, QPoint, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QDrag, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSizePolicy

from app.ui import palette


class ChipCloseButton(QPushButton):
    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        if not self.isEnabled() or self.text():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        center = QRectF(self.rect()).center()
        span = 4.2
        painter.setPen(QPen(palette.color("text"), 1.4, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(QPointF(center.x() - span, center.y() - span), QPointF(center.x() + span, center.y() + span))
        painter.drawLine(QPointF(center.x() + span, center.y() - span), QPointF(center.x() - span, center.y() + span))


class TagChip(QFrame):
    removed = Signal(str)
    renamed = Signal(str, str)
    move_requested = Signal(str, str, str)
    add_requested = Signal(str, str)
    drag_preview_requested = Signal(str, str, str)
    drag_preview_cleared = Signal()

    def __init__(self, tag: str, parent=None, add_position: str | None = None) -> None:
        super().__init__(parent)
        self.tag = tag
        self.add_position = add_position
        self.editing = False
        self._press_pos = QPoint()
        self._hovered = False
        self._selected = False
        self._drop_preview_side: str | None = None

        self.setObjectName("TagChip")
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.StrongFocus if add_position is None else Qt.NoFocus)
        self.setAcceptDrops(True)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.setMinimumHeight(38)
        self._edit_base_width = 0

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(6)
        self.label = QLabel(tag)
        self.label.setAttribute(Qt.WA_TranslucentBackground, True)
        self.editor = QLineEdit(tag if add_position is None else "")
        self.editor.setAttribute(Qt.WA_TranslucentBackground, True)
        self.editor.setObjectName("ChipEditor")
        self.editor.setFixedHeight(30)
        self.editor.setMinimumHeight(30)
        self.editor.hide()
        self.close_button = ChipCloseButton("+" if add_position else "")
        self.close_button.setObjectName("ChipCloseButton")
        self.close_button.setFixedSize(18, 18)
        self.close_button.setFocusPolicy(Qt.NoFocus)
        self.close_button.setEnabled(False)
        if add_position is not None:
            self.close_button.setText("")
        layout.addWidget(self.label)
        layout.addWidget(self.editor)
        layout.addWidget(self.close_button)

        self.close_button.clicked.connect(self._handle_close)
        self.editor.returnPressed.connect(self._confirm_edit)
        self.editor.editingFinished.connect(self._confirm_edit)
        self.editor.installEventFilter(self)
        self.editor.textEdited.connect(self._fit_editor_to_text)

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        bg = palette.color("card_hover" if self._hovered or self._selected else "card")
        border = palette.color("accent" if self._hovered or self._selected else "border")
        pen = QPen(border, 1.8 if self._selected else 1.1)
        if self.add_position is not None:
            pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.setBrush(bg)
        chip_rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.drawRoundedRect(chip_rect, 16, 16)
        if self._drop_preview_side:
            painter.setPen(QPen(palette.color("drop"), 3))
            x = 3 if self._drop_preview_side == "before" else self.width() - 4
            painter.drawLine(x, 5, x, self.height() - 6)

    def begin_edit(self) -> None:
        self.editing = True
        self.label.hide()
        self.close_button.setEnabled(False)
        self.editor.setText("" if self.add_position else self.tag)
        self.editor.show()
        self._edit_base_width = max(1, self.label.sizeHint().width())
        self.editor.setMinimumWidth(self._edit_base_width)
        self.editor.setFixedWidth(self._edit_base_width)
        self.editor.setFocus(Qt.MouseFocusReason)
        self.editor.selectAll()

    def eventFilter(self, watched, event) -> bool:
        if watched is self.editor and event.type() == QEvent.FocusOut:
            self._confirm_edit()
        return super().eventFilter(watched, event)

    def _confirm_edit(self) -> None:
        if not self.editing:
            return
        old_tag = self.tag
        new_tag = self.editor.text().strip()
        self.editing = False
        self.editor.hide()
        self.label.show()
        if self.add_position is not None:
            if new_tag:
                self.add_requested.emit(self.add_position, new_tag)
            self.editor.clear()
            return
        if new_tag and new_tag != old_tag:
            self.tag = new_tag
            self.label.setText(new_tag)
            self.renamed.emit(old_tag, new_tag)
        self.close_button.setEnabled(self._hovered)

    def _fit_editor_to_text(self) -> None:
        if not self.editing:
            return
        desired = self.fontMetrics().horizontalAdvance(self.editor.text() or " ") + 8
        self.editor.setFixedWidth(max(self._edit_base_width, desired))

    def _handle_close(self) -> None:
        if self.add_position is not None:
            return
        self.removed.emit(self.tag)

    def sizeHint(self) -> QSize:  # noqa: N802
        hint = super().sizeHint()
        return QSize(hint.width(), max(38, hint.height()))

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton and self.add_position is not None:
            self.begin_edit()
            event.accept()
            return
        if event.button() == Qt.LeftButton:
            self._press_pos = event.position().toPoint()
            self.setFocus(Qt.MouseFocusReason)
            self.set_selected(True)
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if self.add_position is None and self._selected and event.key() in {Qt.Key_Backspace, Qt.Key_Delete}:
            self.removed.emit(self.tag)
            event.accept()
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event) -> None:  # noqa: N802
        self.set_selected(False)
        super().focusOutEvent(event)

    def set_selected(self, selected: bool) -> None:
        if self.add_position is not None or self._selected == selected:
            return
        self._selected = selected
        self.close_button.setEnabled((self._hovered or self._selected) and not self.editing)
        self.update()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.begin_edit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self.add_position is not None or self.editing or not event.buttons() & Qt.LeftButton:
            super().mouseMoveEvent(event)
            return
        if (event.position().toPoint() - self._press_pos).manhattanLength() < 12:
            super().mouseMoveEvent(event)
            return
        mime = QMimeData()
        mime.setData("application/x-lora-tag", self.tag.encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.MoveAction)

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasFormat("application/x-lora-tag"):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasFormat("application/x-lora-tag"):
            source = bytes(event.mimeData().data("application/x-lora-tag")).decode("utf-8")
            target, side = self._drop_target(event.position().x())
            if source and target and source != target:
                self.drag_preview_requested.emit(source, target, side)
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        self.drag_preview_cleared.emit()
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802
        if not event.mimeData().hasFormat("application/x-lora-tag"):
            super().dropEvent(event)
            return
        source = bytes(event.mimeData().data("application/x-lora-tag")).decode("utf-8")
        target, side = self._drop_target(event.position().x())
        self.drag_preview_cleared.emit()
        if source and target and source != target:
            self.move_requested.emit(source, target, side)
            event.acceptProposedAction()
            return
        super().dropEvent(event)

    def set_drop_preview(self, side: str | None) -> None:
        if self._drop_preview_side == side:
            return
        self._drop_preview_side = side
        self.update()

    def _drop_target(self, x_pos: float) -> tuple[str, str]:
        if self.add_position == "start":
            return "__start__", "before"
        if self.add_position == "end":
            return "__end__", "after"
        return self.tag, "before" if x_pos < self.width() / 2 else "after"

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hovered = True
        if not self.editing and self.add_position is None:
            self.close_button.setEnabled(True)
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hovered = False
        if self.add_position is None:
            self.close_button.setEnabled(self._selected)
        self.update()
        super().leaveEvent(event)
