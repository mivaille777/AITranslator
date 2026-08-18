from __future__ import annotations

from unittest.mock import MagicMock

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QToolButton

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


def test_ai_replies_render_markdown_and_copy_only_the_selected_reply(qtbot) -> None:
    window = ConversationalAIOverlayWindow(win32_adapter=MagicMock())
    qtbot.addWidget(window)
    window.open_chat(source_text="source", translated_text="译文")

    markdown_reply = (
        "好的，以下是建议：\n\n"
        "1. **提前规划行程**：提前预订。\n"
        "2. **错峰出行**：避开高峰。"
    )
    window.append_chat_message(ChatRole.USER, "给出建议")
    window.append_chat_message(ChatRole.ASSISTANT, markdown_reply)
    window.append_chat_message(ChatRole.ASSISTANT, "第二条 **AI 回复**")

    user_row, first_ai_row, second_ai_row = window.chat_panel._message_rows
    user_body = user_row.findChild(QLabel, "OverlayChatMessageBody")
    ai_body = first_ai_row.findChild(QLabel, "OverlayChatMessageBody")
    first_copy = first_ai_row.findChild(QToolButton, "OverlayChatMessageCopyButton")
    second_copy = second_ai_row.findChild(QToolButton, "OverlayChatMessageCopyButton")

    assert user_body is not None
    assert ai_body is not None
    assert user_body.textFormat() == Qt.TextFormat.PlainText
    assert ai_body.textFormat() == Qt.TextFormat.MarkdownText
    assert ai_body.property("rawMessage") == markdown_reply
    assert user_row.findChild(QToolButton, "OverlayChatMessageCopyButton") is None
    assert first_copy is not None
    assert second_copy is not None

    QApplication.clipboard().clear()
    qtbot.mouseClick(first_copy, Qt.MouseButton.LeftButton)

    assert QApplication.clipboard().text() == markdown_reply
    assert first_copy.text() == "已复制"
    assert second_copy.text() == "复制"
