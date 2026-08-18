from __future__ import annotations

from unittest.mock import MagicMock

from app.ai.chat.models import ChatRole
from app.ai.chat_overlay import ConversationalAIOverlayWindow


def test_chat_button_switches_overlay_into_bounded_conversation_mode(qtbot) -> None:
    window = ConversationalAIOverlayWindow(win32_adapter=MagicMock())
    qtbot.addWidget(window)
    events: list[tuple[str, object]] = []
    window.context_action.connect(lambda key, value: events.append((key, value)))
    window.show_translation("GP anchor text", "GP 锚点译文", "en", "zh-CN")

    window.chat_button.click()
    assert ("ai_chat", None) in events

    window.open_chat(
        source_text="GP anchor text",
        translated_text="GP 锚点译文",
        provider="DeepSeek",
        model="deepseek-v4-flash",
    )

    assert window.chat_open
    assert window.chat_panel.isVisible()
    assert window.content_scroll_area.isHidden()
    assert "DeepSeek" in window.chat_panel.identity_label.text()
    assert "14 chars" in window.chat_panel.context_button.text()
    assert window.chat_panel.maximumHeight() == 430

    window.append_chat_message(ChatRole.ASSISTANT, "GP 用于统计定位。")
    assert window.chat_panel.message_count == 1

    window.close_chat()
    assert not window.chat_open
    assert window.chat_panel.isHidden()
    assert not window.content_scroll_area.isHidden()


def test_chat_input_and_context_menu_emit_semantic_actions(qtbot) -> None:
    window = ConversationalAIOverlayWindow(win32_adapter=MagicMock())
    qtbot.addWidget(window)
    events: list[tuple[str, object]] = []
    window.context_action.connect(lambda key, value: events.append((key, value)))
    window.show_translation("source", "译文", "en", "zh-CN")
    window.open_chat(source_text="source", translated_text="译文")

    window.chat_panel.input_edit.setPlainText("为什么这样设计？")
    window.chat_panel.send_button.click()
    window.chat_action.trigger()

    assert ("ai_chat_send", "为什么这样设计？") in events
    assert events.count(("ai_chat", None)) >= 1
