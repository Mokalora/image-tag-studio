from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QLocale, QObject, QPoint, QRect, QThread, QTimer, Qt, Signal
from PySide6.QtGui import QCloseEvent, QColor, QCursor, QIcon, QKeySequence, QPalette, QShortcut
from PySide6.QtWidgets import QApplication, QCheckBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSplitter, QTabWidget, QVBoxLayout, QWidget
from qframelesswindow import FramelessWindow

from app.constants import APP_NAME
from app.logging_utils import install_excepthook, log_exception
from app.models import PreviewChange, TagFile
from app.operations import apply_changes, build_tag_stats, preview_add, preview_delete, preview_format, preview_replace
from app.save_service import restore_deleted_files, save_files
from app.scanner import scan_folder
from app.state import StudioState
from app.startup_trace import install_startup_trace, trace_point
from app.tag_parser import parse_tags
from app.thumbs import ThumbnailService
from app.ui import palette
from app.ui.batch_page import BatchPage
from app.ui.app_dialog import ConfirmDialog
from app.ui.caption_dialog import CaptionPage, CaptionWorker
from app.ui.completion import TabCompleteLineEdit
from app.ui.current_page import CurrentPage
from app.ui.file_panel import FilePanel
from app.ui.resize_handle import ResizeHandle
from app.ui.tag_overview import TagOverview
from app.ui.theme import style_for_theme
from app.ui.title_bar import TitleBar


class ScanWorker(QObject):
    finished = Signal(list)
    failed = Signal(str)

    def __init__(self, folder: Path, recursive: bool) -> None:
        super().__init__()
        self.folder = folder
        self.recursive = recursive

    def run(self) -> None:
        try:
            self.finished.emit(scan_folder(self.folder, self.recursive))
        except Exception as exc:  # noqa: BLE001
            log_exception("scan failed", exc)
            self.failed.emit(str(exc))


def system_language() -> str:
    language = QLocale.system().language()
    return "zh" if language in {QLocale.Chinese, QLocale.Cantonese} else "en"


def system_theme() -> str:
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
                apps_use_light, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return "light" if int(apps_use_light) else "dark"
        except Exception:  # noqa: BLE001
            pass
    return "light" if QApplication.palette().window().color().lightness() > 128 else "dark"


class MainWindow(FramelessWindow):
    def __init__(self, theme_name: str | None = None, language: str | None = None) -> None:
        super().__init__()
        if hasattr(self, "titleBar"):
            self.titleBar.hide()
        self.setWindowTitle(APP_NAME)
        self.setAutoFillBackground(True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.resize(1540, 900)
        self.setMinimumSize(1100, 680)
        icon_path = Path(__file__).resolve().parent / "assets" / "app_icon.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self._window_state_transitioning = False
        self.state = StudioState()
        self.theme_name = theme_name or system_theme()
        self.language = language or system_language()
        self._caption_wait_phase = 0
        self._caption_status_base = ""
        palette.set_theme(self.theme_name)
        self.thumbs = ThumbnailService(self)
        self.scan_thread: QThread | None = None
        self.scan_worker: ScanWorker | None = None
        self._build_ui()
        self._connect()
        self.apply_theme(show_toast=False)
        self.apply_language()
        self.refresh_all()
        QTimer.singleShot(0, self._stabilize_initial_layout)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)
        self.title_bar = TitleBar()
        root.addWidget(self.title_bar)

        bar = QFrame()
        bar.setProperty("panel", True)
        bar_layout = QHBoxLayout(bar)
        self.open_button = QPushButton("打开目录")
        self.rescan_button = QPushButton("重新扫描")
        self.save_button = QPushButton("保存修改")
        self.save_button.setProperty("primary", True)
        self.undo_button = QPushButton("撤销修改")
        self.recursive = QCheckBox("递归扫描")
        self.keep_backup = QCheckBox("保留备份")
        self.search = TabCompleteLineEdit()
        self.search.setPlaceholderText("搜索文件名或标签")
        for widget in [self.open_button, self.rescan_button, self.save_button, self.undo_button, self.recursive, self.keep_backup, self.search]:
            bar_layout.addWidget(widget)
        bar_layout.setStretchFactor(self.search, 1)
        self.status = QPushButton("0 文件 · 0 标签 · 0 未保存")
        self.status.setEnabled(False)
        bar_layout.addWidget(self.status)
        root.addWidget(bar)

        splitter = QSplitter(Qt.Horizontal)
        self.file_panel = FilePanel(self.thumbs)
        splitter.addWidget(self.file_panel)
        self.tabs = QTabWidget()
        self.current_page = CurrentPage()
        self.batch_page = BatchPage()
        self.tag_page = TagOverview()
        self.caption_page = CaptionPage(self.state.folder, self.recursive.isChecked(), self.language)
        self.tabs.addTab(self.current_page, "当前文件")
        self.tabs.addTab(self.batch_page, "批量修改")
        self.tabs.addTab(self.tag_page, "标签总览")
        self.tabs.addTab(self.caption_page, "云端识别")
        self.message_bar = QWidget(self)
        self.message_bar.setFixedWidth(560)
        self.message_bar.setFixedHeight(32)
        self.message_bar.setObjectName("StatusOverlay")
        self.message_bar.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.message_bar.setAttribute(Qt.WA_TranslucentBackground, True)
        self.message_bar.setStyleSheet("QWidget#StatusOverlay { background: transparent; border: none; }")
        message_layout = QHBoxLayout(self.message_bar)
        message_layout.setContentsMargins(0, 0, 0, 0)
        self.message_label = QLabel("")
        self.message_label.setObjectName("StatusMessage")
        self.message_label.setProperty("muted", True)
        self.message_label.setWordWrap(False)
        self.message_label.setMinimumWidth(560)
        self.message_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.message_label.setStyleSheet("QLabel#StatusMessage { background: transparent; border: none; }")
        message_layout.addWidget(self.message_label, 1)
        self.message_bar.raise_()
        splitter.addWidget(self.tabs)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([390, 1130])
        splitter.splitterMoved.connect(lambda _pos, _index: self._position_message_bar())
        self.main_splitter = splitter
        root.addWidget(splitter, 1)
        self.right_resize_handle = ResizeHandle(self, mode="right")
        self.bottom_resize_handle = ResizeHandle(self, mode="bottom")
        self.resize_handle = ResizeHandle(self, mode="corner")

    def _connect(self) -> None:
        self.title_bar.minimize_requested.connect(self.showMinimized)
        self.title_bar.maximize_requested.connect(self._toggle_max)
        self.title_bar.close_requested.connect(self.close)
        self.title_bar.theme_toggle_requested.connect(self.toggle_theme)
        self.title_bar.language_toggle_requested.connect(self.toggle_language)
        self.right_resize_handle.resize_delta.connect(self._resize_from_corner)
        self.bottom_resize_handle.resize_delta.connect(self._resize_from_corner)
        self.resize_handle.resize_delta.connect(self._resize_from_corner)
        self.open_button.clicked.connect(self.choose_folder)
        self.rescan_button.clicked.connect(self.rescan)
        self.save_button.clicked.connect(self.save_all)
        self.undo_button.clicked.connect(self.undo)
        self.caption_page.generate_requested.connect(self._start_caption_generation)
        self.caption_page.message_requested.connect(self._toast)
        self._caption_wait_timer = QTimer(self)
        self._caption_wait_timer.setInterval(180)
        self._caption_wait_timer.timeout.connect(self._tick_caption_wait)
        self.search.textChanged.connect(self._search_changed)
        self.recursive.toggled.connect(lambda checked: self.caption_page.set_context(self.state.folder, checked))
        self.file_panel.file_selected.connect(self._select_file)
        self.file_panel.file_activated.connect(self._activate_file)
        self.file_panel.delete_requested.connect(self._delete_tag_file)
        self.current_page.changed.connect(self._current_changed)
        self.current_page.previous_requested.connect(lambda: self._navigate_current_file(-1))
        self.current_page.next_requested.connect(lambda: self._navigate_current_file(1))
        self.batch_page.apply_requested.connect(self._apply_batch)
        self.batch_page.batch_inputs_changed.connect(self._refresh_batch_preview)
        self.batch_page.operation_switch._group.idClicked.connect(lambda _: self._refresh_batch_preview())
        self.batch_page.scope._group.idClicked.connect(lambda _: self._refresh_batch_preview())
        self.batch_page.scope_tag.textChanged.connect(self._update_scope_tag_hint)
        self.tag_page.rows_refresh_requested.connect(self.refresh_tag_page)
        self.tag_page.filter_changed.connect(self._filter_by_tags)
        self._create_shortcuts()

    def _create_shortcuts(self) -> None:
        self._shortcuts = [
            self._shortcut("Ctrl+S", self.save_all),
            self._shortcut("Ctrl+Z", self.undo),
            self._shortcut("Ctrl+Shift+Z", self.redo),
            self._shortcut("Ctrl+F", self.search.setFocus),
            self._shortcut("Ctrl+R", self.rescan),
        ]

    def _shortcut(self, sequence: str, callback) -> QShortcut:
        shortcut = QShortcut(QKeySequence(sequence), self)
        shortcut.activated.connect(callback)
        return shortcut

    def nativeEvent(self, event_type, message):  # noqa: N802, ANN001
        if sys.platform == "win32" and hasattr(self, "title_bar"):
            try:
                import ctypes
                import ctypes.wintypes

                msg = ctypes.wintypes.MSG.from_address(int(message))
                if msg.message == 0x0084:  # WM_NCHITTEST
                    x = ctypes.c_short(msg.lParam & 0xFFFF).value
                    y = ctypes.c_short((msg.lParam >> 16) & 0xFFFF).value
                    button = self._title_button_at(QPoint(x, y))
                    if button:
                        return True, 1  # HTCLIENT
                if msg.message == 0x00A1:  # WM_NCLBUTTONDOWN
                    if msg.wParam == 8:  # HTMINBUTTON
                        self.showMinimized()
                        return True, 0
                    if msg.wParam == 9:  # HTMAXBUTTON
                        self._toggle_max()
                        return True, 0
                    if msg.wParam == 20:  # HTCLOSE
                        self.close()
                        return True, 0
                if msg.message in {0x0201, 0x00A1}:  # WM_LBUTTONDOWN / WM_NCLBUTTONDOWN
                    button = self._title_button_at(QCursor.pos())
                    if button:
                        self._pressed_title_button = button
                        button.setDown(True)
                        return True, 0
                if msg.message in {0x0202, 0x00A2}:  # WM_LBUTTONUP / WM_NCLBUTTONUP
                    pressed = getattr(self, "_pressed_title_button", None)
                    if pressed:
                        pressed.setDown(False)
                        self._pressed_title_button = None
                        if pressed is self._title_button_at(QCursor.pos()):
                            self._activate_title_button(pressed)
                        return True, 0
            except Exception as exc:  # noqa: BLE001
                log_exception("title button native dispatch failed", exc)
        return super().nativeEvent(event_type, message)

    def _title_button_at(self, global_pos: QPoint):
        for button in [self.title_bar.theme_button, self.title_bar.language_button, self.title_bar.min_button, self.title_bar.max_button, self.title_bar.close_button]:
            top_left = button.mapToGlobal(QPoint(0, 0))
            if QRect(top_left, button.size()).contains(global_pos):
                return button
        return None

    def _activate_title_button(self, button) -> None:  # noqa: ANN001
        if button is self.title_bar.min_button:
            self.showMinimized()
        elif button is self.title_bar.max_button:
            self._toggle_max()
        elif button is self.title_bar.close_button:
            self.close()
        elif button is self.title_bar.theme_button:
            self.toggle_theme()
        elif button is self.title_bar.language_button:
            self.toggle_language()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.resize_handle.move(self.width() - self.resize_handle.width() - 8, self.height() - self.resize_handle.height() - 8)
        self.right_resize_handle.move(self.width() - self.right_resize_handle.width() - 2, max(80, (self.height() - self.right_resize_handle.height()) // 2))
        self.bottom_resize_handle.move(max(80, (self.width() - self.bottom_resize_handle.width()) // 2), self.height() - self.bottom_resize_handle.height() - 2)
        self._position_message_bar()

    def changeEvent(self, event) -> None:  # noqa: N802
        super().changeEvent(event)
        self._sync_window_state_controls()
        if hasattr(self, "file_panel"):
            QTimer.singleShot(0, self.file_panel._sync_grid_metrics)

    def _toggle_max(self) -> None:
        if self._window_state_transitioning:
            return
        self._window_state_transitioning = True
        if self._is_effectively_maximized():
            self._restore_from_maximized()
        else:
            self._maximize_window()
        self._schedule_window_state_sync()

    def _maximize_window(self) -> None:
        if sys.platform == "win32":
            try:
                import win32con
                import win32gui

                win32gui.ShowWindow(int(self.winId()), win32con.SW_MAXIMIZE)
                return
            except Exception as exc:  # noqa: BLE001
                log_exception("win32 maximize failed", exc)
        self.showMaximized()

    def _is_effectively_maximized(self) -> bool:
        if self.isMaximized():
            return True
        if sys.platform != "win32":
            return False
        try:
            import win32con
            import win32gui

            return win32gui.GetWindowPlacement(int(self.winId()))[1] == win32con.SW_SHOWMAXIMIZED
        except Exception as exc:  # noqa: BLE001
            log_exception("read maximized state failed", exc)
            return False

    def _restore_from_maximized(self) -> None:
        if sys.platform == "win32":
            try:
                import win32con
                import win32gui

                win32gui.ShowWindow(int(self.winId()), win32con.SW_RESTORE)
                return
            except Exception as exc:  # noqa: BLE001
                log_exception("win32 restore failed", exc)
        self.showNormal()

    def _schedule_window_state_sync(self) -> None:
        for delay in (0, 80, 180):
            QTimer.singleShot(delay, self._sync_window_state_controls)
        if hasattr(self, "file_panel"):
            QTimer.singleShot(180, self.file_panel._sync_grid_metrics)
        QTimer.singleShot(220, self._finish_window_state_transition)

    def _finish_window_state_transition(self) -> None:
        self._window_state_transitioning = False
        self._sync_window_state_controls()

    def _sync_window_state_controls(self) -> None:
        if not all(hasattr(self, name) for name in ("title_bar", "resize_handle", "right_resize_handle", "bottom_resize_handle")):
            return
        maximized = self._is_effectively_maximized()
        self.title_bar.set_maximized(maximized)
        self.resize_handle.setVisible(not maximized)
        self.right_resize_handle.setVisible(not maximized)
        self.bottom_resize_handle.setVisible(not maximized)

    def _stabilize_initial_layout(self) -> None:
        self.main_splitter.setSizes([390, max(900, self.width() - 430)])
        self.file_panel.stabilize_grid_layout()
        self._position_message_bar()
        QTimer.singleShot(120, self.file_panel._sync_grid_metrics)

    def _position_message_bar(self) -> None:
        if not hasattr(self, "message_bar"):
            return
        right_margin = 16
        tab_y_offset = 2
        x = self.tabs.x() + self.tabs.width() - self.message_bar.width() - right_margin
        y = self.main_splitter.y() + tab_y_offset
        self.message_bar.move(max(self.tabs.x(), x), y)
        self.message_bar.raise_()

    def _resize_from_corner(self, dx: int, dy: int) -> None:
        if self.isMaximized():
            return
        self.resize(max(self.minimumWidth(), self.width() + dx), max(self.minimumHeight(), self.height() + dy))

    def choose_folder(self) -> None:
        title = "Choose Image Folder" if self.language == "en" else "选择图片目录"
        folder = QFileDialog.getExistingDirectory(self, title)
        if not folder:
            return
        self.state.folder = Path(folder)
        self.title_bar.set_path(str(self.state.folder))
        self.caption_page.set_context(self.state.folder, self.recursive.isChecked())
        self.rescan()

    def _caption_finished(self, success: int, failures: int, _message: str = "") -> None:
        self._toast(f"Generated {success} TXT files, {failures} failed" if self.language == "en" else f"已生成 {success} 个 TXT，失败 {failures} 个")
        if self.state.folder:
            self.rescan()

    def _start_caption_generation(self, settings) -> None:  # noqa: ANN001
        if not self.state.folder:
            self._toast("Open a folder first" if self.language == "en" else "请先打开目录")
            return
        if getattr(self, "caption_thread", None):
            self._toast("Caption task is already running" if self.language == "en" else "云端识别正在运行")
            return
        self.caption_thread = QThread(self)
        self.caption_worker = CaptionWorker(self.state.folder, self.recursive.isChecked(), settings)
        self.caption_worker.moveToThread(self.caption_thread)
        self.caption_thread.started.connect(self.caption_worker.run)
        self.caption_worker.progress.connect(self._caption_progress)
        self.caption_worker.finished.connect(self._caption_finished)
        self.caption_worker.failed.connect(self._caption_failed)
        self.caption_worker.finished.connect(self.caption_thread.quit)
        self.caption_worker.failed.connect(self.caption_thread.quit)
        self.caption_thread.finished.connect(self._caption_cleanup)
        self.caption_thread.start()
        self._start_caption_wait("Captioning 0/..." if self.language == "en" else "云端识别 0/...")

    def _caption_progress(self, done: int, total: int, filename: str) -> None:
        del filename
        if self.language == "en":
            self._start_caption_wait(f"Captioning {done}/{total}")
        else:
            self._start_caption_wait(f"云端识别 {done}/{total}")

    def _caption_failed(self, message: str) -> None:
        self._toast(f"Caption failed: {message}" if self.language == "en" else f"云端识别失败：{message}")

    def _caption_cleanup(self) -> None:
        if getattr(self, "caption_worker", None):
            self.caption_worker.deleteLater()
        if getattr(self, "caption_thread", None):
            self.caption_thread.deleteLater()
        self.caption_worker = None
        self.caption_thread = None
        self._stop_caption_wait()

    def _start_caption_wait(self, text: str) -> None:
        self._caption_status_base = text
        self._caption_wait_phase = 0
        self._update_caption_wait_text()
        if not self._caption_wait_timer.isActive():
            self._caption_wait_timer.start()

    def _tick_caption_wait(self) -> None:
        self._caption_wait_phase = (self._caption_wait_phase + 1) % 6
        self._update_caption_wait_text()

    def _update_caption_wait_text(self) -> None:
        frames = ["◐", "◓", "◑", "◒", "◑", "◓"]
        self.message_label.setText(f"{frames[self._caption_wait_phase]} {self._caption_status_base}")

    def _stop_caption_wait(self) -> None:
        if self._caption_wait_timer.isActive():
            self._caption_wait_timer.stop()
        self._caption_status_base = ""

    def rescan(self) -> None:
        if not self.state.folder or self.scan_thread:
            return
        self.scan_thread = QThread(self)
        self.scan_worker = ScanWorker(self.state.folder, self.recursive.isChecked())
        self.scan_worker.moveToThread(self.scan_thread)
        self.scan_thread.started.connect(self.scan_worker.run)
        self.scan_worker.finished.connect(self._scan_finished)
        self.scan_worker.failed.connect(lambda text: self._toast((f"Scan failed: {text}" if self.language == "en" else f"扫描失败：{text}")))
        self.scan_worker.finished.connect(self.scan_thread.quit)
        self.scan_worker.failed.connect(self.scan_thread.quit)
        self.scan_thread.finished.connect(self._scan_cleanup)
        self.scan_thread.start()

    def _scan_finished(self, files: list[TagFile]) -> None:
        self.state.set_files(files)
        self.search.clear()
        self.refresh_all()
        self._refresh_batch_preview()
        self.caption_page.set_context(self.state.folder, self.recursive.isChecked())
        self.file_panel.stabilize_grid_layout()

    def _scan_cleanup(self) -> None:
        if self.scan_worker:
            self.scan_worker.deleteLater()
        if self.scan_thread:
            self.scan_thread.deleteLater()
        self.scan_worker = None
        self.scan_thread = None

    def refresh_all(self) -> None:
        self.refresh_files()
        self.current_page.set_file(self.state.current_file())
        self.refresh_tag_page()
        self.refresh_status()

    def refresh_files(self) -> None:
        self.file_panel.set_files(self.state.filtered_files(), self.state.current_path)
        self.file_panel.set_filter_summary(self._filter_summary())

    def refresh_tag_page(self) -> None:
        rows = build_tag_stats(self.state.files)
        self.tag_page.set_rows(rows)
        tags = sorted(row.tag for row in rows)
        self.search.set_suggestions(sorted({item.filename for item in self.state.files} | set(tags)))
        self.batch_page.set_tag_suggestions(tags)
        self._update_scope_tag_hint()
        self._refresh_batch_preview()

    def refresh_status(self) -> None:
        total_tags = sum(item.tag_count for item in self.state.files)
        if self.language == "en":
            self.status.setText(f"{len(self.state.files)} files · {total_tags} labels · {len(self.state.modified_files())} unsaved")
        else:
            self.status.setText(f"{len(self.state.files)} 文件 · {total_tags} 标签 · {len(self.state.modified_files())} 未保存")

    def _search_changed(self, text: str) -> None:
        self.state.search_text = text
        self.refresh_files()

    def _select_file(self, path: Path) -> None:
        self.current_page.apply_pending()
        self.state.current_path = path
        self.current_page.set_file(self.state.current_file())

    def _activate_file(self, path: Path) -> None:
        self._select_file(path)
        self.tabs.setCurrentIndex(0)

    def _navigate_current_file(self, step: int) -> None:
        files = self.state.filtered_files()
        if not files:
            return
        current_path = self.state.current_path
        index = next((idx for idx, item in enumerate(files) if item.path == current_path), 0)
        next_file = files[(index + step) % len(files)]
        self._select_file(next_file.path)
        self.refresh_files()

    def _delete_tag_file(self, path: Path) -> None:
        tag_file = next((item for item in self.state.files if item.path == path), None)
        if not tag_file or tag_file.pending_delete:
            return
        self.state.push_undo(
            "Delete file" if self.language == "en" else "\u5220\u9664\u6587\u4ef6",
            [
                PreviewChange(
                    tag_file.path,
                    tag_file.filename,
                    list(tag_file.tags),
                    list(tag_file.tags),
                    before_pending_delete=False,
                    after_pending_delete=True,
                )
            ],
        )
        tag_file.pending_delete = True
        tag_file.delete_saved = False
        tag_file.modified = True
        if self.state.current_path == path:
            visible = self.state.filtered_files()
            self.state.current_path = visible[0].path if visible else None
        self.refresh_all()
        self._toast("Deletion buffered" if self.language == "en" else "\u5df2\u6682\u5b58\u5220\u9664\u64cd\u4f5c")

    def _current_changed(self, message: str) -> None:
        current = self.state.current_file()
        if current:
            before_tags = self.current_page.last_before_tags or list(current.original_tags)
            self.state.push_undo(
                message,
                [
                    PreviewChange(
                        current.path,
                        current.filename,
                        list(before_tags),
                        list(current.tags),
                    )
                ],
            )
            self.current_page.last_before_tags = None
        self.refresh_all()
        self._toast(message)

    def _target_files(self) -> list[TagFile]:
        mode = self.batch_page.scope.currentIndex()
        if mode == 1:
            selected = self.file_panel.selected_files()
            return selected or ([self.state.current_file()] if self.state.current_file() else [])
        if mode == 2:
            return self.state.filtered_files()
        if mode == 3:
            tag = self.batch_page.scope_tag.text().strip()
            return [item for item in self.state.files if tag and tag in item.tags]
        return list(self.state.files)

    def _update_scope_tag_hint(self) -> None:
        text = self.batch_page.scope_tag.text().strip()
        if not text:
            self.batch_page.set_scope_tag_exists(None)
            self._refresh_batch_preview()
            return
        self.batch_page.set_scope_tag_exists(any(text == tag for item in self.state.files for tag in item.tags))
        self._refresh_batch_preview()

    def _build_batch_changes(self, op: str) -> list[PreviewChange]:
        files = self._target_files()
        if op == "add":
            tags = parse_tags(self.batch_page.add_input.text())
            position = "start" if self.batch_page.add_position.currentIndex() == 0 else "end"
            return preview_add(files, tags, position, self.batch_page.add_skip.isChecked(), self.batch_page.add_case.isChecked())
        if op == "delete":
            return preview_delete(files, parse_tags(self.batch_page.delete_input.text()), self.batch_page.delete_case.isChecked(), self.batch_page.delete_contains.isChecked())
        if op == "format":
            return preview_format(files)
        return preview_replace(
            files,
            self.batch_page.replace_from.text().strip(),
            self.batch_page.replace_to.text().strip(),
            self.batch_page.replace_case.isChecked(),
            self.batch_page.replace_contains.isChecked(),
            self.batch_page.replace_dedupe.isChecked(),
        )

    def _build_delete_file_targets(self) -> list[TagFile]:
        targets = parse_tags(self.batch_page.delete_input.text())
        if not targets:
            return []
        matched: list[TagFile] = []
        for item in self._target_files():
            if item.pending_delete:
                continue
            if preview_delete([item], targets, self.batch_page.delete_case.isChecked(), self.batch_page.delete_contains.isChecked()):
                matched.append(item)
        return matched

    def _refresh_batch_preview(self) -> None:
        if not hasattr(self, "batch_page"):
            return
        for op in ["add", "delete", "delete_files", "replace", "format"]:
            empty_input = {
                "add": not self.batch_page.add_input.text().strip(),
                "delete": not self.batch_page.delete_input.text().strip(),
                "delete_files": not self.batch_page.delete_input.text().strip(),
                "replace": not self.batch_page.replace_from.text().strip(),
                "format": False,
            }[op]
            if op == "delete_files":
                count = len(self._target_files()) if empty_input else len(self._build_delete_file_targets())
            else:
                count = len(self._target_files()) if empty_input else len(self._build_batch_changes(op))
            self.batch_page.set_preview_summary(op, count, is_scope_count=empty_input)

    def _apply_batch(self, op: str) -> None:
        if op == "delete_files":
            changes = [
                PreviewChange(
                    item.path,
                    item.filename,
                    list(item.tags),
                    list(item.tags),
                    before_pending_delete=item.pending_delete,
                    after_pending_delete=True,
                )
                for item in self._build_delete_file_targets()
            ]
            if not changes:
                self._toast("No files can be modified" if self.language == "en" else "没有可修改的文件")
                return
            self.state.push_undo("Batch delete files" if self.language == "en" else "批量删除文件", changes)
            for change in changes:
                tag_file = next((item for item in self.state.files if item.path == change.file_path), None)
                if tag_file:
                    tag_file.pending_delete = True
                    tag_file.delete_saved = False
                    tag_file.modified = True
            if self.state.current_path and not self.state.current_file():
                visible = self.state.filtered_files()
                self.state.current_path = visible[0].path if visible else None
            count = len(changes)
            self.batch_page.summary.setText(f"Buffered {count} files" if self.language == "en" else f"已暂存 {count} 个文件")
            self.refresh_all()
            self._refresh_batch_preview()
            self._toast(f"Buffered {count} files" if self.language == "en" else f"已暂存 {count} 个文件")
            return
        changes = self._build_batch_changes(op)
        if not changes:
            self._toast("No files can be modified" if self.language == "en" else "没有可修改的文件")
            return
        self.state.push_undo("Batch operation" if self.language == "en" else "批量操作", changes)
        count = apply_changes(self.state.files, changes)
        self.batch_page.summary.setText(f"Buffered {count} files" if self.language == "en" else f"已暂存 {count} 个文件")
        self.refresh_all()
        self._refresh_batch_preview()
        self._toast(f"Buffered {count} files" if self.language == "en" else f"已暂存 {count} 个文件")

    def _filter_by_tags(self, tags: list[str], mode: str, display_mode: str) -> None:
        self.state.filter_tags = tags
        self.state.filter_mode = mode
        self.state.filter_display_mode = display_mode
        self.refresh_files()
        self.refresh_status()

    def _filter_summary(self) -> str:
        parts: list[str] = []
        search = self.state.search_text.strip()
        if search:
            parts.append(f"Search: {search}" if self.language == "en" else f"搜索：{search}")
        if self.state.filter_tags:
            relation = ("AND" if self.state.filter_mode == "and" else "OR") if self.language == "en" else ("与" if self.state.filter_mode == "and" else "或")
            display = ("Show" if self.state.filter_display_mode == "positive" else "Hide") if self.language == "en" else ("正" if self.state.filter_display_mode == "positive" else "反")
            tags = sorted(self.state.filter_tags)
            shown = ", ".join(tags[:3]) if self.language == "en" else "，".join(tags[:3])
            suffix = "" if len(tags) <= 3 else (f" and {len(tags)} total" if self.language == "en" else f" 等 {len(tags)} 个")
            parts.append(f"Labels {relation}/{display}: {shown}{suffix}" if self.language == "en" else f"标签{relation}/{display}：{shown}{suffix}")
        if self.language == "en":
            return "Filter: All" if not parts else "Filter: " + "; ".join(parts)
        return "筛选：全部" if not parts else "筛选：" + "；".join(parts)

    def toggle_theme(self) -> None:
        self.theme_name = "light" if self.theme_name == "dark" else "dark"
        self.apply_theme()

    def apply_theme(self, show_toast: bool = True) -> None:
        palette.set_theme(self.theme_name)
        self._apply_window_background()
        self._apply_windows_frame_colors()
        app = QApplication.instance()
        if app:
            app.setStyleSheet(style_for_theme(self.theme_name))
        self.setProperty("theme", self.theme_name)
        self.title_bar.set_theme(self.theme_name)
        self.file_panel.apply_theme()
        self.current_page.apply_theme()
        self.tag_page.apply_theme()
        self.caption_page.style().unpolish(self.caption_page)
        self.caption_page.style().polish(self.caption_page)
        self.message_label.style().unpolish(self.message_label)
        self.message_label.style().polish(self.message_label)
        if show_toast:
            self._toast("Light theme" if self.language == "en" and self.theme_name == "light" else "Dark theme" if self.language == "en" else "已切换浅色主题" if self.theme_name == "light" else "已切换暗色主题")

    def _apply_window_background(self) -> None:
        color = QColor("#F4F7FB" if self.theme_name == "light" else "#0F131A")
        window_palette = self.palette()
        window_palette.setColor(QPalette.Window, color)
        self.setPalette(window_palette)
        self.update()

    def _apply_windows_frame_colors(self) -> None:
        if sys.platform != "win32":
            return
        try:
            import ctypes
            from ctypes import byref, c_int, c_uint

            hwnd = int(self.winId())
            dark = c_int(1 if self.theme_name == "dark" else 0)
            # 20 is DWMWA_USE_IMMERSIVE_DARK_MODE on current Windows 10/11; 19 is the older alias.
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, byref(dark), ctypes.sizeof(dark))
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 19, byref(dark), ctypes.sizeof(dark))
            if self.theme_name == "dark":
                border = c_uint(0x001A130F)
            else:
                border = c_uint(0x00FBF7F4)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 34, byref(border), ctypes.sizeof(border))
        except Exception as exc:  # noqa: BLE001
            log_exception("apply windows frame colors failed", exc)

    def toggle_language(self) -> None:
        self.language = "en" if self.language == "zh" else "zh"
        self.apply_language()
        self._toast("Language: English" if self.language == "en" else "语言：中文")

    def apply_language(self) -> None:
        if self.language == "en":
            self.open_button.setText("Open Folder")
            self.rescan_button.setText("Rescan")
            self.save_button.setText("Save Changes")
            self.undo_button.setText("Undo Changes")
            self.recursive.setText("Recursive")
            self.keep_backup.setText("Keep Backups")
            self.search.setPlaceholderText("Search filename or label")
            self.tabs.setTabText(0, "Current File")
            self.tabs.setTabText(1, "Batch Edit")
            self.tabs.setTabText(2, "Label Overview")
            self.tabs.setTabText(3, "Cloud Caption")
        else:
            self.open_button.setText("打开目录")
            self.rescan_button.setText("重新扫描")
            self.save_button.setText("保存修改")
            self.undo_button.setText("撤销修改")
            self.recursive.setText("递归扫描")
            self.keep_backup.setText("保留备份")
            self.search.setPlaceholderText("搜索文件名或标签")
            self.tabs.setTabText(0, "当前文件")
            self.tabs.setTabText(1, "批量修改")
            self.tabs.setTabText(2, "标签总览")
            self.tabs.setTabText(3, "云端识别")
        self.file_panel.apply_language(self.language)
        self.batch_page.apply_language(self.language)
        self.current_page.apply_language(self.language)
        self.tag_page.apply_language(self.language)
        self.caption_page.apply_language(self.language)
        self.refresh_status()
        self.file_panel.set_filter_summary(self._filter_summary())
        self._update_scope_tag_hint()
        self._refresh_batch_preview()

    def undo(self) -> None:
        if not self.state.undo_stack:
            self._toast("Nothing to undo" if self.language == "en" else "\u6ca1\u6709\u53ef\u64a4\u9500\u7684\u64cd\u4f5c")
            return
        group = self.state.undo_stack.pop()
        self.state.redo_stack.append(group)
        for change in group.changes:
            for tag_file in self.state.files:
                if tag_file.path == change.file_path:
                    if tag_file.delete_saved and change.before_pending_delete is False:
                        restore_deleted_files(tag_file)
                    tag_file.pending_delete = change.before_pending_delete
                    tag_file.delete_saved = False
                    tag_file.tags = list(change.before_tags)
                    from app.tag_parser import format_tags

                    tag_file.raw_text = format_tags(tag_file.tags)
                    tag_file.modified = tag_file.pending_delete or tag_file.raw_text != tag_file.original_text or tag_file.tags != tag_file.original_tags
        if self.state.current_path and not self.state.current_file():
            visible = self.state.filtered_files()
            self.state.current_path = visible[0].path if visible else None
        self.refresh_all()
        self._toast(f"Undone: {group.label}" if self.language == "en" else f"\u5df2\u64a4\u9500\uff1a{group.label}")

    def redo(self) -> None:
        if not self.state.redo_stack:
            self._toast("Nothing to redo" if self.language == "en" else "\u6ca1\u6709\u53ef\u91cd\u505a\u7684\u64cd\u4f5c")
            return
        group = self.state.redo_stack.pop()
        self.state.undo_stack.append(group)
        for change in group.changes:
            for tag_file in self.state.files:
                if tag_file.path == change.file_path:
                    tag_file.pending_delete = change.after_pending_delete
                    tag_file.delete_saved = False
                    tag_file.tags = list(change.after_tags)
                    from app.tag_parser import format_tags

                    tag_file.raw_text = format_tags(tag_file.tags)
                    tag_file.modified = tag_file.pending_delete or tag_file.raw_text != tag_file.original_text or tag_file.tags != tag_file.original_tags
        if self.state.current_path and not self.state.current_file():
            visible = self.state.filtered_files()
            self.state.current_path = visible[0].path if visible else None
        self.refresh_all()
        self._toast(f"Redone: {group.label}" if self.language == "en" else f"\u5df2\u91cd\u505a\uff1a{group.label}")

    def save_current(self) -> None:
        self.current_page.apply_pending()
        current = self.state.current_file()
        if not current or not current.modified:
            self._toast("Current file has no changes to save" if self.language == "en" else "当前文件没有需要保存的修改")
            return
        self._save([current])

    def save_all(self) -> None:
        self.current_page.apply_pending()
        modified = self.state.modified_files()
        if not modified:
            self._toast("No changes to save" if self.language == "en" else "没有需要保存的修改")
            return
        self._save(modified)

    def _save(self, files: list[TagFile]) -> None:
        result = save_files(files, self.keep_backup.isChecked(), allow_external_overwrite=True)
        self.refresh_all()
        if result.failures:
            self._toast(f"Failed to write {len(result.failures)} files" if self.language == "en" else f"\u5199\u5165\u5931\u8d25\uff1a{len(result.failures)} \u4e2a\u6587\u4ef6")
            return
        self._toast(f"Saved {result.saved_count} text files" if self.language == "en" else f"\u5df2\u4fdd\u5b58 {result.saved_count} \u4e2a\u6587\u672c\u6587\u4ef6")

    def _toast(self, text: str) -> None:
        text = self._localized_toast(text)
        self.message_label.setText(text)

    def _localized_toast(self, text: str) -> str:
        if self.language != "en":
            return text
        translations = {
            "删除当前标签": "Deleted current label",
            "修改当前标签": "Edited current label",
            "新增当前标签": "Added current label",
            "调整标签顺序": "Reordered labels",
            "应用文本修改": "Applied text changes",
            "没有可修改的文件": "No files can be modified",
        }
        return translations.get(text, text)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self.state.modified_files():
            title = "Unsaved Changes" if self.language == "en" else "还有未保存修改"
            text = "Some files are not saved. Exit anyway?" if self.language == "en" else "还有文件未保存，确认退出吗？"
            dialog = ConfirmDialog(title, text, "Yes" if self.language == "en" else "是", "No" if self.language == "en" else "否", self)
            if dialog.exec() != ConfirmDialog.Accepted:
                event.ignore()
                return
        event.accept()


def run() -> None:
    install_excepthook()
    trace_point("before QApplication")
    app = QApplication(sys.argv)
    trace_filter = install_startup_trace(app)
    app._startup_trace_filter = trace_filter
    initial_theme = system_theme()
    palette.set_theme(initial_theme)
    app.setStyleSheet(style_for_theme(initial_theme))
    trace_point("after QApplication and stylesheet")
    window = MainWindow(theme_name=initial_theme, language=system_language())
    trace_point("after MainWindow constructed")
    trace_point("before show")
    window.show()
    window.raise_()
    window.activateWindow()
    trace_point("after show")
    sys.exit(app.exec())
