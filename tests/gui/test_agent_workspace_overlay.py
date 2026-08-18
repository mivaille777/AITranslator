from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from app.ai.agent_workspace_overlay import (
    AGENT_DOCK_COMPACT_WIDTH,
    AGENT_DOCK_MAX_HEIGHT,
    AgentWorkspaceOverlayWindow,
)


def test_agent_translation_workspace_keeps_compact_chat_dock(qtbot) -> None:
    window = AgentWorkspaceOverlayWindow()
    qtbot.addWidget(window)
    window.show_translation("hello", "你好", "en", "zh-CN")

    window.enter_agent_translation_mode("已进入翻译任务")

    assert window.agent_translation_mode is True
    assert not window.agent_dock.isHidden()
    assert window.source_editor.isVisible()
    assert window.agent_dock.reply_label.text() == "已进入翻译任务"
    assert window.agent_dock.maximumHeight() == AGENT_DOCK_MAX_HEIGHT

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


def test_agent_dock_compacts_on_narrow_workspace_and_return_uses_agent_path(qtbot) -> None:
    window = AgentWorkspaceOverlayWindow()
    qtbot.addWidget(window)
    window.resize(AGENT_DOCK_COMPACT_WIDTH - 80, 420)
    window.show_translation("hello", "你好", "en", "zh-CN")
    window.enter_agent_translation_mode()

    assert window.agent_dock.state_label.isHidden()
    assert window.agent_dock.return_button.text() == "↩"
    assert window.agent_dock.return_button.width() == 32

    events: list[tuple[str, object]] = []
    window.context_action.connect(lambda key, value: events.append((key, value)))
    QTest.mouseClick(window.agent_dock.return_button, Qt.MouseButton.LeftButton)

    assert ("agent_workspace_send", "翻译完了") in events
