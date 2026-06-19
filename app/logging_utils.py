from __future__ import annotations

import sys
import traceback
from datetime import datetime
from typing import Any

from app.constants import LOG_PATH


def log_exception(context: str, exc: BaseException | None = None) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        detail = traceback.format_exc() if exc is None else "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(f"\n[{datetime.now().isoformat(timespec='seconds')}] {context}\n")
            handle.write(detail)
            handle.write("\n")
    except Exception:
        return


def install_excepthook() -> None:
    def _hook(exc_type: type[BaseException], exc: BaseException, tb: Any) -> None:
        try:
            LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with LOG_PATH.open("a", encoding="utf-8") as handle:
                handle.write(f"\n[{datetime.now().isoformat(timespec='seconds')}] unhandled\n")
                handle.write("".join(traceback.format_exception(exc_type, exc, tb)))
                handle.write("\n")
        except Exception:
            return

    sys.excepthook = _hook
