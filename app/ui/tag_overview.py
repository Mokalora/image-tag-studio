from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QStackedLayout,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from app.models import TagStat
from app.ui import palette
from app.ui.completion import TabCompleteLineEdit
from app.ui.flow_layout import FlowLayout


class TagCloudButton(QPushButton):
    tag_toggled = Signal(str, bool)

    def __init__(self, stat: TagStat, parent=None) -> None:
        super().__init__(f"{stat.tag}  {stat.count}", parent)
        self.tag = stat.key or stat.tag
        self.virtual = stat.virtual
        self.setCheckable(True)
        self.apply_theme()
        self.toggled.connect(lambda checked: self.tag_toggled.emit(self.tag, checked))

    def apply_theme(self) -> None:
        bg = palette.value("card")
        hover = palette.value("card_hover")
        border = palette.value("border")
        checked = palette.value("accent")
        if self.virtual:
            bg = "#2B2227" if palette.theme() == "dark" else "#FFF0E8"
            hover = "#3A2930" if palette.theme() == "dark" else "#FFE3D2"
            border = "#D17A42"
            checked = "#D17A42"
        self.setStyleSheet(
            f"""
            QPushButton {{
                background: {bg};
                color: {palette.value("text")};
                border: 1px solid {border};
                border-radius: 15px;
                padding: 7px 11px;
            }}
            QPushButton:hover {{
                background: {hover};
                border-color: {checked};
                padding: 7px 11px;
                border-radius: 15px;
            }}
            QPushButton:checked {{
                background: {checked};
                border-color: {checked};
                color: #FFFFFF;
            }}
            """
        )


class TagTableModel(QAbstractTableModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.rows: list[TagStat] = []
        self.selected: set[str] = set()
        self.language = "zh"

    def set_rows(self, rows: list[TagStat], selected: set[str] | None = None) -> None:
        self.beginResetModel()
        self.rows = list(rows)
        self.selected = set(selected or set())
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        return 3

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self.rows[index.row()]
        if role == Qt.DisplayRole:
            return [row.tag, row.count, row.file_count][index.column()]
        if role == Qt.ToolTipRole:
            if self.language == "en":
                return f"{row.tag}\nCount: {row.count}\nFiles: {row.file_count}"
            return f"{row.tag}\n次数：{row.count}\n文件数：{row.file_count}"
        key = row.key or row.tag
        if role == Qt.BackgroundRole and key in self.selected:
            return palette.color("accent_soft")
        if role == Qt.ForegroundRole and key in self.selected:
            return QColor("#FFFFFF") if palette.theme() == "dark" else palette.color("text")
        if role == Qt.ForegroundRole and row.virtual:
            return QColor("#F09A5D")
        return None

    def headerData(self, section: int, orientation, role=Qt.DisplayRole):  # noqa: N802
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return (["Label", "Count", "Files"] if self.language == "en" else ["标签", "次数", "文件数"])[section]
        return None

    def set_language(self, language: str) -> None:
        self.language = language
        self.headerDataChanged.emit(Qt.Horizontal, 0, 2)


class TagOverview(QFrame):
    filter_changed = Signal(list, str, str)
    rows_refresh_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setProperty("panel", True)
        self.language = "zh"
        self.theme = "dark"
        self.all_rows: list[TagStat] = []
        self.visible_rows: list[TagStat] = []
        self.selected: set[str] = set()
        self._mode = "or"
        self._display_mode = "positive"

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        top_card = QFrame()
        top_card.setProperty("section", True)
        top = QHBoxLayout(top_card)
        top.setContentsMargins(12, 10, 12, 10)
        self.title = QLabel("标签总览")
        self.title.setStyleSheet("font-size: 18px; font-weight: 600;")
        top.addWidget(self.title)

        self.search = TabCompleteLineEdit()
        self.search.setPlaceholderText("搜索标签")
        top.addWidget(self.search, 1)

        self.view_label = QLabel("视图")
        top.addWidget(self.view_label)

        self.cloud_button = QPushButton("云图")
        self.table_button = QPushButton("表格")
        self.view_group = QButtonGroup(self)
        self.view_group.setExclusive(True)
        for index, button in enumerate([self.cloud_button, self.table_button]):
            button.setCheckable(True)
            button.setProperty("choiceButton", True)
            self.view_group.addButton(button, index)
            top.addWidget(button)
        self.cloud_button.setChecked(True)
        layout.addWidget(top_card)

        slider_card = QFrame()
        slider_card.setProperty("section", True)
        slider_row = QHBoxLayout(slider_card)
        slider_row.setContentsMargins(12, 10, 12, 10)
        self.top_slider = QSlider(Qt.Horizontal)
        self.top_slider.setRange(1, 1000)
        self.top_slider.setValue(64)
        self.min_slider = QSlider(Qt.Horizontal)
        self.min_slider.setRange(1, 100)
        self.min_slider.setValue(4)
        self.top_label = QLabel("显示上限 64")
        self.min_label = QLabel("最小次数 4")
        slider_row.addWidget(self.top_label)
        slider_row.addWidget(self.top_slider, 1)
        slider_row.addWidget(self.min_label)
        slider_row.addWidget(self.min_slider, 1)
        layout.addWidget(slider_card)

        action_card = QFrame()
        action_card.setProperty("section", True)
        action_row = QHBoxLayout(action_card)
        action_row.setContentsMargins(12, 10, 12, 10)

        self.selected_label = QLabel("当前筛选：全部")
        self.selected_label.setProperty("muted", True)
        action_row.addWidget(self.selected_label, 1)

        self.sort_label = QLabel("排序")
        action_row.addWidget(self.sort_label)

        self.sort_group = QButtonGroup(self)
        self.sort_group.setExclusive(True)
        self.sort_count_button = QPushButton("按频次")
        self.sort_alpha_button = QPushButton("A-Z")
        for index, button in enumerate([self.sort_count_button, self.sort_alpha_button]):
            button.setCheckable(True)
            button.setProperty("choiceButton", True)
            self.sort_group.addButton(button, index)
            action_row.addWidget(button)
        self.sort_count_button.setChecked(True)

        action_row.addSpacing(10)
        self.relation_label = QLabel("筛选关系")
        action_row.addWidget(self.relation_label)

        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.or_button = QPushButton("或")
        self.and_button = QPushButton("与")
        for index, button in enumerate([self.or_button, self.and_button]):
            button.setCheckable(True)
            button.setProperty("choiceButton", True)
            self.mode_group.addButton(button, index)
            action_row.addWidget(button)
        self.or_button.setChecked(True)

        action_row.addSpacing(10)
        self.display_label = QLabel("显示关系")
        action_row.addWidget(self.display_label)

        self.display_group = QButtonGroup(self)
        self.display_group.setExclusive(True)
        self.positive_button = QPushButton("正")
        self.negative_button = QPushButton("反")
        for index, button in enumerate([self.positive_button, self.negative_button]):
            button.setCheckable(True)
            button.setProperty("choiceButton", True)
            self.display_group.addButton(button, index)
            action_row.addWidget(button)
        self.positive_button.setChecked(True)

        action_row.addSpacing(10)
        self.invert_button = QPushButton("反选")
        self.clear_button = QPushButton("清空")
        self.clear_button.setProperty("primary", True)
        action_row.addWidget(self.invert_button)
        action_row.addWidget(self.clear_button)
        layout.addWidget(action_card)

        self.stack_host = QWidget(self)
        self.stack = QStackedLayout(self.stack_host)

        self.cloud_area = QScrollArea()
        self.cloud_area.setWidgetResizable(True)
        self.cloud_widget = QWidget()
        self.cloud_layout = FlowLayout(self.cloud_widget, spacing=8)
        self.cloud_area.setWidget(self.cloud_widget)

        self.table = QTableView()
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table_model = TagTableModel(self.table)
        self.table.setModel(self.table_model)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(False)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.setWordWrap(False)

        self.stack.addWidget(self.cloud_area)
        self.stack.addWidget(self.table)
        layout.addWidget(self.stack_host, 1)

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(90)
        self.timer.timeout.connect(self.rows_refresh_requested.emit)

        self.search.textChanged.connect(lambda _: self.timer.start())
        self.top_slider.valueChanged.connect(self._slider_changed)
        self.min_slider.valueChanged.connect(self._slider_changed)
        self.view_group.idClicked.connect(self._set_view)
        self.sort_group.idClicked.connect(lambda _: self._render())
        self.mode_group.idClicked.connect(self._set_mode)
        self.display_group.idClicked.connect(self._set_display_mode)
        self.table.clicked.connect(self._toggle_table_row)
        self.invert_button.clicked.connect(self._invert_visible)
        self.clear_button.clicked.connect(self._clear)

    def set_rows(self, rows: list[TagStat]) -> None:
        self.all_rows = list(rows)
        self.search.set_suggestions(sorted(row.tag for row in rows))
        max_count = max((row.count for row in rows), default=1)
        self.min_slider.blockSignals(True)
        self.min_slider.setRange(1, max(1, max_count))
        self.min_slider.setValue(min(self.min_slider.value(), max_count))
        self.min_slider.blockSignals(False)
        self._render()

    def filtered_rows(self) -> list[TagStat]:
        keyword = self.search.text().strip().casefold()
        min_count = self.min_slider.value()
        rows = [row for row in self.all_rows if row.count >= min_count and (not keyword or keyword in row.tag.casefold())]
        rows.sort(key=lambda row: (-row.count, row.tag.casefold()))
        limited = rows[: self.top_slider.value()]
        if self.sort_group.checkedId() == 1:
            limited.sort(key=lambda row: row.tag.casefold())
        return limited

    def _render(self) -> None:
        self.visible_rows = self.filtered_rows()
        self.table_model.set_rows(self.visible_rows, self.selected)
        while self.cloud_layout.count():
            item = self.cloud_layout.takeAt(0)
            widget = item.widget() if item else None
            if widget:
                widget.deleteLater()
        for row in self.visible_rows:
            chip = TagCloudButton(row)
            chip.blockSignals(True)
            chip.setChecked((row.key or row.tag) in self.selected)
            chip.blockSignals(False)
            chip.tag_toggled.connect(self._toggle_tag)
            self.cloud_layout.addWidget(chip)
        self._update_label()

    def apply_theme(self) -> None:
        self.table.viewport().update()
        self.table.horizontalHeader().viewport().update()
        for index in range(self.cloud_layout.count()):
            item = self.cloud_layout.itemAt(index)
            widget = item.widget() if item else None
            if isinstance(widget, TagCloudButton):
                widget.apply_theme()

    def _slider_changed(self) -> None:
        self._update_slider_labels()
        self.selected.clear()
        self._emit_filter()
        self.timer.start()

    def _update_slider_labels(self) -> None:
        if self.language == "en":
            self.top_label.setText(f"Show limit {self.top_slider.value()}")
            self.min_label.setText(f"Min count {self.min_slider.value()}")
        else:
            self.top_label.setText(f"显示上限 {self.top_slider.value()}")
            self.min_label.setText(f"最小次数 {self.min_slider.value()}")

    def _set_mode(self, index: int) -> None:
        self._mode = "and" if index == 1 else "or"
        self._emit_filter()

    def _set_display_mode(self, index: int) -> None:
        self._display_mode = "negative" if index == 1 else "positive"
        self._emit_filter()

    def _set_view(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        self.cloud_button.setChecked(index == 0)
        self.table_button.setChecked(index == 1)

    def _toggle_tag(self, tag: str, checked: bool) -> None:
        self.selected.add(tag) if checked else self.selected.discard(tag)
        self.table_model.set_rows(self.visible_rows, self.selected)
        self._emit_filter()

    def _toggle_table_row(self, index: QModelIndex) -> None:
        if not index.isValid() or index.row() >= len(self.visible_rows):
            return
        row = self.visible_rows[index.row()]
        tag = row.key or row.tag
        if tag in self.selected:
            self.selected.remove(tag)
        else:
            self.selected.add(tag)
        self._render()
        self.table.clearSelection()
        self._emit_filter()

    def _invert_visible(self) -> None:
        visible = {row.key or row.tag for row in self.visible_rows}
        self.selected = (self.selected - visible) | (visible - self.selected)
        self._render()
        self._emit_filter()

    def _clear(self) -> None:
        self.selected.clear()
        self._render()
        self._emit_filter()

    def _emit_filter(self) -> None:
        self._update_label()
        self.filter_changed.emit(sorted(self.selected), self._mode, self._display_mode)

    def _update_label(self) -> None:
        if not self.selected:
            self.selected_label.setText("Current filter: All" if self.language == "en" else "当前筛选：全部")
            self.selected_label.setToolTip("")
            return
        tags = sorted(self.selected)
        relation = ("AND" if self._mode == "and" else "OR") if self.language == "en" else ("与" if self._mode == "and" else "或")
        display = ("Show" if self._display_mode == "positive" else "Hide") if self.language == "en" else ("正" if self._display_mode == "positive" else "反")
        shown = ", ".join(tags[:5]) if self.language == "en" else "，".join(tags[:5])
        suffix = "" if len(tags) <= 5 else (f" and {len(tags)} total" if self.language == "en" else f" 等 {len(tags)} 个")
        text = f"Current filter: {relation}/{display} · {shown}{suffix}" if self.language == "en" else f"当前筛选：{relation}/{display} · {shown}{suffix}"
        tooltip = f"Current filter: {relation}/{display} · {', '.join(tags)}" if self.language == "en" else f"当前筛选：{relation}/{display} · {'，'.join(tags)}"
        self.selected_label.setText(text)
        self.selected_label.setToolTip(tooltip)

    def apply_language(self, language: str) -> None:
        self.language = language
        self.table_model.set_language(language)
        if language == "en":
            self.title.setText("Label Overview")
            self.search.setPlaceholderText("Search labels")
            self.view_label.setText("View")
            self.cloud_button.setText("Cloud")
            self.table_button.setText("Table")
            self.sort_label.setText("Sort")
            self.sort_count_button.setText("By Count")
            self.sort_alpha_button.setText("A-Z")
            self.relation_label.setText("Relation")
            self.or_button.setText("OR")
            self.and_button.setText("AND")
            self.display_label.setText("Display")
            self.positive_button.setText("Show")
            self.negative_button.setText("Hide")
            self.invert_button.setText("Invert")
            self.clear_button.setText("Clear")
        else:
            self.title.setText("标签总览")
            self.search.setPlaceholderText("搜索标签")
            self.view_label.setText("视图")
            self.cloud_button.setText("云图")
            self.table_button.setText("表格")
            self.sort_label.setText("排序")
            self.sort_count_button.setText("按频次")
            self.sort_alpha_button.setText("A-Z")
            self.relation_label.setText("筛选关系")
            self.or_button.setText("或")
            self.and_button.setText("与")
            self.display_label.setText("显示关系")
            self.positive_button.setText("正")
            self.negative_button.setText("反")
            self.invert_button.setText("反选")
            self.clear_button.setText("清空")
        self._update_slider_labels()
        self._update_label()
