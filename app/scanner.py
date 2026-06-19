from __future__ import annotations

from pathlib import Path

from app.constants import IMAGE_SUFFIXES
from app.models import FileSnapshot, TagFile
from app.tag_parser import parse_tags


ENCODINGS = ("utf-8", "utf-8-sig", "gbk")


def read_text_file(path: Path) -> tuple[str, str]:
    last_error: Exception | None = None
    for encoding in ENCODINGS:
        try:
            return path.read_text(encoding=encoding), encoding
        except UnicodeDecodeError as exc:
            last_error = exc
    raise UnicodeDecodeError("utf-8", b"", 0, 1, f"无法读取文件编码: {last_error}")


def build_snapshot(path: Path) -> FileSnapshot:
    text, encoding = read_text_file(path)
    stat = path.stat()
    return FileSnapshot(text=text, size=stat.st_size, mtime_ns=stat.st_mtime_ns, encoding=encoding)


def find_image_for_txt(path: Path) -> Path | None:
    for suffix in IMAGE_SUFFIXES:
        image_path = path.with_suffix(suffix)
        if image_path.exists():
            return image_path
    return None


def _empty_snapshot(encoding: str = "utf-8") -> FileSnapshot:
    return FileSnapshot(text="", size=0, mtime_ns=0, encoding=encoding)


def _tag_file_from_txt(txt_path: Path, image_path: Path | None) -> TagFile:
    try:
        snapshot = build_snapshot(txt_path)
        tags = parse_tags(snapshot.text)
        return TagFile(
            path=txt_path,
            filename=txt_path.name,
            image_path=image_path,
            raw_text=snapshot.text,
            tags=tags,
            original_text=snapshot.text,
            original_tags=list(tags),
            snapshot=snapshot,
        )
    except Exception as exc:  # noqa: BLE001
        return TagFile(
            path=txt_path,
            filename=txt_path.name,
            image_path=image_path,
            raw_text="",
            tags=[],
            original_text="",
            original_tags=[],
            snapshot=_empty_snapshot("unknown"),
            error=str(exc),
        )


def scan_folder(folder: Path, recursive: bool = False) -> list[TagFile]:
    files: list[TagFile] = []
    image_pattern_prefix = "**/*" if recursive else "*"
    image_paths: list[Path] = []
    for suffix in IMAGE_SUFFIXES:
        image_paths.extend(folder.glob(f"{image_pattern_prefix}{suffix}"))
    seen_txt: set[Path] = set()
    for image_path in sorted(set(image_paths), key=lambda item: item.name.casefold()):
        txt_path = image_path.with_suffix(".txt")
        seen_txt.add(txt_path)
        if txt_path.exists():
            files.append(_tag_file_from_txt(txt_path, image_path))
            continue
        files.append(
            TagFile(
                path=txt_path,
                filename=txt_path.name,
                image_path=image_path,
                raw_text="",
                tags=[],
                original_text="",
                original_tags=[],
                snapshot=_empty_snapshot(),
            )
        )

    txt_pattern = "**/*.txt" if recursive else "*.txt"
    for txt_path in sorted(folder.glob(txt_pattern), key=lambda item: item.name.casefold()):
        if txt_path in seen_txt:
            continue
        files.append(_tag_file_from_txt(txt_path, find_image_for_txt(txt_path)))

    files.sort(key=lambda item: item.display_name.casefold())
    return files
