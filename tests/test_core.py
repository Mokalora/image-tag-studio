from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut, QWheelEvent
from PySide6.QtWidgets import QApplication, QMessageBox

from app.main_window import MainWindow
from app.operations import apply_changes, build_tag_stats, preview_add, preview_delete, preview_format, preview_replace
from app.save_service import save_files
from app.scanner import scan_folder
from app.tag_parser import add_tags, delete_tags, format_tags, parse_tags, replace_tags
from app.ui.popup_suppressor import StartupPopupSuppressor


def app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


def test_v2_tag_parser_handles_chinese_comma() -> None:
    assert parse_tags("tachi-e，diorama, ") == ["tachi-e", "diorama"]
    assert format_tags(["a", "b"]) == "a, b"
    assert add_tags(["b"], ["a"], "start") == ["a", "b"]
    assert delete_tags(["a", "b"], ["a"]) == ["b"]
    assert replace_tags(["a", "b"], "a", "c") == ["c", "b"]


def test_v2_scan_preview_apply_and_save(tmp_path: Path) -> None:
    (tmp_path / "001.txt").write_text("a, b", encoding="utf-8")
    files = scan_folder(tmp_path)
    assert len(files) == 1
    changes = preview_add(files, ["c"], "end", True, False)
    assert apply_changes(files, changes) == 1
    assert files[0].modified is True
    result = save_files(files, keep_backup_in_dataset=False, allow_external_overwrite=True)
    assert result.saved_count == 1
    assert result.failures == []
    assert (tmp_path / "001.txt").read_text(encoding="utf-8") == "a, b, c"
    assert not (tmp_path / "_lora_tag_backup").exists()


def test_v2_image_without_txt_can_be_tagged_and_saved(tmp_path: Path) -> None:
    from PySide6.QtGui import QColor, QPixmap

    app()
    image_path = tmp_path / "image_only.png"
    pixmap = QPixmap(16, 16)
    pixmap.fill(QColor("#4488cc"))
    pixmap.save(str(image_path))

    files = scan_folder(tmp_path)
    assert len(files) == 1
    assert files[0].display_name == "image_only.png"
    assert files[0].path == tmp_path / "image_only.txt"
    assert files[0].tags == []

    files[0].tags = ["blue", "sample"]
    files[0].raw_text = "blue, sample"
    files[0].modified = True
    result = save_files(files, keep_backup_in_dataset=False, allow_external_overwrite=True)
    assert result.saved_count == 1
    assert (tmp_path / "image_only.txt").read_text(encoding="utf-8") == "blue, sample"


def test_v2_empty_modified_tags_delete_existing_txt(tmp_path: Path) -> None:
    from PySide6.QtGui import QColor, QPixmap

    app()
    image_path = tmp_path / "clear_me.jpg"
    pixmap = QPixmap(16, 16)
    pixmap.fill(QColor("#8844cc"))
    pixmap.save(str(image_path))
    txt_path = tmp_path / "clear_me.txt"
    txt_path.write_text("old_tag", encoding="utf-8")

    files = scan_folder(tmp_path)
    tag_file = files[0]
    assert tag_file.display_name == "clear_me.jpg"
    tag_file.tags = []
    tag_file.raw_text = ""
    tag_file.modified = True
    result = save_files(files, keep_backup_in_dataset=False, allow_external_overwrite=True)
    assert result.saved_count == 1
    assert not txt_path.exists()
    assert tag_file.modified is False


def test_v2_operations_and_stats(tmp_path: Path) -> None:
    (tmp_path / "001.txt").write_text("a, b, b", encoding="utf-8")
    (tmp_path / "002.txt").write_text("a, c", encoding="utf-8")
    files = scan_folder(tmp_path)
    stats = {row.tag: row for row in build_tag_stats(files)}
    assert stats["a"].count == 2
    assert stats["a"].file_count == 2
    assert stats["b"].count == 2
    assert stats["b"].file_count == 1
    assert len(preview_delete(files, ["a"], False, False)) == 2
    assert len(preview_replace(files, "c", "d", False, False, False)) == 1
    assert len(preview_format(files)) == 1


def test_v2_virtual_missing_tags_are_filterable(tmp_path: Path) -> None:
    from PySide6.QtGui import QColor, QPixmap

    app()
    image_path = tmp_path / "missing_txt.png"
    pixmap = QPixmap(16, 16)
    pixmap.fill(QColor("#4488cc"))
    pixmap.save(str(image_path))
    (tmp_path / "missing_image.txt").write_text("tagged", encoding="utf-8")

    files = scan_folder(tmp_path)
    stats = {row.key: row for row in build_tag_stats(files)}
    assert stats["virtual:missing_txt"].virtual is True
    assert stats["virtual:missing_image"].virtual is True

    from app.state import StudioState

    state = StudioState()
    state.set_files(files)
    state.filter_tags = ["virtual:missing_txt"]
    assert [item.display_name for item in state.filtered_files()] == ["missing_txt.png"]
    state.filter_tags = ["virtual:missing_image"]
    assert [item.filename for item in state.filtered_files()] == ["missing_image.txt"]


def test_v2_negative_filter_display_mode_returns_complement(tmp_path: Path) -> None:
    (tmp_path / "001.txt").write_text("a, b", encoding="utf-8")
    (tmp_path / "002.txt").write_text("b, c", encoding="utf-8")
    (tmp_path / "003.txt").write_text("d", encoding="utf-8")

    files = scan_folder(tmp_path)

    from app.state import StudioState

    state = StudioState()
    state.set_files(files)
    state.filter_tags = ["b"]
    state.filter_mode = "or"
    assert [item.filename for item in state.filtered_files()] == ["001.txt", "002.txt"]

    state.filter_display_mode = "negative"
    assert [item.filename for item in state.filtered_files()] == ["003.txt"]


def test_v2_gui_scan_and_view_switch_do_not_popup() -> None:
    app()
    window = MainWindow()
    window.show()
    window.state.folder = Path("test_exam")
    window._scan_finished(scan_folder(Path("test_exam")))
    window.file_panel.set_mode("grid")
    for _ in range(30):
        QApplication.processEvents()
        time.sleep(0.005)
    window.file_panel.set_mode("list")
    window.file_panel.set_mode("grid")
    for _ in range(20):
        QApplication.processEvents()
        time.sleep(0.005)
    boxes = [widget for widget in QApplication.topLevelWidgets() if isinstance(widget, QMessageBox) and widget.isVisible()]
    assert boxes == []
    assert window.message_label.text() == ""
    window.close()


def test_v2_preview_zoom_anchors_to_cursor() -> None:
    app()
    window = MainWindow()
    window.show()
    window.state.folder = Path("test_exam")
    window._scan_finished(scan_folder(Path("test_exam")))
    window.current_page.image.resize(320, 220)
    before = QPointF(window.current_page.image.offset)
    event = QWheelEvent(
        QPointF(260, 160),
        QPointF(260, 160),
        QPoint(0, 120),
        QPoint(0, 120),
        Qt.NoButton,
        Qt.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    window.current_page.image.wheelEvent(event)
    assert window.current_page.image.zoom > 1.0
    assert window.current_page.image.offset != before
    window.close()


def test_v2_tag_move_and_status_message_work() -> None:
    app()
    window = MainWindow()
    window.show()
    window.state.folder = Path("test_exam")
    window._scan_finished(scan_folder(Path("test_exam")))
    current = window.state.current_file()
    assert current is not None
    current.tags = ["a", "b", "c"]
    current.raw_text = "a, b, c"
    window.current_page.set_file(current)
    window.current_page._move_tag("a", "c", "after")
    QApplication.processEvents()
    assert current.tags == ["b", "c", "a"]
    assert window.message_label.text()
    current.modified = False
    window.close()
    window.deleteLater()
    QApplication.processEvents()


def test_v2_startup_popup_suppressor_hides_message_box() -> None:
    app()
    window = MainWindow()
    window.show()
    box = QMessageBox(window)
    box.setText("startup noise")
    box.show()
    QApplication.processEvents()
    assert box.isVisible() is True
    suppressor = StartupPopupSuppressor(window, duration_ms=80)
    suppressor.start()
    QApplication.processEvents()
    assert box.isVisible() is False
    window.close()


def test_v2_shortcuts_and_redo_restore_single_operation() -> None:
    app()
    window = MainWindow()
    window.state.folder = Path("test_exam")
    window._scan_finished(scan_folder(Path("test_exam")))
    current = window.state.current_file()
    assert current is not None
    current.tags = ["a", "b"]
    current.raw_text = "a, b"
    current.original_tags = ["a"]
    current.original_text = "a"
    window.current_page.set_file(current)
    window.current_page._add_tags("end", "c")
    assert current.tags == ["a", "b", "c"]
    window.undo()
    assert current.tags == ["a", "b"]
    window.redo()
    assert current.tags == ["a", "b", "c"]
    shortcuts = {shortcut.key().toString(QKeySequence.NativeText) for shortcut in window.findChildren(QShortcut)}
    assert "Ctrl+S" in shortcuts
    assert "Ctrl+Z" in shortcuts
    assert "Ctrl+Shift+Z" in shortcuts
    current.modified = False
    window.close()


def test_v2_tab_completion_and_scope_hint() -> None:
    app()
    window = MainWindow()
    window.state.folder = Path("test_exam")
    window._scan_finished(scan_folder(Path("test_exam")))
    window.search.setText("blue")
    window.search.complete_first_match()
    assert window.search.text()
    tag = window.search.text()
    window.batch_page.scope_tag.setText(tag[: max(1, len(tag) // 2)])
    assert window.batch_page.scope_tag.complete_first_match() is True
    assert window.batch_page.scope_tag.text() == tag
    window._update_scope_tag_hint()
    assert window.batch_page.scope_tag_hint.text() == "已匹配"
    window.close()


def test_v2_chip_edit_width_and_max_restore() -> None:
    app()
    window = MainWindow()
    window.resize(1488, 900)
    before = window.geometry()
    window._toggle_max()
    window._toggle_max()
    assert window.geometry().size() == before.size()
    from app.ui.chips import TagChip

    chip = TagChip("abc")
    chip.show()
    chip.adjustSize()
    label_width = chip.label.sizeHint().width()
    chip.begin_edit()
    assert chip.editor.width() == label_width
    assert chip.editor.height() >= 30
    assert chip.sizeHint().height() >= 38
    before_width = chip.editor.width()
    chip.editor.setText("abc_longer_than_before")
    chip._fit_editor_to_text()
    assert chip.editor.width() >= before_width
    chip.close()
    window.close()


def test_v2_tag_chip_selected_delete_key_removes() -> None:
    from PySide6.QtGui import QKeyEvent
    from app.ui.chips import TagChip

    app()
    chip = TagChip("soft muted colors")
    removed: list[str] = []
    chip.removed.connect(removed.append)
    chip.show()
    chip.set_selected(True)
    chip.keyPressEvent(QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier))
    assert removed == ["soft muted colors"]
    chip.close()


def test_v2_image_canvas_edge_navigation_signals() -> None:
    from PySide6.QtGui import QColor, QMouseEvent, QPixmap
    from app.ui.current_page import ImageCanvas

    app()
    image_path = Path(os.environ.get("TEMP", ".")) / "image_tag_studio_nav_test.png"
    pixmap = QPixmap(16, 16)
    pixmap.fill(QColor("#335577"))
    pixmap.save(str(image_path))
    canvas = ImageCanvas()
    canvas.resize(400, 240)
    canvas.set_image(image_path)
    seen: list[str] = []
    canvas.previous_requested.connect(lambda: seen.append("previous"))
    canvas.next_requested.connect(lambda: seen.append("next"))
    assert canvas._nav_hover(QPointF(8, 120)) == "previous"
    assert canvas._nav_hover(QPointF(392, 120)) == "next"
    assert canvas._nav_click_hit(QPointF(8, 120)) is None
    assert canvas._nav_click_hit(canvas._nav_rect("previous").center()) == "previous"
    assert canvas._nav_click_hit(canvas._nav_rect("next").center()) == "next"
    canvas.previous_requested.emit()
    canvas.next_requested.emit()
    assert seen == ["previous", "next"]
    seen.clear()
    center = canvas._nav_rect("next").center()
    canvas.mousePressEvent(QMouseEvent(QMouseEvent.MouseButtonPress, center, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
    canvas.mousePressEvent(QMouseEvent(QMouseEvent.MouseButtonPress, center, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
    assert seen == ["next"]
    image_path.unlink(missing_ok=True)


def test_v2_completion_cycles_with_arrows() -> None:
    app()
    from app.ui.completion import TabCompleteLineEdit

    field = TabCompleteLineEdit()
    field.set_suggestions(["blue dress", "blue hair", "brown eyes"])
    field.setText("blu")
    assert field.current_completion() == "blue dress"
    from PySide6.QtGui import QKeyEvent

    field.keyPressEvent(QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Down, Qt.NoModifier))
    assert field.current_completion() == "blue hair"
    assert field.accept_current_completion() is True
    assert field.text() == "blue hair"


def test_v2_completion_tab_does_not_move_focus() -> None:
    app()
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QKeyEvent
    from app.ui.completion import TabCompleteLineEdit

    field = TabCompleteLineEdit()
    field.set_suggestions(["blue dress"])
    field.setText("blu")
    event = QKeyEvent(QEvent.KeyPress, Qt.Key_Tab, Qt.NoModifier)
    assert field.event(event) is True
    assert field.text() == "blue dress"
    assert field.focusNextPrevChild(True) is False


def test_v2_tag_overview_sort_and_table_toggle() -> None:
    app()
    from app.models import TagStat
    from app.ui.tag_overview import TagOverview

    panel = TagOverview()
    panel.set_rows(
        [
            TagStat("z_tag", 4, 2),
            TagStat("a_tag", 10, 3),
            TagStat("m_tag", 6, 1),
        ]
    )
    assert [row.tag for row in panel.visible_rows] == ["a_tag", "m_tag", "z_tag"]
    panel.sort_alpha_button.click()
    assert [row.tag for row in panel.visible_rows] == ["a_tag", "m_tag", "z_tag"]
    panel._toggle_table_row(panel.table_model.index(1, 0))
    assert panel.selected == {"m_tag"}
    assert panel.table_model.selected == {"m_tag"}
    assert panel.table.focusPolicy() == Qt.NoFocus
    assert "或" in panel.selected_label.text()
    assert "m_tag" in panel.selected_label.text()
    assert panel.table_model.data(panel.table_model.index(1, 0), Qt.BackgroundRole) is not None


def test_v2_tag_overview_display_mode_toggle_emits_and_updates_label() -> None:
    app()
    from app.models import TagStat
    from app.ui.tag_overview import TagOverview

    panel = TagOverview()
    panel.set_rows(
        [
            TagStat("a_tag", 10, 3),
            TagStat("m_tag", 6, 1),
        ]
    )
    emitted: list[tuple[list[str], str, str]] = []
    panel.filter_changed.connect(lambda tags, mode, display: emitted.append((tags, mode, display)))

    panel._toggle_tag("a_tag", True)
    assert emitted[-1] == (["a_tag"], "or", "positive")
    assert "正" in panel.selected_label.text()

    panel.negative_button.click()
    assert emitted[-1] == (["a_tag"], "or", "negative")
    assert "反" in panel.selected_label.text()


def test_v2_tag_overview_alpha_sorts_within_frequency_limited_rows() -> None:
    app()
    from app.models import TagStat
    from app.ui.tag_overview import TagOverview

    panel = TagOverview()
    panel.top_slider.setValue(2)
    panel.set_rows(
        [
            TagStat("z_top", 100, 5),
            TagStat("a_low", 1, 1),
            TagStat("m_top", 90, 4),
        ]
    )
    assert [row.tag for row in panel.visible_rows] == ["z_top", "m_top"]
    panel.sort_alpha_button.click()
    assert [row.tag for row in panel.visible_rows] == ["m_top", "z_top"]


def test_v2_batch_preview_labels_live_next_to_apply_buttons() -> None:
    app()
    from app.ui.batch_page import BatchPage

    page = BatchPage()
    assert not hasattr(page, "preview_button")
    assert page.add_preview_label.parent() is page.add_apply_button.parent()
    assert page.delete_preview_label.parent() is page.delete_apply_button.parent()
    assert page.replace_preview_label.parent() is page.replace_apply_button.parent()
    assert page.format_preview_label.parent() is page.format_page_apply_button.parent()


def test_v2_batch_delete_removes_tags_not_files(tmp_path: Path) -> None:
    app()
    (tmp_path / "001.txt").write_text("tag_a, tag_b", encoding="utf-8")
    window = MainWindow()
    window.state.folder = tmp_path
    window._scan_finished(scan_folder(tmp_path))
    window.batch_page.delete_input.setText("tag_a")
    window._apply_batch("delete")
    assert window.state.files[0].pending_delete is False
    assert window.state.files[0].tags == ["tag_b"]
    window.state.files[0].modified = False
    window.close()


def test_v2_batch_delete_files_marks_matching_files_pending_delete(tmp_path: Path) -> None:
    app()
    (tmp_path / "001.txt").write_text("tag_a, tag_b", encoding="utf-8")
    (tmp_path / "002.txt").write_text("tag_c", encoding="utf-8")
    window = MainWindow()
    window.state.folder = tmp_path
    window._scan_finished(scan_folder(tmp_path))
    window.batch_page.delete_input.setText("tag_a")
    window._apply_batch("delete_files")
    states = {item.filename: item.pending_delete for item in window.state.files}
    assert states["001.txt"] is True
    assert states["002.txt"] is False
    for item in window.state.files:
        item.pending_delete = False
        item.modified = False
    window.close()


def test_v2_batch_format_dedupes_tags_in_buffer(tmp_path: Path) -> None:
    app()
    (tmp_path / "001.txt").write_text("TagA, taga, tag_b, tag_b", encoding="utf-8")
    window = MainWindow()
    window.state.folder = tmp_path
    window._scan_finished(scan_folder(tmp_path))
    window._apply_batch("format")
    assert window.state.files[0].tags == ["TagA", "tag_b"]
    window.state.files[0].modified = False
    window.close()


def test_v2_file_panel_defaults_to_grid_and_shows_filter_summary() -> None:
    app()
    window = MainWindow()
    window.show()
    QApplication.processEvents()
    assert window.file_panel.stack.currentIndex() == 1
    assert window.file_panel.grid_button.isChecked() is True
    assert window.file_panel.list_button.isChecked() is False
    assert window.file_panel.minimumWidth() <= 260
    assert window.file_panel.grid_view.gridSize().width() >= 160
    window.state.search_text = "abc"
    window.state.filter_tags = ["tag_a", "tag_b", "very_long_tag_name_a", "very_long_tag_name_b"]
    window.state.filter_mode = "or"
    window.refresh_files()
    assert window.file_panel.filter_label.width() >= 120
    assert "搜索：abc" in window.file_panel.filter_label.toolTip()
    assert "标签或" in window.file_panel.filter_label.toolTip()
    assert len(window.file_panel.filter_label.text()) < len(window.file_panel.filter_label.toolTip())
    old_width = window.file_panel.filter_label.width()
    window.file_panel.setFixedWidth(window.file_panel.width() + 320)
    QApplication.processEvents()
    window.file_panel._sync_filter_width()
    assert window.file_panel.filter_label.width() > old_width
    window.file_panel.setFixedWidth(16777215)
    window.close()


def test_v2_grid_defaults_to_two_columns_and_can_expand() -> None:
    app()
    window = MainWindow()
    window.show()
    QApplication.processEvents()
    panel = window.file_panel
    panel.grid_view.resize(420, 600)
    panel._sync_grid_metrics()
    two_col_width = panel.grid_view.gridSize().width()
    assert two_col_width <= panel.grid_view.viewport().width() // 2 + 20
    panel.grid_view.resize(760, 600)
    panel._sync_grid_metrics()
    assert panel.grid_view.gridSize().width() <= panel.grid_view.viewport().width() // 4 + 40
    window.close()


def test_v2_slider_clear_filter_syncs_file_panel() -> None:
    app()
    window = MainWindow()
    window.state.filter_tags = ["abc"]
    window.state.filter_mode = "or"
    window.refresh_files()
    assert "abc" in window.file_panel.filter_label.text()
    window.tag_page._slider_changed()
    assert window.state.filter_tags == []
    assert window.file_panel.filter_label.text() == "筛选：全部"
    window.close()


def test_v2_tag_overview_refresh_does_not_shrink_file_panel() -> None:
    app()
    window = MainWindow()
    before = window.file_panel.width()
    window.tag_page.search.setText("abc")
    window.refresh_tag_page()
    assert window.file_panel.minimumWidth() <= 260
    assert window.file_panel.width() >= min(before, window.file_panel.minimumWidth())
    window.close()


def test_v2_current_page_has_single_apply_action() -> None:
    app()
    window = MainWindow()
    assert not hasattr(window.current_page, "save_button")
    assert window.current_page.apply_text_button.text() == "应用到暂存区"
    assert window.current_page.apply_text_button.property("primary") is True
    window.close()


def test_v2_window_title_and_toolbar_copy() -> None:
    app()
    window = MainWindow()
    assert window.windowTitle() == "Image Tag Studio"
    assert window.title_bar.title_label.text() == "Image Tag Studio"
    assert window.open_button.text() == "打开目录"
    assert window.save_button.text() == "保存修改"
    assert window.undo_button.text() == "撤销修改"
    assert "标签" in window.search.placeholderText()
    assert window.tabs.tabText(1) == "批量修改"
    assert window.title_bar.theme_button.kind == "theme"
    assert window.title_bar.language_button.kind == "lang"
    assert window.batch_page.summary.isVisible() is False
    window.close()


def test_v2_window_uses_mature_frameless_backend() -> None:
    from qframelesswindow import FramelessWindow

    app()
    window = MainWindow()
    assert isinstance(window, FramelessWindow)
    assert hasattr(window, "windowEffect") or os.name != "nt"
    assert not hasattr(window, "_windows_hit_test")
    assert not hasattr(window, "_enable_windows_window_behaviors")
    window.close()


def test_v2_maximize_button_state_follows_window_state() -> None:
    app()
    window = MainWindow()
    window.showMaximized()
    window._sync_window_state_controls()
    assert window.title_bar.max_button.kind == "restore"
    assert window.resize_handle.isVisible() is False
    window.showNormal()
    window._sync_window_state_controls()
    assert window.title_bar.max_button.kind == "max"
    window.close()


def test_v2_manual_resize_handles_hide_while_maximized() -> None:
    app()
    window = MainWindow()
    window.showMaximized()
    window._sync_window_state_controls()
    assert window.resize_handle.isVisible() is False
    assert window.right_resize_handle.isVisible() is False
    assert window.bottom_resize_handle.isVisible() is False
    window.close()


def test_v2_delete_file_buffers_image_and_txt_until_save(tmp_path: Path) -> None:
    from PySide6.QtGui import QColor, QPixmap

    app()
    image_path = tmp_path / "delete_me.png"
    pixmap = QPixmap(16, 16)
    pixmap.fill(QColor("#336699"))
    pixmap.save(str(image_path))
    txt_path = tmp_path / "delete_me.txt"
    txt_path.write_text("old", encoding="utf-8")
    window = MainWindow(theme_name="dark", language="en")
    window.state.folder = tmp_path
    window._scan_finished(scan_folder(tmp_path))
    window._delete_tag_file(txt_path)
    assert txt_path.exists()
    assert image_path.exists()
    assert len(window.state.files) == 1
    assert window.state.files[0].pending_delete is True
    assert window.state.filtered_files() == []
    assert len(window.state.undo_stack) == 1
    window.undo()
    window.close()


def test_v2_saved_delete_can_be_undone_and_redone(tmp_path: Path) -> None:
    from PySide6.QtGui import QColor, QPixmap

    app()
    image_path = tmp_path / "restore_me.jpg"
    pixmap = QPixmap(16, 16)
    pixmap.fill(QColor("#336699"))
    pixmap.save(str(image_path))
    txt_path = tmp_path / "restore_me.txt"
    txt_path.write_text("old", encoding="utf-8")
    window = MainWindow(theme_name="dark", language="en")
    window.state.folder = tmp_path
    window._scan_finished(scan_folder(tmp_path))
    window._delete_tag_file(txt_path)
    window.save_all()
    assert not txt_path.exists()
    assert not image_path.exists()
    assert window.state.files[0].pending_delete is True
    assert window.state.files[0].delete_saved is True
    assert window.state.modified_files() == []

    window.undo()
    assert txt_path.exists()
    assert image_path.exists()
    assert window.state.files[0].pending_delete is False

    window.redo()
    window.save_all()
    assert not txt_path.exists()
    assert not image_path.exists()
    window.close()


def test_v2_saved_delete_orphan_txt_can_be_undone(tmp_path: Path) -> None:
    app()
    txt_path = tmp_path / "orphan.txt"
    txt_path.write_text("old", encoding="utf-8")
    window = MainWindow(theme_name="dark", language="en")
    window.state.folder = tmp_path
    window._scan_finished(scan_folder(tmp_path))
    window._delete_tag_file(txt_path)
    window.save_all()
    assert not txt_path.exists()
    window.undo()
    assert txt_path.read_text(encoding="utf-8") == "old"
    assert window.state.filtered_files()[0].path == txt_path
    window.close()


def test_v2_grid_delegate_does_not_request_thumbnail_for_missing_image(tmp_path: Path) -> None:
    from PySide6.QtGui import QImage
    from app.models import FileSnapshot, TagFile
    from app.ui.file_panel import FileModel, GridDelegate

    app()

    class FakeThumbs:
        requested = False

        def image(self, _path):  # noqa: ANN001
            return QImage()

        def request(self, _path, front=False):  # noqa: ANN001
            self.requested = True

    tag_file = TagFile(
        path=tmp_path / "orphan.txt",
        filename="orphan.txt",
        image_path=None,
        raw_text="tag",
        tags=["tag"],
        original_text="tag",
        original_tags=["tag"],
        snapshot=FileSnapshot("tag", 3, 0, "utf-8"),
    )
    model = FileModel()
    model.set_files([tag_file])
    fake = FakeThumbs()
    delegate = GridDelegate(fake)
    from PySide6.QtGui import QPainter, QPixmap
    from PySide6.QtWidgets import QStyleOptionViewItem

    pixmap = QPixmap(180, 230)
    painter = QPainter(pixmap)
    option = QStyleOptionViewItem()
    option.rect = pixmap.rect()
    delegate.paint(painter, option, model.index(0, 0))
    painter.end()
    assert fake.requested is False


def test_v2_batch_preview_updates_from_inputs() -> None:
    app()
    window = MainWindow()
    window.state.folder = Path("test_exam")
    window._scan_finished(scan_folder(Path("test_exam")))
    assert window.batch_page.add_preview_label.text().startswith("作用范围 ")
    window.batch_page.add_input.setText("new_tag")
    window._refresh_batch_preview()
    assert window.batch_page.add_preview_label.text().startswith("将影响 ")
    assert "个文件" in window.batch_page.add_preview_label.text()
    window.close()


def test_v2_file_panel_preserves_scroll_after_refresh() -> None:
    from PySide6.QtGui import QColor, QPixmap
    from app.thumbs import ThumbnailService
    from app.ui.file_panel import FilePanel

    app()
    root = Path(os.environ.get("TEMP", ".")) / "its_scroll_case"
    root.mkdir(parents=True, exist_ok=True)
    paths = []
    for index in range(18):
        image_path = root / f"its_scroll_{index}.png"
        txt_path = root / f"its_scroll_{index}.txt"
        pixmap = QPixmap(24, 24)
        pixmap.fill(QColor("#446688"))
        pixmap.save(str(image_path))
        txt_path.write_text(f"tag{index}", encoding="utf-8")
        paths.append((image_path, txt_path))

    files = [item for item in scan_folder(root) if item.display_name.startswith("its_scroll_")]
    panel = FilePanel(ThumbnailService())
    panel.resize(320, 520)
    panel.show()
    panel.set_mode("list")
    panel.set_files(files, None)
    QApplication.processEvents()
    panel.list_view.verticalScrollBar().setValue(120)
    before = panel.list_view.verticalScrollBar().value()
    panel.set_files(files[1:], None)
    QApplication.processEvents()
    after = panel.list_view.verticalScrollBar().value()
    assert after > 0
    assert abs(after - before) <= 80
    panel.close()
    for image_path, txt_path in paths:
        image_path.unlink(missing_ok=True)
        txt_path.unlink(missing_ok=True)
    root.rmdir()


def test_v2_theme_and_language_toggles_are_real() -> None:
    app_instance = app()
    window = MainWindow(theme_name="dark", language="zh")
    window.toggle_theme()
    assert window.theme_name == "light"
    assert "#F4F7FB" in app_instance.styleSheet()
    window.toggle_language()
    assert window.language == "en"
    assert window.open_button.text() == "Open Folder"
    assert window.tabs.tabText(1) == "Batch Edit"
    assert window.batch_page.add_preview_label.text().startswith("Scope:")
    window.close()


def test_v2_button_feedback_styles_exist() -> None:
    from app.ui.theme import DARK_STYLE, LIGHT_STYLE

    assert 'QPushButton[primary="true"]:hover' in DARK_STYLE
    assert 'QPushButton[primary="true"]:pressed' in DARK_STYLE
    assert 'QPushButton[choiceButton="true"]:hover' in DARK_STYLE
    assert 'QPushButton[choiceButton="true"]:pressed' in DARK_STYLE
    assert 'QPushButton[primary="true"]:hover' in LIGHT_STYLE
    assert 'QPushButton[primary="true"]:pressed' in LIGHT_STYLE


def test_v2_language_controls_dynamic_file_and_close_text() -> None:
    from PySide6.QtWidgets import QDialog
    from app.ui.app_dialog import ConfirmDialog

    app()
    window = MainWindow(theme_name="dark", language="en")
    assert window.title_bar.path_label.text() == ""
    tmp = Path("test_exam")
    files = scan_folder(tmp)
    window._scan_finished(files)
    assert window.file_panel.list_delegate.language == "en"
    assert window.file_panel.grid_delegate.language == "en"
    assert "labels" in window.current_page.meta.text()
    current = window.state.current_file()
    assert current is not None
    current.modified = True
    dialogs: list[ConfirmDialog] = []
    original_exec = ConfirmDialog.exec

    def fake_exec(self):  # noqa: ANN001
        dialogs.append(self)
        return QDialog.Rejected

    ConfirmDialog.exec = fake_exec
    try:
        event = QCloseEvent()
        window.closeEvent(event)
    finally:
        ConfirmDialog.exec = original_exec
    assert dialogs
    assert dialogs[0].title_label.text() == "Unsaved Changes"
    assert dialogs[0].message.text() == "Some files are not saved. Exit anyway?"
    assert dialogs[0].windowFlags() & Qt.FramelessWindowHint
    assert dialogs[0].no_button.property("primary") is True
    assert dialogs[0].yes_button.property("primary") is None
    current.modified = False
    window.close()


def test_v2_light_theme_reaches_custom_painted_widgets() -> None:
    from app.models import TagStat
    from app.ui import palette
    from app.ui.chips import TagChip
    from app.ui.tag_overview import TagOverview

    app()
    window = MainWindow(theme_name="dark", language="zh")
    window.toggle_theme()
    assert palette.theme() == "light"
    chip = TagChip("abc")
    chip.show()
    chip.update()
    assert palette.value("card") == "#FFFFFF"
    panel = TagOverview()
    panel.set_rows([TagStat("abc", 2, 1)])
    panel._toggle_table_row(panel.table_model.index(0, 0))
    bg = panel.table_model.data(panel.table_model.index(0, 0), Qt.BackgroundRole)
    assert bg == palette.color("accent_soft")
    window.close()


def test_v2_status_message_uses_tab_corner_fixed_area() -> None:
    app()
    window = MainWindow(theme_name="dark", language="zh")
    window.resize(1540, 900)
    window.show()
    QApplication.processEvents()
    window._toast("测试提示")
    assert window.message_bar.parent() is window
    assert window.message_label.text() == "测试提示"
    assert window.message_bar.styleSheet()
    assert "transparent" in window.message_bar.styleSheet()
    assert window.message_label.minimumWidth() >= 560
    assert window.message_label.alignment() & Qt.AlignRight
    right_gap = (window.tabs.x() + window.tabs.width()) - (window.message_bar.x() + window.message_bar.width())
    assert 12 <= right_gap <= 20
    window.close()


def test_v2_cloud_caption_button_and_image_only_scan(tmp_path: Path) -> None:
    from PySide6.QtGui import QColor, QPixmap

    app()
    image_path = tmp_path / "only_image.png"
    pixmap = QPixmap(32, 32)
    pixmap.fill(QColor("#ff0000"))
    pixmap.save(str(image_path))
    files = scan_folder(tmp_path)
    assert len(files) == 1
    assert files[0].path == tmp_path / "only_image.txt"
    assert files[0].image_path == image_path
    window = MainWindow(theme_name="dark", language="zh")
    assert window.tabs.tabText(3) == "云端识别"
    assert window.caption_page.settings().api_concurrency == 4
    toolbar_widgets = [window.status.parent().layout().itemAt(index).widget() for index in range(window.status.parent().layout().count())]
    assert window.status in toolbar_widgets
    assert not hasattr(window, "caption_button")
    window.close()


def test_v2_caption_api_openai_payload_and_parse(tmp_path: Path) -> None:
    from PySide6.QtGui import QColor, QPixmap
    from app.caption_api import CaptionApiSettings, _openai_payload, image_files_without_txt, parse_openai_caption, ping_openai_api, resolve_endpoint, write_caption_txt

    app()
    image_path = tmp_path / "img.png"
    pixmap = QPixmap(16, 16)
    pixmap.fill(QColor("#00ff00"))
    pixmap.save(str(image_path))
    assert image_files_without_txt(tmp_path) == [image_path]
    assert resolve_endpoint("https://example.com/v1") == "https://example.com/v1/chat/completions"
    settings = CaptionApiSettings(api_key="secret")
    assert settings.model == "mimo-v2.5"
    assert settings.api_concurrency == 4
    assert parse_openai_caption({"choices": [{"message": {"content": "a, b"}}]}) == "a, b"
    payload = _openai_payload(settings, image_path)
    image_url = payload["messages"][0]["content"][1]["image_url"]["url"]
    assert image_url.startswith("data:image/png;base64,")
    try:
        write_caption_txt(image_path, "   ")
    except ValueError as exc:
        assert "empty" in str(exc)
    else:
        raise AssertionError("blank captions must not create empty txt files")
    assert not image_path.with_suffix(".txt").exists()

    captured: dict[str, object] = {}

    class FakeResponse:
        def __enter__(self):  # noqa: ANN001
            return self

        def __exit__(self, *args):  # noqa: ANN002
            return False

        def read(self):  # noqa: ANN001
            return json.dumps({"choices": [{"message": {"content": "1"}}]}).encode("utf-8")

    def fake_urlopen(req, timeout=0):  # noqa: ANN001
        captured["body"] = json.loads(req.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse()

    import app.caption_api as caption_api

    original = caption_api.request.urlopen
    caption_api.request.urlopen = fake_urlopen
    try:
        assert ping_openai_api(settings) == "1"
    finally:
        caption_api.request.urlopen = original
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["max_tokens"] == 4
    assert "image_url" not in json.dumps(body)


def test_v2_caption_dialog_token_and_concurrency_sliders() -> None:
    from PySide6.QtWidgets import QLabel
    from app.caption_api import DEFAULT_CAPTION_PROMPT
    from app.ui.caption_dialog import CaptionDialog

    app()
    dialog = CaptionDialog(Path("test_exam"), False, "zh")
    assert dialog.windowFlags() & Qt.FramelessWindowHint
    assert dialog.close_button.text() == "×"
    assert dialog.max_token_values == [256, 512, 1024, 2048, 4096, 8192]
    dialog.max_tokens.setValue(5)
    assert dialog.settings().max_tokens == 8192
    assert dialog.concurrency_values == [1, 2, 4, 8, 16, 32]
    assert dialog.settings().api_concurrency == 4
    dialog.concurrency.setValue(3)
    assert dialog.settings().api_concurrency == 8
    assert dialog.prompt.toPlainText() == DEFAULT_CAPTION_PROMPT
    assert any("OpenAI-compatible" in label.text() for label in dialog.findChildren(QLabel))
    dialog.api_key.clear()
    dialog._request_generate()
    assert "API Key" in dialog.status_label.text()


def test_v2_cloud_caption_is_embedded_tab_and_tracks_folder(tmp_path: Path) -> None:
    from PySide6.QtGui import QColor, QPixmap

    app()
    image_path = tmp_path / "solo.png"
    pixmap = QPixmap(16, 16)
    pixmap.fill(QColor("#336699"))
    pixmap.save(str(image_path))

    window = MainWindow(theme_name="dark", language="en")
    window.state.folder = tmp_path
    window._scan_finished(scan_folder(tmp_path))
    assert window.tabs.tabText(3) == "Cloud Caption"
    assert window.caption_page.folder == tmp_path
    assert window.caption_page.preview.text() == "Target images: 1"
    window.toggle_language()
    assert window.tabs.tabText(3) == "云端识别"
    assert "目标图片：1" in window.caption_page.preview.text()
    window.caption_page.api_key.clear()
    window.caption_page._request_generate()
    assert window.caption_page.status_label.isHidden()
    assert window.message_label.text() == "请输入 API Key"
    window.close()


def test_v2_caption_progress_updates_status_text() -> None:
    app()
    window = MainWindow(theme_name="dark", language="zh")
    assert not hasattr(window, "progress_bar")
    window._caption_progress(2, 5, "abc.png")
    assert window.message_label.text().endswith("云端识别 2/5")
    assert window._caption_wait_timer.isActive()
    before = window.message_label.text()
    window._tick_caption_wait()
    assert window.message_label.text().endswith("云端识别 2/5")
    assert window.message_label.text() != before
    window._stop_caption_wait()
    window.close()


def test_v2_caption_worker_overwrites_existing_txt_with_parallel_local_api(tmp_path: Path) -> None:
    from PySide6.QtGui import QColor, QPixmap
    from app.caption_api import CaptionApiSettings
    from app.ui.caption_dialog import CaptionWorker

    app()
    for index in range(3):
        image_path = tmp_path / f"img_{index}.png"
        pixmap = QPixmap(16, 16)
        pixmap.fill(QColor(30 + index, 80, 130))
        pixmap.save(str(image_path))
        image_path.with_suffix(".txt").write_text("old caption", encoding="utf-8")

    request_count = 0
    seen_images: list[str] = []
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            nonlocal request_count
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            content = body["messages"][0]["content"]
            assert any(item.get("type") == "image_url" for item in content)
            with lock:
                request_count += 1
                index = request_count
                seen_images.append(content[1]["image_url"]["url"][:32])
            payload = {"choices": [{"message": {"content": f"caption_{index}"}}]}
            data = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *_args):  # noqa: ANN002
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        settings = CaptionApiSettings(
            base_url=f"http://127.0.0.1:{server.server_port}/v1",
            model="fake-vision",
            api_key="test",
            api_concurrency=4,
            overwrite_existing=True,
        )
        for _round in range(3):
            worker = CaptionWorker(tmp_path, False, settings)
            progress: list[tuple[int, int, str]] = []
            finished: list[tuple[int, int, str]] = []
            worker.progress.connect(lambda done, total, message: progress.append((done, total, message)))
            worker.finished.connect(lambda success, failures, message: finished.append((success, failures, message)))
            worker.run()
            assert finished[-1][0] == 3
            assert finished[-1][1] == 0
            assert len(progress) >= 3
            for path in sorted(tmp_path.glob("*.txt")):
                text = path.read_text(encoding="utf-8")
                assert text.startswith("caption_")
                assert text != "old caption"
        assert request_count == 9
        assert len(seen_images) == 9
    finally:
        server.shutdown()
        server.server_close()


def test_v2_caption_scan_dedupes_same_txt_target_in_overwrite_mode(tmp_path: Path) -> None:
    from PySide6.QtGui import QColor, QPixmap
    from app.caption_api import image_files_without_txt

    app()
    for suffix, color in [(".png", "#ff0000"), (".jpg", "#00ff00")]:
        image_path = tmp_path / f"same{suffix}"
        pixmap = QPixmap(16, 16)
        pixmap.fill(QColor(color))
        pixmap.save(str(image_path))
    (tmp_path / "same.txt").write_text("old", encoding="utf-8")

    images = image_files_without_txt(tmp_path, overwrite_existing=True)
    assert len(images) == 1
    assert images[0].with_suffix(".txt") == tmp_path / "same.txt"


def test_v2_caption_targets_missing_and_empty_txt_without_overwrite(tmp_path: Path) -> None:
    from PySide6.QtGui import QColor, QPixmap
    from app.caption_api import image_files_without_txt

    app()
    expected = []
    for name, text in [("missing", None), ("empty", ""), ("tagged", "already tagged")]:
        image_path = tmp_path / f"{name}.png"
        pixmap = QPixmap(16, 16)
        pixmap.fill(QColor("#336699"))
        pixmap.save(str(image_path))
        if text is not None:
            image_path.with_suffix(".txt").write_text(text, encoding="utf-8")
        if name != "tagged":
            expected.append(image_path)

    assert set(image_files_without_txt(tmp_path, overwrite_existing=False)) == set(expected)


def test_v2_right_bottom_and_corner_resize_handles_exist() -> None:
    app()
    window = MainWindow()
    assert window.right_resize_handle.mode == "right"
    assert window.bottom_resize_handle.mode == "bottom"
    assert window.resize_handle.mode == "corner"
    before = window.geometry()
    window._resize_from_corner(20, 0)
    assert window.width() >= before.width()
    width_after_right = window.width()
    window._resize_from_corner(0, 15)
    assert window.height() >= before.height()
    height_after_bottom = window.height()
    window._resize_from_corner(25, 15)
    assert window.width() >= width_after_right
    assert window.height() >= height_after_bottom
    window.close()


def test_v2_title_bar_buttons_are_excluded_from_drag_region() -> None:
    app()
    window = MainWindow()
    window.resize(1200, 760)
    window.show()
    QApplication.processEvents()
    title_center = window.title_bar.title_label.mapTo(window.title_bar, window.title_bar.title_label.rect().center())
    max_center = window.title_bar.max_button.mapTo(window.title_bar, window.title_bar.max_button.rect().center())
    close_center = window.title_bar.close_button.mapTo(window.title_bar, window.title_bar.close_button.rect().center())
    assert window.title_bar._is_caption_point(title_center) is True
    assert window.title_bar._is_caption_point(max_center) is False
    assert window.title_bar._is_caption_point(close_center) is False
    window.close()
