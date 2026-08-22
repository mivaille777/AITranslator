"""GUI contracts for SVG-backed Overlay context-menu icons."""

from __future__ import annotations

from app.overlay.context_menu import OverlayContextMenu, symbol_icon


def test_overlay_context_actions_use_vector_icons(qtbot) -> None:
    menu = OverlayContextMenu()
    qtbot.addWidget(menu)

    for key in (
        "copy_original",
        "copy_translation",
        "ai_translate",
        "ai_polish",
        "hide",
        "lock_position",
        "always_on_top",
        "show_original",
        "settings",
        "ai_settings",
        "about",
        "exit",
    ):
        assert not menu.actions_by_name[key].icon().isNull()

    assert not menu.ai_menu.icon().isNull()
    assert not menu.settings_menu.icon().isNull()


def test_overlay_context_icons_survive_theme_recolor(qtbot) -> None:
    menu = OverlayContextMenu()
    qtbot.addWidget(menu)

    menu.apply_theme("soft")

    assert not menu.actions_by_name["copy_translation"].icon().isNull()
    assert not menu.ai_menu.icon().isNull()
    assert not menu.language_menu.icon().isNull()


def test_legacy_symbol_icon_is_now_svg_backed() -> None:
    assert not symbol_icon("↻", "#CBD5E1").isNull()
    assert not symbol_icon("⚙", "#CBD5E1").isNull()
