from __future__ import annotations

from PySide6.QtGui import QColor


_THEME = "dark"

COLORS = {
    "dark": {
        "card": "#151B24",
        "card_hover": "#222C3B",
        "image_bg": "#101722",
        "border": "#2B3546",
        "text": "#E7ECF3",
        "muted": "#93A0B3",
        "accent": "#7B61FF",
        "accent_soft": "#2D285A",
        "drop": "#9DD8FF",
    },
    "light": {
        "card": "#FFFFFF",
        "card_hover": "#EAF0FF",
        "image_bg": "#EEF3FA",
        "border": "#D7DFEC",
        "text": "#172033",
        "muted": "#68778D",
        "accent": "#5A6CFF",
        "accent_soft": "#DDE5FF",
        "drop": "#2A7FFF",
    },
}


def set_theme(theme: str) -> None:
    global _THEME
    _THEME = "light" if theme == "light" else "dark"


def theme() -> str:
    return _THEME


def color(name: str) -> QColor:
    return QColor(COLORS[_THEME][name])


def value(name: str) -> str:
    return COLORS[_THEME][name]
