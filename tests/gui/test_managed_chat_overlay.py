from __future__ import annotations

from unittest.mock import MagicMock

from PySide6.QtCore import Qt

from app.ai.chat_selection_overlay import SelectionCaptureConversationalAIOverlayWindow


def test_chat_history_menu_switches_conversations(qtbot) -> None:
    window = SelectionCaptureConversationalAIOverlayWindow(win32_adapter=MagicMock())
    qtbot.addWidget(window)
    events: list[tuple[str, object]] = []
    window.context_action.connect(lambda key, value: events.append((key, value)))
    window.open_chat(provider="DeepSeek", model="deepseek-v4-flash")

    window.set_chat_conversations(
        [
            {"conversation_id": "c1", "title": "GP 方法分析"},
            {"conversation_id": "c2", "title": "PID 鲁棒性"},
        ],
        "c1",
    )

    switch_action = next(
        action
        for action in window.chat_panel.history_menu.actions()
        if action.text() == "PID 鲁棒性"
    )
    switch_action.trigger()

    assert ("ai_chat_switch", "c2") in events


def test_clicking_model_display_emits_model_selection(qtbot) -> None:
    window = SelectionCaptureConversationalAIOverlayWindow(win32_adapter=MagicMock())
    qtbot.addWidget(window)
    events: list[tuple[str, object]] = []
    window.context_action.connect(lambda key, value: events.append((key, value)))
    window.open_chat(provider="DeepSeek", model="deepseek-v4-flash")

    window.set_chat_model_options(
        [
            {
                "provider": "deepseek",
                "provider_label": "DeepSeek",
                "model": "deepseek-v4-flash",
                "label": "deepseek-v4-flash",
                "base_url": "https://api.deepseek.com",
            },
            {
                "provider": "deepseek",
                "provider_label": "DeepSeek",
                "model": "deepseek-v4-pro",
                "label": "deepseek-v4-pro",
                "base_url": "https://api.deepseek.com",
            },
        ],
        current_provider="deepseek",
        current_model="deepseek-v4-flash",
    )

    pro_action = next(
        action
        for action in window.chat_panel.model_menu.actions()
        if "deepseek-v4-pro" in action.text()
    )
    pro_action.trigger()

    assert any(
        key == "ai_chat_model"
        and isinstance(value, dict)
        and value.get("model") == "deepseek-v4-pro"
        for key, value in events
    )


def test_first_chat_open_keeps_visible_drag_handle_operational(qtbot) -> None:
    window = SelectionCaptureConversationalAIOverlayWindow(win32_adapter=MagicMock())
    qtbot.addWidget(window)
    window.open_chat(provider="DeepSeek", model="deepseek-v4-flash")

    assert window.chat_open
    assert not window.is_dragging

    qtbot.mousePress(
        window.chat_panel.title_label,
        Qt.MouseButton.LeftButton,
        pos=window.chat_panel.title_label.rect().center(),
    )
    assert window.is_dragging

    qtbot.mouseRelease(
        window.chat_panel.title_label,
        Qt.MouseButton.LeftButton,
        pos=window.chat_panel.title_label.rect().center(),
    )
    assert not window.is_dragging
