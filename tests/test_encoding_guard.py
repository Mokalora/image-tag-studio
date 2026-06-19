from __future__ import annotations

from pathlib import Path


MOJIBAKE_MARKERS = (
    "锛",
    "鏍",
    "涓",
    "鐢",
    "楠",
    "鈥",
    "甯冨眬",
    "鐢熸垚",
    "閺",
    "闁",
    "锟",
    "\ufffd",
)


def test_sources_do_not_contain_common_mojibake() -> None:
    roots = [Path("app"), Path("scripts"), Path("tests"), Path("README.md")]
    checked_suffixes = {".py", ".md", ".txt", ".bat", ".json"}
    offenders: list[str] = []

    paths: list[Path] = []
    for root in roots:
        if root.is_file():
            paths.append(root)
        elif root.exists():
            paths.extend(path for path in root.rglob("*") if path.is_file())

    for path in paths:
        if path.suffix.lower() not in checked_suffixes:
            continue
        text = path.read_text(encoding="utf-8")
        for marker in MOJIBAKE_MARKERS:
            if marker in text and path.name != "test_encoding_guard.py":
                offenders.append(f"{path}: contains {marker!r}")
                break

    assert offenders == []
