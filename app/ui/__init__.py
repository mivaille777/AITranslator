"""User-interface components and shared AITrans design-system primitives."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.ui.design_tokens import (
    CONTROL,
    ICON,
    LAYOUT,
    MOTION,
    RADIUS,
    SETTINGS,
    SPACING,
    THEMES,
    TYPOGRAPHY,
    legacy_overlay_palette,
    size_class,
    theme_tokens,
)

if TYPE_CHECKING:
    from app.ui.settings import SettingsWindow


def __getattr__(name: str):
    """Lazy-load heavyweight QWidget surfaces while keeping the public API."""

    if name == "SettingsWindow":
        from app.ui.settings import SettingsWindow

        return SettingsWindow
    raise AttributeError(name)


__all__ = [
    "CONTROL",
    "ICON",
    "LAYOUT",
    "MOTION",
    "RADIUS",
    "SETTINGS",
    "SPACING",
    "THEMES",
    "TYPOGRAPHY",
    "SettingsWindow",
    "legacy_overlay_palette",
    "size_class",
    "theme_tokens",
]
