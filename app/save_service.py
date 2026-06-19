from __future__ import annotations

import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from app.models import FileSnapshot, SaveFailure, SaveResult, TagFile
from app.scanner import build_snapshot, read_text_file
from app.tag_parser import format_tags


def _session_backup_dir() -> Path:
    root = Path(tempfile.gettempdir()) / "ImageTagStudio" / datetime.now().strftime("session_%Y%m%d_%H%M%S")
    root.mkdir(parents=True, exist_ok=True)
    return root


def restore_deleted_files(tag_file: TagFile) -> None:
    for original, backup in list(tag_file.deleted_backups.items()):
        if backup.exists() and not original.exists():
            original.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup, original)
    tag_file.pending_delete = False
    tag_file.delete_saved = False
    tag_file.modified = False


def _backup_path(root: Path, source: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    target = root / source.name
    if not target.exists():
        return target
    return root / f"{source.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{source.suffix}"


def was_modified_externally(tag_file: TagFile) -> bool:
    if tag_file.pending_delete:
        return False
    if not tag_file.path.exists():
        return False
    stat = tag_file.path.stat()
    return stat.st_size != tag_file.snapshot.size or stat.st_mtime_ns != tag_file.snapshot.mtime_ns


def save_files(files: list[TagFile], keep_backup_in_dataset: bool = False, allow_external_overwrite: bool = False) -> SaveResult:
    result = SaveResult()
    modified = [item for item in files if item.modified or (item.pending_delete and not item.delete_saved)]
    if not modified:
        return result
    session_backup = _session_backup_dir()
    kept_restore_backup = False
    for tag_file in modified:
        try:
            if tag_file.pending_delete:
                targets = [tag_file.path]
                if tag_file.image_path is not None:
                    targets.append(tag_file.image_path)
                tag_file.deleted_backups.clear()
                for target in targets:
                    if not target.exists():
                        continue
                    backup = _backup_path(session_backup, target)
                    shutil.copy2(target, backup)
                    tag_file.deleted_backups[target] = backup
                    if keep_backup_in_dataset:
                        dataset_root = tag_file.path.parent / "_lora_tag_backup"
                        shutil.copy2(target, _backup_path(dataset_root, target))
                        result.backup_dir = dataset_root
                    target.unlink()
                kept_restore_backup = bool(tag_file.deleted_backups) or kept_restore_backup
                tag_file.delete_saved = True
                tag_file.modified = False
                result.saved_count += 1
                continue
            if was_modified_externally(tag_file) and not allow_external_overwrite:
                raise RuntimeError("扫描后文件已被外部修改")
            disk_text, _ = read_text_file(tag_file.path) if tag_file.path.exists() else ("", "utf-8")
            _backup_path(session_backup, tag_file.path).write_text(disk_text, encoding="utf-8")
            if keep_backup_in_dataset:
                dataset_root = tag_file.path.parent / "_lora_tag_backup"
                _backup_path(dataset_root, tag_file.path).write_text(disk_text, encoding="utf-8")
                result.backup_dir = dataset_root
            content = format_tags(tag_file.tags)
            if not content:
                if tag_file.path.exists():
                    tag_file.path.unlink()
                tag_file.tags = []
                tag_file.mark_clean("", FileSnapshot(text="", size=0, mtime_ns=0, encoding="utf-8"))
                result.saved_count += 1
                continue
            tag_file.path.write_text(content, encoding="utf-8")
            if tag_file.path.read_text(encoding="utf-8") != content:
                raise RuntimeError("写回校验失败")
            snapshot = build_snapshot(tag_file.path)
            tag_file.mark_clean(snapshot.text, snapshot)
            result.saved_count += 1
        except Exception as exc:  # noqa: BLE001
            result.failures.append(SaveFailure(tag_file.filename, str(exc)))
    if result.failures or kept_restore_backup:
        result.backup_dir = session_backup
    else:
        shutil.rmtree(session_backup, ignore_errors=True)
    return result
