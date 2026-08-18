"""GUI coverage for the compact AI Overlay entry points."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.ai.overlay import AIOverlayWindow


def test_ai_button_and_context_submenu_expose_translate_and_polish(qtbot) -> None:
    window = AIOverlayWindow(win32_adapter=MagicMock())
    qtbot.addWidget(window)
    events: list[tuple[str, object]] = []
    window.context_action.connect(lambda key, value: events.append((key, value)))

    # No selected/source text means AI actions are intentionally unavailable.
    assert not window.ai_button.isEnabled()
    assert not window.context_menu.actions_by_name["ai_translate"].isEnabled()
    assert not window.context_menu.actions_by_name["ai_polish"].isEnabled()

    window.show_translation("source text", "译文", "en", "zh-CN")

    assert window.ai_button.isEnabled()
    assert window.ai_button.menu() is window.context_menu.ai_menu
    assert window.context_menu.ai_menu.title() == "AI 助手"
    assert window.context_menu.actions_by_name["ai_translate"].text() == "AI 翻译"
    assert window.context_menu.actions_by_name["ai_polish"].text() == "AI 润色"

    window.context_menu.actions_by_name["ai_translate"].trigger()
    window.context_menu.actions_by_name["ai_polish"].trigger()

    assert ("ai_translate", None) in events
    assert ("ai_polish", None) in events


def test_ai_actions_disable_when_overlay_no_longer_has_source_text(qtbot) -> None:
    window = AIOverlayWindow(win32_adapter=MagicMock())
    qtbot.addWidget(window)

    window.show_translation("source", "译文", "en", "zh-CN")
    assert window.ai_button.isEnabled()

    window.show_text("provider error")

    assert not window.ai_button.isEnabled()
    assert not window.context_menu.ai_menu.isEnabled()


def test_ai_button_uses_current_theme_accent(qtbot) -> None:
    window = AIOverlayWindow(win32_adapter=MagicMock())
    qtbot.addWidget(window)
    window.show_translation("source", "译文", "en", "zh-CN")

    window.set_theme("contrast")

    assert window.theme_name == "contrast"
    assert not window.ai_button.icon().isNull()
    assert "#00E6B8" in window.ai_button.styleSheet()
