from __future__ import annotations

from pathlib import Path


APP_NAME = "Image Tag Studio"
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".bmp")
APP_DATA_DIR = Path.home() / "AppData" / "Local" / "ImageTagStudio"
LOG_PATH = APP_DATA_DIR / "runtime_errors.log"
THUMB_CACHE_DIR = APP_DATA_DIR / "thumb_cache"
