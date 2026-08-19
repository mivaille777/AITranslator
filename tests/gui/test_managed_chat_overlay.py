from __future__ import annotations

from unittest.mock import MagicMock

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QApplication

from app.ai.chat_selection_overlay import SelectionCaptureConversationalAIOverlayWindow
from app.overlay.context_menu import OVERLAY_THEMES


class FakeSettingsConfig:
    def __init__(self, capture_enabled: bool = True) -> None:
        self.capture_enabled = capture_enabled

    def get(self, section: str, key: str, default=None):
        if section == "ai" and key == "chat_selection_capture_enabled":
            return self.capture_enabled
        return default

    def save(self, values):
        ai_values = values.get("ai", {}) if isinstance(values, dict) else {}
        if "chat_selection_capture_enabled" in ai_values:
            self.capture_enabled = bool(ai_values["chat_selection_capture_enabled"])
        return values


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

    conversation_action = next(
        action
        for action in window.chat_panel.history_menu.actions()
        if action.text() == "PID 鲁棒性"
    )
    conversation_menu = conversation_action.menu()
    assert conversation_menu is not None
    open_action = next(
        action for action in conversation_menu.actions() if action.text() == "打开"
    )
    open_action.trigger()

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


def test_settings_menu_can_toggle_chat_selection_capture(qtbot) -> None:
    config = FakeSettingsConfig(capture_enabled=True)
    window = SelectionCaptureConversationalAIOverlayWindow(
        win32_adapter=MagicMock(),
        config_manager=config,
    )
    qtbot.addWidget(window)

    action = window.chat_selection_capture_action
    assert action.isChecked()
    action.trigger()

    assert config.capture_enabled is False
    assert not action.isChecked()

    action.trigger()
    assert config.capture_enabled is True
    assert action.isChecked()


def test_first_chat_open_keeps_visible_drag_handle_operational(qtbot) -> None:
    window = SelectionCaptureConversationalAIOverlayWindow(win32_adapter=MagicMock())
    qtbot.addWidget(window)
    window.open_chat(provider="DeepSeek", model="deepseek-v4-flash")

    assert window.chat_open
    assert not window.is_dragging
    assert window.drag_handle.isVisible()
    expected_center_x = window._header.width() // 2
    actual_center_x = window.drag_handle.geometry().center().x()
    assert abs(actual_center_x - expected_center_x) <= 1

    qtbot.mousePress(
        window.drag_handle,
        Qt.MouseButton.LeftButton,
        pos=window.drag_handle.rect().center(),
    )
    assert window.is_dragging

    qtbot.mouseRelease(
        window.drag_handle,
        Qt.MouseButton.LeftButton,
        pos=window.drag_handle.rect().center(),
    )
    assert not window.is_dragging


def test_drag_handle_hover_theme_and_double_click_return_to_translation(qtbot) -> None:
    window = SelectionCaptureConversationalAIOverlayWindow(win32_adapter=MagicMock())
    qtbot.addWidget(window)
    window.show_translation("source", "译文", "en", "zh-CN")
    window.open_chat(provider="DeepSeek", model="deepseek-v4-flash")

    for theme in ("dark", "soft", "contrast"):
        window.set_theme(theme)
        palette = OVERLAY_THEMES[theme]
        assert window.drag_handle._normal_color.name().lower() == palette[
            "muted_text"
        ].lower()
        assert window.drag_handle._hover_color.name().lower() == palette[
            "accent"
        ].lower()

    QApplication.sendEvent(window.drag_handle, QEvent(QEvent.Type.Enter))
    assert window.drag_handle._hovered
    QApplication.sendEvent(window.drag_handle, QEvent(QEvent.Type.Leave))
    assert not window.drag_handle._hovered

    qtbot.mouseDClick(
        window.drag_handle,
        Qt.MouseButton.LeftButton,
        pos=window.drag_handle.rect().center(),
    )
    assert not window.chat_open
    assert window.chat_panel.isHidden()
    assert not window.content_scroll_area.isHidden()
