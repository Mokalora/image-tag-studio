from __future__ import annotations

import os
import traceback
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QApplication, QWidget


TRACE_ENABLED = os.environ.get("LTS_TRACE_STARTUP") == "1"
TRACE_PATH = Path(os.environ.get("LTS_TRACE_PATH", Path.home() / "AppData" / "Local" / "ImageTagStudio" / "startup_trace.log"))


def _write(line: str) -> None:
    if not TRACE_ENABLED:
        return
    TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with TRACE_PATH.open("a", encoding="utf-8") as handle:
        handle.write(f"{datetime.now().isoformat(timespec='milliseconds')} {line}\n")


def describe_widget(widget: QWidget) -> str:
    parent = widget.parent()
    return (
        f"{type(widget).__name__} title={widget.windowTitle()!r} object={widget.objectName()!r} "
        f"size={widget.width()}x{widget.height()} visible={widget.isVisible()} "
        f"flags={int(widget.windowFlags())} parent={type(parent).__name__ if parent else None}"
    )


def trace_point(label: str) -> None:
    if not TRACE_ENABLED:
        return
    app = QApplication.instance()
    _write(f"POINT {label}")
    if app is None:
        _write("  no QApplication")
        return
    for widget in app.topLevelWidgets():
        _write(f"  top {describe_widget(widget)}")


class StartupTraceFilter(QObject):
    def eventFilter(self, watched, event):  # noqa: N802, ANN001
        if TRACE_ENABLED and isinstance(watched, QWidget) and event.type() in {QEvent.Show, QEvent.WinIdChange, QEvent.ShowToParent}:
            _write(f"EVENT {event.type().name} {describe_widget(watched)}")
            stack = "".join(traceback.format_stack(limit=8)).replace("\n", "\\n")
            _write(f"  stack {stack}")
        return super().eventFilter(watched, event)


def install_startup_trace(app: QApplication) -> StartupTraceFilter | None:
    if not TRACE_ENABLED:
        return None
    TRACE_PATH.write_text("", encoding="utf-8")
    trace_filter = StartupTraceFilter(app)
    app.installEventFilter(trace_filter)
    _write("installed startup trace")
    return trace_filter
