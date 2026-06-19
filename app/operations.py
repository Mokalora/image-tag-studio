from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable

from app.models import PreviewChange, TagFile, TagStat
from app.tag_parser import add_tags, delete_tags, format_tags, replace_tags


def build_tag_stats(files: Iterable[TagFile]) -> list[TagStat]:
    counts: Counter[str] = Counter()
    file_counts: dict[str, int] = defaultdict(int)
    virtual_file_counts: Counter[str] = Counter()
    for tag_file in files:
        counts.update(tag_file.tags)
        for tag in set(tag_file.tags):
            file_counts[tag] += 1
        virtual_file_counts.update(tag_file.virtual_tag_keys)
    rows = [TagStat(tag=tag, count=count, file_count=file_counts[tag]) for tag, count in counts.items()]
    virtual_labels = {
        "virtual:missing_image": "missing image",
        "virtual:missing_txt": "missing txt",
    }
    rows.extend(
        TagStat(tag=virtual_labels[key], count=count, file_count=count, key=key, virtual=True)
        for key, count in virtual_file_counts.items()
    )
    return rows


def preview_add(files: Iterable[TagFile], tags: list[str], position: str, skip_existing: bool, case_insensitive: bool) -> list[PreviewChange]:
    return _preview(files, lambda item: add_tags(item.tags, tags, position, skip_existing, case_insensitive))


def preview_delete(files: Iterable[TagFile], tags: list[str], case_insensitive: bool, contains_mode: bool) -> list[PreviewChange]:
    return _preview(files, lambda item: delete_tags(item.tags, tags, case_insensitive, contains_mode))


def preview_replace(files: Iterable[TagFile], from_tag: str, to_tag: str, case_insensitive: bool, contains_mode: bool, dedupe: bool) -> list[PreviewChange]:
    return _preview(files, lambda item: replace_tags(item.tags, from_tag, to_tag, case_insensitive, contains_mode, dedupe))


def preview_format(files: Iterable[TagFile], case_insensitive: bool = True) -> list[PreviewChange]:
    def dedupe_tags(tag_file: TagFile) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for tag in tag_file.tags:
            key = tag.casefold() if case_insensitive else tag
            if key in seen:
                continue
            seen.add(key)
            result.append(tag)
        return result

    return _preview(files, dedupe_tags)


def _preview(files: Iterable[TagFile], update) -> list[PreviewChange]:
    changes: list[PreviewChange] = []
    for tag_file in files:
        next_tags = update(tag_file)
        if next_tags != tag_file.tags:
            changes.append(PreviewChange(tag_file.path, tag_file.filename, list(tag_file.tags), list(next_tags)))
    return changes


def apply_changes(files: list[TagFile], changes: list[PreviewChange]) -> int:
    mapping = {change.file_path: change for change in changes}
    count = 0
    for tag_file in files:
        change = mapping.get(tag_file.path)
        if not change:
            continue
        tag_file.tags = list(change.after_tags)
        tag_file.raw_text = format_tags(tag_file.tags)
        tag_file.modified = tag_file.tags != tag_file.original_tags or tag_file.raw_text != tag_file.original_text
        count += 1
    return count
