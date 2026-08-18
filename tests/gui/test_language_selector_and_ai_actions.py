from __future__ import annotations

from unittest.mock import MagicMock

from PySide6.QtCore import Qt

from app.ai.resizable_overlay import ResizableConversationalAIOverlayWindow
from app.overlay.context_menu import LANGUAGE_OPTIONS
from app.overlay.language_bar import normalize_target_language_code


def test_language_selector_is_split_and_target_never_contains_auto(qtbot) -> None:
    window = ResizableConversationalAIOverlayWindow(win32_adapter=MagicMock())
    qtbot.addWidget(window)

    bar = window.language_bar
    source_codes = {code for code, _label, _compact in LANGUAGE_OPTIONS}
    target_codes = source_codes - {"auto"}

    assert set(bar.source_actions) == source_codes
    assert set(bar.target_actions) == target_codes
    assert "auto" not in bar.target_actions
    assert bar.source_button.text() == "Auto"
    assert bar.target_button.text() == "中文"
    assert not bar.swap_button.isEnabled()
    assert normalize_target_language_code("auto") == "zh-CN"


def test_language_swap_updates_both_sides_and_never_creates_auto_target(qtbot) -> None:
    window = ResizableConversationalAIOverlayWindow(win32_adapter=MagicMock())
    qtbot.addWidget(window)
    events: list[tuple[str, object]] = []
    window.context_action.connect(lambda key, value: events.append((key, value)))

    window.set_languages("en", "ja")
    assert window.language_bar.swap_button.isEnabled()

    qtbot.mouseClick(window.language_bar.swap_button, Qt.MouseButton.LeftButton)

    assert window.source_language == "ja"
    assert window.target_language == "en"
    assert window.language_bar.source_button.text() == "JA"
    assert window.language_bar.target_button.text() == "EN"
    assert ("swap_languages", ("ja", "en")) in events
    assert window.target_language != "auto"


def test_auto_detected_language_is_visible_and_can_be_swapped(qtbot) -> None:
    window = ResizableConversationalAIOverlayWindow(win32_adapter=MagicMock())
    qtbot.addWidget(window)
    events: list[tuple[str, object]] = []
    window.context_action.connect(lambda key, value: events.append((key, value)))

    window.set_languages("auto", "zh-CN")
    detected = window.set_detected_source_language("en")

    assert detected == "en"
    assert window.language_bar.source_language == "auto"
    assert window.language_bar.detected_source_language == "en"
    assert window.language_bar.effective_source_language == "en"
    assert window.language_bar.source_button.text() == "EN·Auto"
    assert window.language_bar.swap_button.isEnabled()

    qtbot.mouseClick(window.language_bar.swap_button, Qt.MouseButton.LeftButton)

    assert window.source_language == "zh-CN"
    assert window.target_language == "en"
    assert ("swap_languages", ("zh-CN", "en")) in events
    assert window.target_language != "auto"


def test_target_language_menu_updates_only_target_language(qtbot) -> None:
    window = ResizableConversationalAIOverlayWindow(win32_adapter=MagicMock())
    qtbot.addWidget(window)
    events: list[tuple[str, object]] = []
    window.context_action.connect(lambda key, value: events.append((key, value)))

    window.set_languages("auto", "zh-CN")
    window.language_bar.target_actions["fr"].trigger()

    assert window.source_language == "auto"
    assert window.target_language == "fr"
    assert window.language_bar.target_button.text() == "FR"
    assert not window.language_bar.swap_button.isEnabled()
    assert ("target_language", "fr") in events


def test_ai_menu_stays_reachable_and_text_actions_enable_with_source(qtbot) -> None:
    window = ResizableConversationalAIOverlayWindow(win32_adapter=MagicMock())
    qtbot.addWidget(window)

    ai_translate = window.context_menu.actions_by_name["ai_translate"]
    ai_polish = window.context_menu.actions_by_name["ai_polish"]

    # With no source text, only the text-dependent actions are unavailable;
    # the sparkle menu entry itself remains usable for Chat and settings.
    assert window.ai_button.isEnabled()
    assert window.context_menu.ai_menu.isEnabled()
    assert not ai_translate.isEnabled()
    assert not ai_polish.isEnabled()

    window.show_translation("hello", "你好", "en", "zh-CN")

    assert window.ai_button.isEnabled()
    assert window.context_menu.ai_menu.isEnabled()
    assert ai_translate.isEnabled()
    assert ai_polish.isEnabled()
