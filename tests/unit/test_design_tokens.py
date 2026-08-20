"""Contract tests for the shared AITrans design system."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from app.ai.research_quick_actions import QUICK_ACTION_COMPACT_WIDTH
from app.overlay.context_menu import (
    OVERLAY_THEMES,
    SETTINGS_MENU_ITEM_HEIGHT,
    SETTINGS_MENU_MAX_HEIGHT,
    SETTINGS_MENU_MAX_VISIBLE_ITEMS,
    SETTINGS_MENU_MIN_WIDTH,
)
from app.ui.design_tokens import (
    CONTROL,
    LAYOUT,
    MOTION,
    RADIUS,
    SPACING,
    THEMES,
    TYPOGRAPHY,
    legacy_overlay_palette,
    size_class,
    theme_tokens,
)


_LEGACY_KEYS = {
    "label_background",
    "menu_background",
    "text",
    "muted_text",
    "border",
    "hover",
    "accent",
    "shadow",
}


def test_design_tokens_preserve_existing_overlay_theme_contract() -> None:
    assert set(THEMES) == set(OVERLAY_THEMES)
    for name, old_palette in OVERLAY_THEMES.items():
        new_palette = legacy_overlay_palette(name)
        assert {key: new_palette[key] for key in _LEGACY_KEYS} == {
            key: old_palette[key] for key in _LEGACY_KEYS
        }


def test_semantic_palette_adds_chrome_and_status_tokens() -> None:
    palette = legacy_overlay_palette("dark")

    assert palette["surface_elevated"] == palette["menu_background"]
    assert palette["text_primary"] == palette["text"]
    assert palette["chrome_background"] == palette["surface_elevated"]
    assert palette["success"]
    assert palette["warning"]
    assert palette["danger"]


def test_token_objects_are_immutable() -> None:
    with pytest.raises(FrozenInstanceError):
        SPACING.md = 99  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        theme_tokens("dark").accent = "#FFFFFF"  # type: ignore[misc]


def test_shared_metrics_follow_one_consistent_scale() -> None:
    assert (SPACING.xs, SPACING.sm, SPACING.md, SPACING.lg) == (4, 8, 12, 16)
    assert RADIUS.sm < RADIUS.lg < RADIUS.floating
    assert CONTROL.compact_height < CONTROL.large_height
    assert TYPOGRAPHY.caption < TYPOGRAPHY.body < TYPOGRAPHY.title
    assert MOTION.fast_ms < MOTION.deliberate_ms
    assert LAYOUT.readable_content_width > LAYOUT.medium_max_width


def test_overlay_menu_metrics_are_design_system_driven() -> None:
    assert SETTINGS_MENU_ITEM_HEIGHT == CONTROL.normal_height + SPACING.xxs
    assert SETTINGS_MENU_MIN_WIDTH == LAYOUT.menu_min_width
    assert SETTINGS_MENU_MAX_HEIGHT == LAYOUT.menu_max_height
    assert SETTINGS_MENU_MAX_VISIBLE_ITEMS == LAYOUT.menu_visible_items


def test_quick_action_breakpoint_is_design_system_driven() -> None:
    assert QUICK_ACTION_COMPACT_WIDTH == LAYOUT.quick_action_compact_width


def test_size_class_is_shared_and_boundary_stable() -> None:
    assert size_class(320) == "compact"
    assert size_class(LAYOUT.compact_max_width) == "compact"
    assert size_class(LAYOUT.compact_max_width + 1) == "medium"
    assert size_class(LAYOUT.medium_max_width) == "medium"
    assert size_class(LAYOUT.medium_max_width + 1) == "expanded"


def test_unknown_theme_falls_back_to_dark() -> None:
    assert theme_tokens("missing") is THEMES["dark"]
