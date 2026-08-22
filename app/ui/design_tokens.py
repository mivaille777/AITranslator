"""AITrans design-system primitives shared by QWidget and future QML surfaces.

The module intentionally contains no Qt imports. It is the single semantic
source for spacing, radius, typography, control metrics, motion, breakpoints,
and theme colors. QWidget/QSS code can consume the plain values today while
future Qt Quick/QML adapters can expose the same tokens without duplicating
visual constants.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True, slots=True)
class SpacingTokens:
    xxs: int = 2
    xs: int = 4
    sm: int = 8
    md: int = 12
    lg: int = 16
    xl: int = 24
    xxl: int = 32


@dataclass(frozen=True, slots=True)
class RadiusTokens:
    xs: int = 4
    sm: int = 6
    md: int = 8
    lg: int = 10
    xl: int = 14
    floating: int = 18
    pill: int = 999


@dataclass(frozen=True, slots=True)
class TypographyTokens:
    family: str = "Segoe UI"
    mono_family: str = "Cascadia Mono"
    caption: int = 11
    body: int = 13
    body_large: int = 15
    title: int = 18
    title_large: int = 22
    display: int = 24
    weight_regular: int = 400
    weight_medium: int = 500
    weight_semibold: int = 600
    weight_bold: int = 700


@dataclass(frozen=True, slots=True)
class ControlTokens:
    compact_height: int = 28
    normal_height: int = 36
    large_height: int = 44
    icon_button: int = 36
    toolbar_height: int = 40
    input_min_height: int = 44
    touch_target_min: int = 32


@dataclass(frozen=True, slots=True)
class IconTokens:
    xs: int = 14
    sm: int = 16
    md: int = 18
    lg: int = 20
    xl: int = 24


@dataclass(frozen=True, slots=True)
class MotionTokens:
    fast_ms: int = 120
    normal_ms: int = 160
    deliberate_ms: int = 200
    toast_ms: int = 2200
    final_reflow_ms: tuple[int, ...] = (0, 32, 96)


@dataclass(frozen=True, slots=True)
class LayoutTokens:
    panel_padding: int = 12
    floating_margin: int = 10
    card_padding_x: int = 12
    card_padding_y: int = 10
    readable_content_width: int = 780
    compact_max_width: int = 479
    medium_max_width: int = 760
    menu_min_width: int = 260
    menu_max_height: int = 260
    menu_item_min_width: int = 150
    menu_visible_items: int = 6
    quick_action_compact_width: int = 300
    chat_model_min_width: int = 118
    chat_model_max_width: int = 168


@dataclass(frozen=True, slots=True)
class SettingsTokens:
    default_width: int = 620
    navigation_width: int = 860
    default_height: int = 660
    minimum_width: int = 540
    navigation_minimum_width: int = 720
    minimum_height: int = 500
    maximum_height: int = 720
    scroll_step: int = 48
    navigation_rail_width: int = 154


@dataclass(frozen=True, slots=True)
class ThemeTokens:
    name: str
    surface_base: str
    surface_elevated: str
    surface_floating: str
    surface_hover: str
    content_surface: str
    text_primary: str
    text_secondary: str
    text_muted: str
    border_subtle: str
    border_strong: str
    accent: str
    accent_muted: str
    success: str
    warning: str
    danger: str
    shadow: str

    def legacy_overlay_palette(self) -> dict[str, str]:
        """Return the current Overlay palette contract for staged migration."""

        return {
            "label_background": self.content_surface,
            "menu_background": self.surface_elevated,
            "text": self.text_primary,
            "muted_text": self.text_secondary,
            "border": self.border_subtle,
            "hover": self.surface_hover,
            "accent": self.accent,
            "shadow": self.shadow,
            "surface_base": self.surface_base,
            "surface_elevated": self.surface_elevated,
            "surface_floating": self.surface_floating,
            "surface_hover": self.surface_hover,
            "content_surface": self.content_surface,
            "text_primary": self.text_primary,
            "text_secondary": self.text_secondary,
            "text_muted": self.text_muted,
            "border_subtle": self.border_subtle,
            "border_strong": self.border_strong,
            "accent_muted": self.accent_muted,
            "success": self.success,
            "warning": self.warning,
            "danger": self.danger,
            "chrome_background": self.surface_elevated,
            "chrome_border": self.border_subtle,
            "chrome_hover": self.surface_hover,
            "chrome_text": self.text_primary,
            "chrome_muted_text": self.text_secondary,
        }


SPACING = SpacingTokens()
RADIUS = RadiusTokens()
TYPOGRAPHY = TypographyTokens()
CONTROL = ControlTokens()
ICON = IconTokens()
MOTION = MotionTokens()
LAYOUT = LayoutTokens()
SETTINGS = SettingsTokens()


_DARK = ThemeTokens(
    name="dark",
    surface_base="#0F172A",
    surface_elevated="#1E293B",
    surface_floating="#162033",
    surface_hover="#334155",
    content_surface="rgba(30, 41, 59, 242)",
    text_primary="#F8FAFC",
    text_secondary="#CBD5E1",
    text_muted="#94A3B8",
    border_subtle="#334155",
    border_strong="#475569",
    accent="#60A5FA",
    accent_muted="#1E3A5F",
    success="#34D399",
    warning="#FBBF24",
    danger="#FB7185",
    shadow="rgba(0, 0, 0, 165)",
)

_SOFT = ThemeTokens(
    name="soft",
    surface_base="#23262C",
    surface_elevated="#2B2F36",
    surface_floating="#30353D",
    surface_hover="#494F5A",
    content_surface="rgba(43, 47, 54, 242)",
    text_primary="#F5F7FA",
    text_secondary="#D5DAE2",
    text_muted="#AEB6C2",
    border_subtle="#494F5A",
    border_strong="#5B6370",
    accent="#AEB9C9",
    accent_muted="#414954",
    success="#8AC7A4",
    warning="#D8BA78",
    danger="#D68C98",
    shadow="rgba(0, 0, 0, 150)",
)

_CONTRAST = ThemeTokens(
    name="contrast",
    surface_base="#080B10",
    surface_elevated="#0D1117",
    surface_floating="#101820",
    surface_hover="#173C3A",
    content_surface="rgba(13, 17, 23, 248)",
    text_primary="#00E6B8",
    text_secondary="#B7FFF1",
    text_muted="#7ED9C8",
    border_subtle="#00E6B8",
    border_strong="#5CFFE0",
    accent="#00E6B8",
    accent_muted="#103D38",
    success="#4CFFB0",
    warning="#FFE66D",
    danger="#FF6B81",
    shadow="rgba(0, 0, 0, 190)",
)

THEMES: Mapping[str, ThemeTokens] = MappingProxyType(
    {
        _DARK.name: _DARK,
        _SOFT.name: _SOFT,
        _CONTRAST.name: _CONTRAST,
    }
)

LEGACY_OVERLAY_THEMES: Mapping[str, Mapping[str, str]] = MappingProxyType(
    {
        name: MappingProxyType(theme.legacy_overlay_palette())
        for name, theme in THEMES.items()
    }
)


def theme_tokens(name: object, *, fallback: str = "dark") -> ThemeTokens:
    candidate = str(name or "").strip().lower()
    return THEMES.get(candidate, THEMES[fallback])


def legacy_overlay_palette(name: object, *, fallback: str = "dark") -> dict[str, str]:
    """Return a mutable palette for QWidget code that still expects dicts."""

    return dict(theme_tokens(name, fallback=fallback).legacy_overlay_palette())


def size_class(width: object) -> str:
    """Return the shared responsive size class for Overlay/Workspace surfaces."""

    try:
        resolved = max(0, int(width))
    except (TypeError, ValueError):
        resolved = 0
    if resolved <= LAYOUT.compact_max_width:
        return "compact"
    if resolved <= LAYOUT.medium_max_width:
        return "medium"
    return "expanded"


__all__ = [
    "CONTROL",
    "ICON",
    "LAYOUT",
    "LEGACY_OVERLAY_THEMES",
    "MOTION",
    "RADIUS",
    "SETTINGS",
    "SPACING",
    "THEMES",
    "TYPOGRAPHY",
    "ControlTokens",
    "IconTokens",
    "LayoutTokens",
    "MotionTokens",
    "RadiusTokens",
    "SettingsTokens",
    "SpacingTokens",
    "ThemeTokens",
    "TypographyTokens",
    "legacy_overlay_palette",
    "size_class",
    "theme_tokens",
]
