from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QButtonGroup, QCheckBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QStackedWidget, QVBoxLayout, QWidget

from app.ui.completion import TabCompleteLineEdit


class ChoiceBar(QFrame):
    def __init__(self, labels: list[str], parent=None, compact: bool = False) -> None:
        super().__init__(parent)
        self.setProperty("choiceBar", True)
        self.setProperty("compact", compact)
        self._buttons: list[QPushButton] = []
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        for index, label in enumerate(labels):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setProperty("choiceButton", True)
            if compact:
                button.setFixedWidth(max(64, button.fontMetrics().horizontalAdvance(label) + 30))
            self._group.addButton(button, index)
            self._buttons.append(button)
            layout.addWidget(button)
        if self._buttons:
            self._buttons[0].setChecked(True)

    def set_labels(self, labels: list[str]) -> None:
        for button, label in zip(self._buttons, labels):
            button.setText(label)
            if self.property("compact"):
                button.setFixedWidth(max(64, button.fontMetrics().horizontalAdvance(label) + 30))

    def currentIndex(self) -> int:  # noqa: N802
        return max(0, self._group.checkedId())

    def setCurrentIndex(self, index: int) -> None:  # noqa: N802
        if 0 <= index < len(self._buttons):
            self._buttons[index].setChecked(True)


class BatchPage(QFrame):
    apply_requested = Signal(str)
    batch_inputs_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setProperty("panel", True)
        self.language = "zh"
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        self.title = QLabel("批量修改")
        self.title.setStyleSheet("font-size: 18px; font-weight: 600;")
        self.operation_switch = ChoiceBar(["添加", "删除", "替换", "格式化"])
        header.addWidget(self.title)
        header.addSpacing(12)
        header.addWidget(self.operation_switch)
        header.addStretch(1)
        layout.addLayout(header)

        scope_card = QFrame()
        scope_card.setProperty("section", True)
        scope_layout = QGridLayout(scope_card)
        scope_layout.setContentsMargins(12, 10, 12, 10)
        scope_layout.setHorizontalSpacing(10)
        self.scope = ChoiceBar(["全部文件", "左侧选中", "当前搜索", "包含标签"])
        self.scope_tag = TabCompleteLineEdit()
        self.scope_tag.setPlaceholderText("范围为“包含标签”时输入目标标签")
        self.scope_tag_hint = QLabel("未输入")
        self.scope_tag_hint.setProperty("muted", True)
        self.scope_label = QLabel("作用范围")
        scope_layout.addWidget(self.scope_label, 0, 0)
        scope_layout.addWidget(self.scope, 0, 1)
        scope_layout.addWidget(self.scope_tag, 0, 2)
        scope_layout.addWidget(self.scope_tag_hint, 0, 3)
        scope_layout.setColumnStretch(2, 1)
        layout.addWidget(scope_card)

        self.stack = QStackedWidget(self)
        self.stack.addWidget(self._build_add_page())
        self.stack.addWidget(self._build_delete_page())
        self.stack.addWidget(self._build_replace_page())
        self.stack.addWidget(self._build_format_page())
        layout.addWidget(self.stack)
        layout.addStretch(1)

        self.summary = QLabel("")
        self.summary.setProperty("muted", True)
        self.summary.hide()

        self.operation_switch._group.idClicked.connect(self.stack.setCurrentIndex)

    def _build_add_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        form = QFrame()
        form.setProperty("section", True)
        grid = QGridLayout(form)
        grid.setContentsMargins(12, 12, 12, 12)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        self.add_input = TabCompleteLineEdit()
        self.add_input.setPlaceholderText("例如: tachi-e, diorama")
        self.add_position = ChoiceBar(["开头", "末尾"], compact=True)
        self.add_skip = QCheckBox("跳过已存在标签")
        self.add_skip.setChecked(True)
        self.add_case = QCheckBox("忽略大小写")
        self.add_apply_button = QPushButton("添加到暂存区")
        self.add_apply_button.setProperty("primary", True)
        self.add_preview_label = QLabel("将影响 0 个文件")
        self.add_preview_label.setProperty("muted", True)
        self.add_label = QLabel("新增标签")
        grid.addWidget(self.add_label, 0, 0)
        grid.addWidget(self.add_input, 0, 1, 1, 3)
        add_action = QHBoxLayout()
        add_action.setContentsMargins(0, 0, 0, 0)
        add_action.addStretch(1)
        add_action.addWidget(self.add_preview_label)
        add_action.addWidget(self.add_apply_button)
        grid.addLayout(add_action, 2, 1, 1, 3)
        self.add_position_label = QLabel("插入位置")
        grid.addWidget(self.add_position_label, 1, 0)
        position_row = QHBoxLayout()
        position_row.setContentsMargins(0, 0, 0, 0)
        position_row.addWidget(self.add_position)
        position_row.addSpacing(10)
        position_row.addWidget(self.add_skip)
        position_row.addWidget(self.add_case)
        position_row.addStretch(1)
        grid.addLayout(position_row, 1, 1, 1, 3)
        grid.setColumnStretch(1, 1)
        layout.addWidget(form)
        self.add_apply_button.clicked.connect(lambda: self.apply_requested.emit("add"))
        for widget in [self.add_input]:
            widget.textChanged.connect(self.batch_inputs_changed.emit)
        self.add_skip.toggled.connect(self.batch_inputs_changed.emit)
        self.add_case.toggled.connect(self.batch_inputs_changed.emit)
        self.add_position._group.idClicked.connect(lambda _: self.batch_inputs_changed.emit())
        return page

    def _build_delete_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        form = QFrame()
        form.setProperty("section", True)
        grid = QGridLayout(form)
        grid.setContentsMargins(12, 12, 12, 12)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        self.delete_input = TabCompleteLineEdit()
        self.delete_input.setPlaceholderText("例如: soft shading")
        self.delete_case = QCheckBox("忽略大小写")
        self.delete_contains = QCheckBox("包含匹配")
        self.delete_apply_button = QPushButton("删除到暂存区")
        self.delete_apply_button.setProperty("danger", True)
        self.delete_files_button = QPushButton("删除包含标签的文件")
        self.delete_files_button.setProperty("danger", True)
        self.delete_preview_label = QLabel("将影响 0 个文件")
        self.delete_preview_label.setProperty("muted", True)
        self.delete_label = QLabel("删除标签")
        grid.addWidget(self.delete_label, 0, 0)
        grid.addWidget(self.delete_input, 0, 1, 1, 3)
        delete_action = QHBoxLayout()
        delete_action.setContentsMargins(0, 0, 0, 0)
        delete_action.addStretch(1)
        delete_action.addWidget(self.delete_preview_label)
        delete_action.addWidget(self.delete_apply_button)
        delete_action.addWidget(self.delete_files_button)
        grid.addLayout(delete_action, 2, 1, 1, 3)
        self.delete_match_label = QLabel("匹配方式")
        grid.addWidget(self.delete_match_label, 1, 0)
        grid.addWidget(self.delete_case, 1, 1)
        grid.addWidget(self.delete_contains, 1, 2)
        grid.setColumnStretch(1, 1)
        layout.addWidget(form)
        self.delete_apply_button.clicked.connect(lambda: self.apply_requested.emit("delete"))
        self.delete_files_button.clicked.connect(lambda: self.apply_requested.emit("delete_files"))
        self.delete_input.textChanged.connect(self.batch_inputs_changed.emit)
        self.delete_case.toggled.connect(self.batch_inputs_changed.emit)
        self.delete_contains.toggled.connect(self.batch_inputs_changed.emit)
        return page

    def _build_replace_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        form = QFrame()
        form.setProperty("section", True)
        grid = QGridLayout(form)
        grid.setContentsMargins(12, 12, 12, 12)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        self.replace_from = TabCompleteLineEdit()
        self.replace_from.setPlaceholderText("查找标签")
        self.replace_to = TabCompleteLineEdit()
        self.replace_to.setPlaceholderText("替换为")
        self.replace_case = QCheckBox("忽略大小写")
        self.replace_contains = QCheckBox("包含匹配")
        self.replace_dedupe = QCheckBox("替换后去重")
        self.replace_apply_button = QPushButton("替换到暂存区")
        self.replace_apply_button.setProperty("primary", True)
        self.format_apply_button = QPushButton("格式化到暂存区")
        self.format_apply_button.setProperty("primary", True)
        self.replace_preview_label = QLabel("将影响 0 个文件")
        self.replace_preview_label.setProperty("muted", True)
        self.replace_from_label = QLabel("查找")
        grid.addWidget(self.replace_from_label, 0, 0)
        grid.addWidget(self.replace_from, 0, 1)
        self.replace_to_label = QLabel("替换为")
        grid.addWidget(self.replace_to_label, 0, 2)
        grid.addWidget(self.replace_to, 0, 3)
        self.replace_match_label = QLabel("匹配方式")
        grid.addWidget(self.replace_match_label, 1, 0)
        grid.addWidget(self.replace_case, 1, 1)
        grid.addWidget(self.replace_contains, 1, 2)
        grid.addWidget(self.replace_dedupe, 1, 3)
        replace_action = QHBoxLayout()
        replace_action.setContentsMargins(0, 0, 0, 0)
        replace_action.addStretch(1)
        replace_action.addWidget(self.replace_preview_label)
        replace_action.addWidget(self.replace_apply_button)
        replace_action.addWidget(self.format_apply_button)
        grid.addLayout(replace_action, 2, 1, 1, 3)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        layout.addWidget(form)
        self.replace_apply_button.clicked.connect(lambda: self.apply_requested.emit("replace"))
        self.format_apply_button.clicked.connect(lambda: self.apply_requested.emit("format"))
        self.replace_from.textChanged.connect(self.batch_inputs_changed.emit)
        self.replace_to.textChanged.connect(self.batch_inputs_changed.emit)
        self.replace_case.toggled.connect(self.batch_inputs_changed.emit)
        self.replace_contains.toggled.connect(self.batch_inputs_changed.emit)
        self.replace_dedupe.toggled.connect(self.batch_inputs_changed.emit)
        return page

    def operation(self) -> str:
        return ["add", "delete", "replace", "format"][self.stack.currentIndex()]

    def _build_format_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        form = QFrame()
        form.setProperty("section", True)
        grid = QGridLayout(form)
        grid.setContentsMargins(12, 12, 12, 12)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        self.format_label = QLabel("批量格式化")
        self.format_note = QLabel("统一逗号格式，并移除同一文件内的重复标签")
        self.format_note.setProperty("muted", True)
        self.format_preview_label = QLabel("将影响 0 个文件")
        self.format_preview_label.setProperty("muted", True)
        self.format_page_apply_button = QPushButton("格式化到暂存区")
        self.format_page_apply_button.setProperty("primary", True)
        grid.addWidget(self.format_label, 0, 0)
        grid.addWidget(self.format_note, 0, 1, 1, 3)
        format_action = QHBoxLayout()
        format_action.setContentsMargins(0, 0, 0, 0)
        format_action.addStretch(1)
        format_action.addWidget(self.format_preview_label)
        format_action.addWidget(self.format_page_apply_button)
        grid.addLayout(format_action, 2, 1, 1, 3)
        grid.setColumnStretch(1, 1)
        layout.addWidget(form)
        self.format_page_apply_button.clicked.connect(lambda: self.apply_requested.emit("format"))
        return page

    def set_tag_suggestions(self, tags: list[str]) -> None:
        self.scope_tag.set_suggestions(tags)
        self.add_input.set_suggestions(tags)
        self.delete_input.set_suggestions(tags)
        self.replace_from.set_suggestions(tags)
        self.replace_to.set_suggestions(tags)

    def set_scope_tag_exists(self, exists: bool | None) -> None:
        if exists is None:
            self.scope_tag_hint.setText("Empty" if self.language == "en" else "未输入")
            self.scope_tag_hint.setProperty("ok", False)
        else:
            if self.language == "en":
                self.scope_tag_hint.setText("Matched" if exists else "Not found")
            else:
                self.scope_tag_hint.setText("已匹配" if exists else "未找到")
            self.scope_tag_hint.setProperty("ok", exists)
        self.scope_tag_hint.style().unpolish(self.scope_tag_hint)
        self.scope_tag_hint.style().polish(self.scope_tag_hint)

    def set_preview_summary(self, operation: str, count: int, is_scope_count: bool = False) -> None:
        label = {
            "add": self.add_preview_label,
            "delete": self.delete_preview_label,
            "delete_files": self.delete_preview_label,
            "replace": self.replace_preview_label,
            "format": self.format_preview_label,
        }[operation]
        if self.language == "en":
            prefix = "Scope" if is_scope_count else "Affects"
            label.setText(f"{prefix}: {count} files")
        else:
            prefix = "作用范围" if is_scope_count else "将影响"
            label.setText(f"{prefix} {count} 个文件")

    def apply_language(self, language: str) -> None:
        self.language = language
        if language == "en":
            self.title.setText("Batch Edit")
            self.operation_switch.set_labels(["Add", "Delete", "Replace", "Format"])
            self.scope.set_labels(["All files", "Selected", "Current filter", "Has label"])
            self.scope_tag.setPlaceholderText('Enter a label when scope is "Has label"')
            self.scope_label.setText("Scope")
            self.add_input.setPlaceholderText("Example: tachi-e, diorama")
            self.add_position.set_labels(["Start", "End"])
            self.add_skip.setText("Skip existing labels")
            self.add_case.setText("Ignore case")
            self.add_apply_button.setText("Add to Buffer")
            self.add_label.setText("New Labels")
            self.add_position_label.setText("Position")
            self.delete_input.setPlaceholderText("Example: soft shading")
            self.delete_case.setText("Ignore case")
            self.delete_contains.setText("Contains match")
            self.delete_apply_button.setText("Delete Labels")
            self.delete_files_button.setText("Delete Matching Files")
            self.delete_label.setText("Delete Labels")
            self.delete_match_label.setText("Match")
            self.replace_from.setPlaceholderText("Find label")
            self.replace_to.setPlaceholderText("Replace with")
            self.replace_case.setText("Ignore case")
            self.replace_contains.setText("Contains match")
            self.replace_dedupe.setText("Dedupe after replace")
            self.replace_apply_button.setText("Replace to Buffer")
            self.format_apply_button.setText("Format to Buffer")
            self.replace_from_label.setText("Find")
            self.replace_to_label.setText("Replace With")
            self.replace_match_label.setText("Match")
            self.format_label.setText("Batch Format")
            self.format_note.setText("Normalize comma spacing and remove duplicate labels in each file")
            self.format_page_apply_button.setText("Format to Buffer")
        else:
            self.title.setText("批量修改")
            self.operation_switch.set_labels(["添加", "删除", "替换", "格式化"])
            self.scope.set_labels(["全部文件", "左侧选中", "当前搜索", "包含标签"])
            self.scope_tag.setPlaceholderText("范围为“包含标签”时输入目标标签")
            self.scope_label.setText("作用范围")
            self.add_input.setPlaceholderText("例如: tachi-e, diorama")
            self.add_position.set_labels(["开头", "末尾"])
            self.add_skip.setText("跳过已存在标签")
            self.add_case.setText("忽略大小写")
            self.add_apply_button.setText("添加到暂存区")
            self.add_label.setText("新增标签")
            self.add_position_label.setText("插入位置")
            self.delete_input.setPlaceholderText("例如: soft shading")
            self.delete_case.setText("忽略大小写")
            self.delete_contains.setText("包含匹配")
            self.delete_apply_button.setText("删除标签")
            self.delete_files_button.setText("删除包含标签的文件")
            self.delete_label.setText("删除标签")
            self.delete_match_label.setText("匹配方式")
            self.replace_from.setPlaceholderText("查找标签")
            self.replace_to.setPlaceholderText("替换为")
            self.replace_case.setText("忽略大小写")
            self.replace_contains.setText("包含匹配")
            self.replace_dedupe.setText("替换后去重")
            self.replace_apply_button.setText("替换到暂存区")
            self.format_apply_button.setText("格式化到暂存区")
            self.replace_from_label.setText("查找")
            self.replace_to_label.setText("替换为")
            self.replace_match_label.setText("匹配方式")
            self.format_label.setText("批量格式化")
            self.format_note.setText("统一逗号格式，并移除同一文件内的重复标签")
            self.format_page_apply_button.setText("格式化到暂存区")
