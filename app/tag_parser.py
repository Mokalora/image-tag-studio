from __future__ import annotations

import re
from collections.abc import Iterable


def normalize_text(text: str) -> str:
    text = text.replace("，", ",")
    text = text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    return re.sub(r"\s+", " ", text).strip()


def parse_tags(text: str) -> list[str]:
    normalized = normalize_text(text)
    if not normalized:
        return []
    return [part.strip() for part in normalized.split(",") if part.strip()]


def format_tags(tags: Iterable[str]) -> str:
    return ", ".join(str(tag).strip() for tag in tags if str(tag).strip())


def _key(tag: str, case_insensitive: bool) -> str:
    return tag.casefold() if case_insensitive else tag


def add_tags(old_tags: list[str], new_tags: list[str], position: str, skip_existing: bool = True, case_insensitive: bool = False) -> list[str]:
    existing = {_key(tag, case_insensitive) for tag in old_tags}
    prepared: list[str] = []
    for tag in new_tags:
        key = _key(tag, case_insensitive)
        if skip_existing and key in existing:
            continue
        prepared.append(tag)
        existing.add(key)
    return prepared + list(old_tags) if position == "start" else list(old_tags) + prepared


def delete_tags(old_tags: list[str], target_tags: list[str], case_insensitive: bool = False, contains_mode: bool = False) -> list[str]:
    targets = [_key(tag, case_insensitive) for tag in target_tags if tag.strip()]
    if not targets:
        return list(old_tags)
    result: list[str] = []
    for tag in old_tags:
        current = _key(tag, case_insensitive)
        matched = any(target in current for target in targets) if contains_mode else current in targets
        if not matched:
            result.append(tag)
    return result


def replace_tags(
    old_tags: list[str],
    from_tag: str,
    to_tag: str,
    case_insensitive: bool = False,
    contains_mode: bool = False,
    dedupe_after_replace: bool = False,
) -> list[str]:
    if not from_tag.strip():
        return list(old_tags)
    source = _key(from_tag, case_insensitive)
    replaced: list[str] = []
    for tag in old_tags:
        current = _key(tag, case_insensitive)
        matched = source in current if contains_mode else current == source
        replaced.append(to_tag if matched else tag)
    if not dedupe_after_replace:
        return replaced
    seen: set[str] = set()
    result: list[str] = []
    for tag in replaced:
        key = _key(tag, case_insensitive)
        if key in seen:
            continue
        seen.add(key)
        result.append(tag)
    return result
