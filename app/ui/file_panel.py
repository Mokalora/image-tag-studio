from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QAbstractListModel, QModelIndex, QPoint, QPointF, QRect, QRectF, QSize, QTimer, Qt, Signal
from PySide6.QtGui import QFontMetrics, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QAbstractItemView, QFrame, QHBoxLayout, QLabel, QListView, QPushButton, QSizePolicy, QStackedLayout, QStyledItemDelegate, QVBoxLayout, QWidget

from app.models import TagFile
from app.thumbs import ThumbnailService
from app.ui import palette


def draw_close_badge(painter: QPainter, close_rect: QRect, active: bool = False) -> None:
    badge_rect = QRectF(close_rect).adjusted(0.5, 0.5, -0.5, -0.5)
    painter.setBrush(palette.color("accent") if active else palette.color("card_hover"))
    painter.setPen(QPen(palette.color("accent"), 1.2))
    painter.drawEllipse(badge_rect)
    center = badge_rect.center()
    span = 4.2
    painter.setPen(QPen(palette.color("text"), 1.5, Qt.SolidLine, Qt.RoundCap))
    painter.drawLine(QPointF(center.x() - span, center.y() - span), QPointF(center.x() + span, center.y() + span))
    painter.drawLine(QPointF(center.x() + span, center.y() - span), QPointF(center.x() - span, center.y() + span))


class FileModel(QAbstractListModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.files: list[TagFile] = []

    def set_files(self, files: list[TagFile]) -> None:
        self.beginResetModel()
        self.files = list(files)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.files)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self.files):
            return None
        item = self.files[index.row()]
        if role == Qt.DisplayRole:
            return item.display_name
        if role == Qt.UserRole:
            return item
        if role == Qt.UserRole + 1:
            return item.path
        return None


class ListDelegate(QStyledItemDelegate):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.language = "zh"
        self.hovered_row = -1
        self.active_row = -1

    def set_language(self, language: str) -> None:
        self.language = language

    def paint(self, painter: QPainter, option, index) -> None:  # noqa: N802
        item: TagFile = index.data(Qt.UserRole)
        painter.save()
        rect = option.rect.adjusted(4, 3, -4, -3)
        selected = bool(option.state & option.state.State_Selected)
        hovered = index.row() == self.hovered_row
        active = selected or index.row() == self.active_row
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(palette.color("card_hover" if selected or hovered else "card"))
        painter.setPen(QPen(palette.color("accent" if selected or hovered else "border"), 1.6 if active else 1.1))
        painter.drawRoundedRect(rect, 8, 8)
        if item.modified:
            painter.setBrush(palette.color("accent"))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(rect.left() + 10, rect.center().y() - 4, 8, 8)
        x = rect.left() + 24
        painter.setPen(palette.color("text"))
        painter.drawText(QRect(x, rect.top() + 5, rect.width() - 90, 18), Qt.AlignVCenter, item.display_name)
        painter.setPen(palette.color("muted"))
        meta = f"{item.tag_count} labels" if self.language == "en" else f"{item.tag_count} 标签"
        if item.image_path:
            meta += " · Preview" if self.language == "en" else " · 有预览"
        if item.error:
            meta += " · Error" if self.language == "en" else " · 异常"
        painter.drawText(QRect(x, rect.top() + 24, rect.width() - 30, 18), Qt.AlignVCenter, meta)
        if index.row() in {self.hovered_row, self.active_row}:
            close_rect = QRect(rect.right() - 30, rect.center().y() - 9, 18, 18)
            draw_close_badge(painter, close_rect, index.row() == self.active_row)
        painter.restore()

    def sizeHint(self, option, index) -> QSize:  # noqa: N802
        return QSize(220, 54)


class GridDelegate(QStyledItemDelegate):
    CARD_WIDTH = 156
    CARD_HEIGHT = 210

    def __init__(self, thumbs: ThumbnailService, parent=None) -> None:
        super().__init__(parent)
        self.thumbs = thumbs
        self.language = "zh"
        self.hovered_row = -1
        self.active_row = -1

    def set_language(self, language: str) -> None:
        self.language = language

    def paint(self, painter: QPainter, option, index) -> None:  # noqa: N802
        item: TagFile = index.data(Qt.UserRole)
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        rect = option.rect.adjusted(5, 5, -5, -5)
        selected = bool(option.state & option.state.State_Selected)
        hovered = index.row() == self.hovered_row
        active = selected or index.row() == self.active_row
        painter.setBrush(palette.color("card_hover" if selected or hovered else "card"))
        painter.setPen(QPen(palette.color("accent" if selected or hovered else "border"), 1.8 if active else 1.1))
        painter.drawRoundedRect(rect, 12, 12)
        image_rect = QRect(rect.left() + 10, rect.top() + 10, rect.width() - 20, rect.height() - 66)
        image = self.thumbs.image(item.path)
        if item.image_path is None:
            painter.fillRect(image_rect, palette.color("image_bg"))
            painter.setPen(palette.color("muted"))
            painter.drawText(image_rect, Qt.AlignCenter, "No image" if self.language == "en" else "没有图像")
        elif image.isNull():
            self.thumbs.request(item.path, front=True)
            painter.fillRect(image_rect, palette.color("image_bg"))
            painter.setPen(palette.color("muted"))
            painter.drawText(image_rect, Qt.AlignCenter, "Loading" if self.language == "en" else "加载中")
        else:
            pixmap = QPixmap.fromImage(image).scaled(image_rect.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            x = image_rect.x() + (image_rect.width() - pixmap.width()) // 2
            y = image_rect.y() + (image_rect.height() - pixmap.height()) // 2
            painter.drawPixmap(x, y, pixmap)
        painter.setPen(palette.color("text"))
        title = painter.fontMetrics().elidedText(item.display_name, Qt.ElideRight, rect.width() - 20)
        painter.drawText(QRect(rect.left() + 10, rect.bottom() - 46, rect.width() - 20, 20), Qt.AlignVCenter, title)
        painter.setPen(palette.color("muted"))
        meta = f"{item.tag_count} labels" if self.language == "en" else f"{item.tag_count} 标签"
        painter.drawText(QRect(rect.left() + 10, rect.bottom() - 25, rect.width() - 20, 18), Qt.AlignVCenter, meta)
        if item.modified:
            painter.setBrush(palette.color("accent"))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(rect.right() - 20, rect.top() + 12, 9, 9)
        if index.row() in {self.hovered_row, self.active_row}:
            close_rect = QRect(rect.right() - 28, rect.top() + 10, 18, 18)
            draw_close_badge(painter, close_rect, index.row() == self.active_row)
        painter.restore()

    def sizeHint(self, option, index) -> QSize:  # noqa: N802
        return QSize(self.CARD_WIDTH, self.CARD_HEIGHT)


class FilePanel(QFrame):
    file_selected = Signal(object)
    file_activated = Signal(object)
    delete_requested = Signal(object)

    def __init__(self, thumbs: ThumbnailService, parent=None) -> None:
        super().__init__(parent)
        self.setProperty("panel", True)
        self.setMinimumWidth(240)
        self.thumbs = thumbs
        self.files: list[TagFile] = []
        self.current_path: Path | None = None
        self.hovered_path: Path | None = None
        self.active_delete_path: Path | None = None
        self.language = "zh"
        self._filter_summary_text = "筛选：全部"
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        header = QHBoxLayout()
        self.title = QLabel("文件")
        self.count = QLabel("0")
        self.count.setProperty("muted", True)
        self.list_button = QPushButton("列表")
        self.grid_button = QPushButton("缩略图")
        for button in [self.list_button, self.grid_button]:
            button.setCheckable(True)
            button.setProperty("choiceButton", True)
        self.filter_label = QLabel("筛选：全部")
        self.filter_label.setProperty("muted", True)
        self.filter_label.setMinimumWidth(120)
        self.filter_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.filter_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        header.addWidget(self.title)
        header.addWidget(self.count)
        header.addWidget(self.filter_label, 1)
        header.addWidget(self.list_button)
        header.addWidget(self.grid_button)
        layout.addLayout(header)

        self.model = FileModel(self)
        self.list_view = QListView()
        self.list_view.setModel(self.model)
        self.list_delegate = ListDelegate(self.list_view)
        self.list_view.setItemDelegate(self.list_delegate)
        self.list_view.setSelectionMode(QListView.ExtendedSelection)
        self.list_view.setMouseTracking(True)
        self.list_view.setUniformItemSizes(True)
        self.list_view.setVerticalScrollMode(QListView.ScrollPerPixel)

        self.grid_view = QListView()
        self.grid_view.setModel(self.model)
        self.grid_delegate = GridDelegate(thumbs, self.grid_view)
        self.grid_view.setItemDelegate(self.grid_delegate)
        self.grid_view.setViewMode(QListView.IconMode)
        self.grid_view.setFlow(QListView.LeftToRight)
        self.grid_view.setResizeMode(QListView.Adjust)
        self.grid_view.setMovement(QListView.Static)
        self.grid_view.setWrapping(True)
        self.grid_view.setSpacing(8)
        self.grid_view.setUniformItemSizes(True)
        self.grid_view.setMouseTracking(True)
        self.grid_view.setVerticalScrollMode(QListView.ScrollPerPixel)
        self.grid_view.setGridSize(QSize(GridDelegate.CARD_WIDTH + 12, GridDelegate.CARD_HEIGHT + 12))

        self.stack_host = QWidget(self)
        self.stack = QStackedLayout(self.stack_host)
        self.stack.addWidget(self.list_view)
        self.stack.addWidget(self.grid_view)
        layout.addWidget(self.stack_host, 1)

        self.list_button.clicked.connect(lambda: self.set_mode("list"))
        self.grid_button.clicked.connect(lambda: self.set_mode("grid"))
        self.list_view.selectionModel().currentChanged.connect(self._emit_selected)
        self.grid_view.selectionModel().currentChanged.connect(self._emit_selected)
        self.list_view.doubleClicked.connect(lambda index: self.file_activated.emit(index.data(Qt.UserRole + 1)))
        self.grid_view.doubleClicked.connect(lambda index: self.file_activated.emit(index.data(Qt.UserRole + 1)))
        self.list_view.viewport().installEventFilter(self)
        self.grid_view.viewport().installEventFilter(self)
        self.list_view.installEventFilter(self)
        self.grid_view.installEventFilter(self)
        self.thumbs.ready.connect(lambda _: self.grid_view.viewport().update())
        self.set_mode("grid")

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._sync_filter_width()
        self._sync_grid_metrics()

    def set_files(self, files: list[TagFile], current_path: Path | None) -> None:
        view = self.grid_view if self.stack.currentIndex() == 1 else self.list_view
        scroll_value = view.verticalScrollBar().value()
        anchor_index = view.indexAt(QPoint(8, 8))
        anchor_path = anchor_index.data(Qt.UserRole + 1) if anchor_index.isValid() else current_path
        self.files = list(files)
        self.current_path = current_path
        self.count.setText(str(len(files)))
        self.model.set_files(files)
        self.thumbs.set_items({item.path: item.image_path for item in files})
        self.thumbs.warmup([item.path for item in files])
        self._sync_grid_metrics()
        self._sync_current()
        self._restore_view_state(view, anchor_path, scroll_value)

    def apply_language(self, language: str) -> None:
        self.language = language
        self.list_delegate.set_language(language)
        self.grid_delegate.set_language(language)
        if language == "en":
            self.title.setText("Files")
            self.list_button.setText("List")
            self.grid_button.setText("Grid")
            if self.filter_label.text().startswith("筛选：全部"):
                self.set_filter_summary("Filter: All")
        else:
            self.title.setText("文件")
            self.list_button.setText("列表")
            self.grid_button.setText("缩略图")
            if self.filter_label.text().startswith("Filter: All"):
                self.set_filter_summary("筛选：全部")
        self.list_view.viewport().update()
        self.grid_view.viewport().update()

    def apply_theme(self) -> None:
        self.list_view.viewport().update()
        self.grid_view.viewport().update()

    def set_mode(self, mode: str) -> None:
        is_grid = mode == "grid"
        self.stack.setCurrentIndex(1 if is_grid else 0)
        self.grid_button.setChecked(is_grid)
        self.list_button.setChecked(not is_grid)
        self._sync_grid_metrics()
        self._sync_current()

    def set_filter_summary(self, text: str) -> None:
        self._filter_summary_text = text
        self._sync_filter_width()

    def _sync_filter_width(self) -> None:
        metrics = QFontMetrics(self.filter_label.font())
        width = max(120, self.filter_label.width())
        self.filter_label.setText(metrics.elidedText(self._filter_summary_text, Qt.ElideRight, width))
        self.filter_label.setToolTip(self._filter_summary_text)

    def _sync_grid_metrics(self) -> None:
        spacing = self.grid_view.spacing()
        min_cell = GridDelegate.CARD_WIDTH + spacing + 4
        self.grid_view.setGridSize(QSize(min_cell, GridDelegate.CARD_HEIGHT + spacing + 4))
        self.grid_view.scheduleDelayedItemsLayout()
        self.grid_view.doItemsLayout()
        self.grid_view.viewport().update()

    def stabilize_grid_layout(self) -> None:
        for delay in (0, 60, 160, 360):
            QTimer.singleShot(delay, self._sync_grid_metrics)

    def selected_files(self) -> list[TagFile]:
        view = self.grid_view if self.stack.currentIndex() == 1 else self.list_view
        return [index.data(Qt.UserRole) for index in view.selectedIndexes()]

    def eventFilter(self, watched, event) -> bool:
        view = self._view_for_viewport(watched)
        if view is None:
            return super().eventFilter(watched, event)
        if event.type() == event.Type.MouseMove:
            self._update_hover(view, event.position().toPoint())
        elif event.type() == event.Type.Leave:
            self._clear_hover()
        elif event.type() == event.Type.MouseButtonPress and event.button() == Qt.LeftButton:
            index = view.indexAt(event.position().toPoint())
            if index.isValid() and self._delete_rect(view, index).contains(event.position().toPoint()):
                item: TagFile = index.data(Qt.UserRole)
                self.active_delete_path = item.path
                view.setCurrentIndex(index)
                self._sync_delegate_state()
                event.accept()
                return True
        elif event.type() == event.Type.MouseButtonRelease and event.button() == Qt.LeftButton:
            index = view.indexAt(event.position().toPoint())
            if index.isValid() and self.active_delete_path == index.data(Qt.UserRole + 1) and self._delete_rect(view, index).contains(event.position().toPoint()):
                self.delete_requested.emit(self.active_delete_path)
                self.active_delete_path = None
                self._sync_delegate_state()
                event.accept()
                return True
            self.active_delete_path = None
            self._sync_delegate_state()
        elif event.type() == event.Type.KeyPress and event.key() in {Qt.Key_Delete, Qt.Key_Backspace}:
            index = view.currentIndex()
            if index.isValid():
                self.delete_requested.emit(index.data(Qt.UserRole + 1))
                event.accept()
                return True
        return super().eventFilter(watched, event)

    def _view_for_viewport(self, viewport) -> QListView | None:
        if viewport is self.list_view.viewport() or viewport is self.list_view:
            return self.list_view
        if viewport is self.grid_view.viewport() or viewport is self.grid_view:
            return self.grid_view
        return None

    def _update_hover(self, view: QListView, point: QPoint) -> None:
        index = view.indexAt(point)
        self.hovered_path = index.data(Qt.UserRole + 1) if index.isValid() else None
        self._sync_delegate_state()

    def _clear_hover(self) -> None:
        self.hovered_path = None
        self._sync_delegate_state()

    def _sync_delegate_state(self) -> None:
        hovered_row = -1
        active_row = -1
        for row, item in enumerate(self.files):
            if item.path == self.hovered_path:
                hovered_row = row
            if item.path == self.active_delete_path:
                active_row = row
        self.list_delegate.hovered_row = hovered_row
        self.list_delegate.active_row = active_row
        self.grid_delegate.hovered_row = hovered_row
        self.grid_delegate.active_row = active_row
        self.list_view.viewport().update()
        self.grid_view.viewport().update()

    def _delete_rect(self, view: QListView, index: QModelIndex) -> QRect:
        rect = view.visualRect(index).adjusted(5, 5, -5, -5)
        if view is self.list_view:
            return QRect(rect.right() - 30, rect.center().y() - 9, 18, 18)
        return QRect(rect.right() - 28, rect.top() + 10, 18, 18)

    def _sync_current(self) -> None:
        if not self.current_path:
            return
        for row, item in enumerate(self.files):
            if item.path == self.current_path:
                index = self.model.index(row, 0)
                self.list_view.setCurrentIndex(index)
                self.grid_view.setCurrentIndex(index)
                return

    def _emit_selected(self, current, previous=None) -> None:
        del previous
        if current.isValid():
            self.file_selected.emit(current.data(Qt.UserRole + 1))

    def _restore_view_state(self, view: QListView, anchor_path: Path | None, scroll_value: int) -> None:
        def _apply() -> None:
            if anchor_path is not None:
                for row, item in enumerate(self.files):
                    if item.path == anchor_path:
                        view.scrollTo(self.model.index(row, 0), QAbstractItemView.PositionAtTop)
                        break
            view.verticalScrollBar().setValue(min(scroll_value, view.verticalScrollBar().maximum()))

        QTimer.singleShot(0, _apply)
