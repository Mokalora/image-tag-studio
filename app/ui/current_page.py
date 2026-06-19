from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QElapsedTimer, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QPainter, QPainterPath, QPen, QPixmap, QWheelEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QScrollArea, QSplitter, QStackedLayout, QVBoxLayout, QWidget

from app.models import TagFile
from app.tag_parser import add_tags, format_tags, parse_tags, replace_tags
from app.ui import palette
from app.ui.chips import TagChip
from app.ui.flow_layout import FlowLayout


class ImageCanvas(QWidget):
    previous_requested = Signal()
    next_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(180)
        self.setMouseTracking(True)
        self.pixmap = QPixmap()
        self.message = "暂无图片预览"
        self.language = "zh"
        self.mode = 0
        self.zoom = 1.0
        self.offset = QPointF(0, 0)
        self.drag_origin: QPointF | None = None
        self.drag_offset = QPointF(0, 0)
        self.hover_nav: str | None = None
        self._nav_timer = QElapsedTimer()
        self._nav_timer.invalidate()

    def set_image(self, path: Path | None) -> None:
        self.pixmap = QPixmap(str(path)) if path and path.exists() else QPixmap()
        self.message = ("No matching image" if self.language == "en" else "没有同名图片") if self.pixmap.isNull() else ""
        self.update()

    def apply_language(self, language: str) -> None:
        self.language = language
        if self.pixmap.isNull():
            self.message = "No image preview" if language == "en" else "暂无图片预览"
        self.update()

    def set_mode(self, mode: int) -> None:
        self.mode = mode
        self.zoom = 1.0
        self.offset = QPointF(0, 0)
        self.update()

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        if self.pixmap.isNull():
            return
        old_rect = self._image_rect()
        old_zoom = self.zoom
        factor = 1.12 if event.angleDelta().y() > 0 else 1 / 1.12
        self.zoom = max(0.05, min(10.0, self.zoom * factor))
        if old_zoom != self.zoom and old_rect.width() > 1 and old_rect.height() > 1:
            cursor = event.position()
            rel_x = (cursor.x() - old_rect.x()) / old_rect.width()
            rel_y = (cursor.y() - old_rect.y()) / old_rect.height()
            new_rect = self._image_rect()
            self.offset += QPointF(
                cursor.x() - (new_rect.x() + rel_x * new_rect.width()),
                cursor.y() - (new_rect.y() + rel_y * new_rect.height()),
            )
        self.update()
        event.accept()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        nav = self._nav_click_hit(event.position())
        if event.button() == Qt.LeftButton and nav:
            if self._nav_timer.isValid() and self._nav_timer.elapsed() < 220:
                event.accept()
                return
            self._nav_timer.restart()
            if nav == "previous":
                self.previous_requested.emit()
            else:
                self.next_requested.emit()
            event.accept()
            return
        if event.button() == Qt.MiddleButton:
            self.zoom = 1.0
            self.offset = QPointF(0, 0)
            self.update()
            event.accept()
            return
        if event.button() in {Qt.LeftButton, Qt.RightButton}:
            self.drag_origin = event.position()
            self.drag_offset = QPointF(self.offset)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self.drag_origin is None:
            nav = self._nav_hover(event.position())
            if nav != self.hover_nav:
                self.hover_nav = nav
                self.update()
        if self.drag_origin is not None:
            self.offset = self.drag_offset + event.position() - self.drag_origin
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self.drag_origin = None
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self.hover_nav = None
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.fillRect(self.rect(), palette.color("image_bg"))
        if self.pixmap.isNull():
            painter.setPen(palette.color("muted"))
            painter.drawText(self.rect(), Qt.AlignCenter, self.message)
            return
        painter.drawPixmap(self._image_rect(), self.pixmap, QRectF(self.pixmap.rect()))
        self._paint_nav(painter)

    def _image_rect(self) -> QRectF:
        if self.mode == 2:
            width, height = self.pixmap.width(), self.pixmap.height()
        else:
            target_w = max(1, self.width() - 20)
            target_h = max(1, self.height() - 20)
            ratio = self.pixmap.width() / max(1, self.pixmap.height())
            if self.mode == 1:
                width, height = int(target_h * ratio), target_h
            else:
                scale = min(target_w / self.pixmap.width(), target_h / self.pixmap.height())
                width, height = int(self.pixmap.width() * scale), int(self.pixmap.height() * scale)
        width, height = max(1, int(width * self.zoom)), max(1, int(height * self.zoom))
        return QRectF((self.width() - width) / 2 + self.offset.x(), (self.height() - height) / 2 + self.offset.y(), width, height)

    def _nav_rect(self, side: str) -> QRectF:
        width = 64
        height = 96
        margin = 18
        x = margin if side == "previous" else self.width() - width - margin
        return QRectF(x, (self.height() - height) / 2, width, height)

    def _nav_hover(self, point: QPointF) -> str | None:
        if self.pixmap.isNull():
            return None
        edge_zone = max(76, self.width() * 0.14)
        if point.x() <= edge_zone:
            return "previous"
        if point.x() >= self.width() - edge_zone:
            return "next"
        return None

    def _nav_click_hit(self, point: QPointF) -> str | None:
        if self.pixmap.isNull():
            return None
        for side in ("previous", "next"):
            if self._nav_rect(side).contains(point):
                return side
        return None

    def _paint_nav(self, painter: QPainter) -> None:
        if self.hover_nav is None:
            return
        rect = self._nav_rect(self.hover_nav)
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        center = rect.center()
        direction = -1 if self.hover_nav == "previous" else 1
        path = QPainterPath()
        path.moveTo(center.x() - direction * 16, center.y() - 28)
        path.lineTo(center.x() + direction * 13, center.y())
        path.lineTo(center.x() - direction * 16, center.y() + 28)
        painter.setPen(QPen(palette.color("text"), 5.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setOpacity(0.82)
        painter.drawPath(path)
        painter.restore()


class CurrentPage(QFrame):
    changed = Signal(str)
    previous_requested = Signal()
    next_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setProperty("panel", True)
        self.file: TagFile | None = None
        self._preview_chip: TagChip | None = None
        self.last_before_tags: list[str] | None = None
        self.language = "zh"
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        self.title = QLabel("当前文件")
        self.meta = QLabel("未选择文件")
        self.meta.setProperty("muted", True)
        self.format_button = QPushButton("格式化")
        self.apply_text_button = QPushButton("应用到暂存区")
        self.apply_text_button.setProperty("primary", True)
        header.addWidget(self.title)
        header.addWidget(self.meta)
        header.addStretch(1)
        header.addWidget(self.format_button)
        header.addWidget(self.apply_text_button)
        layout.addLayout(header)

        self.splitter = QSplitter(Qt.Horizontal)
        self.image = ImageCanvas()
        image_host = QFrame()
        image_host.setProperty("panel", True)
        image_layout = QVBoxLayout(image_host)
        buttons = QHBoxLayout()
        self.fit_button = QPushButton("适应")
        self.height_button = QPushButton("高度")
        self.original_button = QPushButton("原始")
        buttons.addStretch(1)
        buttons.addWidget(self.fit_button)
        buttons.addWidget(self.height_button)
        buttons.addWidget(self.original_button)
        image_layout.addLayout(buttons)
        image_layout.addWidget(self.image, 1)
        self.splitter.addWidget(image_host)

        editor_host = QFrame()
        editor_host.setProperty("panel", True)
        editor_layout = QVBoxLayout(editor_host)
        mode_row = QHBoxLayout()
        self.tag_mode = QPushButton("标签模式")
        self.text_mode = QPushButton("文本模式")
        for button in [self.tag_mode, self.text_mode]:
            button.setCheckable(True)
            button.setProperty("choiceButton", True)
        self.tag_mode.setChecked(True)
        mode_row.addWidget(self.tag_mode)
        mode_row.addWidget(self.text_mode)
        mode_row.addStretch(1)
        editor_layout.addLayout(mode_row)
        self.stack_host = QWidget(editor_host)
        self.stack = QStackedLayout(self.stack_host)
        self.chip_scroll = QScrollArea()
        self.chip_scroll.setWidgetResizable(True)
        self.chip_box = QWidget()
        self.chip_layout = FlowLayout(self.chip_box, spacing=8)
        self.chip_scroll.setWidget(self.chip_box)
        self.text_editor = QPlainTextEdit()
        self.stack.addWidget(self.chip_scroll)
        self.stack.addWidget(self.text_editor)
        editor_layout.addWidget(self.stack_host, 1)
        self.splitter.addWidget(editor_host)
        self.splitter.setSizes([460, 620])
        layout.addWidget(self.splitter, 1)

        self.tag_mode.clicked.connect(lambda: self._set_editor_mode(0))
        self.text_mode.clicked.connect(lambda: self._set_editor_mode(1))
        self.fit_button.clicked.connect(lambda: self.image.set_mode(0))
        self.height_button.clicked.connect(lambda: self.image.set_mode(1))
        self.original_button.clicked.connect(lambda: self.image.set_mode(2))
        self.image.previous_requested.connect(self.previous_requested.emit)
        self.image.next_requested.connect(self.next_requested.emit)
        self.format_button.clicked.connect(self._format_text)
        self.apply_text_button.clicked.connect(self.apply_text)

    def set_file(self, tag_file: TagFile | None) -> None:
        self.file = tag_file
        self._render()

    def apply_theme(self) -> None:
        self.image.update()
        self.chip_box.update()
        for index in range(self.chip_layout.count()):
            item = self.chip_layout.itemAt(index)
            widget = item.widget() if item else None
            if widget:
                widget.update()

    def apply_language(self, language: str) -> None:
        self.language = language
        if language == "en":
            if not self.file:
                self.title.setText("Current File")
                self.meta.setText("No file selected")
            self.format_button.setText("Format")
            self.apply_text_button.setText("Apply to Buffer")
            self.fit_button.setText("Fit")
            self.height_button.setText("Height")
            self.original_button.setText("Original")
            self.tag_mode.setText("Label Mode")
            self.text_mode.setText("Text Mode")
        else:
            if not self.file:
                self.title.setText("当前文件")
                self.meta.setText("未选择文件")
            self.format_button.setText("格式化")
            self.apply_text_button.setText("应用到暂存区")
            self.fit_button.setText("适应")
            self.height_button.setText("高度")
            self.original_button.setText("原始")
            self.tag_mode.setText("标签模式")
            self.text_mode.setText("文本模式")
        self.image.apply_language(language)
        self._render()

    def _set_editor_mode(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        self.tag_mode.setChecked(index == 0)
        self.text_mode.setChecked(index == 1)

    def apply_pending(self) -> None:
        if self.stack.currentIndex() == 1:
            self.apply_text(silent=True)

    def _render(self) -> None:
        self._clear_chips()
        if not self.file:
            self.title.setText("Current File" if self.language == "en" else "当前文件")
            self.meta.setText("No file selected" if self.language == "en" else "未选择文件")
            self.image.set_image(None)
            self.text_editor.clear()
            return
        self.title.setText(self.file.display_name)
        if self.language == "en":
            self.meta.setText(f"{self.file.tag_count} labels" + (" · Unsaved" if self.file.modified else ""))
        else:
            self.meta.setText(f"{self.file.tag_count} 个标签" + (" · 未保存" if self.file.modified else ""))
        self.image.set_image(self.file.image_path)
        self.text_editor.blockSignals(True)
        self.text_editor.setPlainText(self.file.raw_text)
        self.text_editor.blockSignals(False)
        start_chip = TagChip("+ Start" if self.language == "en" else "+ 开头", add_position="start")
        start_chip.add_requested.connect(self._add_tags)
        start_chip.move_requested.connect(self._move_tag)
        start_chip.drag_preview_requested.connect(self._preview_tag_move)
        start_chip.drag_preview_cleared.connect(self._clear_tag_move_preview)
        self.chip_layout.addWidget(start_chip)
        for tag in self.file.tags:
            chip = TagChip(tag)
            chip.removed.connect(self._remove_tag)
            chip.renamed.connect(self._rename_tag)
            chip.move_requested.connect(self._move_tag)
            chip.drag_preview_requested.connect(self._preview_tag_move)
            chip.drag_preview_cleared.connect(self._clear_tag_move_preview)
            self.chip_layout.addWidget(chip)
        end_chip = TagChip("+ End" if self.language == "en" else "+ 末尾", add_position="end")
        end_chip.add_requested.connect(self._add_tags)
        end_chip.move_requested.connect(self._move_tag)
        end_chip.drag_preview_requested.connect(self._preview_tag_move)
        end_chip.drag_preview_cleared.connect(self._clear_tag_move_preview)
        self.chip_layout.addWidget(end_chip)

    def _clear_chips(self) -> None:
        self._preview_chip = None
        while self.chip_layout.count():
            item = self.chip_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _remove_tag(self, tag: str) -> None:
        if not self.file:
            return
        self.last_before_tags = list(self.file.tags)
        self.file.tags = [item for item in self.file.tags if item != tag]
        self._mark("删除当前标签")

    def _rename_tag(self, old: str, new: str) -> None:
        if not self.file:
            return
        self.last_before_tags = list(self.file.tags)
        self.file.tags = replace_tags(self.file.tags, old, new)
        self._mark("修改当前标签")

    def _add_tags(self, position: str, text: str) -> None:
        if not self.file:
            return
        tags = parse_tags(text)
        if not tags:
            return
        self.last_before_tags = list(self.file.tags)
        self.file.tags = add_tags(self.file.tags, tags, position, skip_existing=True)
        self._mark("新增当前标签")

    def _move_tag(self, source: str, target: str, side: str) -> None:
        if not self.file or source not in self.file.tags:
            return
        self.last_before_tags = list(self.file.tags)
        tags = list(self.file.tags)
        moved = tags.pop(tags.index(source))
        if target == "__start__":
            index = 0
        elif target == "__end__":
            index = len(tags)
        else:
            if target not in tags:
                return
            index = tags.index(target)
            if side == "after":
                index += 1
        tags.insert(index, moved)
        if tags != self.file.tags:
            self.file.tags = tags
            self._mark("调整标签顺序")

    def _preview_tag_move(self, source: str, target: str, side: str) -> None:
        del source
        self._clear_tag_move_preview()
        for index in range(self.chip_layout.count()):
            item = self.chip_layout.itemAt(index)
            widget = item.widget() if item else None
            if isinstance(widget, TagChip):
                is_target = widget.tag == target or (target == "__start__" and widget.add_position == "start") or (target == "__end__" and widget.add_position == "end")
                if is_target:
                    widget.set_drop_preview(side)
                    self._preview_chip = widget
                    return

    def _clear_tag_move_preview(self) -> None:
        if self._preview_chip is not None:
            self._preview_chip.set_drop_preview(None)
            self._preview_chip = None

    def _format_text(self) -> None:
        self.text_editor.setPlainText(format_tags(parse_tags(self.text_editor.toPlainText())))

    def apply_text(self, silent: bool = False) -> None:
        if not self.file:
            return
        self.last_before_tags = list(self.file.tags)
        text = self.text_editor.toPlainText()
        self.file.raw_text = text
        self.file.tags = parse_tags(text)
        self.file.modified = self.file.raw_text != self.file.original_text or self.file.tags != self.file.original_tags
        self._render()
        if not silent:
            self.changed.emit("应用文本修改")

    def _mark(self, message: str) -> None:
        if not self.file:
            return
        self.file.raw_text = format_tags(self.file.tags)
        self.file.modified = self.file.raw_text != self.file.original_text or self.file.tags != self.file.original_tags
        self._render()
        self.changed.emit(message)
