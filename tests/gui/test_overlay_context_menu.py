"""Coverage for the reference-style Overlay and its right-click menu."""

from __future__ import annotations

from unittest.mock import MagicMock

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QAction, QMouseEvent

from app.overlay.context_menu import (
    SETTINGS_MENU_MAX_HEIGHT,
    SETTINGS_MENU_MAX_VISIBLE_ITEMS,
    ScrollableSettingsMenu,
)
from app.overlay.manager import OverlayManager
from app.overlay.window import OverlayWindow


def test_right_click_opens_overlay_context_menu(qtbot) -> None:
    window = OverlayWindow(win32_adapter=MagicMock())
    qtbot.addWidget(window)
    window.show_overlay()

    event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(10, 10),
        QPointF(10, 10),
        QPointF(10, 10),
        Qt.MouseButton.RightButton,
        Qt.MouseButton.RightButton,
        Qt.KeyboardModifier.NoModifier,
    )
    window.mousePressEvent(event)

    assert window.context_menu.isVisible()
    assert window.context_menu.actions_by_name["copy_original"].text() == "复制原文"
    assert window.context_menu.actions_by_name["copy_translation"].text() == "复制译文"
    assert window.context_menu.settings_menu.title() == "设置"
    assert window.context_menu.actions_by_name["settings"].text() == "常规设置..."
    assert (
        window.context_menu.actions_by_name["ai_settings"].text()
        == "AI 大模型与 API Key..."
    )
    assert window.context_menu._background_opacity_menu.title() == "背景透明度"
    assert window.context_menu._text_opacity_menu.title() == "字体透明度"
    window.context_menu.close()


def test_settings_submenu_emits_ai_settings_action(qtbot) -> None:
    window = OverlayWindow(win32_adapter=MagicMock())
    qtbot.addWidget(window)
    events: list[tuple[str, object]] = []
    window.context_action.connect(lambda key, value: events.append((key, value)))

    window.context_menu.actions_by_name["ai_settings"].trigger()

    assert ("ai_settings", None) in events


def test_settings_submenu_is_bounded_and_scrolls_when_items_exceed_limit(
    qtbot,
) -> None:
    window = OverlayWindow(win32_adapter=MagicMock())
    qtbot.addWidget(window)
    menu = window.context_menu.settings_menu

    assert isinstance(menu, ScrollableSettingsMenu)
    assert menu.maximumHeight() == SETTINGS_MENU_MAX_HEIGHT
    assert menu.visible_item_limit == SETTINGS_MENU_MAX_VISIBLE_ITEMS
    assert (
        menu.scroll_area.verticalScrollBarPolicy()
        == Qt.ScrollBarPolicy.ScrollBarAsNeeded
    )
    assert not menu.has_overflow

    # Add enough future-style settings rows to exceed the visible row cap.
    # They intentionally remain plain QAction objects so the scroll container
    # exercises the same rendering path as production settings actions.
    for index in range(SETTINGS_MENU_MAX_VISIBLE_ITEMS + 4):
        action = QAction(f"Extra setting {index}", menu)
        action.setObjectName(f"ExtraSetting{index}Action")
        menu.add_scrollable_action(action)

    assert menu.has_overflow
    menu.popup(QPoint(100, 100))
    qtbot.wait(30)

    assert menu.height() <= SETTINGS_MENU_MAX_HEIGHT
    qtbot.waitUntil(
        lambda: menu.scroll_area.verticalScrollBar().maximum() > 0,
        timeout=1000,
    )
    menu.close()


def test_context_menu_has_no_shortcuts_and_uses_compact_width(qtbot) -> None:
    window = OverlayWindow(win32_adapter=MagicMock())
    qtbot.addWidget(window)
    menu = window.context_menu

    all_actions = menu.findChildren(QAction)

    assert all(action.shortcut().isEmpty() for action in all_actions)
    assert menu.sizeHint().width() <= 240


def test_context_menu_popup_is_protected_from_auto_selection(qtbot) -> None:
    window = OverlayWindow(win32_adapter=MagicMock())
    qtbot.addWidget(window)
    window.show_overlay()
    manager = OverlayManager(window=window)

    window.context_menu.popup(QPoint(100, 100))
    qtbot.wait(30)
    assert window.context_menu.isVisible()
    menu_point = window.context_menu.frameGeometry().center()

    assert manager.contains_global_point(menu_point.x(), menu_point.y())
    window.context_menu.close()


def test_font_size_menu_changes_size_without_changing_font_family(qtbot) -> None:
    window = OverlayWindow(win32_adapter=MagicMock())
    qtbot.addWidget(window)
    events: list[tuple[str, object]] = []
    window.context_action.connect(lambda key, value: events.append((key, value)))
    original_family = window.font_family

    window.context_menu._font_size_actions[18].trigger()

    assert window.font_size == 18
    assert window.font_family == original_family
    assert ("font_size", 18) in events


def test_background_and_text_opacity_are_independent(qtbot) -> None:
    window = OverlayWindow(win32_adapter=MagicMock())
    qtbot.addWidget(window)
    events: list[tuple[str, object]] = []
    window.context_action.connect(lambda key, value: events.append((key, value)))

    window.context_menu._background_opacity_actions[0.4].trigger()

    assert window.background_opacity == 0.4
    assert window.text_opacity == 1.0
    assert window.opacity == 0.4
    assert ("background_opacity", 0.4) in events
    assert "background-color: rgba(30, 41, 59, 97)" in window.text_label.styleSheet()

    window.context_menu._text_opacity_actions[0.6].trigger()

    assert window.background_opacity == 0.4
    assert window.text_opacity == 0.6
    assert "color: rgba(248, 250, 252, 153)" in window.text_label.styleSheet()
    assert ("text_opacity", 0.6) in events


def test_theme_menu_applies_reference_palettes(qtbot) -> None:
    window = OverlayWindow(win32_adapter=MagicMock())
    qtbot.addWidget(window)

    window.context_menu._theme_actions["contrast"].trigger()

    assert window.theme_name == "contrast"
    assert "#00E6B8" in window.text_label.styleSheet()
    assert window.context_menu.theme_name == "contrast"


def test_header_actions_and_original_toggle(qtbot) -> None:
    window = OverlayWindow(win32_adapter=MagicMock())
    qtbot.addWidget(window)
    events: list[tuple[str, object]] = []
    window.context_action.connect(lambda key, value: events.append((key, value)))

    window.show_translation("The source text", "译文内容", "en", "zh-CN")

    assert "EN" in window.language_button.text()
    assert "中" in window.language_button.text()
    assert window.language_button.width() <= (
        window._header.contentsRect().width() * 0.25 + 1
    )
    assert window.copy_button.iconSize().width() >= 20
    assert window.menu_button.iconSize().width() >= 22
    assert "background-color: rgba" in window._header.styleSheet()
    assert "border: 1px solid rgba" in window._header.styleSheet()
    assert window.translation_text == "译文内容"
    assert window.source_text == "The source text"
    assert not window.original_visible
    assert window._source_label.isHidden()

    window.copy_button.click()
    assert ("copy_translation", None) in events

    window.context_menu.actions_by_name["show_original"].trigger()

    assert window.original_visible
    assert not window._source_label.isHidden()
    assert window._source_label.text() == "The source text"
    assert "background-color: rgba" in window._source_label.styleSheet()
    assert "border-radius: 7px" in window._source_label.styleSheet()
    assert ("show_original", True) in events

    window.context_menu.source_language_actions["ja"].trigger()
    assert window.source_language == "ja"
    assert "JA" in window.language_button.text()
    assert "中" in window.language_button.text()
    assert ("source_language", "ja") in events


def test_multiline_translation_expands_card(qtbot) -> None:
    window = OverlayWindow(win32_adapter=MagicMock(), max_width=420)
    qtbot.addWidget(window)

    window.show_translation("source", "short", "en", "zh-CN")
    short_height = window.height()
    window.show_translation(
        "source",
        "第一行翻译内容\n第二行翻译内容\n第三行翻译内容",
        "en",
        "zh-CN",
    )

    assert window.height() > short_height
