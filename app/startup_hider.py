from __future__ import annotations

import ctypes
import os
import threading
import time


class Win32StartupWindowHider:
    """Hide transient native windows owned by this process during startup."""

    def __init__(self, duration_seconds: float = 8.0) -> None:
        self.duration_seconds = duration_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._user32 = ctypes.windll.user32 if os.name == "nt" else None
        self._pid = os.getpid()

    def start(self) -> None:
        if self._user32 is None or self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="startup-window-hider", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        deadline = time.monotonic() + self.duration_seconds
        while not self._stop.is_set() and time.monotonic() < deadline:
            self._hide_owned_windows()
            time.sleep(0.015)

    def _hide_owned_windows(self) -> None:
        enum_proc_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        user32 = self._user32

        def callback(hwnd, lparam):  # noqa: ANN001
            del lparam
            if not user32.IsWindowVisible(hwnd):
                return True
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == self._pid:
                user32.ShowWindow(hwnd, 0)
            return True

        user32.EnumWindows(enum_proc_type(callback), 0)
