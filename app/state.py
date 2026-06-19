from __future__ import annotations

from pathlib import Path

from app.models import PreviewChange, TagFile, UndoGroup


class StudioState:
    def __init__(self) -> None:
        self.folder: Path | None = None
        self.files: list[TagFile] = []
        self.current_path: Path | None = None
        self.search_text = ""
        self.filter_tags: list[str] = []
        self.filter_mode = "or"
        self.filter_display_mode = "positive"
        self.undo_stack: list[UndoGroup] = []
        self.redo_stack: list[UndoGroup] = []

    def set_files(self, files: list[TagFile]) -> None:
        self.files = files
        self.current_path = files[0].path if files else None
        self.filter_tags = []
        self.filter_mode = "or"
        self.filter_display_mode = "positive"

    def current_file(self) -> TagFile | None:
        return next((item for item in self.files if item.path == self.current_path and not item.pending_delete), None)

    def modified_files(self) -> list[TagFile]:
        return [item for item in self.files if item.modified or (item.pending_delete and not item.delete_saved)]

    def filtered_files(self) -> list[TagFile]:
        result = [item for item in self.files if not item.pending_delete]
        if self.search_text.strip():
            keyword = self.search_text.strip().casefold()
            result = [item for item in result if keyword in item.display_name.casefold() or keyword in item.filename.casefold() or any(keyword in tag.casefold() for tag in item.tags)]
        if self.filter_tags:
            selected = set(self.filter_tags)
            if self.filter_mode == "and":
                matched = [item for item in result if selected.issubset(set(item.tags) | set(item.virtual_tag_keys))]
            else:
                matched = [item for item in result if selected.intersection(set(item.tags) | set(item.virtual_tag_keys))]
            if self.filter_display_mode == "negative":
                matched_paths = {item.path for item in matched}
                result = [item for item in result if item.path not in matched_paths]
            else:
                result = matched
        return result

    def push_undo(self, label: str, changes: list[PreviewChange]) -> None:
        if not changes:
            return
        self.undo_stack.append(UndoGroup(label, changes))
        self.redo_stack.clear()
