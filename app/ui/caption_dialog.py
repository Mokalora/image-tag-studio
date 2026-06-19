from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import time

from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.caption_api import DEFAULT_CAPTION_PROMPT, CaptionApiSettings, caption_image, image_files_without_txt, ping_openai_api, write_caption_txt
from app.ui.app_dialog import AppDialog


class CaptionWorker(QObject):
    progress = Signal(int, int, str)
    finished = Signal(int, int, str)
    failed = Signal(str)

    def __init__(self, folder: Path, recursive: bool, settings: CaptionApiSettings, limit: int | None = None, write_files: bool = True) -> None:
        super().__init__()
        self.folder = folder
        self.recursive = recursive
        self.settings = settings
        self.limit = limit
        self.write_files = write_files

    def run(self) -> None:
        try:
            images = image_files_without_txt(self.folder, self.recursive, self.settings.overwrite_existing)
            if self.limit is not None:
                images = images[: self.limit]
            if not images:
                self.finished.emit(0, 0, "No images need captioning")
                return
            success = 0
            failures = 0
            last_message = ""
            max_workers = max(1, min(int(self.settings.api_concurrency or 1), len(images)))

            def process_one(image_path: Path) -> tuple[bool, str]:
                last_error: Exception | None = None
                for attempt in range(3):
                    try:
                        caption = caption_image(self.settings, image_path)
                        if self.write_files:
                            write_caption_txt(image_path, caption)
                        return True, image_path.name
                    except Exception as exc:  # noqa: BLE001
                        last_error = exc
                        if attempt < 2:
                            time.sleep(0.45 * (attempt + 1))
                return False, f"{image_path.name}: {last_error}"

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                if max_workers == 1:
                    for image_path in images:
                        ok, last_message = process_one(image_path)
                        if ok:
                            success += 1
                        else:
                            failures += 1
                        self.progress.emit(success + failures, len(images), last_message)
                else:
                    futures = [executor.submit(process_one, image_path) for image_path in images]
                    for future in as_completed(futures):
                        ok, last_message = future.result()
                        if ok:
                            success += 1
                        else:
                            failures += 1
                        self.progress.emit(success + failures, len(images), last_message)
            self.finished.emit(success, failures, last_message)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class ApiPingWorker(QObject):
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, settings: CaptionApiSettings) -> None:
        super().__init__()
        self.settings = settings

    def run(self) -> None:
        try:
            self.finished.emit(ping_openai_api(self.settings))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class CaptionPage(QWidget):
    generate_requested = Signal(object)
    message_requested = Signal(str)

    def __init__(self, folder: Path | None, recursive: bool, language: str = "zh", parent=None) -> None:
        super().__init__(parent)
        self.folder = folder
        self.recursive = recursive
        self.language = language
        self.worker_thread: QThread | None = None
        self.worker: QObject | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)
        self.intro = QLabel()
        self.intro.setProperty("muted", True)
        self.intro.setWordWrap(True)
        layout.addWidget(self.intro)

        form = QFormLayout()
        self.base_url = QLineEdit("https://api.xiaomimimo.com/v1")
        self.model = QLineEdit("mimo-v2.5")
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.Password)
        self.max_token_values = [256, 512, 1024, 2048, 4096, 8192]
        self.max_tokens = QSlider(Qt.Horizontal)
        self.max_tokens.setRange(0, len(self.max_token_values) - 1)
        self.max_tokens.setValue(0)
        self.max_tokens_label = QLabel("256")
        token_row = QHBoxLayout()
        token_row.addWidget(self.max_tokens, 1)
        token_row.addWidget(self.max_tokens_label)
        self.concurrency_values = [1, 2, 4, 8, 16, 32]
        self.concurrency = QSlider(Qt.Horizontal)
        self.concurrency.setRange(0, len(self.concurrency_values) - 1)
        self.concurrency.setValue(2)
        self.concurrency_label = QLabel("4")
        concurrency_row = QHBoxLayout()
        concurrency_row.addWidget(self.concurrency, 1)
        concurrency_row.addWidget(self.concurrency_label)
        self.overwrite = QCheckBox()
        self.prompt = QPlainTextEdit()
        self.prompt.setPlainText(DEFAULT_CAPTION_PROMPT)
        self.prompt.setMinimumHeight(180)

        self.base_label = QLabel("Base URL")
        self.model_label = QLabel()
        self.key_label = QLabel("API Key")
        self.token_label = QLabel()
        self.parallel_label = QLabel()
        self.prompt_label = QLabel()
        form.addRow(self.base_label, self.base_url)
        form.addRow(self.model_label, self.model)
        form.addRow(self.key_label, self.api_key)
        form.addRow(self.token_label, token_row)
        form.addRow(self.parallel_label, concurrency_row)
        form.addRow("", self.overwrite)
        form.addRow(self.prompt_label, self.prompt)
        layout.addLayout(form)

        info_row = QHBoxLayout()
        self.preview = QLabel("")
        self.preview.setProperty("muted", True)
        self.status_label = QLabel("")
        self.status_label.setProperty("muted", True)
        self.status_label.setWordWrap(True)
        self.status_label.hide()
        info_row.addWidget(self.preview)
        info_row.addStretch(1)
        info_row.addWidget(self.status_label)
        layout.addLayout(info_row)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.test_button = QPushButton()
        self.run_button = QPushButton()
        self.run_button.setProperty("primary", True)
        buttons.addWidget(self.test_button)
        buttons.addWidget(self.run_button)
        layout.addLayout(buttons)
        layout.addStretch(1)

        self.overwrite.toggled.connect(self._refresh_preview)
        self.max_tokens.valueChanged.connect(self._update_token_label)
        self.concurrency.valueChanged.connect(self._update_concurrency_label)
        self.test_button.clicked.connect(self._start_api_ping)
        self.run_button.clicked.connect(self._request_generate)
        self.apply_language(self.language)
        self._refresh_preview()

    def set_context(self, folder: Path | None, recursive: bool) -> None:
        self.folder = folder
        self.recursive = recursive
        self._refresh_preview()

    def apply_language(self, language: str) -> None:
        self.language = language
        if language == "en":
            self.intro.setText("OpenAI-compatible image caption API only. It generates missing or overwritten TXT files for images in the current folder")
            self.model_label.setText("Model")
            self.token_label.setText("Max tokens")
            self.parallel_label.setText("Parallel")
            self.prompt_label.setText("Prompt")
            self.overwrite.setText("Overwrite existing TXT")
            self.test_button.setText("Test API")
            self.run_button.setText("Generate TXT")
        else:
            self.intro.setText("当前仅支持 OpenAI-compatible 图像识别接口，用于为当前目录图片生成或覆盖同名 TXT 标签文本")
            self.model_label.setText("模型名称")
            self.token_label.setText("最大 Token")
            self.parallel_label.setText("并行数量")
            self.prompt_label.setText("反推提示词")
            self.overwrite.setText("覆盖已有 TXT")
            self.test_button.setText("测试 API")
            self.run_button.setText("生成 TXT")
        self._refresh_preview()

    def _update_token_label(self) -> None:
        self.max_tokens_label.setText(str(self.max_token_values[self.max_tokens.value()]))

    def _update_concurrency_label(self) -> None:
        self.concurrency_label.setText(str(self.concurrency_values[self.concurrency.value()]))

    def settings(self) -> CaptionApiSettings:
        return CaptionApiSettings(
            base_url=self.base_url.text().strip(),
            model=self.model.text().strip(),
            api_key=self.api_key.text().strip(),
            protocol="openai",
            prompt=self.prompt.toPlainText().strip(),
            max_tokens=self.max_token_values[self.max_tokens.value()],
            api_concurrency=self.concurrency_values[self.concurrency.value()],
            overwrite_existing=self.overwrite.isChecked(),
        )

    def _refresh_preview(self) -> None:
        count = 0 if not self.folder else len(image_files_without_txt(self.folder, self.recursive, self.overwrite.isChecked()))
        self.preview.setText(f"Target images: {count}" if self.language == "en" else f"目标图片：{count} 张")

    def _start_api_ping(self) -> None:
        settings = self.settings()
        if not self._validate_settings(settings, require_folder=False):
            return
        self._set_status("Testing API..." if self.language == "en" else "正在测试 API...")
        self.test_button.setEnabled(False)
        self.run_button.setEnabled(False)
        self.worker_thread = QThread(self)
        self.worker = ApiPingWorker(settings)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._ping_finished)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.failed.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self._cleanup_worker)
        self.worker_thread.start()

    def _request_generate(self) -> None:
        settings = self.settings()
        if not self._validate_settings(settings, require_folder=True):
            return
        self.generate_requested.emit(settings)

    def _validate_settings(self, settings: CaptionApiSettings, require_folder: bool) -> bool:
        if require_folder and not self.folder:
            self._set_status("Open a folder first" if self.language == "en" else "请先打开目录")
            return False
        if not settings.base_url:
            self._set_status("Base URL is required" if self.language == "en" else "请输入 Base URL")
            return False
        if not settings.model:
            self._set_status("Model is required" if self.language == "en" else "请输入模型名称")
            return False
        if not settings.api_key:
            self._set_status("API Key is required" if self.language == "en" else "请输入 API Key")
            return False
        return True

    def _ping_finished(self, message: str) -> None:
        self._set_status(f"API test succeeded: {message}" if self.language == "en" else f"API 测试成功：{message}")
        self._set_buttons_enabled(True)

    def _failed(self, message: str) -> None:
        self._set_status(message)
        self._set_buttons_enabled(True)

    def _set_status(self, message: str) -> None:
        self.status_label.setText(message)
        self.message_requested.emit(message)

    def _cleanup_worker(self) -> None:
        if self.worker:
            self.worker.deleteLater()
        if self.worker_thread:
            self.worker_thread.deleteLater()
        self.worker = None
        self.worker_thread = None

    def _set_buttons_enabled(self, enabled: bool) -> None:
        self.test_button.setEnabled(enabled)
        self.run_button.setEnabled(enabled)


class CaptionDialog(AppDialog):
    caption_finished = Signal(int, int)
    generate_requested = Signal(object)

    def __init__(self, folder: Path | None, recursive: bool, language: str = "zh", parent=None) -> None:
        super().__init__("Cloud Caption API" if language == "en" else "云端识别 API", parent)
        self.folder = folder
        self.recursive = recursive
        self.language = language
        self.worker_thread: QThread | None = None
        self.worker: QObject | None = None
        self.setMinimumWidth(720)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = self.body_layout
        intro = QLabel(
            "OpenAI-compatible image caption API only. It generates missing TXT files for images in the current folder."
            if self.language == "en"
            else "当前仅支持 OpenAI-compatible 图像识别接口。用于为当前目录里没有同名 TXT 的图片生成标签文本。"
        )
        intro.setProperty("muted", True)
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QFormLayout()
        self.base_url = QLineEdit("https://api.xiaomimimo.com/v1")
        self.model = QLineEdit("mimo-v2.5")
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.Password)
        self.max_token_values = [256, 512, 1024, 2048, 4096, 8192]
        self.max_tokens = QSlider(Qt.Horizontal)
        self.max_tokens.setRange(0, len(self.max_token_values) - 1)
        self.max_tokens.setValue(0)
        self.max_tokens_label = QLabel("256")
        token_row = QHBoxLayout()
        token_row.addWidget(self.max_tokens, 1)
        token_row.addWidget(self.max_tokens_label)
        self.concurrency_values = [1, 2, 4, 8, 16, 32]
        self.concurrency = QSlider(Qt.Horizontal)
        self.concurrency.setRange(0, len(self.concurrency_values) - 1)
        self.concurrency.setValue(2)
        self.concurrency_label = QLabel("4")
        concurrency_row = QHBoxLayout()
        concurrency_row.addWidget(self.concurrency, 1)
        concurrency_row.addWidget(self.concurrency_label)
        self.overwrite = QCheckBox("Overwrite existing TXT" if self.language == "en" else "覆盖已有 TXT")
        self.prompt = QPlainTextEdit()
        self.prompt.setPlainText(DEFAULT_CAPTION_PROMPT)
        self.prompt.setMinimumHeight(120)

        form.addRow("Base URL", self.base_url)
        form.addRow("Model" if self.language == "en" else "模型名称", self.model)
        form.addRow("API Key", self.api_key)
        form.addRow("Max tokens" if self.language == "en" else "最大 Token", token_row)
        form.addRow("Parallel" if self.language == "en" else "并行数量", concurrency_row)
        form.addRow("", self.overwrite)
        form.addRow("Prompt" if self.language == "en" else "反推提示词", self.prompt)
        layout.addLayout(form)

        self.preview = QLabel("")
        self.preview.setProperty("muted", True)
        layout.addWidget(self.preview)
        self.status_label = QLabel("")
        self.status_label.setProperty("muted", True)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        self._refresh_preview()

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.test_button = QPushButton("Test API" if self.language == "en" else "测试 API")
        self.run_button = QPushButton("Generate TXT" if self.language == "en" else "生成 TXT")
        self.run_button.setProperty("primary", True)
        self.cancel_button = QPushButton("Close" if self.language == "en" else "关闭")
        buttons.addWidget(self.test_button)
        buttons.addWidget(self.run_button)
        buttons.addWidget(self.cancel_button)
        layout.addLayout(buttons)

        self.overwrite.toggled.connect(self._refresh_preview)
        self.max_tokens.valueChanged.connect(self._update_token_label)
        self.concurrency.valueChanged.connect(self._update_concurrency_label)
        self.test_button.clicked.connect(self._start_api_ping)
        self.run_button.clicked.connect(self._request_generate)
        self.cancel_button.clicked.connect(self.reject)

    def _update_token_label(self) -> None:
        self.max_tokens_label.setText(str(self.max_token_values[self.max_tokens.value()]))

    def _update_concurrency_label(self) -> None:
        self.concurrency_label.setText(str(self.concurrency_values[self.concurrency.value()]))

    def settings(self) -> CaptionApiSettings:
        return CaptionApiSettings(
            base_url=self.base_url.text().strip(),
            model=self.model.text().strip(),
            api_key=self.api_key.text().strip(),
            protocol="openai",
            prompt=self.prompt.toPlainText().strip(),
            max_tokens=self.max_token_values[self.max_tokens.value()],
            api_concurrency=self.concurrency_values[self.concurrency.value()],
            overwrite_existing=self.overwrite.isChecked(),
        )

    def _refresh_preview(self) -> None:
        if not self.folder:
            count = 0
        else:
            count = len(image_files_without_txt(self.folder, self.recursive, self.overwrite.isChecked()))
        if self.language == "en":
            self.preview.setText(f"Target images: {count}")
        else:
            self.preview.setText(f"目标图片：{count} 张")

    def _start_api_ping(self) -> None:
        settings = self.settings()
        if not self._validate_settings(settings, require_folder=False):
            return
        self.status_label.setText("Testing API..." if self.language == "en" else "正在测试 API...")
        self.test_button.setEnabled(False)
        self.run_button.setEnabled(False)
        self.worker_thread = QThread(self)
        self.worker = ApiPingWorker(settings)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._ping_finished)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.failed.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self._cleanup_worker)
        self.worker_thread.start()

    def _request_generate(self) -> None:
        settings = self.settings()
        if not self._validate_settings(settings, require_folder=True):
            return
        self.generate_requested.emit(settings)
        self.accept()

    def _validate_settings(self, settings: CaptionApiSettings, require_folder: bool) -> bool:
        if require_folder and not self.folder:
            self.status_label.setText("Open a folder first." if self.language == "en" else "请先打开目录。")
            return False
        if not settings.base_url:
            self.status_label.setText("Base URL is required." if self.language == "en" else "请输入 Base URL。")
            return False
        if not settings.model:
            self.status_label.setText("Model is required." if self.language == "en" else "请输入模型名称。")
            return False
        if not settings.api_key:
            self.status_label.setText("API Key is required." if self.language == "en" else "请输入 API Key。")
            return False
        return True

    def _finished(self, success: int, failures: int, message: str) -> None:
        self.caption_finished.emit(success, failures)
        if self.language == "en":
            self.status_label.setText(f"Done: {success} saved, {failures} failed. {message}")
        else:
            self.status_label.setText(f"完成：保存 {success} 个，失败 {failures} 个。{message}")
        self._set_buttons_enabled(True)

    def _ping_finished(self, message: str) -> None:
        if self.language == "en":
            self.status_label.setText(f"API test succeeded: {message}")
        else:
            self.status_label.setText(f"API 测试成功：{message}")
        self._set_buttons_enabled(True)

    def _failed(self, message: str) -> None:
        self.status_label.setText(message)
        self._set_buttons_enabled(True)

    def _cleanup_worker(self) -> None:
        if self.worker:
            self.worker.deleteLater()
        if self.worker_thread:
            self.worker_thread.deleteLater()
        self.worker = None
        self.worker_thread = None

    def _set_buttons_enabled(self, enabled: bool) -> None:
        self.test_button.setEnabled(enabled)
        self.run_button.setEnabled(enabled)
