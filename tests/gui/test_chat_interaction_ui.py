"""GUI regression tests for the high-level chat interaction layer."""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QLabel, QLineEdit, QMenu, QSizePolicy, QToolButton

from app.ai.chat.models import ChatRole
from app.ai.chat_interaction_ui import InteractiveManagedChatPanel
from app.ai.editable_overlay import EditableResizableConversationalAIOverlayWindow
from app.overlay.context_menu import OVERLAY_THEMES


def test_production_overlay_constructs_interactive_chat_without_reentrant_crash(qtbot) -> None:
    """Qt may dispatch hide/show events while parent constructors are running."""

    window = EditableResizableConversationalAIOverlayWindow()
    qtbot.addWidget(window)

    assert isinstance(window.chat_panel, InteractiveManagedChatPanel)
    assert window.chat_panel._assistant_action_rows == {}


def test_back_button_is_explicit_and_stop_replaces_send_while_busy(qtbot) -> None:
    panel = InteractiveManagedChatPanel()
    qtbot.addWidget(panel)
    panel.show()

    assert panel.back_button.isVisible()
    assert not panel.close_button.isVisible()
    assert panel.send_button.isVisible()
    assert not panel.stop_button.isVisible()

    with qtbot.waitSignal(panel.close_requested):
        qtbot.mouseClick(panel.back_button, Qt.MouseButton.LeftButton)

    panel.set_busy(True)
    assert not panel.send_button.isVisible()
    assert panel.stop_button.isVisible()

    with qtbot.waitSignal(panel.stop_generation_requested):
        qtbot.mouseClick(panel.stop_button, Qt.MouseButton.LeftButton)

    panel.set_busy(False)
    assert panel.send_button.isVisible()
    assert not panel.stop_button.isVisible()


def test_history_search_filters_conversation_submenus(qtbot) -> None:
    panel = InteractiveManagedChatPanel()
    qtbot.addWidget(panel)
    panel.set_conversations(
        [
            {"conversation_id": "a", "title": "PID tuning notes"},
            {"conversation_id": "b", "title": "LangGraph agent design"},
        ],
        "a",
    )

    search = panel.history_menu.findChild(QLineEdit, "OverlayChatHistorySearch")
    assert search is not None
    submenus = panel.history_menu.findChildren(QMenu, "OverlayChatHistoryConversationMenu")
    assert len(submenus) == 2

    search.setText("langgraph")
    visible_titles = {
        submenu.title().replace("✓ ", "")
        for submenu in submenus
        if submenu.menuAction().isVisible()
    }
    assert visible_titles == {"LangGraph agent design"}


def test_history_rename_emits_payload(monkeypatch, qtbot) -> None:
    panel = InteractiveManagedChatPanel()
    qtbot.addWidget(panel)
    monkeypatch.setattr(
        "app.ai.chat_interaction_ui.QInputDialog.getText",
        lambda *_args, **_kwargs: ("  Renamed   conversation  ", True),
    )

    captured: list[object] = []
    panel.conversation_rename_requested.connect(captured.append)
    panel._prompt_rename_conversation("abc", "Old")

    assert captured == [
        {
            "conversation_id": "abc",
            "title": "Renamed conversation",
        }
    ]


def test_assistant_actions_are_hover_only_and_regenerate_selected_reply(qtbot) -> None:
    panel = InteractiveManagedChatPanel()
    qtbot.addWidget(panel)
    panel.show()
    panel.append_message(ChatRole.ASSISTANT, "**Rendered** answer")

    row = panel._message_rows[-1]
    copy_button = row.findChild(QToolButton, "OverlayChatMessageCopyButton")
    regenerate = row.findChild(QToolButton, "OverlayChatMessageRegenerateButton")
    assert copy_button is not None
    assert regenerate is not None
    assert not panel.assistant_actions_visible(row)
    assert copy_button.isHidden()
    assert regenerate.isHidden()

    panel.eventFilter(row, QEvent(QEvent.Type.Enter))
    assert panel.assistant_actions_visible(row)
    assert not copy_button.isHidden()
    assert not regenerate.isHidden()

    with qtbot.waitSignal(panel.regenerate_requested) as blocker:
        qtbot.mouseClick(regenerate, Qt.MouseButton.LeftButton)
    assert blocker.args == ["**Rendered** answer"]


def test_message_surface_uses_opaque_theme_background_and_wraps_long_markdown(qtbot) -> None:
    panel = InteractiveManagedChatPanel()
    qtbot.addWidget(panel)
    panel.resize(560, 430)
    panel.apply_palette(OVERLAY_THEMES["dark"])
    panel.show()

    long_reply = (
        "### 三种方法对比\n\n"
        + "这是用于验证长文本不会越过 AI 对话框可见边界的中文 Markdown 内容。" * 18
    )
    panel.append_message(ChatRole.ASSISTANT, long_reply)
    qtbot.waitUntil(lambda: panel.messages_scroll.viewport().width() > 100, timeout=1000)
    qtbot.wait(50)

    row = panel._message_rows[-1]
    body = row.findChild(QLabel, "OverlayChatMessageBody")
    assert body is not None
    assert body.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Ignored
    assert row.width() <= panel.messages_scroll.viewport().width()
    assert body.width() <= panel.messages_scroll.viewport().width()

    stylesheet = panel.styleSheet()
    assert "QScrollArea#OverlayChatMessagesScroll" in stylesheet
    assert (
        f"background-color: {OVERLAY_THEMES['dark']['menu_background']};"
        in stylesheet
    )


def test_completed_long_reply_follows_tail_when_user_stays_at_bottom(qtbot) -> None:
    """A user who has not scrolled away should continue seeing the latest text."""

    panel = InteractiveManagedChatPanel()
    qtbot.addWidget(panel)
    panel.resize(520, 430)
    panel.show()

    panel.append_message(ChatRole.USER, "请解释这个算法。")
    long_reply = "\n".join(
        f"{index}. 这是第 {index} 条详细说明，用来制造足够长的回答。"
        for index in range(1, 45)
    )
    panel.append_message(ChatRole.ASSISTANT, long_reply)
    qtbot.wait(100)

    bar = panel.messages_scroll.verticalScrollBar()
    assert bar.maximum() > 0
    assert panel.follow_tail
    assert bar.value() == bar.maximum()
    assert panel.jump_to_bottom_button.isHidden()
