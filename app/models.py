from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FileSnapshot:
    text: str
    size: int
    mtime_ns: int
    encoding: str


@dataclass
class TagFile:
    path: Path
    filename: str
    image_path: Path | None
    raw_text: str
    tags: list[str]
    original_text: str
    original_tags: list[str]
    snapshot: FileSnapshot
    modified: bool = False
    pending_delete: bool = False
    delete_saved: bool = False
    deleted_backups: dict[Path, Path] = field(default_factory=dict)
    error: str | None = None

    @property
    def tag_count(self) -> int:
        return len(self.tags)

    @property
    def display_name(self) -> str:
        return self.image_path.name if self.image_path else self.filename

    @property
    def virtual_tag_keys(self) -> list[str]:
        keys: list[str] = []
        if self.image_path is None:
            keys.append("virtual:missing_image")
        if not self.path.exists() or not self.raw_text.strip():
            keys.append("virtual:missing_txt")
        return keys

    def mark_clean(self, text: str, snapshot: FileSnapshot) -> None:
        self.raw_text = text
        self.original_text = text
        self.original_tags = list(self.tags)
        self.snapshot = snapshot
        self.modified = False


@dataclass
class TagStat:
    tag: str
    count: int
    file_count: int
    key: str | None = None
    virtual: bool = False

    def __post_init__(self) -> None:
        if self.key is None:
            self.key = self.tag


@dataclass
class PreviewChange:
    file_path: Path
    filename: str
    before_tags: list[str]
    after_tags: list[str]
    before_pending_delete: bool = False
    after_pending_delete: bool = False


@dataclass
class UndoGroup:
    label: str
    changes: list[PreviewChange] = field(default_factory=list)


@dataclass
class SaveFailure:
    filename: str
    reason: str


@dataclass
class SaveResult:
    saved_count: int = 0
    failures: list[SaveFailure] = field(default_factory=list)
    backup_dir: Path | None = None
