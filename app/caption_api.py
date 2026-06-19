from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path
from urllib import error, request
from urllib.parse import urlparse

from app.constants import IMAGE_SUFFIXES


DEFAULT_CAPTION_PROMPT = (
    "Your task is to generate a clean list of comma-separated tags for a text-to-image AI, "
    "based *only* on the visual information in the image. Limit the output to a maximum of "
    "50 unique tags. Strictly describe visual elements like subject, clothing, environment, "
    "colors, lighting, and composition. Do not include abstract concepts, interpretations, "
    "marketing terms, or technical jargon (e.g., no 'SEO', 'brand-aligned', 'viral potential'). "
    "The goal is a concise list of visual descriptors. Avoid repeating tags. \n\n"
    "Output the description directly without any conversational fillers (e.g., 'Here is a description')."
)


@dataclass
class CaptionApiSettings:
    base_url: str = "https://api.xiaomimimo.com/v1"
    model: str = "mimo-v2.5"
    api_key: str = ""
    protocol: str = "openai"
    prompt: str = DEFAULT_CAPTION_PROMPT
    max_tokens: int = 256
    api_concurrency: int = 4
    overwrite_existing: bool = False


def resolve_endpoint(base_url: str, protocol: str = "openai") -> str:
    normalized = (base_url or "").strip().rstrip("/")
    if not normalized:
        raise ValueError("API Base URL is required")
    parsed = urlparse(normalized)
    path = parsed.path.rstrip("/")
    if protocol == "anthropic":
        return normalized if path.endswith("/messages") else f"{normalized}/messages"
    return normalized if path.endswith("/chat/completions") else f"{normalized}/chat/completions"


def image_files_without_txt(folder: Path, recursive: bool = False, overwrite_existing: bool = False) -> list[Path]:
    if not folder.exists():
        return []
    patterns = [f"**/*{suffix}" if recursive else f"*{suffix}" for suffix in IMAGE_SUFFIXES]
    files: list[Path] = []
    for pattern in patterns:
        files.extend(folder.glob(pattern))
    result = []
    seen: set[Path] = set()
    seen_txt_targets: set[Path] = set()
    for image_path in sorted(files, key=lambda item: item.name.casefold()):
        if image_path in seen:
            continue
        seen.add(image_path)
        txt_path = image_path.with_suffix(".txt")
        txt_key = txt_path.resolve() if txt_path.exists() else txt_path.absolute()
        if txt_key in seen_txt_targets:
            continue
        seen_txt_targets.add(txt_key)
        txt_missing_or_empty = not txt_path.exists() or not txt_path.read_text(encoding="utf-8", errors="ignore").strip()
        if overwrite_existing or txt_missing_or_empty:
            result.append(image_path)
    return result


def _encode_image_data_url(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".")
    mime = "jpeg" if suffix in {"jpg", "jpeg"} else suffix or "png"
    data = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:image/{mime};base64,{data}"


def _openai_payload(settings: CaptionApiSettings, image_path: Path) -> dict:
    return {
        "model": settings.model.strip(),
        "max_tokens": int(settings.max_tokens or 256),
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": settings.prompt.strip() or DEFAULT_CAPTION_PROMPT},
                    {"type": "image_url", "image_url": {"url": _encode_image_data_url(image_path)}},
                ],
            }
        ],
    }


def parse_openai_caption(response_json: dict) -> str:
    choices = response_json.get("choices") or []
    if not choices:
        raise ValueError("OpenAI response missing choices")
    content = ((choices[0] or {}).get("message") or {}).get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = [item.get("text", "").strip() for item in content if isinstance(item, dict) and item.get("type") == "text"]
        merged = "\n".join(part for part in parts if part)
        if merged:
            return merged
    raise ValueError("OpenAI response did not contain usable text content")


def caption_image(settings: CaptionApiSettings, image_path: Path, timeout: int = 120) -> str:
    if settings.protocol != "openai":
        raise ValueError("Only OpenAI-compatible caption API is enabled in this lightweight MVP")
    if not settings.model.strip():
        raise ValueError("Model name is required")
    if not settings.api_key.strip():
        raise ValueError("API Key is required")
    endpoint = resolve_endpoint(settings.base_url, settings.protocol)
    body = json.dumps(_openai_payload(settings, image_path)).encode("utf-8")
    req = request.Request(
        endpoint,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.api_key.strip()}",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout) as response:
            response_json = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API request failed with status {exc.code}: {details}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"API request failed: {exc}") from exc
    return parse_openai_caption(response_json)


def ping_openai_api(settings: CaptionApiSettings, timeout: int = 45) -> str:
    if not settings.model.strip():
        raise ValueError("Model name is required")
    if not settings.api_key.strip():
        raise ValueError("API Key is required")
    endpoint = resolve_endpoint(settings.base_url, "openai")
    payload = {
        "model": settings.model.strip(),
        "max_tokens": 4,
        "messages": [{"role": "user", "content": "Reply with the single character: 1"}],
    }
    req = request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.api_key.strip()}",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout) as response:
            response_json = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API ping failed with status {exc.code}: {details}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"API ping failed: {exc}") from exc
    return parse_openai_caption(response_json)


def write_caption_txt(image_path: Path, caption: str) -> Path:
    if not caption.strip():
        raise ValueError("API returned an empty caption")
    txt_path = image_path.with_suffix(".txt")
    txt_path.write_text(caption.strip(), encoding="utf-8")
    return txt_path
