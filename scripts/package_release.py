from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
import ctypes
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP_TITLE = "Image Tag Studio"
DIST_EXE = ROOT / "dist" / "ImageTagStudio.exe"
RELEASE_DIR = ROOT / "release"
RELEASE_EXE = RELEASE_DIR / "ImageTagStudio.exe"
README_SRC = ROOT / "README.md"
README_RELEASE = RELEASE_DIR / "README.txt"
REPORT_PATH = RELEASE_DIR / "release_validation.json"
ICON_PATH = ROOT / "app" / "assets" / "app_icon.ico"
PYTHON_EXE = ROOT / ".venv" / "Scripts" / "python.exe"
PYINSTALLER_EXE = ROOT / ".venv" / "Scripts" / "pyinstaller.exe"


def run_pyinstaller() -> None:
    cmd = [
        str(PYINSTALLER_EXE),
        "--clean",
        "--onefile",
        "--noconsole",
        "--disable-windowed-traceback",
        "--name",
        "ImageTagStudio",
        "--icon",
        str(ICON_PATH),
        "--add-data",
        f"{ICON_PATH}{';'}app/assets",
        "main.py",
    ]
    subprocess.run(cmd, cwd=ROOT, check=True)


def run_checks() -> dict:
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    test_cmd = [str(PYTHON_EXE), "-m", "pytest", "-q"]
    compile_cmd = [str(PYTHON_EXE), "-m", "compileall", "app", "tests", "scripts", "main.py"]
    test_run = subprocess.run(test_cmd, cwd=ROOT, env=env, text=True, capture_output=True)
    compile_run = subprocess.run(compile_cmd, cwd=ROOT, env=env, text=True, capture_output=True)
    return {
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "pytest": {
            "returncode": test_run.returncode,
            "stdout": test_run.stdout.strip(),
            "stderr": test_run.stderr.strip(),
        },
        "compileall": {
            "returncode": compile_run.returncode,
            "stdout": compile_run.stdout.strip(),
            "stderr": compile_run.stderr.strip(),
        },
        "ok": test_run.returncode == 0 and compile_run.returncode == 0,
    }


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def capture_startup_windows(exe_path: Path, seconds: float = 7.0) -> dict:
    if os.name != "nt":
        return {"records": [], "unexpected_before_main": [], "main_seen": False}

    user32 = ctypes.windll.user32
    enum_proc_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    user32.IsWindowVisible.argtypes = [ctypes.c_void_p]
    user32.IsWindowVisible.restype = ctypes.c_bool
    user32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
    user32.GetWindowThreadProcessId.restype = ctypes.c_ulong
    user32.GetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetClassNameW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
    user32.GetClassNameW.restype = ctypes.c_int
    user32.EnumWindows.argtypes = [enum_proc_type, ctypes.c_void_p]
    user32.EnumWindows.restype = ctypes.c_bool

    class RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

    user32.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(RECT)]
    user32.GetWindowRect.restype = ctypes.c_bool

    def snapshot() -> list[tuple[int, int, str, str, tuple[int, int, int, int]]]:
        rows: list[tuple[int, int, str, str, tuple[int, int, int, int]]] = []

        def callback(hwnd, lparam):  # noqa: ANN001
            del lparam
            if not user32.IsWindowVisible(hwnd):
                return True
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            title_buffer = ctypes.create_unicode_buffer(512)
            class_buffer = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, title_buffer, 512)
            user32.GetClassNameW(hwnd, class_buffer, 256)
            rect = RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            width = rect.right - rect.left
            height = rect.bottom - rect.top
            if width > 20 and height > 20:
                rows.append((int(hwnd), int(pid.value), title_buffer.value, class_buffer.value, (rect.left, rect.top, width, height)))
            return True

        user32.EnumWindows(enum_proc_type(callback), None)
        return rows

    baseline = {(row[0], row[1]) for row in snapshot()}
    process = subprocess.Popen([str(exe_path)], cwd=exe_path.parent)
    start = time.perf_counter()
    records: list[dict] = []
    seen: set[tuple] = set()

    while time.perf_counter() - start < seconds:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        for hwnd, pid, title, class_name, rect in snapshot():
            if pid != process.pid and (hwnd, pid) in baseline:
                continue
            key = (hwnd, pid, title, class_name, rect)
            if key in seen:
                continue
            seen.add(key)
            records.append(
                {
                    "ms": elapsed_ms,
                    "hwnd": hwnd,
                    "pid": pid,
                    "title": title,
                    "class": class_name,
                    "rect": rect,
                }
            )
        time.sleep(0.01)

    running = process.poll() is None
    if running:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        if process.poll() is None:
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", f"Stop-Process -Id {process.pid} -Force"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", f"Stop-Process -Id {process.pid} -Force"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    cleanup_release_processes(exe_path)

    main_records = [row for row in records if row["title"] == APP_TITLE]
    first_main_ms = min((row["ms"] for row in main_records), default=None)
    unexpected = []
    for row in records:
        before_main = first_main_ms is None or row["ms"] < first_main_ms
        same_process_or_launcher = row["pid"] == process.pid or Path(row["title"] or "").name == exe_path.name
        app_like_title = row["title"] in {"ImageTagStudio", APP_TITLE, exe_path.stem}
        qt_window = str(row["class"]).startswith("Qt")
        if before_main and (same_process_or_launcher or app_like_title or qt_window):
            if row["title"] != APP_TITLE:
                unexpected.append(row)

    return {
        "launch_ok": running,
        "returncode_after_probe": process.poll(),
        "main_seen": bool(main_records),
        "first_main_ms": first_main_ms,
        "records": records,
        "unexpected_before_main": unexpected,
        "no_transient_windows": not unexpected,
    }


def validate_launch(exe_path: Path) -> dict:
    return capture_startup_windows(exe_path)


def cleanup_release_processes(exe_path: Path) -> None:
    escaped = str(exe_path).replace("'", "''")
    command = (
        "Get-Process | "
        f"Where-Object {{ $_.Path -eq '{escaped}' }} | "
        "Stop-Process -Force"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def write_release_readme(report: dict) -> None:
    checks = report["checks"]
    launch = report["launch_validation"]
    readme_text = README_SRC.read_text(encoding="utf-8")
    readme_text += (
        "\n\n## 最新自动发布校验\n\n"
        f"- 生成时间：`{report['generated_at']}`\n"
        f"- exe：`{report['exe_name']}`\n"
        f"- 大小：`{report['exe_size']}` bytes\n"
        f"- 修改时间：`{report['exe_mtime']}`\n"
        f"- SHA-256：`{report['sha256']}`\n"
        f"- pytest：`{checks['pytest']['stdout']}`\n"
        f"- compileall：`returncode {checks['compileall']['returncode']}`\n"
        f"- 真实启动校验：`launch_ok={launch['launch_ok']}`\n"
        f"- 启动闪窗校验：`no_transient_windows={launch.get('no_transient_windows')}`，"
        f"`unexpected_before_main={len(launch.get('unexpected_before_main', []))}`\n"
    )
    README_RELEASE.write_text(readme_text, encoding="utf-8")


def main() -> int:
    RELEASE_DIR.mkdir(exist_ok=True)
    for path in RELEASE_DIR.iterdir():
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()

    checks = run_checks()
    if not checks["ok"]:
        print(json.dumps(checks, indent=2, ensure_ascii=False))
        return 1

    run_pyinstaller()
    shutil.copy2(DIST_EXE, RELEASE_EXE)

    stat = RELEASE_EXE.stat()
    launch = validate_launch(RELEASE_EXE)
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "exe_name": RELEASE_EXE.name,
        "exe_size": stat.st_size,
        "exe_mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        "sha256": sha256_of(RELEASE_EXE),
        "checks": checks,
        "launch_validation": launch,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    write_release_readme(report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if launch["launch_ok"] and launch.get("main_seen") and launch.get("no_transient_windows") else 1


if __name__ == "__main__":
    raise SystemExit(main())
