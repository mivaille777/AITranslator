from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from app.ai.agent_workspace_overlay import AgentWorkspaceOverlayWindow


def test_agent_translation_workspace_keeps_compact_chat_dock(qtbot) -> None:
    window = AgentWorkspaceOverlayWindow()
    qtbot.addWidget(window)
    window.show_translation("hello", "你好", "en", "zh-CN")

    window.enter_agent_translation_mode("已进入翻译任务")

    assert window.agent_translation_mode is True
    assert not window.agent_dock.isHidden()
    assert window.source_editor.isVisible()
    assert window.agent_dock.reply_label.text() == "已进入翻译任务"

    events: list[tuple[str, object]] = []
    window.context_action.connect(lambda key, value: events.append((key, value)))
    window.agent_dock.input_edit.setPlainText("这句话更自然吗？")
    QTest.keyClick(window.agent_dock.input_edit, Qt.Key.Key_Return)

    assert ("agent_workspace_send", "这句话更自然吗？") in events

    window.open_chat()
    assert window.chat_open is True
    assert window.agent_dock.isHidden()

    window.close_chat()
    assert window.chat_open is False
    assert not window.agent_dock.isHidden()

    window.leave_agent_translation_mode()
    assert window.agent_translation_mode is False
    assert window.agent_dock.isHidden()
